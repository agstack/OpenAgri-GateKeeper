from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DefaultAuthUserExtend, ServiceMaster, PermissionMaster, CustomPermissions, GroupCustomPermissions


@admin.register(DefaultAuthUserExtend)
class DefaultAuthUserExtendAdmin(UserAdmin):
    # Specify the fields to be displayed in the user list view within the admin panel.
    list_display = ('email', 'first_name', 'last_name', 'uuid', 'is_active', 'date_joined', 'last_login')

    # Specify fields that should have a searchable multiple selection interface in the admin form.
    filter_horizontal = ('user_permissions', 'groups')

    # Customize the form fields displayed when viewing or editing a user, adding a new 'Assign projects' section.
    fieldsets = UserAdmin.fieldsets

    def get_fieldsets(self, request, obj=None):
        """
        Remove 'user_permissions' from any fieldset before rendering.
        This avoids the KeyError while keeping everything else intact.
        """
        base = super().get_fieldsets(request, obj)
        cleaned = []
        for name, opts in base:
            opts = dict(opts)  # shallow copy
            fields = opts.get('fields', ())
            if isinstance(fields, (list, tuple)):
                fields = tuple(f for f in fields if f != 'user_permissions')
                opts['fields'] = fields
            cleaned.append((name, opts))
        return tuple(cleaned)

    # Define which fields should be read-only in the admin form based on the current request and object being viewed.
    def get_readonly_fields(self, request, obj=None):
        # If a user is editing their own profile, restrict them from changing sensitive fields.
        if obj is not None and obj == request.user:
            return 'email', 'username', 'groups', 'user_permissions'
        # For superusers and staff (or other users with the permission to change user models)
        # return an empty tuple or any fields that should always be read-only
        # Otherwise, no fields are read-only unless specified here.
        return ()

    # Customize the queryset for the list view, which determines which users are displayed based on the request.
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superuser can see all users


@admin.register(ServiceMaster)
class ServiceMasterAdmin(admin.ModelAdmin):
    list_display = ("service_code", "service_name", "status", "updated_at")
    list_filter  = ("status",)
    search_fields = ("service_code", "service_name")
    ordering = ("service_code",)

    prepopulated_fields = {"service_code": ("service_name",)}


@admin.register(PermissionMaster)
class PermissionMasterAdmin(admin.ModelAdmin):
    list_display = ("id", "service", "action", "is_virtual", "status", "updated_at")
    list_filter = ("action", "is_virtual", "status")
    search_fields = ("service__service_code", "service__service_name")
    autocomplete_fields = ("service",)
    ordering = ("service__service_code", "action")


@admin.register(CustomPermissions)
class CustomPermissionsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "permission_name", "status", "updated_at")
    list_filter = ("status",)
    search_fields = (
        "user__email", "user__username",
        "permission_name__menu__menu_name", "permission_name__menu__menu_route",
    )
    autocomplete_fields = ("user", "permission_name")
    ordering = ("-updated_at",)


@admin.register(GroupCustomPermissions)
class GroupCustomPermissionsAdmin(admin.ModelAdmin):
    list_display = ("group_name", "status", "updated_at")
    list_display_links = ("group_name",)
    list_filter = ("status",)
    search_fields = ("group__name", "permission_names__menu__menu_name")
    autocomplete_fields = ("group",)
    filter_horizontal = ("permission_names",)
    ordering = ("group__name",)

    def group_name(self, obj):
        return obj.group.name

    group_name.short_description = "Group"
    group_name.admin_order_field = "group__name"
