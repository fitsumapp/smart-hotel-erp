from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import *  # noqa: F401,F403

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"menu-items", MenuItemViewSet, basename="menuitem")
router.register(r"manage", RestaurantTableViewSet, basename="restauranttable")

urlpatterns = [
    path("dashboard-stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("orders/", AdminOrdersView.as_view(), name="admin-orders"),
    path("orders/create/", CreateOrderView.as_view(), name="create-order"),
    path("kitchen/orders/", KitchenOrdersView.as_view(), name="kitchen-orders"),
    path("orders/<int:order_id>/update-status/", UpdateOrderStatusView.as_view(), name="update-order-status"),
    path("waiter/my-orders/", WaiterOrdersView.as_view(), name="waiter-orders"),
    path("orders/<int:order_id>/mark-served/", MarkOrderServedView.as_view(), name="mark-served"),
    path("orders/<int:order_id>/request-bill/", RequestBillView.as_view(), name="request-bill"),
    path("orders/<int:order_id>/complete/", CompleteOrderView.as_view(), name="complete-order"),
    path("orders/<int:order_id>/payment-summary/", OrderPaymentSummaryView.as_view(), name="order-payment-summary"),
    path("orders/<int:order_id>/cash-payment/", WaiterCashPaymentView.as_view(), name="order-cash-payment"),
    path("orders/<int:order_id>/digital-session/", CreateDigitalPaymentSessionView.as_view(), name="order-digital-session"),
    path("cashier/pending-bills/", CashierPendingBillsView.as_view(), name="cashier-pending-bills"),
    path("cashier/completed-bills/", CashierCompletedBillsView.as_view(), name="cashier-completed-bills"),
    path("cashier/process/<int:order_id>/", CashierOrderProcessView.as_view(), name="process_payment"),
    path("cashier/receipt/<int:order_id>/", CashierReceiptView.as_view(), name="cashier-receipt"),
    path("settings/", SystemSettingsView.as_view(), name="system-settings"),
    path("notifications/", NotificationView.as_view(), name="notifications"),
    path("notifications/<int:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
] + router.urls
