from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from aegis.views.api.AuthV import TokenObtainPairView

app_name = "aegis"

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
