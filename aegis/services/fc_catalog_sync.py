# aegis/services/fc_catalog_sync.py

import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone as django_timezone

from aegis.models import FarmCalendarResourceCache, ServiceScopeAssignment

LOG = logging.getLogger(__name__)
FC_CATALOG_SYNC_LOCK_KEY = "gk:fc_catalog_sync_lock"
FC_CATALOG_SYNC_LOCK_TTL_SECONDS = 300
FC_CATALOG_DEFAULT_TTL_SECONDS = 3600


def _normalize_fc_api_root():
    fc_api = settings.AVAILABLE_SERVICES.get("FarmCalendar", {}).get("api", "").strip()
    if not fc_api:
        raise RuntimeError("FarmCalendar API URL not configured in settings.AVAILABLE_SERVICES")

    # Accept both .../api/ and .../api/v1/
    if fc_api.endswith("/api/"):
        return urljoin(fc_api, "v1/")
    if fc_api.endswith("/api/v1/"):
        return fc_api
    if fc_api.endswith("/"):
        return urljoin(fc_api, "api/v1/")
    return f"{fc_api}/api/v1/"


def _safe_uuid_from_urn_or_id(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        # FC payloads can include URN-like IDs: urn:farmcalendar:Farm:uuid
        if ":" in raw_value:
            candidate = raw_value.split(":")[-1]
            return candidate
        return raw_value
    return str(raw_value)


def _extract_name(item):
    for key in ("name", "title", "identifier"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_graph_items(payload):
    # FC JSON-LD list often uses @graph; fallback to list/dict patterns.
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            return graph
        if isinstance(payload.get("results"), list):
            return payload["results"]
    if isinstance(payload, list):
        return payload
    return []


def _normalize_fc_type(value):
    return (value or "").strip().lower().replace(" ", "")


def _infer_resource_type(item):
    # Trust only the declared type: other FC records (activities, machines,
    # observations, ...) also carry farm/parcel fields and are not farms.
    item_type = _normalize_fc_type(item.get("@type") or item.get("resource_type") or "")
    if item_type in {"farm"}:
        return "farm"
    if item_type in {"parcel", "farmparcel"}:
        return "parcel"
    return None


def upsert_fc_cache_from_payload(payload, *, tenant=None):
    """
    Upsert FC cache rows from a response payload without mutating FC itself.
    Used by GK to stamp tenant ownership of newly created farms/parcels after
    successful proxied writes.
    """
    items = _extract_graph_items(payload)
    if isinstance(payload, dict) and not items:
        items = [payload]

    tenant_id = getattr(tenant, "id", tenant)
    upserted = []

    for item in items:
        if not isinstance(item, dict):
            continue

        resource_type = _infer_resource_type(item)
        resource_id = _safe_uuid_from_urn_or_id(item.get("id") or item.get("@id"))
        if not resource_type or not resource_id:
            continue

        raw_farm = item.get("farm") or item.get("farm_id")
        if isinstance(raw_farm, dict):
            raw_farm = raw_farm.get("id") or raw_farm.get("@id")
        farm_id = _safe_uuid_from_urn_or_id(raw_farm) or (resource_id if resource_type == "farm" else None)

        defaults = {
            "name": _extract_name(item),
            "farm_id": farm_id,
            "payload": item,
            "status": 1,
            "deleted_at": None,
        }
        # The tenant is set only when GK first sees the record; a later write
        # must never move an existing record to the writer's tenant.
        create_defaults = dict(defaults)
        if tenant_id:
            create_defaults["tenant_id"] = tenant_id

        FarmCalendarResourceCache.objects.update_or_create(
            resource_type=resource_type,
            resource_id=resource_id,
            defaults=defaults,
            create_defaults=create_defaults,
        )
        upserted.append((resource_type, resource_id))

    return upserted


def _get_fc_access_token(timeout=10):
    username = (
        os.getenv("FC_SYNC_USERNAME")
        or os.getenv("GATEKEEPER_SUPERUSER_USERNAME")
        or os.getenv("SUPERUSER_USERNAME")
    )
    password = (
        os.getenv("FC_SYNC_PASSWORD")
        or os.getenv("GATEKEEPER_SUPERUSER_PASSWORD")
        or os.getenv("SUPERUSER_PASSWORD")
    )
    if not username or not password:
        raise RuntimeError(
            "Missing sync credentials. Set FC_SYNC_USERNAME/FC_SYNC_PASSWORD "
            "(or SUPERUSER_USERNAME/SUPERUSER_PASSWORD, or "
            "GATEKEEPER_SUPERUSER_USERNAME/GATEKEEPER_SUPERUSER_PASSWORD)."
        )

    gk_base = (os.getenv("INTERNAL_GK_URL") or "").strip() or "http://127.0.0.1:8001/"
    login_url = urljoin(gk_base, "api/login/")
    response = requests.post(login_url, data={"username": username, "password": password}, timeout=timeout)
    if response.status_code == 401:
        raise RuntimeError(
            f"GK login failed (401) for catalog sync user '{username}'. "
            "Set FC_SYNC_USERNAME/FC_SYNC_PASSWORD to valid GK credentials."
        )
    response.raise_for_status()
    token = response.json().get("access")
    if not token:
        raise RuntimeError("GK login succeeded but no access token returned.")
    return token


def sync_farmcalendar_catalog(timeout=10):
    """
    Pull Farm and FarmParcels from FC and upsert cache rows.
    This sync updates only the GK-side catalog mirror; it does not mutate
    authorization assignments such as ServiceScopeAssignment rows.
    """
    api_root = _normalize_fc_api_root()
    token = _get_fc_access_token(timeout=timeout)
    headers = {"Authorization": f"Bearer {token}"}

    farms_url = urljoin(api_root, "Farm/")
    parcels_url = urljoin(api_root, "FarmParcels/")

    farms_response = requests.get(farms_url, headers=headers, timeout=timeout)
    farms_response.raise_for_status()
    parcels_response = requests.get(parcels_url, headers=headers, timeout=timeout)
    parcels_response.raise_for_status()

    farms = _extract_graph_items(farms_response.json())
    parcels = _extract_graph_items(parcels_response.json())

    seen_farms = set()
    seen_parcels = set()

    for farm in farms:
        raw_id = farm.get("id") or farm.get("@id")
        farm_id = _safe_uuid_from_urn_or_id(raw_id)
        if not farm_id:
            continue
        seen_farms.add(farm_id)

        FarmCalendarResourceCache.objects.update_or_create(
            resource_type="farm",
            resource_id=farm_id,
            defaults={
                "name": _extract_name(farm),
                "farm_id": farm_id,
                "payload": farm,
                "status": 1,
                "deleted_at": None,
            },
        )

    for parcel in parcels:
        raw_id = parcel.get("id") or parcel.get("@id")
        parcel_id = _safe_uuid_from_urn_or_id(raw_id)
        if not parcel_id:
            continue

        raw_farm = parcel.get("farm") or {}
        if isinstance(raw_farm, dict):
            raw_farm_id = raw_farm.get("id") or raw_farm.get("@id")
        else:
            raw_farm_id = raw_farm
        farm_id = _safe_uuid_from_urn_or_id(raw_farm_id)

        seen_parcels.add(parcel_id)
        FarmCalendarResourceCache.objects.update_or_create(
            resource_type="parcel",
            resource_id=parcel_id,
            defaults={
                "name": _extract_name(parcel),
                "farm_id": farm_id,
                "payload": parcel,
                "status": 1,
                "deleted_at": None,
            },
        )

    # Soft-deactivate missing cache rows to keep the mirror aligned.
    now = datetime.now(timezone.utc)
    stale_farm_ids = list(
        FarmCalendarResourceCache.objects.filter(resource_type="farm", status=1).exclude(
            resource_id__in=seen_farms
        ).values_list("resource_id", flat=True)
    )
    stale_parcel_ids = list(
        FarmCalendarResourceCache.objects.filter(resource_type="parcel", status=1).exclude(
            resource_id__in=seen_parcels
        ).values_list("resource_id", flat=True)
    )

    FarmCalendarResourceCache.objects.filter(resource_type="farm", status=1).exclude(
        resource_id__in=seen_farms
    ).update(status=0, deleted_at=now)
    FarmCalendarResourceCache.objects.filter(resource_type="parcel", status=1).exclude(
        resource_id__in=seen_parcels
    ).update(status=0, deleted_at=now)

    # Soft-deactivate scope assignments that now point to missing FC resources.
    stale_scope_updates = 0
    if stale_farm_ids:
        stale_scope_updates += ServiceScopeAssignment.objects.filter(
            scope_type="farm",
            scope_id__in=stale_farm_ids,
            status=1,
        ).update(status=0)
    if stale_parcel_ids:
        stale_scope_updates += ServiceScopeAssignment.objects.filter(
            scope_type="parcel",
            scope_id__in=stale_parcel_ids,
            status=1,
        ).update(status=0)

    LOG.info(
        "FC catalog sync completed: farms=%s parcels=%s deactivated_scope_assignments=%s",
        len(seen_farms),
        len(seen_parcels),
        stale_scope_updates,
    )
    return {
        "farms": len(seen_farms),
        "parcels": len(seen_parcels),
        "deactivated_scope_assignments": stale_scope_updates,
    }


def get_fc_catalog_last_synced_at():
    return FarmCalendarResourceCache.objects.aggregate(last_synced_at=Max("synced_at"))["last_synced_at"]


def is_fc_catalog_stale(ttl_seconds=FC_CATALOG_DEFAULT_TTL_SECONDS):
    last_synced_at = get_fc_catalog_last_synced_at()
    if last_synced_at is None:
        return True
    cutoff = django_timezone.now() - timedelta(seconds=max(1, int(ttl_seconds)))
    return last_synced_at < cutoff


def ensure_farmcalendar_catalog_fresh(ttl_seconds=FC_CATALOG_DEFAULT_TTL_SECONDS, timeout=10):
    if not is_fc_catalog_stale(ttl_seconds=ttl_seconds):
        return {
            "synced": False,
            "skipped": True,
            "reason": "fresh",
            "last_synced_at": get_fc_catalog_last_synced_at(),
            "result": None,
        }

    lock_acquired = cache.add(FC_CATALOG_SYNC_LOCK_KEY, "1", timeout=FC_CATALOG_SYNC_LOCK_TTL_SECONDS)
    if not lock_acquired:
        return {
            "synced": False,
            "skipped": True,
            "reason": "locked",
            "last_synced_at": get_fc_catalog_last_synced_at(),
            "result": None,
        }

    try:
        if not is_fc_catalog_stale(ttl_seconds=ttl_seconds):
            return {
                "synced": False,
                "skipped": True,
                "reason": "fresh",
                "last_synced_at": get_fc_catalog_last_synced_at(),
                "result": None,
            }

        result = sync_farmcalendar_catalog(timeout=timeout)
        return {
            "synced": True,
            "skipped": False,
            "reason": "synced",
            "last_synced_at": get_fc_catalog_last_synced_at(),
            "result": result,
        }
    finally:
        cache.delete(FC_CATALOG_SYNC_LOCK_KEY)
