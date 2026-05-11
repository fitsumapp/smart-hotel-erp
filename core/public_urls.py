"""
core/public_urls.py
— URL config for the PUBLIC schema (Platform Super-Admin domain).
  e.g. http://localhost/ or http://myerp.com/

  Only the Django admin is exposed here.
  Hotel staff APIs are NOT available on the public domain.
"""
from django.contrib import admin
from django.urls import path
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
    path("api/users/public-booking/rooms/", PublicRoomCatalogView.as_view()),
    path("api/users/public-booking/rooms/<int:room_id>/reserve/", PublicRoomReserveView.as_view()),
    path("api/users/reservations/public/<str:token>/", PublicReservationDetailView.as_view()),
    path("api/users/reservations/public/<str:token>/verify/", PublicReservationVerifyPaymentView.as_view()),
    path("api/users/reservations/qr-checkin/", PublicQRCheckInView.as_view()),
    path("api/users/payments/chapa/webhook/", ChapaWebhookView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
