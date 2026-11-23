import json
import logging
import math
import secrets
import uuid

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from django.conf import settings
from django.db import transaction

from rest_framework_simplejwt.tokens import RefreshToken

from aegis.services.fc_catalog_sync import upsert_fc_cache_from_payload
from aegis.services.upstream_security import validate_allowed_upstream


LOG = logging.getLogger(__name__)
PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "temporary_farm_profiles.json"


@lru_cache(maxsize=1)
def load_temporary_farm_profiles():
    with PROFILE_PATH.open(encoding="utf-8") as profile_file:
        profiles = json.load(profile_file)
    if not isinstance(profiles, list) or len(profiles) != 100:
        raise ValueError("Temporary farm profile catalogue must contain exactly 100 profiles.")
    return tuple(profiles)


def _farmcalendar_api_root():
    configured_url = settings.AVAILABLE_SERVICES.get("FarmCalendar", {}).get("api", "").strip()
    if not configured_url:
        raise ValueError("FarmCalendar API URL is not configured.")

    parsed = urlsplit(configured_url)
    port = parsed.port
    if not parsed.hostname or port is None:
        raise ValueError("FarmCalendar API URL must include a hostname and port.")
    rendered_host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    origin = f"{parsed.scheme}://{rendered_host}:{port}/"
    validate_allowed_upstream(origin)

    if configured_url.endswith("/api/"):
        return urljoin(configured_url, "v1/")
    if configured_url.endswith("/api/v1/"):
        return configured_url
    if configured_url.endswith("/"):
        return urljoin(configured_url, "api/v1/")
    return f"{configured_url}/api/v1/"


def _resource_item(payload, expected_type):
    item = payload
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        item = next(
            (
                entry
                for entry in payload["@graph"]
                if isinstance(entry, dict)
                and (entry.get("@type") or "").strip().lower() == expected_type.lower()
            ),
            None,
        )
    if not isinstance(item, dict):
        raise ValueError(f"FarmCalendar returned no {expected_type} object.")

    return item


def _resource_reference(payload, expected_type):
    item = _resource_item(payload, expected_type)
    raw_id = item.get("@id") or item.get("id")
    if not raw_id:
        raise ValueError(f"FarmCalendar returned a {expected_type} without an ID.")
    return str(raw_id)


def _resource_id(payload, expected_type):
    raw_id = _resource_reference(payload, expected_type)

    candidate = str(raw_id).rsplit(":", 1)[-1]
    return str(uuid.UUID(candidate))


def _iso_datetime(value):
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rectangle_wkt(latitude, longitude, area_hectares):
    # Approximate an axis-aligned square whose surface matches the declared
    # parcel area. This is accurate enough for small demonstration parcels.
    half_side_metres = math.sqrt(float(area_hectares) * 10_000) / 2
    offset_lat = half_side_metres / 111_320
    offset_long = half_side_metres / (
        111_320 * math.cos(math.radians(latitude))
    )
    south = latitude - offset_lat
    north = latitude + offset_lat
    west = longitude - offset_long
    east = longitude + offset_long
    return (
        "POLYGON (("
        f"{west:.6f} {south:.6f}, "
        f"{east:.6f} {south:.6f}, "
        f"{east:.6f} {north:.6f}, "
        f"{west:.6f} {north:.6f}, "
        f"{west:.6f} {south:.6f}"
        "))"
    )


