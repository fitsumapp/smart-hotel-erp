from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, VerifyOTPView, LoginView,
    UserViewSet, CategoryViewSet, MenuItemViewSet,
    RoomViewSet, RestaurantTableViewSet,
    DashboardStatsView, CreateOrderView,
    KitchenOrdersView, UpdateOrderStatusView, WaiterOrdersView,
    MarkOrderServedView, RequestBillView, CompleteOrderView,
    NotificationView, NotificationDetailView, SystemSettingsView,
    CashierPendingBillsView, CashierCompletedBillsView, CashierOrderProcessView, CashierReceiptView,
    OrderPaymentSummaryView, WaiterCashPaymentView, CreateDigitalPaymentSessionView,
    PublicPaymentDetailView, PublicInitiateChapaPaymentView, PublicVerifyChapaPaymentView, ChapaWebhookView,
    ReserveRoomNowView, UpdateRoomFrontDeskStatusView, PublicRoomCatalogView,
    PublicRoomReserveView, PublicReservationDetailView, PublicReservationVerifyPaymentView,
    PublicQRCheckInView, ReservationListView, CurrentTenantPublicSiteView,
    # PMS Views
    MaintenanceLogView, MaintenanceLogDetailView,
    RoomHistoryView,
    GuestProfileView, GuestProfileDetailView,
    FolioChargeView, FolioChargeDeleteView,
    GenerateFinalBillView,
    DigitalCheckInView,
    EnhancedCheckoutView,
    # Report Views
    PoliceReportView, XReportView, ZReportView, OccupancyReportView,
)

router = DefaultRouter()

router.register(r'users', UserViewSet, basename='user')
router.register(r'categories', CategoryViewSet)
router.register(r'menu-items', MenuItemViewSet)
router.register(r'rooms', RoomViewSet)
router.register(r'manage', RestaurantTableViewSet, basename='restauranttable')

urlpatterns = [
    # --- Auth ---
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', LoginView.as_view(), name='login'),

    # --- Dashboard ---
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # --- Orders ---
    path('orders/create/', CreateOrderView.as_view(), name='create-order'),
    path('kitchen/orders/', KitchenOrdersView.as_view(), name='kitchen-orders'),
    path('orders/<int:order_id>/update-status/', UpdateOrderStatusView.as_view(), name='update-order-status'),
    path('waiter/my-orders/', WaiterOrdersView.as_view(), name='waiter-orders'),
    path('orders/<int:order_id>/mark-served/', MarkOrderServedView.as_view(), name='mark-served'),
    path('orders/<int:order_id>/request-bill/', RequestBillView.as_view(), name='request-bill'),
    path('orders/<int:order_id>/complete/', CompleteOrderView.as_view(), name='complete-order'),
    path('orders/<int:order_id>/payment-summary/', OrderPaymentSummaryView.as_view(), name='order-payment-summary'),
    path('orders/<int:order_id>/cash-payment/', WaiterCashPaymentView.as_view(), name='order-cash-payment'),
    path('orders/<int:order_id>/digital-session/', CreateDigitalPaymentSessionView.as_view(), name='order-digital-session'),

    # --- Room Core ---
    path('rooms/<int:room_id>/reserve-now/', ReserveRoomNowView.as_view(), name='room-reserve-now'),
    path('rooms/<int:room_id>/front-desk-status/', UpdateRoomFrontDeskStatusView.as_view(), name='room-front-desk-status'),

    # --- PMS: Maintenance ---
    path('rooms/<int:room_id>/maintenance/', MaintenanceLogView.as_view(), name='room-maintenance'),
    path('maintenance/<int:log_id>/', MaintenanceLogDetailView.as_view(), name='maintenance-detail'),

    # --- PMS: Room History ---
    path('rooms/<int:room_id>/history/', RoomHistoryView.as_view(), name='room-history'),

    # --- PMS: Digital Check-In ---
    path('rooms/<int:room_id>/digital-checkin/', DigitalCheckInView.as_view(), name='room-digital-checkin'),

    # --- PMS: Enhanced Checkout ---
    path('reservations/<int:reservation_id>/enhanced-checkout/', EnhancedCheckoutView.as_view(), name='enhanced-checkout'),

    # --- PMS: Guest Profile ---
    path('guest-profiles/', GuestProfileView.as_view(), name='guest-profiles'),
    path('guest-profiles/<int:pk>/', GuestProfileDetailView.as_view(), name='guest-profile-detail'),

    # --- PMS: Folio Charges ---
    path('reservations/<int:reservation_id>/folio/', FolioChargeView.as_view(), name='folio-charges'),
    path('folio/<int:charge_id>/', FolioChargeDeleteView.as_view(), name='folio-charge-delete'),

    # --- PMS: Final Bill ---
    path('reservations/<int:reservation_id>/final-bill/', GenerateFinalBillView.as_view(), name='final-bill'),

    # --- Reservations ---
    path('reservations/', ReservationListView.as_view(), name='reservation-list'),
    path('public-site/', CurrentTenantPublicSiteView.as_view(), name='current-tenant-public-site'),

    # --- Public Booking ---
    path('public-booking/rooms/', PublicRoomCatalogView.as_view(), name='public-room-catalog'),
    path('public-booking/rooms/<int:room_id>/reserve/', PublicRoomReserveView.as_view(), name='public-room-reserve'),
    path('reservations/public/<str:token>/', PublicReservationDetailView.as_view(), name='public-reservation-detail'),
    path('reservations/public/<str:token>/verify/', PublicReservationVerifyPaymentView.as_view(), name='public-reservation-verify'),
    path('reservations/qr-checkin/', PublicQRCheckInView.as_view(), name='public-qr-checkin'),

    # --- Cashier ---
    path('cashier/pending-bills/', CashierPendingBillsView.as_view(), name='cashier-pending-bills'),
    path('cashier/completed-bills/', CashierCompletedBillsView.as_view(), name='cashier-completed-bills'),
    path('cashier/process/<int:order_id>/', CashierOrderProcessView.as_view(), name='process_payment'),
    path('cashier/receipt/<int:order_id>/', CashierReceiptView.as_view(), name='cashier-receipt'),
    path('payments/public/<str:token>/', PublicPaymentDetailView.as_view(), name='public-payment-detail'),
    path('payments/public/<str:token>/initiate/', PublicInitiateChapaPaymentView.as_view(), name='public-payment-initiate'),
    path('payments/public/<str:token>/verify/', PublicVerifyChapaPaymentView.as_view(), name='public-payment-verify'),
    path('payments/chapa/webhook/', ChapaWebhookView.as_view(), name='chapa-webhook'),

    # --- Reports ---
    path('reports/police/', PoliceReportView.as_view(), name='report-police'),
    path('reports/x-report/', XReportView.as_view(), name='report-x'),
    path('reports/z-report/', ZReportView.as_view(), name='report-z'),
    path('reports/occupancy/', OccupancyReportView.as_view(), name='report-occupancy'),

    # --- Settings & Notifications ---
    path('settings/', SystemSettingsView.as_view(), name='system-settings'),
    path('notifications/', NotificationView.as_view(), name='notifications'),
    path('notifications/<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),

    # --- Router (ViewSets) ---
    path('', include(router.urls)),
]
