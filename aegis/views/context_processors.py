from aegis.models import AdminMenuMaster
from django.conf import settings


def greeting():
    context_data = {
        'greeting': 'Hello, world!',
    }
    return context_data


def get_admin_menu():
    admin_menu = AdminMenuMaster.objects.filter(status=1, deleted=0).order_by('menu_order')

    context_data = {
        'admin_menu': admin_menu
    }
    return context_data


def session_cookie_age(request):
    return {'session_cookie_age': settings.SESSION_COOKIE_AGE}
