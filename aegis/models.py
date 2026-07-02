# aegis/models.py

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from simple_history.models import HistoricalRecords


class ActivePageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=1)


class BaseModel(models.Model):
    STATUS_CHOICES = [
        (1, 'Active'),
        (0, 'Inactive'),
        (2, 'Deleted'),
    ]

    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name='Status')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Deleted At')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    objects = models.Manager()  # Default manager.
    active_objects = ActivePageManager()  # Custom manager for active objects.

    class Meta:
        abstract = True

    def soft_delete(self):
        self.status = 2
        self.deleted_at = timezone.now()
        self.save()


class Tenant(BaseModel):
    """
    Shared-deployment tenant boundary.
    One SIP organisation maps to one tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'tenant'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ('code',)

    def __str__(self):
        return f"{self.code} - {self.name}"

    def soft_delete(self):
        if self.status == 2 and str(self.code).startswith("deleted__"):
            return
        prefix = f"deleted__{self.id.hex[:12]}__"
        code_budget = max(1, 32 - len(prefix))
        slug_budget = max(1, 64 - len(prefix))
        name_budget = max(1, 255 - len(prefix))
        self.code = f"{prefix}{(self.code or '')[:code_budget]}"
        self.slug = f"{prefix}{(self.slug or '')[:slug_budget]}"
        self.name = f"{prefix}{(self.name or '')[:name_budget]}"
        self.status = 2
        self.deleted_at = timezone.now()
        self.save()


class RequestLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField()
    path = models.CharField(max_length=200)
    query_string = models.TextField()
    body = models.TextField()
    method = models.CharField(max_length=10)
    response_status = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_log'
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'


class DefaultAuthUserExtend(AbstractUser, BaseModel):
    SERVICE_NAME_CHOICES = [
        ('farm_calendar', 'Farm Calendar'),
        ('gatekeeper', 'Gatekeeper'),
        ('weather_data', 'Weather Data'),
        ('unknown', 'Unknown'),
    ]

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    # service_name = models.CharField(max_length=50, default='unknown', choices=SERVICE_NAME_CHOICES,)
    contact_no = models.CharField(max_length=10, null=True, db_index=True, default='', blank=True,
                                  validators=[RegexValidator(regex=r'^[0-9- ]+$', message="Invalid phone number")])
    token_version = models.IntegerField(default=1)
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    is_tenant_admin = models.BooleanField(default=False)

    history = HistoricalRecords(table_name="auth_user_extend_history")

    class Meta:
        db_table = 'auth_user_extend'
        verbose_name = 'User Master'
        verbose_name_plural = 'User Masters'

    def __str__(self):
        return f"{self.email} {self.first_name}"

    def _released_username(self):
        return f"deleted__{self.uuid.hex[:12]}__{self.username}"[:150]

    def _released_email(self):
        local, _, domain = (self.email or "").partition("@")
        domain = domain or "deleted.local"
        suffix = f"deleted+{self.uuid.hex[:12]}__"
        local_budget = max(1, 254 - len(domain) - 1 - len(suffix))
        local = (local or "user")[:local_budget]
        return f"{suffix}{local}@{domain}"

    def soft_delete(self):
        if (
            self.status == 2
            and str(self.username).startswith("deleted__")
            and str(self.email).startswith("deleted+")
        ):
            return
        self.username = self._released_username()
        self.email = self._released_email()
        self.is_active = False
        self.is_staff = False
        self.is_tenant_admin = False
        self.status = 2
        self.deleted_at = timezone.now()
        self.save()


class RegisteredService(BaseModel):
    id = models.AutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
                          blank=False, null=False, verbose_name='ID')
    base_url = models.CharField(max_length=255, default="http://127.0.0.1:8001", blank=False, null=False)
    service_name = models.CharField(max_length=100)
    endpoint = models.CharField(max_length=255)
    methods = models.JSONField()
    params = models.TextField(max_length=100, blank=True, null=True, help_text="Query parameter templates (e.g., 'lat={}&lon={}').")
    comments = models.TextField(blank=True, null=True)
    service_url = models.CharField(max_length=500, blank=True, null=True)

    history = HistoricalRecords(table_name="registered_services_history")

    class Meta:
        db_table = 'registered_services'
        verbose_name = 'Registered Service'
        verbose_name_plural = 'Registered Services'

    def __str__(self):
        return self.service_name


# class AdminMenuMaster(BaseModel):
#     id = models.SmallAutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
#                                blank=False, null=False, verbose_name='ID')
#     parent_id = models.ForeignKey('self', null=True, blank=True, related_name='submenus', db_column='parent_id',
#                                   on_delete=models.CASCADE)
#     menu_name = models.CharField(max_length=30, null=False, blank=False, unique=True,
#                                  validators=[RegexValidator(regex=r'^[a-zA-Z0-9()\s]+$', message="Invalid characters")])
#     menu_icon = models.CharField(max_length=20, null=True, blank=True, default='list',
#                                  validators=[RegexValidator(regex=r'^[a-z0-9-]+$', message="Invalid characters")])
#     menu_route = models.CharField(max_length=30, null=True, blank=True,
#                                   validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s-]+$', message="Invalid characters")])
#     menu_access = models.CharField(max_length=30, null=True, blank=True,
#                                    validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s-]+$', message="Invalid characters")])
#     menu_order = models.SmallIntegerField(null=True, blank=True,
#                                           validators=[RegexValidator(regex=r'^[0-9]+$', message="Invalid characters")])
#
#     history = HistoricalRecords(table_name="admin_menu_master_history")
#
#     class Meta:
#         db_table = "admin_menu_master"
#         verbose_name = "Admin Menu"
#         verbose_name_plural = "Admin Menus"
#
#     def __str__(self):
#         return f"{self.menu_name} ({self.menu_route})"


class PermissionMaster(BaseModel):
    ACTION_CHOICES = (
        ('add', 'add'),
        ('edit', 'edit'),
        ('view', 'view'),
        ('delete', 'delete'),
    )
    id = models.AutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
                          blank=False, null=False, verbose_name='ID')

    service = models.ForeignKey('ServiceMaster', on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    is_virtual = models.BooleanField(default=False)

    class Meta:
        db_table = "permission_master"
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        unique_together = ('service', 'action')

    def __str__(self):
        return f"{self.service.service_code}_{self.action}"


class CustomPermissions(BaseModel):
    id = models.AutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
                             blank=False, null=False, verbose_name='ID')

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    permission_name = models.ForeignKey(PermissionMaster, on_delete=models.CASCADE)

    class Meta:
        db_table = "custom_permissions"
        verbose_name = "Custom Permission"
        verbose_name_plural = "Custom Permissions"
        unique_together = ('user', 'permission_name')

    def __str__(self):
        return str(self.permission_name)


class GroupCustomPermissions(BaseModel):
    id = models.AutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
                          blank=False, null=False, verbose_name='ID')

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    permission_names = models.ManyToManyField(PermissionMaster)

    class Meta:
        db_table = "custom_group_permissions"
        verbose_name = "Group Custom Permission"
        verbose_name_plural = "Group Custom Permissions"

    def __str__(self):
        return f"{self.group} {str(self.permission_names)}"


class BlacklistedRefresh(BaseModel):
    """
    A refresh token that has been 'logged out'.
    Any access token minted from this refresh will carry rjti=<this JTI>
    and must be rejected by authentication.
    """
    id = models.AutoField(
        primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
        blank=False, null=False, verbose_name='ID'
    )
    # SimpleJWT uses a UUID for JTI; 64 keeps headroom
    rjti = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name='Refresh JTI'
    )
    expires_at = models.DateTimeField(verbose_name='Expires At')       # when the refresh naturally expires
    blacklisted_at = models.DateTimeField(auto_now_add=True, verbose_name='Blacklisted At')

    class Meta:
        db_table = 'blacklisted_refresh_tokens'
        verbose_name = 'Blacklisted Refresh Token'
        verbose_name_plural = 'Blacklisted Refresh Tokens'
        indexes = [
            models.Index(fields=['expires_at'], name='blref_exp_idx'),
        ]

    def __str__(self):
        return f"{self.rjti}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class BlacklistedAccess(BaseModel):
    """
    A specific access token that should be rejected immediately.
    """
    id = models.AutoField(
        primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
        blank=False, null=False, verbose_name='ID'
    )
    jti = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name='Access JTI'
    )
    expires_at = models.DateTimeField(verbose_name='Expires At')
    blacklisted_at = models.DateTimeField(auto_now_add=True, verbose_name='Blacklisted At')

    class Meta:
        db_table = 'blacklisted_access_tokens'
        verbose_name = 'Blacklisted Access Token'
        verbose_name_plural = 'Blacklisted Access Tokens'
        indexes = [
            models.Index(fields=['expires_at'], name='blacc_exp_idx'),
        ]

    def __str__(self):
        return f"{self.jti}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class ServiceMaster(BaseModel):
    """
    Normalised list of services (one row per service).
    """
    service_code = models.CharField(max_length=50, unique=True)
    service_name = models.CharField(max_length=100, unique=True)
    service_description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'service_master'
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ('service_code',)

    def __str__(self):
        return f"{self.service_name} ({self.service_code})"

    def soft_delete(self):
        if self.status == 2 and str(self.service_code).startswith("deleted__"):
            return
        code_prefix = f"deleted__{self.pk}__"
        name_prefix = f"deleted__{self.pk}__"
        code_budget = max(1, 50 - len(code_prefix))
        name_budget = max(1, 100 - len(name_prefix))
        self.service_code = f"{code_prefix}{(self.service_code or '')[:code_budget]}"
        self.service_name = f"{name_prefix}{(self.service_name or '')[:name_budget]}"
        self.status = 2
        self.deleted_at = timezone.now()
        self.save()


class GroupServiceAccess(BaseModel):
    """
    One row means: this Group can access this Service.
    Keep it minimal (no per-action scopes for now).
    """
    tenant = models.ForeignKey('Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='group_service_links')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="service_links")
    service = models.ForeignKey(ServiceMaster, on_delete=models.CASCADE, related_name="group_links")

    class Meta:
        db_table = "group_service_access"
        unique_together = (("group", "service"),)
        verbose_name = "Group Service Access"
        verbose_name_plural = "Group Services Access"

    def __str__(self):
        return f"{self.group.name} → {self.service.service_code}"


class ServiceRole(BaseModel):
    """
    DB-backed role definition for a service.
    A role maps to a set of service permissions/actions.
    """
    tenant = models.ForeignKey(
        'Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_roles'
    )
    service = models.ForeignKey(ServiceMaster, on_delete=models.CASCADE, related_name="roles")
    role_code = models.CharField(max_length=50)
    role_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(PermissionMaster, blank=True, related_name="service_roles")

    class Meta:
        db_table = "service_role"
        verbose_name = "Service Role"
        verbose_name_plural = "Service Roles"
        unique_together = (("tenant", "service", "role_code"), ("tenant", "service", "role_name"))
        ordering = ("tenant__code", "service__service_code", "role_name")

    def __str__(self):
        tenant_code = self.tenant.code if self.tenant_id else "global"
        return f"{self.role_name} ({tenant_code}/{self.service.service_code})"


class ServiceScopeAssignment(BaseModel):
    """
    Scoped service permissions for either a user or a group.
    Scope IDs are external resource IDs (e.g. FC farm/parcel UUIDs).
    """
    SCOPE_TYPE_CHOICES = (
        ("farm", "farm"),
        ("parcel", "parcel"),
    )

    id = models.AutoField(
        primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
        blank=False, null=False, verbose_name='ID'
    )
    tenant = models.ForeignKey(
        'Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_scope_assignments'
    )
    service = models.ForeignKey(
        ServiceMaster, on_delete=models.CASCADE, related_name="scope_assignments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="service_scope_assignments"
    )
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, null=True, blank=True,
        related_name="service_scope_assignments"
    )
    role_ref = models.ForeignKey(
        "ServiceRole", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scope_assignments"
    )
    role = models.CharField(max_length=50, default="viewer")
    actions = models.JSONField(default=list, blank=True)
    scope_type = models.CharField(max_length=20, choices=SCOPE_TYPE_CHOICES, blank=True, null=True)
    scope_id = models.UUIDField(db_index=True, blank=True, null=True)

    class Meta:
        db_table = "service_scope_assignments"
        verbose_name = "Role Grant"
        verbose_name_plural = "Role Grants"
        indexes = [
            models.Index(fields=["tenant", "status"], name="ssa_tenant_status_idx"),
            models.Index(fields=["scope_type", "scope_id"], name="ssa_scope_idx"),
            models.Index(fields=["service", "status"], name="ssa_service_status_idx"),
            models.Index(fields=["user", "status"], name="ssa_user_status_idx"),
            models.Index(fields=["group", "status"], name="ssa_group_status_idx"),
        ]
        constraints = [
            # Exactly one subject must be provided: user XOR group.
            models.CheckConstraint(
                condition=(
                    (Q(user__isnull=False) & Q(group__isnull=True))
                    | (Q(user__isnull=True) & Q(group__isnull=False))
                ),
                name="ssa_exactly_one_subject",
            ),
        ]

    def __str__(self):
        subject = self.user.username if self.user_id else (self.group.name if self.group_id else "unknown")
        return f"{self.service.service_code}:{self.role}:{self.scope_type}:{self.scope_id} -> {subject}"


class FarmCalendarResourceCache(BaseModel):
    """
    Local cache of FarmCalendar resources used by GK assignment UIs.
    """
    RESOURCE_TYPE_CHOICES = (
        ("farm", "farm"),
        ("parcel", "parcel"),
    )

    id = models.AutoField(
        primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
        blank=False, null=False, verbose_name='ID'
    )
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES, db_index=True)
    resource_id = models.UUIDField(db_index=True)
    tenant = models.ForeignKey(
        'Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fc_resources'
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    farm_id = models.UUIDField(blank=True, null=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = "farmcalendar_resource_cache"
        verbose_name = "FarmCalendar Resource Cache"
        verbose_name_plural = "FarmCalendar Resource Cache"
        unique_together = (("resource_type", "resource_id"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="fcrc_tenant_status_idx"),
            models.Index(fields=["resource_type", "status"], name="fcrc_type_status_idx"),
            models.Index(fields=["farm_id", "status"], name="fcrc_farm_status_idx"),
            models.Index(fields=["synced_at"], name="fcrc_synced_idx"),
        ]

    def __str__(self):
        return f"{self.resource_type}:{self.resource_id}"
