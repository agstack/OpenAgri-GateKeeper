from django import template
from aegis.models import CustomPermissions, GroupCustomPermissions, PermissionMaster, AdminMenuMaster

register = template.Library()


@register.simple_tag
def has_view_permission(user, menu_route):
    if user.is_superuser or user.is_staff:
        return True

    if menu_route is None:
        return False  # Handle NULL menu_route values as you see fit

    try:
        # Get the AdminMenuMaster instance for the relevant menu
        menus = AdminMenuMaster.objects.filter(menu_route=menu_route)
        # menu = AdminMenuMaster.objects.get(menu_route=menu_route)

        if menus.exists():
            menu = menus.first()
        else:
            return False
        # Get the PermissionMaster instance for 'view' action
        permission_master = PermissionMaster.objects.get(menu=menu, action='view')
    except (AdminMenuMaster.DoesNotExist, PermissionMaster.DoesNotExist):
        return False

    # Check if the user has the permission
    has_permission = CustomPermissions.objects.filter(
        user=user, permission_name=permission_master
    ).exists()

    has_group_permission = GroupCustomPermissions.objects.filter(
        group__in=user.groups.all(), permission_names__in=[permission_master]
    ).exists()

    return has_permission or has_group_permission
