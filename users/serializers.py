import json
from rest_framework import serializers
from django.contrib.auth import get_user_model

from hotel.models import (
    MenuItem, Category, Room, RestaurantTable,
    OrderItem, Order, Notification, SystemSettings, Reservation,
    MaintenanceLog, RoomHistory, GuestProfile, FolioCharge, DayAuditLog,
    InventoryCategory, Supplier, InventoryItem, StockTransaction, RecipeBOM,
    Account, JournalEntry, JournalEntryItem, ExpenseTransaction, Budget,
    PayrollEntry,
)

User = get_user_model()


# ── 1. Users ──────────────────────────────────────────────────────────────────




# ── 2. Category ───────────────────────────────────────────────────────────────


# ── 3. Menu Item ──────────────────────────────────────────────────────────────


# ── 4. Room ───────────────────────────────────────────────────────────────────


# ── 5. Reservation ────────────────────────────────────────────────────────────


# ── 6. Restaurant Table ───────────────────────────────────────────────────────


# ── 7. Order Item ─────────────────────────────────────────────────────────────


# ── 8. System Settings ────────────────────────────────────────────────────────


# ── 9. Order ──────────────────────────────────────────────────────────────────


# ── 10. Notification ──────────────────────────────────────────────────────────


# ── PMS Serializers ───────────────────────────────────────────────────────────





















# ── General Ledger Serializers ──────────────────────────────────────────────────











# ── Payroll Serializer ─────────────────────────────────────────────────────────


# Backward-compatible serializer exports.
from apps.identity.serializers import PublicRegistrationSerializer, UserSerializer  # noqa: E402,F401
from apps.orders.serializers import CategorySerializer, MenuItemSerializer, NotificationSerializer, OrderItemSerializer, OrderSerializer, RestaurantTableSerializer, SystemSettingsSerializer  # noqa: E402,F401
from apps.rooms.serializers import MaintenanceLogSerializer, RoomHistorySerializer, RoomSerializer  # noqa: E402,F401
from apps.reservations.serializers import FolioChargeSerializer, GuestProfileSerializer, ReservationSerializer  # noqa: E402,F401
from apps.reporting.serializers import DayAuditLogSerializer  # noqa: E402,F401
from apps.inventory.serializers import InventoryCategorySerializer, InventoryItemSerializer, RecipeBOMSerializer, StockTransactionSerializer, SupplierSerializer  # noqa: E402,F401
from apps.finance.serializers import AccountSerializer, BudgetSerializer, ExpenseTransactionSerializer, JournalEntryItemSerializer, JournalEntrySerializer, PayrollEntrySerializer  # noqa: E402,F401
