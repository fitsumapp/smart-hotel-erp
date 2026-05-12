"""
core/public_urls.py
— URL config for the PUBLIC schema (Platform Super-Admin domain).
  e.g. http://localhost/ or http://myerp.com/

  Only the Django admin is exposed here.
  Hotel staff APIs are NOT available on the public domain.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import (
    PublicRoomCatalogView,
    PublicRoomReserveView,
    PublicReservationDetailView,
    PublicReservationVerifyPaymentView,
    PublicQRCheckInView,
    ChapaWebhookView,
)

from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/")),
    path("admin/", admin.site.urls),
    # Essential for 127.0.0.1 (public schema) routing
    path("api/users/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
