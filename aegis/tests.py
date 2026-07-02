from django.test import SimpleTestCase

from aegis.views.api.service_registry_views import _has_fc_service_wide_action


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
