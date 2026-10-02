# gatekeeper/urls.py

from django.contrib import admin
from django.contrib.auth import logout
from django.db import connection
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.urls import path, include, re_path

from rest_framework_simplejwt.views import TokenRefreshView

from aegis.views import LoginView, RegisterView, WhoAmIView
from aegis.views.home_view import HomeView
from aegis.views.api.auth_views import (
    LoginAPIView, LogoutAPIView, RegisterAPIView, TokenValidationAPIView, MeAPIView, FarmCalendarScopeAPIView,
    FarmCalendarCatalogAPIView
)
from aegis.views.api.service_registry_views import (ServiceDirectoryAPIView, RegisterServiceAPIView,
                                                    DeleteServiceAPIView, NewReverseProxyAPIView)
from .common import custom_page_not_found_view

def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")

def health_check(request):
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ready"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def admin_logout_redirect(request):
    logout(request)
    return HttpResponseRedirect("/admin/login/?next=/admin/")

urlpatterns = [
    # path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    path('', HomeView.as_view(), name='home'),

    path('admin/logout/', admin_logout_redirect, name='admin_logout_redirect'),
    path('admin/', admin.site.urls),

    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),

    path('api/me/', MeAPIView.as_view(), name='api_me'),
    path('api/farmcalendar-scopes/', FarmCalendarScopeAPIView.as_view(), name='api_farmcalendar_scopes'),
    path('api/farmcalendar-catalog/', FarmCalendarCatalogAPIView.as_view(), name='api_farmcalendar_catalog'),
    path('api/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/logout/', LogoutAPIView.as_view(), name='api_logout'),
    path('api/register/', RegisterAPIView.as_view(), name='api_register'),
    path('api/validate_token/', TokenValidationAPIView.as_view(), name='validate_token'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/register_service/', RegisterServiceAPIView.as_view(), name='register_service'),
    path('api/service_directory/', ServiceDirectoryAPIView.as_view(), name='service_directory'),
    path('api/delete_service/', DeleteServiceAPIView.as_view(), name='delete_service'),

    re_path(r'^api/proxy/(?P<path>.*)$', NewReverseProxyAPIView.as_view(), name='new_reverse_proxy'),

    path('aegis/', include('aegis.urls', namespace='aegis')),

    path("healthz", health_check, name="health_check"),
    path("robots.txt", robots_txt),

    path("api/whoami/", WhoAmIView.as_view(), name="whoami"),
]

handler404 = custom_page_not_found_view
