from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DefaultAuthUserExtend


@admin.register(DefaultAuthUserExtend)
class DefaultAuthUserExtendAdmin(UserAdmin):
    # Specify the fields to be displayed in the user list view within the admin panel.
    list_display = ('email', 'first_name', 'last_name', 'uuid', 'is_active', 'date_joined', 'last_login')

    # Specify fields that should have a searchable multiple selection interface in the admin form.
    filter_horizontal = ('user_permissions', 'groups')

    # Customize the form fields displayed when viewing or editing a user, adding a new 'Assign projects' section.
    fieldsets = UserAdmin.fieldsets + (
        ('Assign projects', {
            'fields': ('projects',),
            'description': 'Optional: Assign project(s) to the user.',
        }),
    )

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

