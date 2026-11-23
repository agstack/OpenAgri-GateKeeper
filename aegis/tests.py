import re

from unittest.mock import Mock, patch

from requests import Timeout

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from rest_framework.test import APIClient

from django.core.exceptions import ValidationError

from aegis.models import (
    FarmCalendarResourceCache,
    PermissionMaster,
    RegisteredService,
    ServiceMaster,
    ServiceScopeAssignment,
    Tenant,
)
from aegis.services.entitlement_service import resolve_service_entitlements_for_user
from aegis.services.farm_provisioning import load_temporary_farm_profiles
from aegis.services.upstream_security import UpstreamPolicyError, validate_allowed_upstream
from aegis.views.api.service_registry_views import (
    _has_fc_service_wide_action,
    _endpoint_matches,
    select_matching_service,
)


class StaticFilesSecurityTests(SimpleTestCase):
    def test_whitenoise_storage_and_media_prefix_are_explicit(self):
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedStaticFilesStorage",
        )
        self.assertEqual(settings.MEDIA_URL, "/media/")

    def test_repository_files_are_not_exposed_by_a_root_media_route(self):
        with self.assertRaises(Resolver404):
            resolve("/.env")


@override_settings(GATEKEEPER_PROVISION_SAMPLE_FARM_ON_REGISTRATION=False)
class TemporaryRegistrationTests(TestCase):
    registration_data = {
        "first_name": "Event",
        "last_name": "User",
        "username": "event-user",
        "email": "event-user@example.com",
        "password": "temporary-pass-123",
        "password_confirm": "temporary-pass-123",
    }

    def test_registration_page_is_available(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/register.html")
        self.assertContains(response, "A new temporary SIP")

    def test_web_registration_creates_isolated_tenant_admin(self):
        existing_sip_codes = set(
            Tenant.objects.filter(code__startswith="sip", status=1).values_list("code", flat=True)
        )

        response = self.client.post(reverse("register"), self.registration_data)

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="event-user")
        self.assertTrue(user.check_password("temporary-pass-123"))
        self.assertTrue(user.is_tenant_admin)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNotNone(user.tenant_id)
        self.assertRegex(user.tenant.code, re.compile(r"^sip-temp-[0-9a-f]{12}$"))
        self.assertEqual(user.tenant.slug, user.tenant.code)
        self.assertTrue(user.tenant.name.startswith("Temporary Event SIP "))
        self.assertEqual(
            existing_sip_codes,
            set(Tenant.objects.filter(code__in=existing_sip_codes).values_list("code", flat=True)),
        )

    def test_password_confirmation_must_match(self):
        data = {**self.registration_data, "password_confirm": "different-pass-123"}

        response = self.client.post(reverse("register"), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")
        self.assertFalse(get_user_model().objects.filter(username="event-user").exists())
        self.assertFalse(Tenant.objects.filter(code__startswith="sip-temp-").exists())

    def test_duplicate_registration_does_not_create_another_user_or_tenant(self):
        first_response = self.client.post(reverse("register"), self.registration_data)
        second_response = self.client.post(reverse("register"), self.registration_data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, "A user with that username already exists.")
        self.assertContains(second_response, "This email is already registered.")
        self.assertEqual(get_user_model().objects.filter(username="event-user").count(), 1)
        self.assertEqual(Tenant.objects.filter(code__startswith="sip-temp-").count(), 1)

    def test_api_registration_uses_the_same_temporary_tenant_flow(self):
        data = {
            **self.registration_data,
            "username": "api-event-user",
            "email": "api-event-user@example.com",
        }

        response = self.client.post(reverse("api_register"), data, content_type="application/json")

        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="api-event-user")
        self.assertEqual(response.json()["tenant_code"], user.tenant.code)
        self.assertTrue(user.is_tenant_admin)
        self.assertTrue(user.is_staff)

    def test_api_registration_accepts_dashboard_field_names(self):
        data = {
            "username": "dashboard-event-user",
            "email": "dashboard-event-user@example.com",
            "password": "temporary-pass-123",
            "confirm_password": "temporary-pass-123",
            "firstName": "Dashboard",
            "lastName": "User",
        }

        response = self.client.post(reverse("api_register"), data, content_type="application/json")

        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="dashboard-event-user")
        self.assertEqual(user.first_name, "Dashboard")
        self.assertEqual(user.last_name, "User")
        self.assertTrue(user.check_password("temporary-pass-123"))
        self.assertTrue(user.is_tenant_admin)
        self.assertTrue(user.is_staff)

    def test_registered_user_can_access_tenant_scoped_user_admin(self):
        self.client.post(reverse("register"), self.registration_data)
        user = get_user_model().objects.get(username="event-user")
        self.client.force_login(user)

        list_response = self.client.get(reverse("admin:aegis_defaultauthuserextend_changelist"))
        add_response = self.client.get(reverse("admin:aegis_defaultauthuserextend_add"))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(add_response.status_code, 200)


