import json
import logging
import random
import hashlib
import hmac
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.core.mail import send_mail
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import connection

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

# Shared (public schema) model
from .models import User
from .permissions import (
    IsCashierOrAdmin,
    IsHotelAdmin,
    IsKitchenBarOrAdmin,
    IsReservationOperator,
    IsFinanceStaff,
    IsInventoryManager,
    IsWaiterOrAdmin,
)

# Tenant (hotel schema) models
from hotel.models import (
    Category,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    Reservation,
    RestaurantTable,
    Room,
    SystemSettings,
    MaintenanceLog,
    RoomHistory,
    GuestProfile,
    FolioCharge,
    DayAuditLog,
    InventoryCategory,
    Supplier,
    InventoryItem,
    PaymentAttempt,
    StockTransaction,
    RecipeBOM,
    Account,
    JournalEntry,
    JournalEntryItem,
    ExpenseTransaction,
    Budget,
    PayrollEntry,
)
from hotel.integrity import (
    create_reservation_safely,
    get_or_create_payment_attempt,
    mark_payment_attempt_verified,
    record_stock_change,
)
from core.api import V1PageNumberPagination
from hotel.accounting import post_entry, reverse_entry

from .serializers import (
    CategorySerializer,
    MenuItemSerializer,
    NotificationSerializer,
    MaintenanceLogSerializer,
    RoomHistorySerializer,
    GuestProfileSerializer,
    FolioChargeSerializer,
    DayAuditLogSerializer,
    OrderSerializer,
    ReservationSerializer,
    RestaurantTableSerializer,
    RoomSerializer,
    SystemSettingsSerializer,
    UserSerializer,
    PublicRegistrationSerializer,
    InventoryCategorySerializer,
    SupplierSerializer,
    InventoryItemSerializer,
    StockTransactionSerializer,
    RecipeBOMSerializer,
    AccountSerializer,
    JournalEntrySerializer,
    JournalEntryItemSerializer,
    ExpenseTransactionSerializer,
    BudgetSerializer,
    PayrollEntrySerializer,
)


logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)






def get_tenant_frontend_base(request=None, tenant_schema=None):
    if request:
        # Try Origin header first
        origin = request.META.get("HTTP_ORIGIN")
        if origin:
            return origin.rstrip("/")
            
        # Try Referer header next
        referer = request.META.get("HTTP_REFERER")
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"

        # Try host
        proto = "https" if request.is_secure() else "http"
        host = request.get_host()
        if host:
            return f"{proto}://{host}"
            
    return settings.FRONTEND_BASE_URL.rstrip("/")














































# ── Status priority for waiter order list ─────────────────────────────────────
_WAITER_STATUS_PRIORITY = {
    "ready": 0,
    "pending": 1,
    "preparing": 2,
    "served": 3,
    "bill_requested": 4,
}


