# aegis/admin.py

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import UserAdmin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils import timezone

try:
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
except Exception:  # pragma: no cover - optional import for admin cleanup only
    OutstandingToken = None

from .models import (Tenant, DefaultAuthUserExtend, ServiceMaster, PermissionMaster, CustomPermissions, GroupCustomPermissions,
                     RegisteredService, BlacklistedAccess, BlacklistedRefresh, RequestLog, GroupServiceAccess,
                     ServiceScopeAssignment, FarmCalendarResourceCache, ServiceRole)
from .services.fc_catalog_sync import ensure_farmcalendar_catalog_fresh
from .services.entitlement_service import fc_service_queryset


class HiddenGroupAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)

    def get_model_perms(self, request):
        return {}


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

admin.site.register(Group, HiddenGroupAdmin)


class GKAdminAuthenticationForm(AdminAuthenticationForm):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={"autofocus": True}),
    )


class TenantCodeListFilter(admin.RelatedFieldListFilter):
    """
    Keep tenant changelist filters compact by showing the tenant code only.
    """

    def field_choices(self, field, request, model_admin):
        remote_model = field.remote_field.model
        ordering = self.field_admin_ordering(field, request, model_admin) or ("code",)
        return [
            (tenant.pk, tenant.code)
            for tenant in remote_model._default_manager.order_by(*ordering)
        ]


