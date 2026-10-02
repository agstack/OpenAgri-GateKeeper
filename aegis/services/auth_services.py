# services/auth_service.py

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from rest_framework_simplejwt.tokens import RefreshToken

from aegis.utils.auth_utils import verify_password
from aegis.models import DefaultAuthUserExtend, Tenant


TEMPORARY_TENANT_PREFIX = "sip-temp-"
TEMPORARY_TENANT_SUFFIX_BYTES = 6
TEMPORARY_TENANT_CREATE_ATTEMPTS = 5


def _create_temporary_tenant():
    for _ in range(TEMPORARY_TENANT_CREATE_ATTEMPTS):
        suffix = secrets.token_hex(TEMPORARY_TENANT_SUFFIX_BYTES)
        code = f"{TEMPORARY_TENANT_PREFIX}{suffix}"
        try:
            # The savepoint keeps a rare uniqueness collision from breaking the
            # outer registration transaction so another identifier can be tried.
            with transaction.atomic():
                return Tenant.objects.create(
                    code=code,
                    slug=code,
                    name=f"Temporary Event SIP {suffix}",
                )
        except IntegrityError:
            continue

    raise ValidationError("Could not allocate a temporary SIP. Please try again.")


def register_user(username, email, password, first_name='', last_name=''):
    """Create an event user and an isolated temporary SIP for that user."""
    with transaction.atomic():
        tenant = _create_temporary_tenant()
        try:
            user = DefaultAuthUserExtend.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                tenant=tenant,
                is_tenant_admin=True,
                is_staff=True,
                is_superuser=False,
                is_active=True,
                status=1,
            )
        except IntegrityError as exc:
            raise ValidationError("Username or email already exists") from exc

    if settings.GATEKEEPER_PROVISION_SAMPLE_FARM_ON_REGISTRATION:
        from aegis.services.farm_provisioning import provision_temporary_farm

        farm_provisioning = provision_temporary_farm(user)
    else:
        farm_provisioning = {"success": False, "skipped": True, "reason": "disabled"}

    return {
        "message": "User and temporary SIP created successfully",
        "user_id": user.uuid,
        "tenant_id": tenant.id,
        "tenant_code": tenant.code,
        "farm_provisioning": farm_provisioning,
    }


def authenticate_user(username: str, password: str):
    try:
        user = DefaultAuthUserExtend.objects.get(username=username, status=1)
    except DefaultAuthUserExtend.DoesNotExist:
        try:
            user = DefaultAuthUserExtend.objects.get(email=username, status=1)
        except DefaultAuthUserExtend.DoesNotExist:
            return None, None, None

    if not verify_password(password, user.password):
        return None, None, None

    # Use SimpleJWT to generate access and refresh tokens
    refresh = RefreshToken.for_user(user)

    # Add custom claims to the access token
    refresh["username"] = user.username
    refresh["email"] = user.email
    refresh["first_name"] = user.first_name
    refresh["last_name"] = user.last_name
    refresh["uuid"] = str(user.uuid)

    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    return user, access_token, refresh_token
