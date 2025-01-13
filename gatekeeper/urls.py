from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from aegis.views.home_view import HomeView
from aegis.views.auth_views import LoginView, RegisterView
from aegis.views.api.auth_views import LoginAPIView, LogoutAPIView, RegisterAPIView, TokenValidationAPIView
from aegis.views.api.service_registry_views import (ServiceDirectoryAPIView, RegisterServiceAPIView,
                                                    DeleteServiceAPIView, NewReverseProxyAPIView)
from .views import GatewayAPIView
from .common import custom_page_not_found_view


schema_view = get_schema_view(
    openapi.Info(
        title="GateKeeper API",
        default_version='v1',
        description="Test description",
        # terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="p.bapat@maastrichtuniversity.nl"),
        license=openapi.License(name="EUPLv1.2 License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    # Swagger UI
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    path('', HomeView.as_view(), name='home'),

    path('admin/', admin.site.urls),

    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),

    path('api/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/logout/', LogoutAPIView.as_view(), name='api_logout'),
    path('api/register/', RegisterAPIView.as_view(), name='api_register'),
    path('api/validate_token/', TokenValidationAPIView.as_view(), name='validate_token'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/register_service/', RegisterServiceAPIView.as_view(), name='register_service'),
    path('api/service_directory/', ServiceDirectoryAPIView.as_view(), name='service_directory'),
    path('api/delete_service/', DeleteServiceAPIView.as_view(), name='delete_service'),

    re_path(r'^api/proxy/(?P<path>.*)$', NewReverseProxyAPIView.as_view(), name='new_reverse_proxy'),
    # re_path(r'^api/proxy/(?P<service_name>[^/]+)/(?P<path>.*)$', NewReverseProxyAPIView.as_view(), name='new_reverse_proxy'),

    path('aegis/', include('aegis.urls', namespace='aegis')),

    # path('api/test_gateway/', GatewayAPIView.as_view(), name='test_gateway'),

    # Catch-all route for GatewayAPIView
    # re_path(r"^api/(?P<path>.*)$", GatewayAPIView.as_view(), name="gateway")
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = custom_page_not_found_view