class ServiceScopeAssignmentAdminForm(forms.ModelForm):
    PERMISSION_ACTION_CHOICES = (
        ("view", "view"),
        ("add", "add"),
        ("edit", "edit"),
        ("delete", "delete"),
    )

    role_ref = forms.ModelChoiceField(
        queryset=ServiceRole.objects.filter(status=1).select_related("service").order_by("service__service_code", "role_name"),
        required=False,
        label="Role (preset)",
        help_text=(
            "RBAC path: pick a predefined Service Role. Its permissions are used. "
            "Leave blank if you want to assign permissions directly below."
        ),
    )
    permissions_direct = forms.MultipleChoiceField(
        choices=PERMISSION_ACTION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissions (direct)",
        help_text=(
            "OBAC path: tick the actions to grant directly. "
            "Only used when Role is left blank."
        ),
    )
    subject_user = forms.ModelChoiceField(
        queryset=DefaultAuthUserExtend.objects.filter(
            is_tenant_admin=False, is_superuser=False
        ).order_by("email"),
        required=True,
        label="Individual user",
        help_text="Select the user who should receive this grant in the selected tenant.",
    )
    scope_farms = forms.ModelMultipleChoiceField(
        queryset=FarmCalendarResourceCache.objects.filter(resource_type="farm", status=1).order_by("name", "resource_id"),
        required=False,
        label="Farms",
        widget=FilteredSelectMultiple("Farms", is_stacked=False),
        help_text="Pick one or more farms. One grant row will be created per farm.",
    )
    scope_parcels = forms.ModelMultipleChoiceField(
        queryset=FarmCalendarResourceCache.objects.filter(resource_type="parcel", status=1).order_by("name", "resource_id"),
        required=False,
        label="Parcels",
        widget=FilteredSelectMultiple("Parcels", is_stacked=False),
        help_text="Pick one or more parcels. One grant row will be created per parcel.",
    )

    class Meta:
        model = ServiceScopeAssignment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        self._request = request
        super().__init__(*args, **kwargs)
        self.fields["user"].widget = forms.HiddenInput()
        self.fields["scope_id"].widget = forms.HiddenInput()
        self.fields["actions"].widget = forms.HiddenInput()
        self.fields["role"].widget = forms.HiddenInput()
        self.fields["user"].required = False
        self.fields["actions"].required = False
        self.fields["role"].required = False
        self.fields["scope_type"].help_text = "Choose 'farm' or 'parcel'. Required for Farm Calendar."
        self.fields["scope_type"].required = False
        self.fields["scope_id"].required = False

        fc_services = fc_service_queryset(ServiceMaster.objects.filter(status=1))
        if request is not None and not request.user.is_superuser and getattr(request.user, "tenant_id", None):
            tenant_id = request.user.tenant_id
            self.fields["role_ref"].queryset = ServiceRole.objects.filter(
                status=1,
                tenant_id=tenant_id,
                service__in=fc_services,
            ).select_related("service", "tenant").order_by("service__service_code", "role_name")
            self.fields["subject_user"].queryset = DefaultAuthUserExtend.objects.filter(
                tenant_id=tenant_id,
                is_tenant_admin=False,
                is_superuser=False,
                status=1,
            ).order_by("email")
            self.fields["scope_farms"].queryset = FarmCalendarResourceCache.objects.filter(
                tenant_id=tenant_id, resource_type="farm", status=1,
            ).order_by("name", "resource_id")
            self.fields["scope_parcels"].queryset = FarmCalendarResourceCache.objects.filter(
                tenant_id=tenant_id, resource_type="parcel", status=1,
            ).order_by("name", "resource_id")
        else:
            self.fields["role_ref"].queryset = ServiceRole.objects.filter(
                status=1,
                service__in=fc_services,
            ).select_related("service", "tenant").order_by("tenant__code", "service__service_code", "role_name")

        self.fields["role_ref"].label_from_instance = lambda obj: (
            f"{obj.role_name} - {obj.service.service_code}"
            + (f" [{obj.tenant.code}]" if obj.tenant_id else "")
        )
        self.fields["scope_farms"].label_from_instance = lambda obj: f"{obj.name or '-'} - {obj.resource_id}"
        self.fields["scope_parcels"].label_from_instance = lambda obj: f"{obj.name or '-'} - {obj.resource_id}"

        if self.instance and self.instance.pk:
            if self.instance.user_id:
                self.fields["subject_user"].initial = self.instance.user
            if self.instance.role_ref_id:
                self.fields["role_ref"].initial = self.instance.role_ref
            elif isinstance(self.instance.actions, list) and self.instance.actions:
                # Only pre-fill direct permissions for OBAC rows (no role_ref).
                # RBAC rows also carry actions[] (copied from the role at save
                # time), but pre-filling both fields would trigger the XOR
                # validator on Save with no field changes.
                self.fields["permissions_direct"].initial = self.instance.actions
            if self.instance.scope_type == "farm":
                existing = FarmCalendarResourceCache.objects.filter(
                    resource_type="farm",
                    resource_id=self.instance.scope_id,
                ).first()
                if existing:
                    self.fields["scope_farms"].initial = [existing]
            elif self.instance.scope_type == "parcel":
                existing = FarmCalendarResourceCache.objects.filter(
                    resource_type="parcel",
                    resource_id=self.instance.scope_id,
                ).first()
                if existing:
                    self.fields["scope_parcels"].initial = [existing]

    def clean(self):
        cleaned_data = super().clean()
        subject_user = cleaned_data.get("subject_user")
        scope_type = cleaned_data.get("scope_type")
        scope_farms = list(cleaned_data.get("scope_farms") or [])
        scope_parcels = list(cleaned_data.get("scope_parcels") or [])
        role_ref = cleaned_data.get("role_ref")
        permissions_direct = list(cleaned_data.get("permissions_direct") or [])
        service = cleaned_data.get("service")
        tenant = cleaned_data.get("tenant")

        if not subject_user:
            raise forms.ValidationError("Select an individual user for this assignment.")
        if tenant and getattr(subject_user, "tenant_id", None) != tenant.id:
            raise forms.ValidationError(
                "Selected user does not belong to the selected tenant."
            )
        cleaned_data["user"] = subject_user
        cleaned_data["group"] = None

        # RBAC XOR OBAC — exactly one path must be chosen.
        if role_ref and permissions_direct:
            raise forms.ValidationError(
                "Choose either a Role OR direct Permissions, not both."
            )
        if not role_ref and not permissions_direct:
            raise forms.ValidationError(
                "Choose a Role OR tick at least one direct Permission."
            )

        if role_ref:
            if service and role_ref.service_id != service.id:
                raise forms.ValidationError(
                    "Selected role does not belong to the selected service."
                )
            cleaned_data["role"] = role_ref.role_code
            cleaned_data["actions"] = list(
                role_ref.permissions.filter(status=1).order_by("action").values_list("action", flat=True)
            )
        else:
            cleaned_data["role"] = ""
            cleaned_data["actions"] = sorted(set(permissions_direct))

        service_for_scope = service or getattr(role_ref, "service", None)
        is_fc = False
        if service_for_scope is not None:
            code = (service_for_scope.service_code or "").strip().lower()
            name = (service_for_scope.service_name or "").strip().lower()
            is_fc = code in {"fc", "farmcalendar"} or name in {"farmcalendar", "farm calendar"}

        if is_fc:
            if scope_type == "farm":
                if not scope_farms:
                    raise forms.ValidationError("Select at least one farm.")
                cleaned_data["_selected_scopes"] = scope_farms
                cleaned_data["scope_id"] = scope_farms[0].resource_id
            elif scope_type == "parcel":
                if not scope_parcels:
                    raise forms.ValidationError("Select at least one parcel.")
                cleaned_data["_selected_scopes"] = scope_parcels
                cleaned_data["scope_id"] = scope_parcels[0].resource_id
            else:
                raise forms.ValidationError(
                    "Farm Calendar grants require a scope (farm or parcel)."
                )
        else:
            cleaned_data["scope_type"] = None
            cleaned_data["scope_id"] = None
            cleaned_data["_selected_scopes"] = []

        return cleaned_data


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


