from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone

from .models import (DefaultAuthUserExtend, ServiceMaster, PermissionMaster, CustomPermissions, GroupCustomPermissions,
                     RegisteredService, BlacklistedAccess, BlacklistedRefresh, RequestLog, GroupServiceAccess)


class StatusBadgeMixin:
    """
    Renders a coloured pill for a 'status' IntegerField with choices like:
      1=Active, 0=Inactive, 2=Deleted
    """
    STATUS_COLOURS = {1: "#16a34a", 0: "#ef4444", 2: "#6b7280"}  # green/red/grey

    @admin.display(description="Status")
    def status_badge(self, obj):
        value = getattr(obj, "status", None)
        labels = dict(getattr(obj, "STATUS_CHOICES", [])) if hasattr(obj, "STATUS_CHOICES") else {
            1: "Active", 0: "Inactive", 2: "Deleted"
        }
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{bg};color:#fff;">{text}</span>',
            bg=self.STATUS_COLOURS.get(value, "#6b7280"),
            text=labels.get(value, value),
        )

class BoolBadgeMixin:
    """Show boolean values as coloured badges."""
    @staticmethod
    def bool_badge(value: bool, true_label="Yes", false_label="No"):
        colour = "#16a34a" if value else "#ef4444"
        label = true_label if value else false_label
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{bg};color:#fff;">{text}</span>',
            bg=colour,
            text=label,
        )

class ActivateDeactivateActions(admin.ModelAdmin):
    """Bulk activate/deactivate by setting status=1/0."""
    @admin.action(description="Mark selected as Active")
    def mark_active(self, request, queryset):
        updated = queryset.update(status=1, deleted_at=None)
        self.message_user(request, f"{updated} record(s) marked Active.", level=messages.SUCCESS)

    @admin.action(description="Mark selected as Inactive")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(status=0)
        self.message_user(request, f"{updated} record(s) marked Inactive.", level=messages.WARNING)


class SoftDeleteActions(admin.ModelAdmin):
    """Soft delete / restore using BaseModel fields."""
    @admin.action(description="Soft delete selected")
    def soft_delete_selected(self, request, queryset):
        updated = queryset.exclude(status=2).update(status=2, deleted_at=timezone.now())
        self.message_user(request, f"{updated} record(s) soft-deleted.", level=messages.WARNING)

    @admin.action(description="Restore selected (set Active)")
    def restore_selected(self, request, queryset):
        updated = queryset.update(status=1, deleted_at=None)
        self.message_user(request, f"{updated} record(s) restored.", level=messages.SUCCESS)


class CSVExportMixin:
    """
    Minimal CSV export. In each admin class set:
      EXPORT_FIELDS = ("field1", "related.field2", ...)
    """
    EXPORT_FIELDS: tuple[str, ...] = ()

    @admin.action(description="Export selected to CSV")
    def export_as_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        if not self.EXPORT_FIELDS:
            self.message_user(request, "No EXPORT_FIELDS defined.", level=messages.ERROR)
            return

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{queryset.model.__name__.lower()}_export.csv"'
        writer = csv.writer(response)
        writer.writerow(self.EXPORT_FIELDS)

        for obj in queryset:
            row = []
            for path in self.EXPORT_FIELDS:
                value = obj
                for part in path.split("."):
                    value = getattr(value, part, "")
                    if callable(value):
                        value = value()
                row.append(value)
            writer.writerow(row)
        return response