def build_temporary_farm_payloads(user):
    profile = secrets.choice(load_temporary_farm_profiles())
    suffix = user.tenant.code.removeprefix("sip-temp-")[-6:].upper()
    farm_name = f"{profile['farm_name']} {suffix}"
    latitude = float(profile["latitude"])
    longitude = float(profile["longitude"])
    now = datetime.now(timezone.utc)
    contact_first_name = (user.first_name or "Event").strip()
    contact_last_name = (user.last_name or "Participant").strip()
    administrator = user.get_full_name().strip() or user.username

    farm_payload = {
        "status": 1,
        "deleted_at": None,
        "name": farm_name,
        "description": profile["farm_description"],
        "administrator": administrator,
        "telephone": profile["telephone"],
        "vatID": f"TEMP-{suffix}",
        "contactPerson": {
            "firstname": contact_first_name,
            "lastname": contact_last_name,
        },
        "address": {
            "adminUnitL1": profile["country"],
            "adminUnitL2": profile["region"],
            "addressArea": profile["address_area"],
            "municipality": profile["municipality"],
            "community": profile["community"],
            "locatorName": farm_name,
        },
    }
    parcel_payload = {
        "status": 1,
        "deleted_at": None,
        "identifier": f"TEMP-{user.tenant.code}-{suffix}",
        "description": profile["parcel_description"],
        "validFrom": _iso_datetime(now),
        "validTo": _iso_datetime(now + timedelta(days=365)),
        "area": f"{float(profile['area_hectares']):.2f}",
        "hasIrrigationFlow": (
            f"{secrets.randbelow(9001) / 100 + 10:.2f}"
            if profile["is_irrigated"]
            else None
        ),
        "category": profile["parcel_category"],
        "inRegion": profile["region"],
        "hasToponym": profile["address_area"],
        "isNitroArea": False,
        "isNatura2000Area": False,
        "isPdopgArea": False,
        "isIrrigated": profile["is_irrigated"],
        "isCultivatedInLevels": False,
        "isGroundSlope": profile["is_ground_slope"],
        "depiction": "",
        "hasGeometry": {
            "@type": "Geometry",
            "asWKT": _rectangle_wkt(
                latitude,
                longitude,
                profile["area_hectares"],
            ),
        },
        "location": {
            "lat": f"{latitude:.6f}",
            "long": f"{longitude:.6f}",
        },
        "hasAgriCrop": [],
    }
    return profile, farm_payload, parcel_payload


def _post_json(url, payload, headers, timeout):
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=(timeout, timeout),
    )
    response.raise_for_status()
    return response.json()


def provision_temporary_farm(user):
    """Create and tenant-stamp one believable sample farm and parcel."""
    if not settings.GATEKEEPER_PROVISION_SAMPLE_FARM_ON_REGISTRATION:
        return {"success": False, "skipped": True, "reason": "disabled"}

    farm_id = None
    headers = {}
    farm_url = None
    timeout = settings.GATEKEEPER_FARM_PROVISION_TIMEOUT_SECONDS
    try:
        api_root = _farmcalendar_api_root()
        farm_url = urljoin(api_root, "Farm/")
        parcel_url = urljoin(api_root, "FarmParcels/")
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        access["rjti"] = str(refresh["jti"])
        headers = {
            "Authorization": f"Bearer {access}",
            "Content-Type": "application/json",
        }

        profile, farm_request, parcel_request = build_temporary_farm_payloads(user)
        farm_response = _post_json(farm_url, farm_request, headers, timeout)
        farm_id = _resource_id(farm_response, "Farm")
        farm_reference = _resource_reference(farm_response, "Farm")
        parcel_request["farm"] = {
            "@type": "Farm",
            "@id": farm_reference,
        }
        parcel_response = _post_json(parcel_url, parcel_request, headers, timeout)
        parcel_id = _resource_id(parcel_response, "Parcel")

        with transaction.atomic():
            upsert_fc_cache_from_payload(farm_response, tenant=user.tenant)
            upsert_fc_cache_from_payload(parcel_response, tenant=user.tenant)

        return {
            "success": True,
            "skipped": False,
            "farm_id": farm_id,
            "parcel_id": parcel_id,
            "farm_name": farm_request["name"],
            "parcel_identifier": parcel_request["identifier"],
            "profile": profile["profile_id"],
        }
    except Exception:
        LOG.exception(
            "Temporary FarmCalendar provisioning failed for user=%s tenant=%s",
            getattr(user, "username", "-"),
            getattr(user, "tenant_id", None),
        )
        if farm_id and farm_url:
            try:
                cleanup_response = requests.delete(
                    urljoin(farm_url, f"{farm_id}/"),
                    headers=headers,
                    timeout=(timeout, timeout),
                )
                cleanup_response.raise_for_status()
            except Exception:
                LOG.exception(
                    "Could not clean up partially provisioned farm=%s tenant=%s",
                    farm_id,
                    getattr(user, "tenant_id", None),
                )
        return {
            "success": False,
            "skipped": False,
            "reason": "farmcalendar_provisioning_failed",
        }