class HideDeletedByDefaultMixin:
    """
    Hide soft-deleted rows from changelists unless the admin explicitly filters
    for a specific status.
    """
    deleted_status_value = "2"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get("status__exact") in {"0", "1", "2"}:
            return qs
        return qs.exclude(status=2)


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


class SuperuserOnlyAdminMixin:
    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_active and request.user.is_superuser)


class HiddenAdminMixin:
    def get_model_perms(self, request):
        return {}

    def has_module_permission(self, request):
        return False


class TenantScopedAdminMixin:
    tenant_field_name = "tenant"

    @staticmethod
    def _disable_related_widget_controls(form, *field_names):
        for field_name in field_names:
            if field_name not in getattr(form, "base_fields", {}):
                continue
            widget = form.base_fields[field_name].widget
            for attr_name in ("can_add_related", "can_change_related", "can_delete_related", "can_view_related"):
                if hasattr(widget, attr_name):
                    setattr(widget, attr_name, False)

    def _is_tenant_admin(self, request):
        return bool(
            request.user
            and request.user.is_active
            and getattr(request.user, "is_tenant_admin", False)
            and getattr(request.user, "tenant_id", None)
        )

    def _tenant_filter_kwargs(self, request):
        tenant_field = self.tenant_field_name
        return {f"{tenant_field}_id": request.user.tenant_id}

    def _filter_foreignkey_queryset(self, request, db_field, queryset):
        if request.user.is_superuser or queryset is None:
            return queryset

        model_name = db_field.remote_field.model._meta.model_name
        if model_name == "tenant":
            return queryset.filter(id=request.user.tenant_id)
        if hasattr(db_field.remote_field.model, "tenant_id"):
            return queryset.filter(tenant_id=request.user.tenant_id)
        return queryset

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if self._is_tenant_admin(request):
            return qs.filter(**self._tenant_filter_kwargs(request))
        return qs.none()

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and (request.user.is_superuser or self._is_tenant_admin(request)))

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self._is_tenant_admin(request):
            return False
        if obj is None:
            return True
        return getattr(obj, f"{self.tenant_field_name}_id", None) == request.user.tenant_id

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and (request.user.is_superuser or self._is_tenant_admin(request)))

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj=obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        queryset = kwargs.get("queryset")
        filtered = self._filter_foreignkey_queryset(request, db_field, queryset)
        if filtered is not None:
            kwargs["queryset"] = filtered
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            setattr(obj, self.tenant_field_name, request.user.tenant)
        super().save_model(request, obj, form, change)


