from django.views.generic.base import ContextMixin
from django.contrib.auth.models import Permission
from django.shortcuts import redirect
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist

from aegis.models import CustomPermissions, GroupCustomPermissions, PermissionMaster, AdminMenuMaster
from .context_processors import get_admin_menu


# Inherits from UserPassesTestMixin to provide a basic framework for permission handling
class CustomPermissionRequiredMixin(UserPassesTestMixin):
    permission_menu = ''    # Placeholder for the menu that needs permission

    # Override test_func method to define custom logic for permission
    def test_func(self):
        # If no specific permission is required, return True
        if not self.permission_menu:
            return True

        # Automatically permit superusers and staff members
        if self.request.user.is_superuser: #or self.request.user.is_staff
            return True

        if not self.request.user.is_authenticated:  # Check if the user is authenticated
            return False

        try:
            # Get the AdminMenuMaster instance for the relevant menu
            menu = AdminMenuMaster.objects.get(menu_route=self.permission_menu)
            # Try fetching the associated permission from PermissionMaster model
            permission_master = PermissionMaster.objects.get(menu=menu, action='view')
        except ObjectDoesNotExist:
            # If either menu or permission doesn't exist, deny access
            return False

        # Check if the user has the permission
        has_permission = CustomPermissions.objects.filter(
            user=self.request.user, permission_name=permission_master
        ).exists()

        # Check if any of the user's groups have the custom permission (from GroupCustomPermissions model)
        has_group_permission = GroupCustomPermissions.objects.filter(
            group__in=self.request.user.groups.all(), permission_names=permission_master
        ).exists()

        # If either individual or group permission exists, grant access
        return has_permission or has_group_permission

    # Redirect to 'backend:dashboard' if the user doesn't have the required permission
    def handle_no_permission(self):
        return redirect('backend:dashboard')


# Inherits from ContextMixin to add extra context data to views
class AdminMenuMixin(ContextMixin):

    # Retrieves permissions for a given user
    def get_permissions(self, user):
        if user.is_authenticated:
            permissions = {}

            # Model-level permissions
            user_permissions = user.user_permissions.all()
            group_permissions = Permission.objects.filter(group__in=user.groups.all()).distinct()

            # Convert Django permissions into a dictionary
            for perm in user_permissions:
                permissions[perm.codename] = True
            for perm in group_permissions:
                permissions[perm.codename] = True

            # Custom user permissions
            custom_user_permissions = CustomPermissions.objects.filter(user=user, status=True)
            for perm in custom_user_permissions:
                permissions[str(perm.permission_name)] = True  # Ensure the name is formatted as a string

            # Custom group permissions
            custom_group_permissions = GroupCustomPermissions.objects.filter(group__in=user.groups.all(), status=True)
            for group_perm in custom_group_permissions:
                for perm in group_perm.permission_names.all():
                    permissions[str(perm)] = True

            # Handle virtual permissions
            if PermissionMaster.objects.filter(is_virtual=True).exists():
                virtual_permissions = PermissionMaster.objects.filter(is_virtual=True)
                for perm in virtual_permissions:
                    for action in ['add', 'view', 'edit', 'delete']:
                        permissions[f'{perm.menu.menu_route}_{action}'] = True

            return {'permissions': permissions}
        else:
            return {'permissions': {}}

    # Retrieves admin menu items
    def get_admin_menu(self):
        context = get_admin_menu()
        return context

    # Adds additional context data for rendering templates
    def can_add(self):
        permission_key = f"{self.permission_menu}_add"
        permissions = self.get_permissions(self.request.user)['permissions']
        return permissions.get(permission_key, False)

    def can_edit(self):
        permission_key = f"{self.permission_menu}_edit"
        permissions = self.get_permissions(self.request.user)['permissions']
        return permissions.get(permission_key, False)

    def can_delete(self):
        permission_key = f"{self.permission_menu}_delete"
        permissions = self.get_permissions(self.request.user)['permissions']
        return permissions.get(permission_key, False)

    def can_view(self):
        permission_key = f"{self.permission_menu}_view"
        permissions = self.get_permissions(self.request.user)['permissions']
        return permissions.get(permission_key, False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_admin_menu())
        permissions_context = self.get_permissions(self.request.user)
        context.update(permissions_context)
        # Update context with specific permissions
        context['add_permission'] = self.can_add()
        context['edit_permission'] = self.can_edit()
        context['delete_permission'] = self.can_delete()
        context['view_permission'] = self.can_view()
        return context


# Inherits from UserPassesTestMixin to check if the user passes a given test, typically a permissions check
class PermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None  # Placeholder for the required permission. This will be set in the view.

    # Override test_func to specify the permission logic
    def test_func(self):
        user = self.request.user

        # Allow superusers by default
        if user.is_superuser:
            return True

        # Check if a specific permission is required and if the user has it
        if self.permission_required and user.has_perm(self.permission_required):
            return True

        # Default to denying access
        return False

    # Handle cases where the user doesn't have the required permission
    def handle_no_permission(self):
        return redirect('backend:dashboard')