@admin.register(DefaultAuthUserExtend)
class DefaultAuthUserExtendAdmin(UserAdmin, CSVExportMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions):
    """
        Polished user admin for DefaultAuthUserExtend (inherits BaseModel):
        - Status badge, soft-delete/restore, activate/deactivate
        - CSV export
        - Self-edit safety
        """
    list_display = ('email', 'first_name', 'last_name', 'uuid', 'status_badge', 'date_joined', 'last_login')
    list_display_links = ('email',)
    search_fields = ('email', 'first_name', 'last_name', 'username', 'uuid')
    list_filter = ('status', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login')
    ordering = ('email',)
    date_hierarchy = 'date_joined'
    list_per_page = 50

    # System fields read-only; deleted_at set via soft delete action
    readonly_fields = ('deleted_at', 'created_at', 'updated_at')
    fieldsets = UserAdmin.fieldsets

    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("email", "first_name", "last_name", "username",
                     "uuid", "status", "is_active", "is_staff", "is_superuser",
                     "date_joined", "last_login", "created_at", "updated_at", "deleted_at")

    def get_fieldsets(self, request, obj=None):
        base = super().get_fieldsets(request, obj)
        cleaned = []
        for name, opts in base:
            opts = dict(opts)
            fields = opts.get('fields', ())
            if isinstance(fields, (list, tuple)):
                fields = tuple(f for f in fields if f != 'user_permissions')
                opts['fields'] = fields
            cleaned.append((name, opts))
        # Append a lifecycle section for BaseModel fields (display only)
        cleaned.append((
            "Lifecycle",
            {"fields": ("status", "deleted_at", "created_at", "updated_at")}
        ))
        return tuple(cleaned)

    def get_readonly_fields(self, request, obj=None):
        base = super().get_readonly_fields(request, obj)
        ro = set(base) | {"deleted_at", "created_at", "updated_at"}
        if obj is not None and obj == request.user:
            ro |= {"email", "username", "groups", "user_permissions"}
        return tuple(sorted(ro))

    # Remove hard delete (nudge admins to soft-delete)
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    # Show all (including deleted); default manager already does that
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related()


@admin.register(ServiceMaster)
class ServiceMasterAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("service_code", "service_name", "status_badge", "updated_at")
    list_display_links = ("service_code", "service_name")
    list_filter  = ("status", "updated_at", "created_at")
    search_fields = ("service_code", "service_name", "service_description")
    ordering = ("service_code",)
    date_hierarchy = "created_at"
    list_per_page = 50

    prepopulated_fields = {"service_code": ("service_name",)}

    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("service_code", "service_name", "service_description", "status", "created_at", "updated_at", "deleted_at")

    # Remove hard delete
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(PermissionMaster)
class PermissionMasterAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("id", "service_code", "action", "virtual_badge", "status_badge", "updated_at")
    list_filter = ("action", "is_virtual", "status", "updated_at", "created_at")
    search_fields = ("service__service_code", "service__service_name", "action")
    autocomplete_fields = ("service",)
    ordering = ("service__service_code", "action")
    list_per_page = 50
    date_hierarchy = "created_at"

    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("id", "service.service_code", "action", "is_virtual", "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="Service")
    def service_code(self, obj):
        return getattr(obj.service, "service_code", "")

    @admin.display(description="Virtual")
    def virtual_badge(self, obj):
        return BoolBadgeMixin.bool_badge(bool(obj.is_virtual), true_label="Virtual", false_label="Real")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(CustomPermissions)
class CustomPermissionsAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("id", "user_email", "permission_display", "status_badge", "updated_at")
    list_filter = ("status", "updated_at", "created_at")
    search_fields = (
        "user__email", "user__username",
        "permission_name__service__service_code", "permission_name__action",
        "permission_name__service__service_name",
    )
    autocomplete_fields = ("user", "permission_name")
    ordering = ("-updated_at",)
    list_per_page = 50
    date_hierarchy = "created_at"

    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("id", "user.email", "user.username", "permission_name.service.service_code",
                     "permission_name.action", "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="User")
    def user_email(self, obj):
        return getattr(obj.user, "email", "") or getattr(obj.user, "username", "")

    @admin.display(description="Permission")
    def permission_display(self, obj):
        # Relies on __str__ in PermissionMaster; otherwise build a custom string
        return str(obj.permission_name)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "permission_name", "permission_name__service")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(GroupCustomPermissions)
class GroupCustomPermissionsAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("group_name", "permission_count", "status_badge", "updated_at")
    list_display_links = ("group_name",)
    list_filter = ("status", "updated_at", "created_at")
    search_fields = ("group__name", "permission_names__service__service_code", "permission_names__action")
    autocomplete_fields = ("group",)
    filter_horizontal = ("permission_names",)
    ordering = ("group__name",)
    list_per_page = 50
    date_hierarchy = "created_at"

    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("group.name", "status", "created_at", "updated_at", "deleted_at")

    def group_name(self, obj):
        return obj.group.name
    group_name.short_description = "Group"
    group_name.admin_order_field = "group__name"

    @admin.display(description="Permissions")
    def permission_count(self, obj):
        return obj.permission_names.count()

    def get_queryset(self, request):
        # Use prefetch_related for the M2M to avoid N+1 on permission_count view clicks
        qs = super().get_queryset(request)
        return qs.select_related("group").prefetch_related("permission_names")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(RegisteredService)
class RegisteredServiceAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("service_name", "endpoint", "base_url", "status_badge", "updated_at")
    list_display_links = ("service_name",)
    search_fields = ("service_name", "endpoint", "base_url", "service_url", "params", "comments")
    list_filter = ("status", "updated_at", "created_at")
    ordering = ("service_name",)
    date_hierarchy = "created_at"
    list_per_page = 50

    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("service_name", "base_url", "endpoint", "methods", "params", "service_url",
                     "status", "created_at", "updated_at", "deleted_at")

@admin.register(BlacklistedRefresh)
class BlacklistedRefreshAdmin(CSVExportMixin, admin.ModelAdmin):
    list_display = ("rjti", "expires_at", "blacklisted_at", "expired_badge", "status_badge")
    # Note: BlacklistedRefresh inherits BaseModel → has status/deleted_at; keep it simple here.
    list_filter = ("expires_at", "blacklisted_at", "status")
    search_fields = ("rjti",)
    date_hierarchy = "blacklisted_at"
    ordering = ("-blacklisted_at",)
    list_per_page = 50
    readonly_fields = ("blacklisted_at", "created_at", "updated_at", "deleted_at")
    EXPORT_FIELDS = ("rjti", "expires_at", "blacklisted_at", "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="Expired")
    def expired_badge(self, obj):
        return BoolBadgeMixin.bool_badge(obj.is_expired, true_label="Expired", false_label="Valid")

    @admin.display(description="Status")
    def status_badge(self, obj):
        colour = "#6b7280"
        return format_html('<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;">{}</span>',
                           colour, "—")


@admin.register(BlacklistedAccess)
class BlacklistedAccessAdmin(CSVExportMixin, admin.ModelAdmin):
    list_display = ("jti", "expires_at", "blacklisted_at", "expired_badge", "status_badge")
    list_filter = ("expires_at", "blacklisted_at", "status")
    search_fields = ("jti",)
    date_hierarchy = "blacklisted_at"
    ordering = ("-blacklisted_at",)
    list_per_page = 50
    readonly_fields = ("blacklisted_at", "created_at", "updated_at", "deleted_at")
    EXPORT_FIELDS = ("jti", "expires_at", "blacklisted_at", "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="Expired")
    def expired_badge(self, obj):
        return BoolBadgeMixin.bool_badge(obj.is_expired, true_label="Expired", false_label="Valid")

    @admin.display(description="Status")
    def status_badge(self, obj):
        colour = "#6b7280"
        return format_html('<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;">{}</span>',
                           colour, "—")

@admin.register(GroupServiceAccess)
class GroupServiceAccessAdmin(StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("group_name", "service_code", "status_badge", "updated_at")
    list_filter = ("status", "updated_at", "created_at", "group")
    search_fields = ("group__name", "service__service_code", "service__service_name")
    autocomplete_fields = ("group", "service")
    ordering = ("group__name", "service__service_code")
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("group.name", "service.service_code", "service.service_name",
                     "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="Group")
    def group_name(self, obj):
        return obj.group.name

    @admin.display(description="Service")
    def service_code(self, obj):
        return obj.service.service_code

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("group", "service")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(RequestLog)
class RequestLogAdmin(CSVExportMixin, admin.ModelAdmin):
    list_display = ("timestamp", "user_display", "ip_address", "method", "path", "response_status")
    list_filter = ("method", "response_status", "timestamp")
    search_fields = ("user__email", "ip_address", "path", "user_agent", "query_string", "body")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    list_per_page = 50
    # Important for log integrity:
    readonly_fields = tuple(f.name for f in RequestLog._meta.fields)

    EXPORT_FIELDS = ("timestamp", "user.email", "ip_address", "method", "path", "response_status")

    @admin.display(description="User")
    def user_display(self, obj):
        return getattr(obj.user, "email", None) or "-"

admin.site.site_header = "OpenAgri GateKeeper Admin"
admin.site.site_title = "OpenAgri Admin"
admin.site.index_title = "Administration"
