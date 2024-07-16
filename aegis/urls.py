from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from aegis.views.api import LoginV

app_name = "aegis"

urlpatterns = [
    # path('api/authenticate/', LoginV.as_view, name='authenticate'),
    path('login/', LoginV.as_view(), name='login'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
