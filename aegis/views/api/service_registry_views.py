# aegis/views/api/service_registry_views.py

import logging
import json
import re
import uuid
import requests

from typing import Optional, cast

from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from aegis.models import FarmCalendarResourceCache, RegisteredService
from aegis.services.fc_catalog_sync import upsert_fc_cache_from_payload
from aegis.services.entitlement_service import resolve_service_entitlements_for_user
from aegis.utils.service_utils import match_endpoint

LOG = logging.getLogger(__name__)


FC_SERVICE_IDENTIFIERS = {"farmcalendar", "fc"}
METHOD_ACTION_MAP = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "add",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}


def _normalize_service_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _is_fc_service_name(value: Optional[str]) -> bool:
    normalized = _normalize_service_key(value)
    return normalized in FC_SERVICE_IDENTIFIERS or normalized == "farm calendar"


def _is_json_media_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _extract_uuidish(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        return _extract_uuidish(value.get("@id") or value.get("id"))
    if isinstance(value, list):
        for item in value:
            extracted = _extract_uuidish(item)
            if extracted:
                return extracted
        return None
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if ":" in candidate:
        candidate = candidate.split(":")[-1]
    return candidate or None


def _collect_scope_targets(item: object) -> tuple[set[str], set[str]]:
    farm_ids: set[str] = set()
    parcel_ids: set[str] = set()

    def _visit(value: object) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for entry in value:
                _visit(entry)
            return
        if isinstance(value, dict):
            item_id = _extract_uuidish(value.get("@id") or value.get("id"))
            item_type = _normalize_service_key(value.get("@type") or value.get("resource_type"))
            if item_type == "farm" and item_id:
                farm_ids.add(item_id)
            elif item_type == "parcel" and item_id:
                parcel_ids.add(item_id)

            direct_farm = _extract_uuidish(value.get("farm") or value.get("farm_id"))
            if direct_farm:
                farm_ids.add(direct_farm)

            for key in ("parcel", "farm_parcel", "agriParcel", "hasAgriParcel", "parcel_id"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    for entry in candidate:
                        extracted = _extract_uuidish(entry)
                        if extracted:
                            parcel_ids.add(extracted)
                else:
                    extracted = _extract_uuidish(candidate)
                    if extracted:
                        parcel_ids.add(extracted)

            for nested in value.values():
                _visit(nested)
            return

        extracted = _extract_uuidish(value)
        if extracted:
            # Standalone scalars are ambiguous, so ignore them unless wrapped in a typed dict.
            return

    _visit(item)
    return farm_ids, parcel_ids


def _targets_within_scope(
    farm_ids: set[str],
    parcel_ids: set[str],
    allowed_farms: set[str],
    allowed_parcels: set[str],
    parcel_to_farm: dict[str, Optional[str]],
    tenant_id: Optional[str],
    farm_tenants: dict[str, Optional[str]],
    parcel_tenants: dict[str, Optional[str]],
) -> bool:
    if not farm_ids and not parcel_ids:
        return True

    for farm_id in farm_ids:
        if not _farm_within_tenant(farm_id, tenant_id, farm_tenants):
            return False
        if farm_id not in allowed_farms:
            return False

    for parcel_id in parcel_ids:
        if not _parcel_within_tenant(parcel_id, tenant_id, parcel_tenants, parcel_to_farm, farm_tenants):
            return False
        if parcel_id in allowed_parcels:
            continue
        parent_farm_id = parcel_to_farm.get(parcel_id)
        if not parent_farm_id or parent_farm_id not in allowed_farms:
            return False

    return True


def _decode_json_body(raw_body: bytes, content_type: str) -> Optional[object]:
    if not raw_body or not _is_json_media_type(content_type):
        return None
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _fetch_upstream_json(upstream_url: str, headers: dict[str, str], params) -> Optional[object]:
    try:
        resp = requests.get(
            upstream_url,
            headers=headers,
            params=params,
            timeout=(10, 60),
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200 or not _is_json_media_type(resp.headers.get("Content-Type", "")):
        return None

    try:
        return resp.json()
    except ValueError:
        return None


def _resolve_fc_write_targets(
    method: str,
    upstream_url: str,
    headers: dict[str, str],
    params,
    raw_body: bytes,
    content_type: str,
) -> tuple[set[str], set[str]]:
    body_data = _decode_json_body(raw_body, content_type)
    if body_data is not None:
        return _collect_scope_targets(body_data)

    if method in {"PUT", "PATCH", "DELETE"}:
        upstream_data = _fetch_upstream_json(upstream_url, headers, params)
        if upstream_data is not None:
            return _collect_scope_targets(upstream_data)

    return set(), set()


def _get_fc_entitlement(user):
    for service in resolve_service_entitlements_for_user(user):
        if _is_fc_service_name(service.get("code")) or _is_fc_service_name(service.get("name")):
            return service
    return None


def _build_scope_action_maps(fc_entitlement) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """
    Map each farm/parcel scope_id to the actions granted ON THAT specific scope,
    read from the entitlement's per-grant ``assignments``. This preserves the
    action<->scope binding that the flattened ``actions``/``scopes`` fields drop.
    """
    farm_actions: dict[str, set[str]] = {}
    parcel_actions: dict[str, set[str]] = {}
    for assignment in fc_entitlement.get("assignments", []) or []:
        scope_type = assignment.get("scope_type")
        scope_id = assignment.get("scope_id")
        actions = {a for a in (assignment.get("actions") or []) if isinstance(a, str) and a}
        if not scope_id or not actions:
            continue
        if scope_type == "farm":
            farm_actions.setdefault(str(scope_id), set()).update(actions)
        elif scope_type == "parcel":
            parcel_actions.setdefault(str(scope_id), set()).update(actions)
    return farm_actions, parcel_actions


def _scopes_with_action(
    action: Optional[str],
    farm_actions: dict[str, set[str]],
    parcel_actions: dict[str, set[str]],
) -> tuple[set[str], set[str]]:
    """Return (farms, parcels) where the given action is granted on that scope."""
    if not action:
        return set(), set()
    farms = {scope_id for scope_id, actions in farm_actions.items() if action in actions}
    parcels = {scope_id for scope_id, actions in parcel_actions.items() if action in actions}
    return farms, parcels


def _has_fc_service_wide_action(fc_entitlement, action: Optional[str]) -> bool:
    if not action:
        return False

    roles = {
        role
        for role in (fc_entitlement.get("roles") or [])
        if isinstance(role, str)
    }
    actions = {
        item
        for item in (fc_entitlement.get("actions") or [])
        if isinstance(item, str)
    }
    return action in actions and bool(roles.intersection({"admin", "tenant_admin"}))


def _parcel_to_farm_map():
    mapping: dict[str, Optional[str]] = {}
    for resource_id, farm_id in (
        FarmCalendarResourceCache.objects.filter(status=1, resource_type="parcel")
        .values_list("resource_id", "farm_id")
    ):
        if resource_id is None:
            continue
        mapping[str(resource_id)] = str(farm_id) if farm_id else None
    return mapping


def _resource_tenant_maps() -> tuple[dict[str, Optional[str]], dict[str, Optional[str]]]:
    farm_tenants: dict[str, Optional[str]] = {}
    parcel_tenants: dict[str, Optional[str]] = {}
    for resource_type, resource_id, tenant_id in (
        FarmCalendarResourceCache.objects.filter(
            status=1,
            resource_type__in=("farm", "parcel"),
        ).values_list("resource_type", "resource_id", "tenant_id")
    ):
        if resource_id is None:
            continue
        normalized_tenant = str(tenant_id) if tenant_id else None
        if resource_type == "farm":
            farm_tenants[str(resource_id)] = normalized_tenant
        elif resource_type == "parcel":
            parcel_tenants[str(resource_id)] = normalized_tenant
    return farm_tenants, parcel_tenants


def _farm_within_tenant(farm_id: Optional[str], tenant_id: Optional[str], farm_tenants: dict[str, Optional[str]]) -> bool:
    if not tenant_id:
        return True
    if not farm_id:
        return False
    return farm_tenants.get(farm_id) == tenant_id


def _parcel_within_tenant(
    parcel_id: Optional[str],
    tenant_id: Optional[str],
    parcel_tenants: dict[str, Optional[str]],
    parcel_to_farm: dict[str, Optional[str]],
    farm_tenants: dict[str, Optional[str]],
) -> bool:
    if not tenant_id:
        return True
    if not parcel_id:
        return False
    if parcel_id in parcel_tenants:
        return parcel_tenants.get(parcel_id) == tenant_id
    parent_farm_id = parcel_to_farm.get(parcel_id)
    return _farm_within_tenant(parent_farm_id, tenant_id, farm_tenants)


def _farm_allowed(
    farm_id: Optional[str],
    allowed_farms: set[str],
    tenant_id: Optional[str],
    farm_tenants: dict[str, Optional[str]],
) -> bool:
    return bool(
        farm_id
        and farm_id in allowed_farms
        and _farm_within_tenant(farm_id, tenant_id, farm_tenants)
    )


def _parcel_allowed(
    parcel_id: Optional[str],
    allowed_parcels: set[str],
    allowed_farms: set[str],
    parcel_to_farm: dict[str, Optional[str]],
    tenant_id: Optional[str],
    farm_tenants: dict[str, Optional[str]],
    parcel_tenants: dict[str, Optional[str]],
) -> bool:
    if not parcel_id:
        return False
    if not _parcel_within_tenant(parcel_id, tenant_id, parcel_tenants, parcel_to_farm, farm_tenants):
        return False
    if parcel_id in allowed_parcels:
        return True
    parent_farm_id = parcel_to_farm.get(parcel_id)
    return bool(parent_farm_id and parent_farm_id in allowed_farms)


def _item_allowed_for_fc(
    item: dict,
    allowed_farms: set[str],
    allowed_parcels: set[str],
    parcel_to_farm: dict[str, Optional[str]],
    tenant_id: Optional[str],
    farm_tenants: dict[str, Optional[str]],
    parcel_tenants: dict[str, Optional[str]],
) -> bool:
    item_id = _extract_uuidish(item.get("@id") or item.get("id"))
    item_type = _normalize_service_key(item.get("@type") or item.get("resource_type"))

    if item_type == "farm" and item_id:
        return _farm_allowed(item_id, allowed_farms, tenant_id, farm_tenants)
    if item_type == "parcel" and item_id:
        return _parcel_allowed(item_id, allowed_parcels, allowed_farms, parcel_to_farm, tenant_id, farm_tenants, parcel_tenants)

    farm_ids, parcel_ids = _collect_scope_targets(item)

    if farm_ids or parcel_ids:
        return _targets_within_scope(
            farm_ids,
            parcel_ids,
            allowed_farms,
            allowed_parcels,
            parcel_to_farm,
            tenant_id,
            farm_tenants,
            parcel_tenants,
        )

    # If a resource has no farm/parcel relationship fields, do not scope-filter it here.
    return item_type not in {"farm", "parcel"} and not any(
        key in item for key in ("farm", "parcel", "farm_parcel", "agriParcel", "hasAgriParcel", "parcel_id")
    )


def _filter_fc_payload(data, allowed_farms: set[str], allowed_parcels: set[str], tenant_id: Optional[str]) -> tuple[object, bool]:
    parcel_to_farm = _parcel_to_farm_map()
    farm_tenants, parcel_tenants = _resource_tenant_maps()

    if isinstance(data, list):
        filtered = [
            item for item in data
            if not isinstance(item, dict) or _item_allowed_for_fc(item, allowed_farms, allowed_parcels, parcel_to_farm, tenant_id, farm_tenants, parcel_tenants)
        ]
        return filtered, len(filtered) != len(data)

    if isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            filtered_graph = [
                item for item in data["@graph"]
                if not isinstance(item, dict) or _item_allowed_for_fc(item, allowed_farms, allowed_parcels, parcel_to_farm, tenant_id, farm_tenants, parcel_tenants)
            ]
            changed = len(filtered_graph) != len(data["@graph"])
            filtered_payload = dict(data)
            filtered_payload["@graph"] = filtered_graph
            if "hydra:member" in filtered_payload and isinstance(filtered_payload["hydra:member"], list):
                filtered_payload["hydra:member"] = filtered_graph
            if "count" in filtered_payload and changed:
                filtered_payload["count"] = len(filtered_graph)
            if "hydra:totalItems" in filtered_payload and changed:
                filtered_payload["hydra:totalItems"] = len(filtered_graph)
            return filtered_payload, changed

        if "results" in data and isinstance(data["results"], list):
            filtered_results = [
                item for item in data["results"]
                if not isinstance(item, dict) or _item_allowed_for_fc(item, allowed_farms, allowed_parcels, parcel_to_farm, tenant_id, farm_tenants, parcel_tenants)
            ]
            changed = len(filtered_results) != len(data["results"])
            filtered_payload = dict(data)
            filtered_payload["results"] = filtered_results
            if "count" in filtered_payload and changed:
                filtered_payload["count"] = len(filtered_results)
            return filtered_payload, changed

        if _item_allowed_for_fc(data, allowed_farms, allowed_parcels, parcel_to_farm, tenant_id, farm_tenants, parcel_tenants):
            return data, False
        return {"detail": "Not found."}, True

    return data, False


class RegisterServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Validate required fields
        required_fields = ["base_url", "service_name", "endpoint"]
        missing_fields = [field for field in required_fields if not request.data.get(field)]

        if missing_fields:
            return JsonResponse(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        base_url = request.data.get("base_url").strip()
        service_name = request.data.get("service_name").strip()
        endpoint = request.data.get("endpoint").strip()
        methods = request.data.get("methods", ["GET", "POST"])
        params = request.data.get("params", "")

        if not service_name or not endpoint:
            return JsonResponse(
                {"error": "Service name and endpoint are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(methods, list) or not all(isinstance(m, str) for m in methods):
            return JsonResponse(
                {"error": "Methods should be a list of strings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(params, str):
            return JsonResponse(
                {"error": "Params should be a string representing query parameters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate base_url
        if len(base_url) > 100:
            return JsonResponse(
                {"error": "Base URL must not exceed 100 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not re.match(r"^(http|https)://[a-zA-Z0-9]([a-zA-Z0-9._]*[a-zA-Z0-9])?:[0-9]{1,5}/$", base_url):
            return JsonResponse(
                {
                    "error": "Base URL must follow the format 'http://baseurl:port/' or 'https://baseurl:port/'. "
                             "The base URL name must only contain alphanumeric characters, dots (.), or underscores (_), "
                             "and must start and end with an alphanumeric character. The port number must be 1-5 digits."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate service_name
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9_]*[a-zA-Z0-9])?$", service_name) or len(service_name) >= 30:
            return JsonResponse(
                {"error": "Service name must only contain alphanumeric characters and underscores. "
                          "It cannot start or end with an underscore, and must be less than 30 characters long."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate endpoint
        if endpoint.startswith("/") or endpoint.startswith("\\"):
            return JsonResponse(
                {"error": "Endpoint must not start with a forward or backward slash."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(endpoint) > 100:
            return JsonResponse(
                {"error": "Endpoint must not exceed 100 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure consistent formatting (always include trailing slash for endpoint)
        endpoint = endpoint.rstrip('/') + '/'  # Ensure trailing slash for endpoint

        # Construct service_url
        if params:
            params = params.strip()  # Remove unnecessary leading/trailing spaces
            key_value_pairs = [pair.strip() for pair in params.split('&') if '=' in pair]  # Split and validate
            query_string = f"?{'&'.join(key_value_pairs)}" if key_value_pairs else ""
        else:
            query_string = ""

        # Final service_url
        service_url = f"http://127.0.0.1:8001/api/proxy/{service_name}/{endpoint}{query_string}"

        try:
            # Check for existing services with the same base_url and endpoint
            existing_services = RegisteredService.objects.filter(
                base_url=base_url,
                status__in=[1, 0]  # Active or inactive services
            )

            for existing_service in existing_services:
                if match_endpoint(endpoint, existing_service.endpoint):
                    # Update the existing service with new data
                    existing_service.base_url = base_url
                    existing_service.service_name = service_name
                    existing_service.endpoint = endpoint
                    existing_service.methods = list(set(existing_service.methods).union(methods))  # Merge methods
                    existing_service.params = params  # Update params
                    existing_service.comments = request.data.get("comments", existing_service.comments)  # Update comments
                    existing_service.service_url = service_url  # Update the service URL
                    existing_service.save()

                    return JsonResponse(
                        {"success": True, "message": "Service updated successfully.",
                         "service_id": existing_service.id},
                        status=status.HTTP_200_OK
                    )

            # If no existing endpoint combination, create a new entry
            service = RegisteredService.objects.create(
                base_url=base_url,
                service_name=service_name,
                endpoint=endpoint,
                methods=methods,
                params=params,
                comments=request.data.get("comments", None),
                service_url=service_url
            )
            return JsonResponse(
                {"success": True, "message": "Service registered successfully", "service_id": service.id},
                status=status.HTTP_201_CREATED
            )

        except (IntegrityError, DatabaseError) as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except ValidationError as val_error:
            logging.error(f"Validation error: {str(val_error)}")
            return JsonResponse(
                # {"error": f"Validation error: {str(val_error)}"},
                {"error": "A validation error has occurred."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ServiceDirectoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get query parameters for filtering
            service_name = request.query_params.get("service_name", "").strip() or None
            endpoint = request.query_params.get("endpoint", "").strip() or None
            method = request.query_params.get("method", "").strip() or None

            filters = {}
            if service_name:
                filters["service_name__icontains"] = service_name
            if endpoint:
                filters["endpoint__icontains"] = endpoint
            if method:
                filters["methods__icontains"] = method

            # Query the database with filters (active services only)
            services_query = RegisteredService.active_objects.filter(**filters)

            # Only fetch specific fields to optimise the query
            services = services_query.only(
                "base_url", "service_name", "endpoint", "methods", "params", "comments"
            ).values("base_url", "service_name", "endpoint", "methods", "params", "comments")

            return JsonResponse(list(services), safe=False, status=status.HTTP_200_OK)

        except DatabaseError as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteServiceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        base_url = request.query_params.get("base_url")
        service_name = request.query_params.get("service_name")
        endpoint = request.query_params.get("endpoint")
        method = request.query_params.get("method")

        if not service_name or not endpoint or not base_url:
            return JsonResponse(
                {"error": "Base URL, service name, and endpoint are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = RegisteredService.objects.filter(
                base_url=base_url, service_name=service_name, endpoint=endpoint, status__in=[1, 0]
            ).first()

            if not service:
                return JsonResponse(
                    {"error": "Service with this base URL, name, and endpoint does not exist or is already deleted."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # If no method is provided, mark the service as deleted
            if not method:
                service.status = 2
                service.deleted_at = timezone.now()
                service.save()
                return JsonResponse(
                    {"success": True, "message": "Base URL, service and endpoint deleted successfully."},
                    status=status.HTTP_200_OK
                )

            # Check if the provided method exists for the service
            if method not in service.methods:
                return JsonResponse(
                    {"error": f"Method '{method}' does not exist for this endpoint."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Remove the method from the service
            updated_methods = [m for m in service.methods if m != method]
            service.methods = updated_methods
            service.save()

            return JsonResponse(
                {"success": True, "message": f"Method '{method}' removed from the service."},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_error:
            logging.error(f"Database error: {str(db_error)}")
            return JsonResponse(
                # {"error": f"Database error: {str(db_error)}"},
                {"error": "A database error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return JsonResponse(
                # {"error": f"Unexpected error: {str(e)}"},
                {"error": "An unexpected error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NewReverseProxyAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = []

    def dispatch(self, request, *args, **kwargs):
        # Check if the path ends with a slash; if not, redirect to the normalized path
        path = kwargs.get('path', '')
        LOG.debug("[GK][dispatch] method=%s raw_path=%s", request.method, path)

        # # only normalise for non-OPTIONS
        # if request.method != "OPTIONS" and not path.endswith("/"):
        #     kwargs["path"] = f"{path}/"
        #     LOG.debug("[GK][dispatch] normalized path -> %s", kwargs["path"])

        # normalise for ALL methods, including OPTIONS
        if path and not path.endswith("/"):
            kwargs["path"] = f"{path}/"
            LOG.debug("[GK][dispatch] normalised path -> %s", kwargs["path"])

        return super().dispatch(request, *args, **kwargs)

    def check_permissions(self, request):
        # Let OPTIONS pass so we can proxy it
        if request.method == 'OPTIONS':
            LOG.debug("[GK][check_permissions] OPTIONS -> skipping permission checks")
            return

        return super().check_permissions(request)

    @staticmethod
    def _scrub_auth(h: Optional[str]) -> str:
        """Hide secrets in Authorization header in logs."""
        if not h:
            return "-"
        hl = h.lower()
        if hl.startswith("bearer "):
            return "Bearer ***"
        if hl.startswith("basic "):
            return "Basic ***"
        return "***"

    def dispatch_request(self, request, path):
        LOG.debug("[GK][dispatch_request] method=%s path=%s", request.method, path)

        try:
            scope_filter_summary = None
            # -------- Correlation + basic request info --------
            corr_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
            req_ct = (request.META.get("CONTENT_TYPE") or "").lower()
            req_cl = request.META.get("CONTENT_LENGTH")
            client_ip = request.META.get("REMOTE_ADDR") or "-"

            LOG.debug("[GK][dispatch_request] incoming path=%s", path)

            # Parse the path to determine service and endpoint
            path_parts = path.split('/')
            service_name = path_parts[0] if len(path_parts) > 0 else None
            endpoint = '/'.join(path_parts[1:]) if len(path_parts) > 1 else None

            LOG.debug("GK IN ↘ method=%s path=%s svc=%s ip=%s ct=%s cl=%s corr=%s",
                      request.method, path, service_name, client_ip, req_ct, req_cl, corr_id)

            if service_name:
                LOG.debug("[GK][dispatch_request] svc=%s endpoint=%s", service_name, endpoint)

            if not service_name or not endpoint:
                LOG.warning("[GK][dispatch_request] invalid path format -> 400 " "svc=%s endpoint=%s",
                            service_name, endpoint)
                return JsonResponse({'error': 'Invalid path format.'}, status=400)

            # Query the database for matching service and endpoint pattern
            services = RegisteredService.objects.filter(service_name=service_name, status=1)

            service_entry = None
            # Filter by service name
            for service in services:
                # Ensure service.endpoint is valid
                if not service.endpoint:
                    continue

                # Check if the stored endpoint has placeholders
                if '{' in service.endpoint and '}' in service.endpoint:
                    # Convert placeholders to a regex pattern
                    safe_endpoint = re.escape(service.endpoint)
                    pattern = re.sub(r"\\\{[^\}]+\\\}", r"[^/]+", safe_endpoint)

                    # Match the incoming endpoint to the regex pattern
                    if re.fullmatch(pattern, cast(str, endpoint)):
                        service_entry = service
                        LOG.debug("[GK][dispatch_request] matched templated endpoint '%s'",
                                  service.endpoint)
                        break
                else:
                    # Direct match for endpoints without placeholders
                    if service.endpoint.strip('/') == endpoint.strip('/'):
                        service_entry = service
                        LOG.debug("[GK][dispatch_request] matched plain endpoint '%s'",
                                  service.endpoint)
                        break

            if not service_entry:
                LOG.warning("GK ROUTE ✖ no match svc=%s endpoint=%s corr=%s", service_name, endpoint, corr_id)
                return JsonResponse({'error': 'No service can provide this resource.'}, status=404)

            # Check if the method is supported
            # if request.method not in service_entry.methods:
            if request.method != "OPTIONS" and request.method not in service_entry.methods:
                LOG.warning("GK ROUTE ✖ method-not-allowed method=%s svc=%s corr=%s",
                            request.method, service_entry.service_name, corr_id)
                return JsonResponse(
                    {'error': f"Method {request.method} not allowed for this endpoint."},
                    status=405
                )

            # Resolve placeholders if present
            resolved_endpoint = service_entry.endpoint
            if '{' in resolved_endpoint and '}' in resolved_endpoint:
                resolved_endpoint_parts = resolved_endpoint.split('/')
                incoming_parts = endpoint.split('/')

                # Replace placeholders with actual values from the request path
                resolved_endpoint = '/'.join(
                    incoming if placeholder.startswith("{") and placeholder.endswith("}") else placeholder
                    for placeholder, incoming in zip(resolved_endpoint_parts, incoming_parts)
                )

            # -------- Build upstream URL (query handled via params=request.GET) --------
            upstream_url = f"{service_entry.base_url}{resolved_endpoint.lstrip('/')}"
            LOG.debug("GK ROUTE → upstream=%s svc=%s corr=%s",
                      upstream_url, service_entry.service_name, corr_id)

            # -------- Forward headers (strip hop-by-hop; add X-Forwarded-*; propagate corr id) --------
            hop_by_hop = {
                "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
                "te", "trailers", "transfer-encoding", "upgrade", "content-length"
            }

            forward_headers = {}
            for k, v in request.headers.items():
                if k.lower() not in hop_by_hop:
                    forward_headers[k] = v

            # Normalise forwards
            existing_xff = forward_headers.get("X-Forwarded-For")
            forward_headers["X-Forwarded-For"] = f"{existing_xff}, {client_ip}" if existing_xff else (client_ip or "-")
            forward_headers["X-Forwarded-Proto"] = request.scheme
            forward_headers["X-Request-ID"] = corr_id

            LOG.debug("GK HEADERS → base=%s Auth=%s Content-Type=%s corr=%s",
                      service_entry.base_url,
                      self._scrub_auth(request.headers.get("Authorization")),
                      req_ct, corr_id)

            # Read the exact bytes once
            raw_body = request.body
            body_len = len(raw_body or b"")
            boundary = None
            m = re.search(r'boundary=([^;]+)', req_ct or "")
            if m:
                boundary = m.group(1)

            # For JSON/text, preview first 300 chars; for others, just size/boundary
            if req_ct.startswith("application/json"):
                preview = raw_body.decode(errors="ignore")[:300]
                LOG.debug("GK BODY (json) len=%s preview=%r corr=%s", body_len, preview, corr_id)
            elif req_ct.startswith("multipart/form-data"):
                LOG.debug("GK BODY (multipart) len=%s boundary=%s corr=%s", body_len, boundary, corr_id)
            else:
                LOG.debug("GK BODY (octet/other) len=%s ct=%s corr=%s", body_len, req_ct, corr_id)

            # 3) Build kwargs for the upstream request
            request_kwargs = {
                "headers": forward_headers,
                "params": request.GET,  # keep query string
                "stream": True,  # stream response back
                "timeout": (10, 300),  # (connect, read)
            }

            # POST/PUT/PATCH/DELETE may carry bodies; GET usually shouldn't
            method = request.method.upper()
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                # Always pass exact bytes to preserve multipart boundary & file payload
                request_kwargs["data"] = raw_body

            if method != "OPTIONS" and _is_fc_service_name(service_entry.service_name):
                fc_entitlement = _get_fc_entitlement(request.user)
                if not fc_entitlement and not getattr(request.user, "is_superuser", False):
                    LOG.warning(
                        "GK PROXY DENY method=%s svc=%s path=%s user=%s reason=no_entitlement corr=%s",
                        method,
                        service_entry.service_name,
                        path,
                        getattr(request.user, "username", "-"),
                        corr_id,
                    )
                    return JsonResponse(
                        {"error": "You do not have access to this FarmCalendar service."},
                        status=403,
                    )
                if fc_entitlement and not fc_entitlement.get("unrestricted"):
                    required_action = METHOD_ACTION_MAP.get(method)
                    farm_actions, parcel_actions = _build_scope_action_maps(fc_entitlement)
                    has_service_wide_action = _has_fc_service_wide_action(fc_entitlement, required_action)
                    allowed_actions = set().union(
                        *farm_actions.values(), *parcel_actions.values()
                    ) if (farm_actions or parcel_actions) else set()
                    if has_service_wide_action and required_action:
                        allowed_actions.add(required_action)

                    if required_action and required_action not in allowed_actions:
                        LOG.warning(
                            "GK PROXY DENY method=%s svc=%s path=%s user=%s reason=missing_action required=%s corr=%s",
                            method,
                            service_entry.service_name,
                            path,
                            getattr(request.user, "username", "-"),
                            required_action,
                            corr_id,
                        )
                        return JsonResponse(
                            {"error": f"Action '{required_action}' is not allowed for this service."},
                            status=403,
                        )

                    if method in {"POST", "PUT", "PATCH", "DELETE"}:
                        target_farms, target_parcels = _resolve_fc_write_targets(
                            method=method,
                            upstream_url=upstream_url,
                            headers=forward_headers,
                            params=request.GET,
                            raw_body=raw_body,
                            content_type=req_ct,
                        )
                        parcel_to_farm = _parcel_to_farm_map()
                        farm_tenants, parcel_tenants = _resource_tenant_maps()
                        tenant_id = str(request.user.tenant_id) if getattr(request.user, "tenant_id", None) else None
                        # Bind the scope check to the required action: only scopes
                        # that grant THIS action count as allowed for this write.
                        action_farms, action_parcels = _scopes_with_action(
                            required_action, farm_actions, parcel_actions
                        )
                        if not has_service_wide_action and not _targets_within_scope(
                            target_farms,
                            target_parcels,
                            action_farms,
                            action_parcels,
                            parcel_to_farm,
                            tenant_id,
                            farm_tenants,
                            parcel_tenants,
                        ):
                            LOG.warning(
                                "GK PROXY DENY method=%s svc=%s path=%s user=%s reason=scope_action required=%s target_farms=%s target_parcels=%s corr=%s",
                                method,
                                service_entry.service_name,
                                path,
                                getattr(request.user, "username", "-"),
                                required_action,
                                sorted(target_farms),
                                sorted(target_parcels),
                                corr_id,
                            )
                            return JsonResponse(
                                {"error": "This target is outside your allowed FarmCalendar scope."},
                                status=403,
                            )

            # -------- Call upstream --------
            LOG.debug("[GK][dispatch_request] calling upstream method=%s url=%s headers=%s",
                      method, upstream_url, list(forward_headers.keys()))
            resp = requests.request(method, upstream_url, **request_kwargs)
            LOG.debug("[GK][dispatch_request] upstream responded status=%s", resp.status_code)

            resp_ct = resp.headers.get("Content-Type", "")
            resp_cl = resp.headers.get("Content-Length")
            LOG.debug("GK OUT ↗ method=%s status=%s ct=%s cl=%s corr=%s",
                      method, resp.status_code, resp_ct, resp_cl, corr_id)

            if resp.status_code >= 400:
                try:
                    if ("application/json" in resp_ct) or ("text/" in resp_ct):
                        LOG.warning("UPSTREAM ERR preview corr=%s: %s", corr_id, resp.text[:1500])
                    else:
                        LOG.warning("UPSTREAM ERR non-text body corr=%s", corr_id)
                except Exception:
                    LOG.warning("UPSTREAM ERR (no preview) corr=%s", corr_id)

            if (
                method in {"POST", "PUT", "PATCH"}
                and 200 <= resp.status_code < 300
                and _is_json_media_type(resp_ct)
                and _is_fc_service_name(service_entry.service_name)
            ):
                payload = resp.json()
                stamped_rows = upsert_fc_cache_from_payload(
                    payload,
                    tenant=getattr(request.user, "tenant", None),
                )
                if stamped_rows:
                    LOG.info(
                        "GK FC CACHE stamped=%s user=%s tenant=%s corr=%s",
                        stamped_rows,
                        getattr(request.user, "username", "-"),
                        getattr(request.user, "tenant_id", None),
                        corr_id,
                    )
                return JsonResponse(
                    payload,
                    safe=not isinstance(payload, list),
                    status=resp.status_code,
                    content_type=resp_ct,
                )

            if (
                method == "GET"
                and resp.status_code == 200
                and _is_json_media_type(resp_ct)
                and _is_fc_service_name(service_entry.service_name)
            ):
                fc_entitlement = _get_fc_entitlement(request.user)
                if fc_entitlement and not fc_entitlement.get("unrestricted"):
                    farm_actions, parcel_actions = _build_scope_action_maps(fc_entitlement)
                    # Only surface scopes where the user can actually 'view'.
                    allowed_farms, allowed_parcels = _scopes_with_action(
                        "view", farm_actions, parcel_actions
                    )
                    tenant_id = str(request.user.tenant_id) if getattr(request.user, "tenant_id", None) else None
                    response_data = resp.json()
                    filtered_payload, changed = _filter_fc_payload(response_data, allowed_farms, allowed_parcels, tenant_id)
                    if changed:
                        scope_filter_summary = (
                            f"scope_filter=on allowed_farms={len(allowed_farms)} "
                            f"allowed_parcels={len(allowed_parcels)}"
                        )
                    else:
                        scope_filter_summary = (
                            f"scope_filter=checked allowed_farms={len(allowed_farms)} "
                            f"allowed_parcels={len(allowed_parcels)}"
                        )
                    status_code = 404 if isinstance(filtered_payload, dict) and filtered_payload.get("detail") == "Not found." else resp.status_code
                    LOG.info(
                        "GK PROXY method=%s svc=%s path=%s upstream=%s status=%s user=%s %s corr=%s",
                        method,
                        service_entry.service_name,
                        path,
                        upstream_url,
                        status_code,
                        getattr(request.user, "username", "-"),
                        scope_filter_summary,
                        corr_id,
                    )
                    return JsonResponse(
                        filtered_payload,
                        safe=not isinstance(filtered_payload, list),
                        status=status_code,
                        content_type=resp_ct,
                    )

            excluded_resp = {"content-encoding", "transfer-encoding", "connection"}
            django_resp = StreamingHttpResponse(resp.iter_content(chunk_size=64 * 1024),
                                                status=resp.status_code)

            for k, v in resp.headers.items():
                if k.lower() not in excluded_resp:
                    django_resp[k] = v

            LOG.info(
                "GK PROXY method=%s svc=%s path=%s upstream=%s status=%s user=%s %s corr=%s",
                method,
                service_entry.service_name,
                path,
                upstream_url,
                resp.status_code,
                getattr(request.user, "username", "-"),
                scope_filter_summary or "scope_filter=off",
                corr_id,
            )

            return django_resp

        except Exception as e:
            LOG.error("GK FATAL corr=%s error=%s", corr_id if 'corr_id' in locals() else "-", str(e), exc_info=True)
            return JsonResponse(
                {'error': "An internal server error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request, path):
        return self.dispatch_request(request, path)

    def post(self, request, path):
        return self.dispatch_request(request, path)

    def put(self, request, path):
        return self.dispatch_request(request, path)

    def delete(self, request, path):
        return self.dispatch_request(request, path)

    def patch(self, request, path):
        return self.dispatch_request(request, path)

    def options(self, request, *args, **kwargs):
        """
        Forward OPTIONS like other methods instead of letting DRF auto-generate it.
        """
        path = kwargs.get("path", "")
        LOG.debug("[GK][options] forwarding OPTIONS for path=%s", path)
        return self.dispatch_request(request, path)