@admin.register(Tenant)
class TenantAdmin(SuperuserOnlyAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("code", "slug", "name", "status_badge", "updated_at")
    list_filter = ("status", "updated_at", "created_at")
    search_fields = ("code", "slug", "name")
    ordering = ("code",)
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("code", "slug", "name", "status", "created_at", "updated_at", "deleted_at")

    @admin.action(description="Soft delete selected")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for obj in queryset.exclude(status=2):
            obj.soft_delete()
            updated += 1
        self.message_user(
            request,
            f"{updated} tenant record(s) soft-deleted and identifiers released.",
            level=messages.WARNING,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

@admin.register(DefaultAuthUserExtend)
class DefaultAuthUserExtendAdmin(TenantScopedAdminMixin, HideDeletedByDefaultMixin, UserAdmin, CSVExportMixin, StatusBadgeMixin, BoolBadgeMixin, SoftDeleteActions, ActivateDeactivateActions):
    """
        Polished user admin for DefaultAuthUserExtend (inherits BaseModel):
        - Status badge, soft-delete/restore, activate/deactivate
        - CSV export
        - Self-edit safety
        """
    list_display = (
        'email',
        'first_name',
        'last_name',
        'tenant_display',
        'platform_admin_display',
        'is_tenant_admin',
        'uuid',
        'status_badge',
        'date_joined',
        'last_login',
    )
    list_display_links = ('email',)
    search_fields = ('email', 'first_name', 'last_name', 'username', 'uuid')
    list_filter = ('status', ('tenant', TenantCodeListFilter), 'is_tenant_admin', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login')
    ordering = ('email',)
    date_hierarchy = 'date_joined'
    list_per_page = 50

    # System fields read-only; deleted_at set via soft delete action
    readonly_fields = ('deleted_at', 'created_at', 'updated_at')
    fieldsets = UserAdmin.fieldsets
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "tenant", "is_tenant_admin", "password1", "password2"),
            },
        ),
        (
            "Permissions",
            {
                "fields": ("is_active", "is_staff"),
            },
        ),
        (
            "Lifecycle",
            {"fields": ("status", "deleted_at", "created_at", "updated_at")}
        ),
    )

    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("email", "first_name", "last_name", "username",
                     "tenant.code", "is_tenant_admin",
                     "uuid", "status", "is_active", "is_staff", "is_superuser",
                     "date_joined", "last_login", "created_at", "updated_at", "deleted_at")

    def get_fieldsets(self, request, obj=None):
        base = super().get_fieldsets(request, obj)
        cleaned = []
        has_lifecycle = False
        is_add_form = obj is None
        for name, opts in base:
            opts = dict(opts)
            fields = opts.get('fields', ())
            if name == "Lifecycle":
                has_lifecycle = True
            if isinstance(fields, (list, tuple)):
                fields = tuple(
                    f for f in fields
                    if f not in {'user_permissions', 'groups'}
                    and (request.user.is_superuser or f != 'is_superuser')
                )
                if name == "Permissions" and not is_add_form:
                    fields = tuple(fields) + ("tenant", "is_tenant_admin")
                opts['fields'] = fields
            cleaned.append((name, opts))
        if not has_lifecycle:
            cleaned.append((
                "Lifecycle",
                {"fields": ("status", "deleted_at", "created_at", "updated_at")}
            ))
        return tuple(cleaned)

    @admin.display(description="Tenant")
    def tenant_display(self, obj):
        if not obj.tenant_id:
            return "-"
        return f"{obj.tenant.code}"

    @admin.display(description="Platform Admin", boolean=False)
    def platform_admin_display(self, obj):
        return self.bool_badge(bool(getattr(obj, "is_superuser", False)), true_label="Yes", false_label="No")

    def get_readonly_fields(self, request, obj=None):
        base = super().get_readonly_fields(request, obj)
        ro = set(base) | {"deleted_at", "created_at", "updated_at"}
        if obj is not None and obj == request.user:
            ro |= {"email", "username", "user_permissions"}
        return tuple(sorted(ro))

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        self._disable_related_widget_controls(form, "tenant")
        if "email" in form.base_fields:
            form.base_fields["email"].required = True
            form.base_fields["email"].help_text = "Required. Must be unique."
        if "tenant" in form.base_fields:
            if request.user.is_superuser:
                form.base_fields["tenant"].queryset = Tenant.objects.filter(status=1).order_by("code")
            else:
                form.base_fields["tenant"].queryset = Tenant.objects.filter(id=request.user.tenant_id, status=1)
                form.base_fields["tenant"].initial = request.user.tenant_id
                form.base_fields["tenant"].disabled = True
        if not request.user.is_superuser and "is_superuser" in form.base_fields:
            form.base_fields["is_superuser"].disabled = True
        if not request.user.is_superuser and "is_staff" in form.base_fields:
            form.base_fields["is_staff"].disabled = True
        return form

    def save_model(self, request, obj, form, change):
        obj.email = (obj.email or "").strip()
        if not obj.email:
            raise forms.ValidationError("Email is required.")
        if not request.user.is_superuser:
            obj.tenant = request.user.tenant
            obj.is_superuser = False
        super().save_model(request, obj, form, change)

    @admin.action(description="Soft delete selected")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for obj in queryset.exclude(status=2):
            obj.soft_delete()
            updated += 1
        self.message_user(
            request,
            f"{updated} user record(s) soft-deleted and login identifiers released.",
            level=messages.WARNING,
        )

    # Remove hard delete (nudge admins to soft-delete)
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    # Show all (including deleted); default manager already does that
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related()

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj == request.user and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj=obj)


