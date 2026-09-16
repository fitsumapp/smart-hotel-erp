from django.urls import path

from .views import *  # noqa: F401,F403

urlpatterns = [
    path("rooms/<int:room_id>/reserve-now/", ReserveRoomNowView.as_view(), name="room-reserve-now"),
    path("rooms/<int:room_id>/front-desk-status/", UpdateRoomFrontDeskStatusView.as_view(), name="room-front-desk-status"),
    path("rooms/<int:room_id>/digital-checkin/", DigitalCheckInView.as_view(), name="room-digital-checkin"),
    path("reservations/", ReservationListView.as_view(), name="reservation-list"),
    path("reservations/<int:reservation_id>/enhanced-checkout/", EnhancedCheckoutView.as_view(), name="enhanced-checkout"),
    path("reservations/<int:reservation_id>/checkout-payment-session/", CreateCheckoutPaymentSessionView.as_view(), name="checkout-payment-session"),
    path("reservations/<int:reservation_id>/verify-checkout-payment/", VerifyCheckoutPaymentView.as_view(), name="verify-checkout-payment"),
    path("reservations/<int:reservation_id>/folio/", FolioChargeView.as_view(), name="folio-charges"),
    path("reservations/<int:reservation_id>/final-bill/", GenerateFinalBillView.as_view(), name="final-bill"),
    path("folio/<int:charge_id>/", FolioChargeDeleteView.as_view(), name="folio-charge-delete"),
    path("guest-profiles/", GuestProfileView.as_view(), name="guest-profiles"),
    path("guest-profiles/<int:pk>/", GuestProfileDetailView.as_view(), name="guest-profile-detail"),
    path("guest-profiles/<int:pk>/id-scan/", SecureGuestIdDownloadView.as_view(), name="guest-profile-id-scan"),
    path("public-booking/rooms/", PublicRoomCatalogView.as_view(), name="public-room-catalog"),
    path("public-booking/rooms/<int:room_id>/reserve/", PublicRoomReserveView.as_view(), name="public-room-reserve"),
    path("reservations/public/<str:token>/", PublicReservationDetailView.as_view(), name="public-reservation-detail"),
    path("reservations/public/<str:token>/verify/", PublicReservationVerifyPaymentView.as_view(), name="public-reservation-verify"),
    path("reservations/qr-checkin/", PublicQRCheckInView.as_view(), name="public-qr-checkin"),
]
