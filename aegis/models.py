import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, AbstractUser
from django.core.validators import RegexValidator
from django.db import models
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

    history = HistoricalRecords(table_name="auth_user_extend_history")

    class Meta:
        db_table = 'auth_user_extend'
        verbose_name = 'User Master'
        verbose_name_plural = 'User Masters'

    def __str__(self):
        return f"{self.email} {self.first_name}"


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


class AdminMenuMaster(BaseModel):
    id = models.SmallAutoField(primary_key=True, db_column='id', db_index=True, editable=False, unique=True,
                               blank=False, null=False, verbose_name='ID')
    parent_id = models.ForeignKey('self', null=True, blank=True, related_name='submenus', db_column='parent_id',
                                  on_delete=models.CASCADE)
    menu_name = models.CharField(max_length=30, null=False, blank=False, unique=True,
                                 validators=[RegexValidator(regex=r'^[a-zA-Z0-9()\s]+$', message="Invalid characters")])
    menu_icon = models.CharField(max_length=20, null=True, blank=True, default='list',
                                 validators=[RegexValidator(regex=r'^[a-z0-9-]+$', message="Invalid characters")])
    menu_route = models.CharField(max_length=30, null=True, blank=True,
                                  validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s-]+$', message="Invalid characters")])
    menu_access = models.CharField(max_length=30, null=True, blank=True,
                                   validators=[RegexValidator(regex=r'^[a-zA-Z0-9\s-]+$', message="Invalid characters")])
    menu_order = models.SmallIntegerField(null=True, blank=True,
                                          validators=[RegexValidator(regex=r'^[0-9]+$', message="Invalid characters")])

    history = HistoricalRecords(table_name="admin_menu_master_history")

    class Meta:
        db_table = "admin_menu_master"
        verbose_name = "Admin Menu"
        verbose_name_plural = "Admin Menus"

    def __str__(self):
        return f"{self.menu_name} ({self.menu_route})"


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
        # unique_together = ('service', 'action')

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


class GroupServiceAccess(BaseModel):
    """
    One row means: this Group can access this Service.
    Keep it minimal (no per-action scopes for now).
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="service_links")
    service = models.ForeignKey(ServiceMaster, on_delete=models.CASCADE, related_name="group_links")

    class Meta:
        db_table = "group_service_access"
        unique_together = (("group", "service"),)
        verbose_name = "Group Service Access"
        verbose_name_plural = "Group Services Access"

    def __str__(self):
        return f"{self.group.name} → {self.service.service_code}"