@admin.register(ServiceMaster)
class ServiceMasterAdmin(SuperuserOnlyAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
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

    @admin.action(description="Soft delete selected")
    def soft_delete_selected(self, request, queryset):
        updated = 0
        for obj in queryset.exclude(status=2):
            obj.soft_delete()
            updated += 1
        self.message_user(
            request,
            f"{updated} service record(s) soft-deleted and identifiers released.",
            level=messages.WARNING,
        )

    # Remove hard delete
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(PermissionMaster)
class PermissionMasterAdmin(SuperuserOnlyAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("id", "service_code", "action", "status_badge", "updated_at")
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
class CustomPermissionsAdmin(TenantScopedAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    tenant_field_name = "user__tenant"
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

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self._is_tenant_admin(request):
            return False
        if obj is None:
            return True
        return getattr(obj.user, "tenant_id", None) == request.user.tenant_id

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and getattr(obj.user, "tenant_id", None) != request.user.tenant_id:
            raise forms.ValidationError("You can only manage custom permissions for users in your tenant.")
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(GroupCustomPermissions)
class GroupCustomPermissionsAdmin(HiddenAdminMixin, SuperuserOnlyAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
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
class RegisteredServiceAdmin(SuperuserOnlyAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
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

# Hidden from admin navigation on purpose. Keep model and runtime logic intact.
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


# Hidden from admin navigation on purpose. Keep model and runtime logic intact.
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
class GroupServiceAccessAdmin(HiddenAdminMixin, TenantScopedAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("tenant_display", "group_name", "service_code", "status_badge", "updated_at")
    list_filter = ("status", ("tenant", TenantCodeListFilter), "updated_at", "created_at", "group")
    search_fields = ("group__name", "service__service_code", "service__service_name")
    autocomplete_fields = ("group", "service")
    ordering = ("group__name", "service__service_code")
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = ("tenant.code", "group.name", "service.service_code", "service.service_name",
                     "status", "created_at", "updated_at", "deleted_at")

    @admin.display(description="Tenant")
    def tenant_display(self, obj):
        return obj.tenant.code if obj.tenant_id else "-"

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


@admin.register(ServiceRole)
class ServiceRoleAdmin(TenantScopedAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("tenant_display", "role_name", "role_code", "service_code", "permission_list", "status_badge", "updated_at")
    list_filter = ("status", ("tenant", TenantCodeListFilter), "service", "updated_at", "created_at")
    search_fields = ("role_name", "role_code", "tenant__code", "tenant__name", "service__service_code", "service__service_name", "description")
    autocomplete_fields = ()
    filter_horizontal = ("permissions",)
    ordering = ("tenant__code", "service__service_code", "role_name")
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = (
        "tenant.code", "service.service_code", "role_code", "role_name", "description",
        "status", "created_at", "updated_at", "deleted_at"
    )

    @admin.display(description="Tenant")
    def tenant_display(self, obj):
        return obj.tenant.code if obj.tenant_id else "-"

    @admin.display(description="Service")
    def service_code(self, obj):
        return obj.service.service_code

    @admin.display(description="Permissions")
    def permission_list(self, obj):
        return ", ".join(obj.permissions.filter(status=1).order_by("action").values_list("action", flat=True))

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("tenant", "service").prefetch_related("permissions")
        if request.user.is_superuser:
            return qs
        if getattr(request.user, "is_tenant_admin", False) and getattr(request.user, "tenant_id", None):
            return qs.filter(tenant_id=request.user.tenant_id)
        return qs.none()

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        self._disable_related_widget_controls(form, "tenant")
        if not request.user.is_superuser and "tenant" in form.base_fields:
            form.base_fields["tenant"].queryset = Tenant.objects.filter(id=request.user.tenant_id)
            form.base_fields["tenant"].initial = request.user.tenant_id
            form.base_fields["tenant"].disabled = True
        if "service" in form.base_fields:
            form.base_fields["service"].queryset = fc_service_queryset(
                ServiceMaster.objects.filter(status=1)
            ).order_by("service_code")
        if "permissions" in form.base_fields:
            form.base_fields["permissions"].queryset = PermissionMaster.objects.filter(
                status=1,
                service__in=fc_service_queryset(ServiceMaster.objects.filter(status=1)),
            ).select_related("service").order_by("service__service_code", "action")
        return form

    def get_autocomplete_fields(self, request):
        if request.user.is_superuser:
            return self.autocomplete_fields
        return ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        queryset = kwargs.get("queryset")
        if not request.user.is_superuser and db_field.name == "tenant":
            kwargs["queryset"] = Tenant.objects.filter(id=request.user.tenant_id)
        elif db_field.name == "service":
            kwargs["queryset"] = fc_service_queryset(
                ServiceMaster.objects.filter(status=1)
            ).order_by("service_code")
        elif queryset is not None:
            kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            kwargs["queryset"] = PermissionMaster.objects.filter(
                status=1,
                service__in=fc_service_queryset(ServiceMaster.objects.filter(status=1)),
            ).select_related("service").order_by("service__service_code", "action")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_active and (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)))

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_active and getattr(request.user, "is_tenant_admin", False) and getattr(request.user, "tenant_id", None)):
            return False
        if obj is None:
            return True
        return getattr(obj, "tenant_id", None) == request.user.tenant_id

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_active and (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)))

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj=obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(ServiceScopeAssignment)
class ServiceScopeAssignmentAdmin(TenantScopedAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    form = ServiceScopeAssignmentAdminForm
    list_display = ("tenant_display", "subject_display", "service_code", "role_display", "scope_type", "scope_display", "actions_display", "status_badge", "updated_at")
    list_filter = ("status", ("tenant", TenantCodeListFilter), "service", "scope_type", "role_ref", "updated_at", "created_at")
    search_fields = ("service__service_code", "service__service_name", "user__username", "user__email", "scope_id")
    autocomplete_fields = ()
    ordering = ("service__service_code", "scope_type", "scope_id")
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("deleted_at", "created_at", "updated_at")
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = (
        "tenant.code", "service.service_code", "user.username", "group.name", "role", "actions",
        "scope_type", "scope_id", "status", "created_at", "updated_at", "deleted_at"
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "status",
                    "tenant",
                    "service",
                    "subject_user",
                    "user",
                    "scope_type",
                    "scope_farms",
                    "scope_parcels",
                    "scope_id",
                )
            },
        ),
        (
            "Permissions",
            {
                "description": (
                    "Choose ONE of the following: either a preset Role "
                    "(RBAC) or tick permissions directly (OBAC)."
                ),
                "fields": (
                    "role_ref",
                    "permissions_direct",
                    "role",
                    "actions",
                ),
            },
        ),
        (
            "Lifecycle",
            {
                "fields": ("deleted_at", "created_at", "updated_at"),
            },
        ),
    )

    class Media:
        js = ("aegis/admin/service_scope_assignment.js",)

    @admin.display(description="Subject")
    def subject_display(self, obj):
        if obj.user_id:
            return obj.user.email or obj.user.username
        return "-"

    @admin.display(description="Tenant")
    def tenant_display(self, obj):
        return obj.tenant.code if obj.tenant_id else "-"

    @admin.display(description="Service")
    def service_code(self, obj):
        return obj.service.service_code

    @admin.display(description="Role")
    def role_display(self, obj):
        if obj.role_ref_id:
            return obj.role_ref.role_name
        return obj.role or "-"

    @admin.display(description="Actions")
    def actions_display(self, obj):
        if isinstance(obj.actions, list):
            return ", ".join(obj.actions)
        return "-"

    @admin.display(description="Scope")
    def scope_display(self, obj):
        cached_scope = FarmCalendarResourceCache.objects.filter(
            resource_type=obj.scope_type,
            resource_id=obj.scope_id,
        ).only("resource_id", "name", "farm_id").first()
        if cached_scope is None:
            return f"{obj.scope_type}:{obj.scope_id}"

        if obj.scope_type == "farm":
            return f"{cached_scope.name or '-'} [{cached_scope.resource_id}]"

        farm_name = (
            FarmCalendarResourceCache.objects.filter(
                resource_type="farm",
                resource_id=cached_scope.farm_id,
            ).values_list("name", flat=True).first()
            or "-"
        )
        parcel_name = cached_scope.name or str(cached_scope.resource_id)
        return f"{parcel_name} ({farm_name}) [{cached_scope.resource_id}]"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("service", "user", "role_ref")

    def get_form(self, request, obj=None, change=False, **kwargs):
        defaults = {"form": self.form}
        defaults.update(kwargs)
        form_class = super().get_form(request, obj, change=change, **defaults)
        admin_request = request

        class RequestAwareServiceScopeAssignmentForm(form_class):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs["request"] = admin_request
                super().__init__(*args, **inner_kwargs)

        form = RequestAwareServiceScopeAssignmentForm
        self._disable_related_widget_controls(form, "tenant")
        if request.user.is_superuser:
            if "service" in form.base_fields:
                form.base_fields["service"].queryset = fc_service_queryset(
                    ServiceMaster.objects.filter(status=1)
                ).order_by("service_code")
            return form
        if "service" in form.base_fields:
            form.base_fields["service"].queryset = fc_service_queryset(
                ServiceMaster.objects.filter(status=1)
            ).order_by("service_code")
        if "tenant" in form.base_fields:
            form.base_fields["tenant"].queryset = Tenant.objects.filter(id=request.user.tenant_id)
            form.base_fields["tenant"].initial = request.user.tenant_id
            form.base_fields["tenant"].disabled = True
        if "subject_user" in form.base_fields:
            form.base_fields["subject_user"].queryset = DefaultAuthUserExtend.objects.filter(
                tenant_id=request.user.tenant_id,
                is_tenant_admin=False,
            ).order_by("email")
        if "role_ref" in form.base_fields:
            form.base_fields["role_ref"].queryset = ServiceRole.objects.filter(
                status=1,
                tenant_id=request.user.tenant_id,
                service__in=fc_service_queryset(ServiceMaster.objects.filter(status=1)),
            ).select_related("service", "tenant").order_by("service__service_code", "role_name")
        if "scope_farms" in form.base_fields:
            form.base_fields["scope_farms"].queryset = FarmCalendarResourceCache.objects.filter(
                tenant_id=request.user.tenant_id,
                resource_type="farm",
                status=1,
            ).order_by("name", "resource_id")
        if "scope_parcels" in form.base_fields:
            form.base_fields["scope_parcels"].queryset = FarmCalendarResourceCache.objects.filter(
                tenant_id=request.user.tenant_id,
                resource_type="parcel",
                status=1,
            ).order_by("name", "resource_id")
        if "subject_user" in form.base_fields:
            form.base_fields["subject_user"].queryset = DefaultAuthUserExtend.objects.filter(
                tenant_id=request.user.tenant_id,
                is_tenant_admin=False,
                is_superuser=False,
                status=1,
            ).order_by("email")
        return form

    def get_autocomplete_fields(self, request):
        if request.user.is_superuser:
            return self.autocomplete_fields
        return ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service":
            kwargs["queryset"] = fc_service_queryset(
                ServiceMaster.objects.filter(status=1)
            ).order_by("service_code")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.tenant = request.user.tenant
            if obj.user_id and getattr(obj.user, "tenant_id", None) != request.user.tenant_id:
                raise forms.ValidationError("You can only assign roles to users in your tenant.")

        if change:
            super().save_model(request, obj, form, change)
            return

        selected_scopes = list(form.cleaned_data.get("_selected_scopes") or [])
        scope_type = form.cleaned_data.get("scope_type")
        if not selected_scopes:
            super().save_model(request, obj, form, change)
            return

        first = selected_scopes[0]
        obj.scope_type = scope_type
        obj.scope_id = first.resource_id
        obj.save()

        for extra in selected_scopes[1:]:
            ServiceScopeAssignment.objects.create(
                tenant=obj.tenant,
                service=obj.service,
                user=obj.user,
                role_ref=obj.role_ref,
                role=obj.role,
                actions=obj.actions,
                scope_type=scope_type,
                scope_id=extra.resource_id,
                status=obj.status,
            )
        if len(selected_scopes) > 1:
            self.message_user(
                request,
                f"Created {len(selected_scopes)} grant rows ({scope_type} × user).",
                level=messages.SUCCESS,
            )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(FarmCalendarResourceCache)