ORDER_STATUS_TRANSITIONS = {
    "pending": {"preparing", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": set(),
    "served": set(),
    "bill_requested": set(),
    "paid": set(),
    "cancelled": set(),
}

# ─────────────────────────────────────────────────────────────────────────────
# Auth Views
# ─────────────────────────────────────────────────────────────────────────────







# ─────────────────────────────────────────────────────────────────────────────
# ViewSets
# ─────────────────────────────────────────────────────────────────────────────











































# ─────────────────────────────────────────────────────────────────────────────
# Dashboard & Orders
# ─────────────────────────────────────────────────────────────────────────────

















# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────





# ─────────────────────────────────────────────────────────────────────────────
# System Settings
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# Payment & Checkout
# ─────────────────────────────────────────────────────────────────────────────







# ─────────────────────────────────────────────────────────────────────────────
# Cashier Views
# ─────────────────────────────────────────────────────────────────────────────











# ─────────────────────────────────────────────────────────────────────────────
# Public Payment Pages (no auth required — customer-facing)
# ─────────────────────────────────────────────────────────────────────────────









# =============================================================================
# PMS VIEWS — Property Management System
# =============================================================================

# ── Maintenance Log ───────────────────────────────────────────────────────────





# ── Room History ──────────────────────────────────────────────────────────────



# ── Guest Profile ─────────────────────────────────────────────────────────────





# ── Folio Charges ─────────────────────────────────────────────────────────────





# ── Final Bill (Check-Out) ────────────────────────────────────────────────────



# ── Digital Check-In (with Guest Registration) ────────────────────────────────



# ── Enhanced Checkout (auto Final Bill + RoomHistory) ────────────────────────



# =============================================================================
# REPORTING VIEWS
# =============================================================================















# ─────────────────────────────────────────────────────────────────────────────
# General Ledger & Double-Entry Views
# ─────────────────────────────────────────────────────────────────────────────












# ─────────────────────────────────────────────────────────────────────────────
# Payroll Management
# ─────────────────────────────────────────────────────────────────────────────




# Backward-compatible service exports.
from apps.finance.services import ensure_default_accounts, post_journal_entry  # noqa: E402,F401
from apps.identity.services import get_tokens_for_user  # noqa: E402,F401
from apps.orders.services import build_payment_summary, calculate_order_financials, create_payment_page_url, finalize_paid_order, generate_tx_ref, get_public_order_from_token, get_system_settings, notify_cashiers, notify_users, sync_order_financials  # noqa: E402,F401
from apps.payments.services import chapa_request, is_valid_chapa_signature, validate_chapa_payment, verify_chapa_transaction  # noqa: E402,F401
from apps.reservations.services import build_reservation_summary, calculate_reservation_amounts, create_public_reservation_url, finalize_paid_reservation, get_public_reservation_from_token, reservation_overlaps, send_reservation_confirmation  # noqa: E402,F401

# Backward-compatible view exports while callers migrate to domain modules.
from apps.identity.views import LoginView, LogoutView, RegisterView, ResendOTPView, UserViewSet, VerifyMFAView, VerifyOTPView  # noqa: E402,F401
from apps.inventory.views import InventoryCategoryViewSet, InventoryDashboardStatsView, InventoryItemViewSet, RecipeBOMViewSet, StockTransactionViewSet, SupplierViewSet  # noqa: E402,F401
from apps.rooms.views import MaintenanceLogDetailView, MaintenanceLogView, RoomHistoryView, RoomViewSet  # noqa: E402,F401
from apps.reservations.views import CreateCheckoutPaymentSessionView, DigitalCheckInView, EnhancedCheckoutView, FolioChargeDeleteView, FolioChargeView, GenerateFinalBillView, GuestProfileDetailView, GuestProfileView, PublicQRCheckInView, PublicReservationDetailView, PublicReservationVerifyPaymentView, PublicRoomCatalogView, PublicRoomReserveView, ReservationListView, ReserveRoomNowView, UpdateRoomFrontDeskStatusView, VerifyCheckoutPaymentView  # noqa: E402,F401
from apps.orders.views import AdminOrdersView, CashierCompletedBillsView, CashierOrderProcessView, CashierPendingBillsView, CashierReceiptView, CategoryViewSet, CompleteOrderView, CreateDigitalPaymentSessionView, CreateOrderView, DashboardStatsView, KitchenOrdersView, MarkOrderServedView, MenuItemViewSet, NotificationDetailView, NotificationView, OrderPaymentSummaryView, RequestBillView, RestaurantTableViewSet, SystemSettingsView, UpdateOrderStatusView, WaiterCashPaymentView, WaiterOrdersView  # noqa: E402,F401
from apps.payments.views import ChapaWebhookView, PublicInitiateChapaPaymentView, PublicPaymentDetailView, PublicVerifyChapaPaymentView  # noqa: E402,F401
from apps.reporting.views import FinanceDashboardStatsView, OccupancyReportView, PoliceReportView, XReportView, ZReportView  # noqa: E402,F401
from apps.finance.views import AccountViewSet, BudgetViewSet, ExpenseTransactionViewSet, FinancialStatementsView, JournalEntryViewSet, PayrollEntryViewSet, PayrollSummaryView, TaxReportView  # noqa: E402,F401
