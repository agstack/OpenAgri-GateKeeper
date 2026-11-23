from rest_framework.permissions import BasePermission


class IsPlatformSuperuser(BasePermission):
    """Allow access only to active GateKeeper platform superusers."""

    message = "Platform administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
            and getattr(user, "status", 1) == 1
        )