class FarmCalendarResourceCacheAdmin(TenantScopedAdminMixin, HideDeletedByDefaultMixin, StatusBadgeMixin, SoftDeleteActions, ActivateDeactivateActions, CSVExportMixin, admin.ModelAdmin):
    list_display = ("tenant_display", "resource_type", "resource_display", "parent_farm_display", "status_badge", "synced_at")
    list_filter = ("status", ("tenant", TenantCodeListFilter), "resource_type", "synced_at")
    search_fields = ("resource_id", "name", "farm_id")
    ordering = ("resource_type", "name", "resource_id")
    list_per_page = 100
    date_hierarchy = "synced_at"
    readonly_fields = (
        "status", "resource_type", "resource_id", "name", "farm_id", "payload",
        "synced_at", "created_at", "updated_at", "deleted_at",
    )
    actions = ("mark_active", "mark_inactive", "soft_delete_selected", "restore_selected", "export_as_csv")
    EXPORT_FIELDS = (
        "tenant.code", "resource_type", "resource_id", "name", "farm_id", "status",
        "synced_at", "created_at", "updated_at", "deleted_at"
    )

    @admin.display(description="Tenant")
    def tenant_display(self, obj):
        return obj.tenant.code if obj.tenant_id else "-"

    @admin.display(description="Resource")
    def resource_display(self, obj):
        label = obj.name or "-"
        return f"{label} [{obj.resource_id}]"

    @admin.display(description="Parent Farm")
    def parent_farm_display(self, obj):
        if obj.resource_type == "farm":
            return obj.name or "-"
        if not obj.farm_id:
            return "-"
        farm_name = FarmCalendarResourceCache.objects.filter(
            resource_type="farm",
            resource_id=obj.farm_id,
        ).values_list("name", flat=True).first()
        return f"{farm_name or '-'} [{obj.farm_id}]"

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def changelist_view(self, request, extra_context=None):
        try:
            refresh = ensure_farmcalendar_catalog_fresh(ttl_seconds=3600, timeout=10)
            if refresh["synced"]:
                result = refresh["result"] or {}
                self.message_user(
                    request,
                    "FarmCalendar catalog refreshed from FC: "
                    f"farms={result.get('farms', 0)} "
                    f"parcels={result.get('parcels', 0)} "
                    f"deactivated_scope_assignments={result.get('deactivated_scope_assignments', 0)}",
                    level=messages.INFO,
                )
        except Exception as exc:
            self.message_user(
                request,
                f"FarmCalendar catalog auto-refresh failed: {exc}",
                level=messages.WARNING,
            )
        return super().changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")


# Hidden from admin navigation on purpose. Keep model and runtime logic intact.
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

# Hide low-signal or legacy models from the admin menu while preserving
# the underlying runtime functionality.
for model in (CustomPermissions, BlacklistedRefresh, BlacklistedAccess, RequestLog, OutstandingToken):
    if model is None:
        continue
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass

admin.site.site_header = "OpenAgri GateKeeper Admin"
admin.site.site_title = "OpenAgri Admin"
admin.site.index_title = "Administration"
admin.site.login_form = GKAdminAuthenticationForm
