from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.urls import path, include, re_path

from rest_framework_simplejwt.views import TokenRefreshView

from aegis.views.home_view import HomeView
from aegis.views.auth_views import LoginView#, RegisterView
from aegis.views.api.auth_views import LoginAPIView, LogoutAPIView, TokenValidationAPIView#, RegisterAPIView
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

urlpatterns = [
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    path('', HomeView.as_view(), name='home'),

    path('admin/', admin.site.urls),

    path('login/', LoginView.as_view(), name='login'),
    # path('register/', RegisterView.as_view(), name='register'),

    path('api/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/logout/', LogoutAPIView.as_view(), name='api_logout'),
    # path('api/register/', RegisterAPIView.as_view(), name='api_register'),
    path('api/validate_token/', TokenValidationAPIView.as_view(), name='validate_token'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/register_service/', RegisterServiceAPIView.as_view(), name='register_service'),
    path('api/service_directory/', ServiceDirectoryAPIView.as_view(), name='service_directory'),
    path('api/delete_service/', DeleteServiceAPIView.as_view(), name='delete_service'),

    re_path(r'^api/proxy/(?P<path>.*)$', NewReverseProxyAPIView.as_view(), name='new_reverse_proxy'),
    # re_path(r'^api/proxy/(?P<service_name>[^/]+)/(?P<path>.*)$', NewReverseProxyAPIView.as_view(), name='new_reverse_proxy'),

    path('aegis/', include('aegis.urls', namespace='aegis')),

    path("healthz", health_check, name="health_check"),
    path("robots.txt", robots_txt),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = custom_page_not_found_view
