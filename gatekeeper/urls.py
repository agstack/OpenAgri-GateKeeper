from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView

from rest_framework import permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from .views import LoginView, RegisterView, PasswordResetView
from aegis.views.api import FarmCalendarView, WeatherDataView

from .views import LoginView, RegisterView, PasswordResetView, reverse_proxy

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


    path('admin/', admin.site.urls),

    # path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/farm_calendar/', FarmCalendarView.as_view(), name='farm_calendar'),
    path('api/weather_data/', WeatherDataView.as_view(), name='weather_data'),

    # path('', LoginView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('reset_password/', PasswordResetView.as_view(), name='reset_password'),

    path('aegis/', include('aegis.urls', namespace='aegis')),
]

# reverse proxy urls
urlpatterns += [
    re_path(r'^api/resources/(?P<path>.*)$', reverse_proxy, name='reverse_proxy'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
