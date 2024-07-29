from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView

from .views import LoginView, RegisterView, PasswordResetView

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path('admin/', admin.site.urls),

    # path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # path('api/farm_calendar/', FarmCalendarView.as_view(), name='farm_calendar'),
    # path('api/weather_data/', WeatherDataView.as_view(), name='weather_data'),

    # path('', LoginView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('reset_password/', PasswordResetView.as_view(), name='reset_password'),

    path('aegis/', include('aegis.urls', namespace='aegis')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