class TemporaryFarmProfileTests(SimpleTestCase):
    def test_catalogue_contains_100_complete_unique_profiles(self):
        profiles = load_temporary_farm_profiles()
        required_fields = {
            "profile_id",
            "farm_name",
            "farm_description",
            "telephone",
            "country",
            "region",
            "address_area",
            "municipality",
            "community",
            "parcel_description",
            "area_hectares",
            "parcel_category",
            "is_irrigated",
            "is_ground_slope",
            "latitude",
            "longitude",
        }

        self.assertEqual(len(profiles), 100)
        self.assertEqual(len({profile["profile_id"] for profile in profiles}), 100)
        for profile in profiles:
            self.assertTrue(required_fields.issubset(profile))
            self.assertGreater(float(profile["area_hectares"]), 0)
            self.assertGreaterEqual(float(profile["latitude"]), -90)
            self.assertLessEqual(float(profile["latitude"]), 90)
            self.assertGreaterEqual(float(profile["longitude"]), -180)
            self.assertLessEqual(float(profile["longitude"]), 180)


@override_settings(
    GATEKEEPER_PROVISION_SAMPLE_FARM_ON_REGISTRATION=True,
    GATEKEEPER_FARM_PROVISION_TIMEOUT_SECONDS=3,
    GATEKEEPER_ALLOWED_UPSTREAMS=("http://farmcalendar:8002/",),
    GATEKEEPER_ALLOW_PRIVATE_UPSTREAMS=True,
    GATEKEEPER_ALLOW_HTTP_UPSTREAMS=True,
    AVAILABLE_SERVICES={
        "FarmCalendar": {
            "api": "http://farmcalendar:8002/api/",
            "post_auth": "http://farmcalendar:8002/post_auth/",
        }
    },
)
class TemporaryFarmProvisioningTests(TestCase):
    registration_data = {
        "first_name": "Event",
        "last_name": "Farmer",
        "username": "provisioned-user",
        "email": "provisioned-user@example.com",
        "password": "temporary-pass-123",
        "password_confirm": "temporary-pass-123",
    }

    @staticmethod
    def _response(payload):
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    @patch("aegis.services.farm_provisioning.requests.post")
    def test_api_registration_creates_farm_then_parcel_and_stamps_tenant(self, post_mock):
        farm_id = "1c2b58f0-c40c-42ce-8d90-a064f9579750"
        parcel_id = "ae2ecfa9-4387-41cb-95b9-72ba83505880"
        farm_reference = f"urn:farmcalendar:Farm:{farm_id}"
        farm_resource = {
            "@type": "Farm",
            "@id": farm_reference,
            "name": "Temporary Farm",
        }
        parcel_resource = {
            "@type": "Parcel",
            "@id": f"urn:farmcalendar:FarmParcel:{parcel_id}",
            "identifier": "Temporary Parcel",
            "farm": {"@type": "Farm", "@id": farm_reference},
        }
        post_mock.side_effect = [
            self._response({"@graph": [farm_resource]}),
            self._response({"@graph": [parcel_resource]}),
        ]

        response = self.client.post(
            reverse("api_register"),
            self.registration_data,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        result = response.json()["farm_provisioning"]
        self.assertTrue(result["success"])
        self.assertEqual(result["farm_id"], farm_id)
        self.assertEqual(result["parcel_id"], parcel_id)
        self.assertEqual(post_mock.call_count, 2)

        farm_call, parcel_call = post_mock.call_args_list
        self.assertEqual(farm_call.args[0], "http://farmcalendar:8002/api/v1/Farm/")
        self.assertEqual(
            parcel_call.args[0],
            "http://farmcalendar:8002/api/v1/FarmParcels/",
        )
        self.assertTrue(farm_call.kwargs["headers"]["Authorization"].startswith("Bearer "))
        self.assertEqual(farm_call.kwargs["timeout"], (3, 3))

        farm_request = farm_call.kwargs["json"]
        self.assertEqual(farm_request["status"], 1)
        self.assertIsNone(farm_request["deleted_at"])
        self.assertEqual(set(farm_request["contactPerson"]), {"firstname", "lastname"})
        self.assertEqual(
            set(farm_request["address"]),
            {
                "adminUnitL1",
                "adminUnitL2",
                "addressArea",
                "municipality",
                "community",
                "locatorName",
            },
        )

        parcel_request = parcel_call.kwargs["json"]
        self.assertEqual(parcel_request["farm"]["@id"], farm_reference)
        self.assertEqual(parcel_request["hasGeometry"]["@type"], "Geometry")
        self.assertTrue(parcel_request["hasGeometry"]["asWKT"].startswith("POLYGON (("))
        self.assertEqual(parcel_request["hasAgriCrop"], [])
        self.assertEqual(parcel_request["depiction"], "")

        user = get_user_model().objects.get(username="provisioned-user")
        farm_cache = FarmCalendarResourceCache.objects.get(
            resource_type="farm",
            resource_id=farm_id,
        )
        parcel_cache = FarmCalendarResourceCache.objects.get(
            resource_type="parcel",
            resource_id=parcel_id,
        )
        self.assertEqual(farm_cache.tenant, user.tenant)
        self.assertEqual(parcel_cache.tenant, user.tenant)
        self.assertEqual(parcel_cache.farm_id, farm_cache.resource_id)

    @patch("aegis.services.farm_provisioning.requests.post", side_effect=Timeout)
    def test_registration_is_retained_when_farmcalendar_is_unavailable(self, post_mock):
        response = self.client.post(
            reverse("api_register"),
            self.registration_data,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["farm_provisioning"]["success"])
        self.assertFalse(response.json()["farm_provisioning"]["skipped"])
        self.assertTrue(get_user_model().objects.filter(username="provisioned-user").exists())
        self.assertTrue(Tenant.objects.filter(code__startswith="sip-temp-").exists())
        self.assertFalse(FarmCalendarResourceCache.objects.exists())
        post_mock.assert_called_once()

    @patch("aegis.services.farm_provisioning.requests.delete")
    @patch("aegis.services.farm_provisioning.requests.post")
    def test_partial_farm_is_removed_when_parcel_creation_fails(
        self,
        post_mock,
        delete_mock,
    ):
        farm_id = "1c2b58f0-c40c-42ce-8d90-a064f9579750"
        farm_reference = f"urn:farmcalendar:Farm:{farm_id}"
        post_mock.side_effect = [
            self._response(
                {
                    "@graph": [
                        {
                            "@type": "Farm",
                            "@id": farm_reference,
                            "name": "Temporary Farm",
                        }
                    ]
                }
            ),
            Timeout(),
        ]
        delete_mock.return_value = self._response({})

        response = self.client.post(
            reverse("api_register"),
            self.registration_data,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["farm_provisioning"]["success"])
        delete_mock.assert_called_once()
        self.assertEqual(
            delete_mock.call_args.args[0],
            f"http://farmcalendar:8002/api/v1/Farm/{farm_id}/",
        )
        self.assertTrue(get_user_model().objects.filter(username="provisioned-user").exists())
        self.assertFalse(FarmCalendarResourceCache.objects.exists())


class ServiceRegistrySecurityTests(TestCase):
    allowed_local_upstreams = {
        "GATEKEEPER_ALLOWED_UPSTREAMS": (
            "http://127.0.0.1:8002/",
            "http://farmcalendar:8002/",
        ),
        "GATEKEEPER_ALLOW_PRIVATE_UPSTREAMS": True,
        "GATEKEEPER_ALLOW_HTTP_UPSTREAMS": True,
    }

    def setUp(self):
        user_model = get_user_model()
        self.tenant = Tenant.objects.create(
            code="sip-temp-security",
            slug="sip-temp-security",
            name="Temporary Security SIP",
        )
        self.tenant_admin = user_model.objects.create_user(
            username="tenant-admin",
            email="tenant-admin@example.com",
            password="temporary-pass-123",
            tenant=self.tenant,
            is_tenant_admin=True,
            is_staff=True,
            status=1,
        )
        self.platform_admin = user_model.objects.create_superuser(
            username="platform-admin",
            email="platform-admin@example.com",
            password="temporary-pass-123",
        )
        self.client = APIClient()

    def test_tenant_admin_cannot_manage_global_service_registry(self):
        self.client.force_authenticate(self.tenant_admin)
        payload = {
            "base_url": "http://127.0.0.1:8002/",
            "service_name": "farmcalendar",
            "endpoint": "api/v1/Farm/",
            "methods": ["GET"],
        }

        register_response = self.client.post(reverse("register_service"), payload, format="json")
        directory_response = self.client.get(reverse("service_directory"))
        delete_response = self.client.delete(reverse("delete_service"), payload, format="json")

        self.assertEqual(register_response.status_code, 403)
        self.assertEqual(directory_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertFalse(RegisteredService.objects.exists())

    @override_settings(**allowed_local_upstreams)
    def test_platform_admin_can_register_allowlisted_service(self):
        self.client.force_authenticate(self.platform_admin)

        response = self.client.post(
            reverse("register_service"),
            {
                "base_url": "http://127.0.0.1:8002/",
                "service_name": "farmcalendar",
                "endpoint": "api/v1/Farm/",
                "methods": ["get", "HEAD"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        service = RegisteredService.objects.get()
        self.assertEqual(service.methods, ["GET", "HEAD"])

    @override_settings(**allowed_local_upstreams)
    def test_platform_admin_cannot_register_unallowlisted_service(self):
        self.client.force_authenticate(self.platform_admin)

        response = self.client.post(
            reverse("register_service"),
            {
                "base_url": "http://169.254.169.254:80/",
                "service_name": "metadata",
                "endpoint": "latest/meta-data/",
                "methods": ["GET"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RegisteredService.objects.exists())

    @override_settings(
        GATEKEEPER_ALLOWED_UPSTREAMS=("http://127.0.0.1:8002/",),
        GATEKEEPER_ALLOW_PRIVATE_UPSTREAMS=False,
        GATEKEEPER_ALLOW_HTTP_UPSTREAMS=True,
    )
    def test_private_address_requires_explicit_configuration(self):
        with self.assertRaises(UpstreamPolicyError):
            validate_allowed_upstream("http://127.0.0.1:8002/")

    @override_settings(**allowed_local_upstreams)
    def test_proxy_rejects_stored_route_outside_allowlist_without_network_call(self):
        RegisteredService.objects.create(
            base_url="http://169.254.169.254:80/",
            service_name="unsafe",
            endpoint="latest/meta-data/",
            methods=["GET"],
        )
        self.client.force_authenticate(self.tenant_admin)

        response = self.client.get(
            reverse("new_reverse_proxy", kwargs={"path": "unsafe/latest/meta-data/"})
        )

        self.assertEqual(response.status_code, 502)

    @override_settings(**allowed_local_upstreams)
    def test_proxy_strips_cookies_and_rebuilds_forwarding_headers(self):
        RegisteredService.objects.create(
            base_url="http://127.0.0.1:8002/",
            service_name="approved",
            endpoint="api/status/",
            methods=["GET"],
        )
        upstream_response = Mock(
            status_code=200,
            headers={"Content-Type": "text/plain"},
        )
        upstream_response.iter_content.return_value = iter([b"ok"])
        self.client.force_authenticate(self.tenant_admin)

        with patch(
            "aegis.views.api.service_registry_views.requests.request",
            return_value=upstream_response,
        ) as request_mock:
            response = self.client.get(
                reverse("new_reverse_proxy", kwargs={"path": "approved/api/status/"}),
                HTTP_AUTHORIZATION="Bearer placeholder",
                HTTP_COOKIE="sessionid=must-not-leave-gatekeeper",
                HTTP_X_FORWARDED_FOR="198.51.100.25",
            )

        self.assertEqual(response.status_code, 200)
        forwarded_headers = request_mock.call_args.kwargs["headers"]
        self.assertNotIn("Cookie", forwarded_headers)
        self.assertEqual(forwarded_headers["Authorization"], "Bearer placeholder")
        self.assertEqual(forwarded_headers["X-Forwarded-For"], "127.0.0.1")

    def test_proxy_options_requires_authentication(self):
        response = self.client.options(
            reverse("new_reverse_proxy", kwargs={"path": "farmcalendar/api/v1/Farm/"})
        )

        self.assertEqual(response.status_code, 401)


class _FakeService:
    """Minimal stand-in for a RegisteredService row (endpoint + methods)."""

    def __init__(self, endpoint, methods):
        self.endpoint = endpoint
        self.methods = methods


class FarmCalendarServiceWideActionTests(SimpleTestCase):
    def test_tenant_admin_can_use_flattened_service_action_without_scope_assignments(self):
        entitlement = {
            "roles": ["tenant_admin"],
            "actions": ["add", "delete", "edit", "view"],
            "assignments": [],
            "unrestricted": False,
        }

        self.assertTrue(_has_fc_service_wide_action(entitlement, "add"))

    def test_scoped_role_does_not_get_service_wide_action_from_flattened_actions(self):
        entitlement = {
            "roles": ["Viewer"],
            "actions": ["view"],
            "assignments": [],
            "unrestricted": False,
        }

        self.assertFalse(_has_fc_service_wide_action(entitlement, "view"))


class EndpointMatchesTests(SimpleTestCase):
    def test_plain_endpoint_matches_ignoring_slashes(self):
        self.assertTrue(_endpoint_matches("api/v1/foo/", "api/v1/foo"))
        self.assertFalse(_endpoint_matches("api/v1/foo/", "api/v1/bar/"))

    def test_template_matches_single_segment_only(self):
        self.assertTrue(_endpoint_matches("api/v1/foo/{id}/", "api/v1/foo/abc-123/"))
        # a template segment must not span a slash
        self.assertFalse(_endpoint_matches("api/v1/foo/{id}/", "api/v1/foo/abc/extra/"))

    def test_plain_endpoint_is_not_treated_as_regex(self):
        # a literal endpoint must match literally, not as a pattern
        self.assertFalse(_endpoint_matches("api/v1/foo/bar/", "api/v1/foo/XXX/"))


class SelectMatchingServiceTests(SimpleTestCase):
    # Registry ordered template-first on purpose: the fix must not depend on
    # DB row order (template-first is what clobbered reporting originally).
    REPORTING = [
        _FakeService("api/v1/openagri-report/{report_id}/", ["GET"]),
        _FakeService("api/v1/openagri-report/irrigation-report/", ["POST", "GET"]),
        _FakeService("api/v1/openagri-report/compost-report/", ["POST"]),
    ]

    def test_generate_routes_to_literal_not_template(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/irrigation-report/", "POST"
        )
        self.assertTrue(matched)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/irrigation-report/")

    def test_retrieval_by_uuid_routes_to_template(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/6a6d9391-7114-45ad-8107-c9eba5329efd/", "GET"
        )
        self.assertTrue(matched)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/{report_id}/")

    def test_matched_path_but_disallowed_method_is_405_not_404(self):
        # POST on a uuid: template matches the path but only allows GET -> 405 semantics
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/6a6d9391-7114-45ad-8107-c9eba5329efd/", "POST"
        )
        self.assertIsNone(entry)
        self.assertTrue(matched)

    def test_no_match_is_404_semantics(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/", "GET"
        )
        self.assertIsNone(entry)
        self.assertFalse(matched)

    def test_options_is_always_allowed_through(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/compost-report/", "OPTIONS"
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/compost-report/")

    def test_pdm_import_literal_and_id_template_coexist(self):
        pdm = [
            _FakeService("api/v1/threat-model/{tm_id}/", ["DELETE", "PATCH"]),
            _FakeService("api/v1/threat-model/import-excel/", ["POST"]),
            _FakeService("api/v1/threat-model/import-json/", ["POST"]),
        ]
        entry, _ = select_matching_service(pdm, "api/v1/threat-model/import-excel/", "POST")
        self.assertEqual(entry.endpoint, "api/v1/threat-model/import-excel/")
        # real DELETE/PATCH on an id still reach the template
        entry, _ = select_matching_service(pdm, "api/v1/threat-model/abc-uuid/", "DELETE")
        self.assertEqual(entry.endpoint, "api/v1/threat-model/{tm_id}/")

    def test_weather_location_literals_and_id_template(self):
        weather = [
            _FakeService("api/v1/locations/locations/{location_id}/", ["DELETE"]),
            _FakeService("api/v1/locations/locations/by-coordinates/", ["GET"]),
            _FakeService("api/v1/locations/locations/unique/", ["POST"]),
        ]
        entry, _ = select_matching_service(
            weather, "api/v1/locations/locations/by-coordinates/", "GET"
        )
        self.assertEqual(entry.endpoint, "api/v1/locations/locations/by-coordinates/")
        entry, _ = select_matching_service(
            weather, "api/v1/locations/locations/some-id/", "DELETE"
        )
        self.assertEqual(entry.endpoint, "api/v1/locations/locations/{location_id}/")
        # GET on an id is unsupported by the service -> matched path, no method -> 405
        entry, matched = select_matching_service(
            weather, "api/v1/locations/locations/some-id/", "GET"
        )
        self.assertIsNone(entry)
        self.assertTrue(matched)


@override_settings(
    GATEKEEPER_ALLOWED_UPSTREAMS=("http://127.0.0.1:8002/",),
    GATEKEEPER_ALLOW_PRIVATE_UPSTREAMS=True,
    GATEKEEPER_ALLOW_HTTP_UPSTREAMS=True,
    GATEKEEPER_READ_ONLY_POST_ALLOWLIST=("pdm:api/v1/fuzzy-risk/fc/forecast/",),
)
class ReadOnlyUserTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tenant = Tenant.objects.create(code="sip-read-only", slug="sip-read-only", name="Read Only SIP")
        other_tenant = Tenant.objects.create(code="sip-other", slug="sip-other", name="Other SIP")

        for code, name in (("FC", "Farm Calendar"), ("PDM", "Pest & Disease Management")):
            service, _ = ServiceMaster.objects.get_or_create(service_code=code, defaults={"service_name": name})
            for action in ("view", "add", "edit", "delete"):
                PermissionMaster.objects.get_or_create(service=service, action=action)
        self.fc_service = ServiceMaster.objects.get(service_code="FC")

        self.farm_id = "11111111-1111-1111-1111-111111111111"
        self.parcel_id = "22222222-2222-2222-2222-222222222222"
        self.other_farm_id = "33333333-3333-3333-3333-333333333333"
        FarmCalendarResourceCache.objects.create(
            resource_type="farm", resource_id=self.farm_id, tenant=self.tenant
        )
        FarmCalendarResourceCache.objects.create(
            resource_type="parcel", resource_id=self.parcel_id, farm_id=self.farm_id, tenant=self.tenant
        )
        FarmCalendarResourceCache.objects.create(
            resource_type="farm", resource_id=self.other_farm_id, tenant=other_tenant
        )

        self.read_only_user = user_model.objects.create_user(
            username="evaluator",
            email="evaluator@example.com",
            password="temporary-pass-123",
            tenant=self.tenant,
            is_read_only=True,
        )
        self.tenant_admin = user_model.objects.create_user(
            username="read-only-tenant-admin",
            email="read-only-tenant-admin@example.com",
            password="temporary-pass-123",
            tenant=self.tenant,
            is_tenant_admin=True,
        )

        for service_name, endpoint, methods in (
            ("farmcalendar", "api/v1/Farm/", ["GET", "POST"]),
            ("farmcalendar", "api/v1/Farm/{farm_id}/", ["GET", "PATCH", "DELETE"]),
            ("pdm", "api/v1/disease/", ["GET", "POST"]),
            ("pdm", "api/v1/fuzzy-risk/fc/forecast/", ["POST"]),
        ):
            RegisteredService.objects.create(
                base_url="http://127.0.0.1:8002/",
                service_name=service_name,
                endpoint=endpoint,
                methods=methods,
            )
        self.client = APIClient()

    @staticmethod
    def _service(entitlements, code):
        return next(service for service in entitlements if service["code"] == code)

    @staticmethod
    def _upstream_ok():
        upstream_response = Mock(status_code=200, headers={"Content-Type": "text/plain"})
        upstream_response.iter_content.return_value = iter([b"ok"])
        return upstream_response

    def _proxy_url(self, path):
        return reverse("new_reverse_proxy", kwargs={"path": path})

    def test_entitlements_are_view_only_and_cover_own_tenant_farms(self):
        entitlements = resolve_service_entitlements_for_user(self.read_only_user)

        fc = self._service(entitlements, "FC")
        self.assertEqual(fc["actions"], ["view"])
        self.assertEqual(fc["roles"], ["read_only"])
        self.assertEqual(fc["scopes"], {"farm": [self.farm_id], "parcel": [self.parcel_id]})
        self.assertTrue(all(a["actions"] == ["view"] for a in fc["assignments"]))
        pdm = self._service(entitlements, "PDM")
        self.assertEqual(pdm["actions"], ["view"])

    def test_role_grant_cannot_give_read_only_user_write_actions(self):
        ServiceScopeAssignment.objects.create(
            tenant=self.tenant,
            service=self.fc_service,
            user=self.read_only_user,
            role="editor",
            actions=["view", "edit", "delete"],
            scope_type="farm",
            scope_id=self.farm_id,
        )

        fc = self._service(resolve_service_entitlements_for_user(self.read_only_user), "FC")

        self.assertEqual(fc["actions"], ["view"])
        self.assertTrue(all(a["actions"] == ["view"] for a in fc["assignments"]))

    def test_other_users_keep_their_write_actions(self):
        entitlements = resolve_service_entitlements_for_user(self.tenant_admin)

        self.assertEqual(self._service(entitlements, "FC")["actions"], ["add", "delete", "edit", "view"])
        self.assertEqual(self._service(entitlements, "PDM")["actions"], ["add", "delete", "edit", "view"])

    def test_me_reports_read_only_flag(self):
        self.client.force_authenticate(self.read_only_user)

        response = self.client.get(reverse("api_me"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["is_read_only"])

    def test_read_only_user_cannot_also_be_admin_or_staff(self):
        for flags in ({"is_tenant_admin": True}, {"is_staff": True}, {"is_superuser": True}):
            user = get_user_model()(
                username="conflict", email="conflict@example.com", tenant=self.tenant, is_read_only=True, **flags
            )
            with self.assertRaises(ValidationError):
                user.clean()

    def test_proxy_refuses_writes_on_every_service(self):
        self.client.force_authenticate(self.read_only_user)

        with patch("aegis.views.api.service_registry_views.requests.request") as request_mock:
            responses = [
                self.client.post(self._proxy_url("farmcalendar/api/v1/Farm/"), {}, format="json"),
                self.client.patch(self._proxy_url(f"farmcalendar/api/v1/Farm/{self.farm_id}/"), {}, format="json"),
                self.client.delete(self._proxy_url(f"farmcalendar/api/v1/Farm/{self.farm_id}/")),
                self.client.post(self._proxy_url("pdm/api/v1/disease/"), {}, format="json"),
            ]

        self.assertEqual([response.status_code for response in responses], [403, 403, 403, 403])
        self.assertEqual(responses[0].json(), {"error": "This account is read-only."})
        request_mock.assert_not_called()

    def test_proxy_allows_reads_and_allowlisted_posts(self):
        self.client.force_authenticate(self.read_only_user)

        with patch(
            "aegis.views.api.service_registry_views.requests.request",
            side_effect=lambda *args, **kwargs: self._upstream_ok(),
        ) as request_mock:
            read_response = self.client.get(self._proxy_url("pdm/api/v1/disease/"))
            forecast_response = self.client.post(
                self._proxy_url("pdm/api/v1/fuzzy-risk/fc/forecast/"), {}, format="json"
            )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(forecast_response.status_code, 200)
        self.assertEqual(request_mock.call_count, 2)

    def test_proxy_still_forwards_writes_for_other_users(self):
        self.client.force_authenticate(self.tenant_admin)

        with patch(
            "aegis.views.api.service_registry_views.requests.request",
            return_value=self._upstream_ok(),
        ) as request_mock:
            response = self.client.post(self._proxy_url("pdm/api/v1/disease/"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        request_mock.assert_called_once()
