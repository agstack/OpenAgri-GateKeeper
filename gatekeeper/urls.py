from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from aegis.views.api import *


urlpatterns = [
    path('admin/', admin.site.urls),

    # path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # path("aegis/", include("aegis.urls")),

    # path('api/farm_calendar/', FarmCalendarView.as_view(), name='farm_calendar'),
    path('api/weather_data/', WeatherDataView.as_view(), name='weather_data'),

    path('', LoginV.as_view(), name='home'),
    path('login/', LoginV.as_view(), name='login'),
    path('register/', LoginV.as_view(), name='register'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
