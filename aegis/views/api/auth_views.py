# aegis/views/api/auth_views.py

import logging

# from django import forms
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from rest_framework import status, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from datetime import datetime, timezone

# from aegis.forms import UserRegistrationForm
# from aegis.services.auth_services import register_user
from aegis.models import BlacklistedRefresh, BlacklistedAccess, FarmCalendarResourceCache
from aegis.serializers import CustomTokenObtainPairSerializer
from aegis.services.entitlement_service import resolve_service_entitlements_for_user
from aegis.throttles import check_login_allowed, clear_login_failures, register_login_failure

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def _is_fc_service_payload(service_payload):
    code = (service_payload.get("code") or "").strip().lower()
    name = (service_payload.get("name") or "").strip().lower()
    return code in {"fc", "farmcalendar"} or name in {"farmcalendar", "farm calendar"}


@method_decorator(never_cache, name='dispatch')
class LoginAPIView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        identifier = (request.data.get("username") or "").strip()
        allowed, retry_after = check_login_allowed(request, identifier=identifier)
        if not allowed:
            response = Response(
                {
                    "error": (
                        "Too many login attempts. "
                        f"Try again in {retry_after} seconds."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(retry_after)
            return response

        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            clear_login_failures(request, identifier=identifier)
        elif response.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED}:
            register_login_failure(request, identifier=identifier)
        return response


# @method_decorator(never_cache, name='dispatch')
# class RegisterAPIView(APIView):
#     permission_classes = [permissions.AllowAny]
#     authentication_classes = []
#
#     def post(self, request):
#         form = UserRegistrationForm(request.data)
#
#         if form.is_valid():
#             try:
#                 register_user(
#                     username=form.cleaned_data["username"],
#                     email=form.cleaned_data["email"],
#                     # service_name=form.cleaned_data["service_name"],
#                     password=form.cleaned_data["password"],
#                     first_name=form.cleaned_data["first_name"],
#                     last_name=form.cleaned_data["last_name"]
#                 )
#                 return Response({
#                     "success": True,
#                     "message": "User registered successfully. Please log in."
#                 }, status=status.HTTP_201_CREATED)
#
#             except forms.ValidationError as e:
#                 return Response({
#                     "success": False,
#                     "error": str(e)
#                 }, status=status.HTTP_400_BAD_REQUEST)
#             except Exception as e:
#                 logging.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
#                 return Response({
#                     "success": False,
#                     # "error": f"An unexpected error occurred: {str(e)}"
#                     "error": "An unexpected error occurred. Please try again later."
#                 }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#         # Return validation errors
#         return Response({
#             "success": False,
#             "errors": form.errors
#         }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(never_cache, name='dispatch')
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        auth = request.headers.get("Authorization", "")

        if auth.startswith("Bearer "):
            raw_access = auth.split(" ", 1)[1].strip()
            try:
                at = AccessToken(raw_access)  # verifies signature & token_type=access
                BlacklistedAccess.objects.update_or_create(
                    jti=str(at["jti"]),
                    defaults={"expires_at": datetime.fromtimestamp(at["exp"], tz=timezone.utc)},
                )
                logger.info("Logout: blacklisted ACCESS jti=%s exp=%s", at["jti"], at["exp"])
            except Exception as e:
                logger.warning("Logout: failed to parse access token from Authorization header: %s", e)
        else:
            logger.info("Logout: no Authorization Bearer header; skipping access JTI blacklist")

        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rt = RefreshToken(refresh_token)  # parse & validate refresh
            rjti = str(rt["jti"])
            exp = datetime.fromtimestamp(rt["exp"], tz=timezone.utc)

            # 1) Persist rjti so all access tokens minted from this refresh are rejected
            BlacklistedRefresh.objects.update_or_create(
                rjti=rjti,
                defaults={"expires_at": exp},
            )

            # 2) Also blacklist the refresh for future refresh attempts
            rt.blacklist()  # requires 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS+migrations

            # token = RefreshToken(refresh_token)
            # token.blacklist()
            return Response({"success": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)


class TokenValidationAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        token_type = request.data.get("token_type", "access")
        token = request.data.get("token")

        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if token_type == "access":
                token_instance = AccessToken(token)
            elif token_type == "refresh":
                token_instance = RefreshToken(token)
            else:
                return Response({"error": "Invalid token type. Must be 'access' or 'refresh'."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Get expiration time
            expiration_time = token_instance["exp"]

        except TokenError as e:
            # Check if the error is due to an expired token
            if "token is expired" in str(e).lower():
                return Response({"error": f"{token_type.capitalize()} token has expired"},
                                status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": f"Invalid {token_type} token"},
                                status=status.HTTP_400_BAD_REQUEST)

        # Calculate remaining time (in seconds)
        current_time = datetime.now(timezone.utc)
        remaining_time = expiration_time - current_time.timestamp()

        if remaining_time > 0:
            return Response({
                "success": True,
                "remaining_time_in_seconds": remaining_time
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "error": "Token has already expired"
            }, status=status.HTTP_400_BAD_REQUEST)


class MeAPIView(APIView):
    """
    GET /api/me/  -> returns the authenticated user's profile and service permissions.
    Requires: Authorization: Bearer <access_token>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user

        # Basic identity payload
        groups = list(u.groups.values_list("name", flat=True))
        user_payload = {
            "uuid": str(getattr(u, "uuid", "")),
            "username": u.username,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "groups": groups,
            "tenant_id": str(u.tenant_id) if getattr(u, "tenant_id", None) else None,
            "tenant_code": getattr(getattr(u, "tenant", None), "code", None),
            "tenant_name": getattr(getattr(u, "tenant", None), "name", None),
            "is_platform_admin": bool(getattr(u, "is_superuser", False)),
            "is_tenant_admin": bool(getattr(u, "is_tenant_admin", False)),
        }

        services_payload = resolve_service_entitlements_for_user(u)

        return Response({
            "user": user_payload,
            "services": services_payload,
        }, status=status.HTTP_200_OK)


class FarmCalendarScopeAPIView(APIView):
    """
    GET /api/farmcalendar-scopes/
    Returns a UI-friendly flattened entitlement block for FarmCalendar.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        services_payload = resolve_service_entitlements_for_user(request.user)
        fc_payload = next((s for s in services_payload if _is_fc_service_payload(s)), None)

        if fc_payload is None:
            fc_payload = {
                "code": "FC",
                "name": "FarmCalendar",
                "roles": [],
                "actions": [],
                "scopes": {},
                "assignments": [],
                "unrestricted": False,
            }

        scopes = fc_payload.get("scopes", {}) or {}
        farm_ids = scopes.get("farm", []) if isinstance(scopes.get("farm", []), list) else []
        parcel_ids = scopes.get("parcel", []) if isinstance(scopes.get("parcel", []), list) else []

        return Response({
            "service": {
                "code": fc_payload.get("code", "FC"),
                "name": fc_payload.get("name", "FarmCalendar"),
            },
            "tenant": {
                "id": str(request.user.tenant_id) if getattr(request.user, "tenant_id", None) else None,
                "code": getattr(getattr(request.user, "tenant", None), "code", None),
                "name": getattr(getattr(request.user, "tenant", None), "name", None),
            },
            "roles": fc_payload.get("roles", []),
            "actions": fc_payload.get("actions", []),
            "assignments": fc_payload.get("assignments", []),
            "unrestricted": bool(fc_payload.get("unrestricted", False)),
            "scopes": {
                "farm": farm_ids,
                "parcel": parcel_ids,
            },
            "summary": {
                "farm_count": len(farm_ids),
                "parcel_count": len(parcel_ids),
            },
        }, status=status.HTTP_200_OK)


class FarmCalendarCatalogAPIView(APIView):
    """
    GET /api/farmcalendar-catalog/
    Returns cached Farm and FarmParcel data synced from FC.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_filter = {}
        if not getattr(request.user, "is_superuser", False) and getattr(request.user, "tenant_id", None):
            tenant_filter["tenant_id"] = request.user.tenant_id

        farms_qs = FarmCalendarResourceCache.objects.filter(
            status=1, resource_type="farm", **tenant_filter
        ).order_by("name", "resource_id")
        parcels_qs = FarmCalendarResourceCache.objects.filter(
            status=1, resource_type="parcel", **tenant_filter
        ).order_by("name", "resource_id")

        farms = [{
            "id": str(row.resource_id),
            "name": row.name or "",
            "payload": row.payload,
            "synced_at": row.synced_at.isoformat() if row.synced_at else None,
        } for row in farms_qs]

        parcels = [{
            "id": str(row.resource_id),
            "name": row.name or "",
            "farm_id": str(row.farm_id) if row.farm_id else None,
            "payload": row.payload,
            "synced_at": row.synced_at.isoformat() if row.synced_at else None,
        } for row in parcels_qs]

        return Response({
            "summary": {
                "farm_count": len(farms),
                "parcel_count": len(parcels),
            },
            "farms": farms,
            "parcels": parcels,
        }, status=status.HTTP_200_OK)
