from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Category, MenuItem, Room, Reservation, RestaurantTable,
    Order, OrderItem, Notification, PaymentAttempt, PaymentWebhookEvent,
    SystemSettings, AuditEvent, MaintenanceLog, RoomHistory, GuestProfile,
    FolioCharge, DayAuditLog, InventoryCategory, Supplier, InventoryItem,
    StockTransaction, RecipeBOM, Account, JournalEntry, JournalEntryItem,
    ExpenseTransaction, Budget, PayrollEntry,
    HousekeepingTask, MinibarItem, LostAndFoundItem
)


# ── Inlines ───────────────────────────────────────────────────────────────────

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ["menu_item", "quantity", "price_at_order"]


class JournalEntryItemInline(TabularInline):
    model = JournalEntryItem
    extra = 0
    fields = ["account", "amount_debit", "amount_credit"]


# ── System Settings ───────────────────────────────────────────────────────────

@admin.register(SystemSettings)
class SystemSettingsAdmin(ModelAdmin):
    list_display = ["hotel_name", "tin_number", "phone_number", "currency_symbol", "active_modules_summary"]
    fieldsets = (
        ("Hotel Identity", {
            "fields": ("hotel_name", "tin_number", "address", "phone_number", "logo"),
        }),
        ("Active System Modules (Super Admin Control)", {
            "description": "Select which modules this hotel is licensed or allowed to access without changing code.",
            "fields": ("module_rooms", "module_pos", "module_inventory", "module_finance"),
        }),
        ("Taxes & Service Charges", {
            "fields": ("vat_enabled", "vat_percentage", "service_charge_enabled", "service_charge_percentage"),
        }),
        ("POS & Fiscal Hardware", {
            "fields": ("fiscal_machine_no", "reading_number", "erca_label", "currency_symbol", "pos_machine_type", "printer_paper_size", "pos_device_ip"),
        }),
    )

    def active_modules_summary(self, obj):
        active = []
        if obj.module_rooms: active.append("Rooms")
        if obj.module_pos: active.append("POS")
        if obj.module_inventory: active.append("Inventory")
        if obj.module_finance: active.append("Finance")
        return ", ".join(active) if active else "None"
    active_modules_summary.short_description = "Active Modules"


# ── Rooms & Reservations ──────────────────────────────────────────────────────

@admin.register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ["room_number", "name", "room_type", "floor_number", "base_price", "display_status", "is_available_online"]
    list_filter = ["status", "room_type", "is_available_online"]
    search_fields = ["name", "room_number"]
    list_filter_submit = True
    list_per_page = 25

    @display(description="Status", label={
        "Available": "success",
        "Occupied": "danger",
        "Reserved": "warning",
        "Cleaning": "info",
        "Maintenance": "secondary",
    })
    def display_status(self, obj):
        return obj.status


@admin.register(Reservation)
class ReservationAdmin(ModelAdmin):
    list_display = ["confirmation_code", "room", "guest_name", "check_in_date", "check_out_date", "total_amount", "display_status", "display_payment_status", "created_at"]
    list_filter = ["status", "payment_status", "source"]
    search_fields = ["confirmation_code", "room__room_number", "guest_name", "payment_reference"]
    list_filter_submit = True
    list_per_page = 25

    @display(description="Status", label={
        "confirmed": "info",
        "checked_in": "success",
        "checked_out": "secondary",
        "cancelled": "danger",
        "pending": "warning",
    })
    def display_status(self, obj):
        return obj.status

    @display(description="Payment", label={
        "paid": "success",
        "pending": "warning",
        "failed": "danger",
    })
    def display_payment_status(self, obj):
        return obj.payment_status


@admin.register(GuestProfile)
class GuestProfileAdmin(ModelAdmin):
    list_display = ["full_name", "phone", "nationality", "id_type", "id_number", "created_at"]
    list_filter = ["id_type"]
    search_fields = ["full_name", "phone", "id_number"]
    list_per_page = 25


@admin.register(FolioCharge)
class FolioChargeAdmin(ModelAdmin):
    list_display = ["id", "reservation", "description", "amount", "added_by", "added_at"]
    list_filter = ["added_at"]
    search_fields = ["description", "reservation__confirmation_code", "added_by"]
    list_per_page = 25


@admin.register(RoomHistory)
class RoomHistoryAdmin(ModelAdmin):
    list_display = ["id", "room", "guest_name", "display_event_type", "revenue", "payment_method", "created_at"]
    list_filter = ["event_type", "payment_method"]
    search_fields = ["room__room_number", "guest_name"]
    list_per_page = 25

    @display(description="Event", label={
        "checkin": "success",
        "checkout": "info",
        "maintenance": "warning",
        "cleaning": "secondary",
    })
    def display_event_type(self, obj):
        return obj.event_type


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(ModelAdmin):
    list_display = ["room", "issue_title", "reported_by", "display_status", "reported_at", "resolved_at"]
    list_filter = ["status", "reported_at"]
    search_fields = ["room__room_number", "issue_title", "notes", "reported_by"]
    list_per_page = 25

    @display(description="Status", label={
        "open": "danger",
        "in_progress": "warning",
        "resolved": "success",
    })
    def display_status(self, obj):
        return obj.status


@admin.register(HousekeepingTask)
class HousekeepingTaskAdmin(ModelAdmin):
    list_display = ["id", "room", "task_type", "priority_badge", "status_badge", "assigned_to_username", "inspected_by_username", "created_at"]
    list_filter = ["status", "task_type", "priority"]
    search_fields = ["room__room_number", "assigned_to_username", "notes"]
    list_filter_submit = True
    list_per_page = 25

    @display(description="Priority", label={
        "urgent": "danger",
        "high": "warning",
        "normal": "info",
        "low": "secondary",
    })
    def priority_badge(self, obj):
        return obj.priority

    @display(description="Status", label={
        "inspected": "success",
        "cleaned": "info",
        "in_progress": "warning",
        "failed": "danger",
        "pending": "secondary",
    })
    def status_badge(self, obj):
        return obj.status


@admin.register(MinibarItem)
class MinibarItemAdmin(ModelAdmin):
    list_display = ["id", "display_room", "item", "current_quantity", "standard_quantity", "price", "last_restocked_at", "last_checked_by"]
    list_filter = ["room"]
    search_fields = ["item__name", "room__room_number", "last_checked_by"]
    list_per_page = 25

    def display_room(self, obj):
        return f"Room {obj.room.room_number}" if obj.room else "Standard Template"
    display_room.short_description = "Room"


@admin.register(LostAndFoundItem)
class LostAndFoundItemAdmin(ModelAdmin):
    list_display = ["id", "item_name", "room", "found_by_name", "found_date", "storage_location", "status_badge", "claimed_by"]
    list_filter = ["status", "found_date"]
    search_fields = ["item_name", "room__room_number", "found_by_name", "guest_name", "claimed_by"]
    list_filter_submit = True
    list_per_page = 25

    @display(description="Status", label={
        "stored": "warning",
        "claimed": "success",
        "disposed": "secondary",
    })
    def status_badge(self, obj):
        return obj.status


# ── Food, Beverage & POS ──────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "display_station", "created_at"]
    list_filter = ["station"]
    search_fields = ["name"]

    @display(description="Station", label={"Kitchen": "warning", "Bar": "info"})
    def display_station(self, obj):
        return obj.station


@admin.register(MenuItem)
class MenuItemAdmin(ModelAdmin):
    list_display = ["name", "category", "price", "is_available", "created_at"]
    list_filter = ["is_available", "category"]
    search_fields = ["name", "category__name"]
    list_editable = ["is_available"]
    list_per_page = 25


@admin.register(RestaurantTable)
class RestaurantTableAdmin(ModelAdmin):
    list_display = ["table_code", "label_name", "capacity", "display_status"]
    list_filter = ["status"]
    search_fields = ["table_code", "label_name"]

    @display(description="Status", label={"available": "success", "occupied": "danger", "reserved": "warning"})
    def display_status(self, obj):
        return obj.status


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ["order_id_display", "table", "waiter_username", "total_amount", "display_status", "display_payment_status", "created_at"]
    list_filter = ["status", "payment_status", "payment_method"]
    search_fields = ["id", "table__table_code", "waiter_username", "payment_reference"]
    inlines = [OrderItemInline]
    list_filter_submit = True
    list_per_page = 25

    def order_id_display(self, obj):
        return f"ORD-{obj.id}"
    order_id_display.short_description = "Order ID"

    @display(description="Status", label={
        "pending": "warning",
        "preparing": "info",
        "ready": "success",
        "served": "secondary",
        "paid": "success",
        "cancelled": "danger",
    })
    def display_status(self, obj):
        return obj.status

    @display(description="Payment", label={"paid": "success", "pending": "warning"})
    def display_payment_status(self, obj):
        return obj.payment_status


# ── Inventory & Stock ─────────────────────────────────────────────────────────

@admin.register(InventoryCategory)
class InventoryCategoryAdmin(ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(InventoryItem)
class InventoryItemAdmin(ModelAdmin):
    list_display = ["name", "item_code", "category", "current_stock", "unit", "unit_cost", "min_reorder_level"]
    list_filter = ["category", "unit"]
    search_fields = ["name", "item_code"]
    list_per_page = 25


@admin.register(Supplier)
class SupplierAdmin(ModelAdmin):
    list_display = ["name", "contact_person", "phone", "email"]
    search_fields = ["name", "contact_person", "phone"]


@admin.register(StockTransaction)
class StockTransactionAdmin(ModelAdmin):
    list_display = ["id", "item", "display_txn_type", "quantity", "unit_cost", "reference_number", "timestamp"]
    list_filter = ["transaction_type"]
    search_fields = ["item__name", "reference_number", "logged_by_username"]
    list_per_page = 25

    @display(description="Transaction Type", label={
        "purchase": "success",
        "issuance": "info",
        "adjustment": "warning",
        "sale_deduction": "secondary",
    })
    def display_txn_type(self, obj):
        return obj.transaction_type


@admin.register(RecipeBOM)
class RecipeBOMAdmin(ModelAdmin):
    list_display = ["menu_item", "ingredient", "quantity_required"]
    search_fields = ["menu_item__name", "ingredient__name"]


# ── Finance & Accounting ──────────────────────────────────────────────────────

@admin.register(Account)
class AccountAdmin(ModelAdmin):
    list_display = ["code", "name", "account_type", "cached_balance", "created_at"]
    list_filter = ["account_type"]
    search_fields = ["code", "name"]
    list_per_page = 25


@admin.register(JournalEntry)
class JournalEntryAdmin(ModelAdmin):
    list_display = ["entry_number", "date", "description", "posted_at"]
    list_filter = ["date"]
    search_fields = ["entry_number", "description"]
    inlines = [JournalEntryItemInline]
    list_per_page = 25


@admin.register(ExpenseTransaction)
class ExpenseTransactionAdmin(ModelAdmin):
    list_display = ["id", "description", "amount", "date", "expense_account", "payment_account", "supplier", "reference_number"]
    list_filter = ["date", "expense_account", "payment_account"]
    search_fields = ["description", "reference_number"]
    list_per_page = 25


@admin.register(Budget)
class BudgetAdmin(ModelAdmin):
    list_display = ["account", "amount", "year", "month", "created_at"]
    list_filter = ["year", "month"]
    search_fields = ["account__name", "account__code"]


@admin.register(PayrollEntry)
class PayrollEntryAdmin(ModelAdmin):
    list_display = ["employee_name", "department", "position", "basic_salary", "gross_pay", "net_pay", "display_status", "pay_period_start", "pay_period_end"]
    list_filter = ["status", "department", "pay_period_start"]
    search_fields = ["employee_name", "employee_id"]

    @display(description="Status", label={
        "draft": "warning",
        "approved": "info",
        "paid": "success",
    })
    def display_status(self, obj):
        return obj.status


# ── Audit, Notifications & Payments ──────────────────────────────────────────

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ["id", "user_id_ref", "message", "is_read", "created_at"]
    list_filter = ["is_read"]
    list_per_page = 25


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ModelAdmin):
    list_display = ["id", "provider", "purpose", "provider_tx_ref", "display_status", "expected_amount", "currency", "verified_at"]
    list_filter = ["provider", "purpose", "status", "currency", "reconciliation_status"]
    search_fields = ["provider_tx_ref", "idempotency_key", "provider_event_ref"]
    readonly_fields = [field.name for field in PaymentAttempt._meta.fields]
    actions = None
    list_per_page = 25

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    @display(description="Status", label={"verified": "success", "initiated": "info", "created": "warning", "failed": "danger"})
    def display_status(self, obj):
        return obj.status


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(ModelAdmin):
    list_display = ["id", "provider", "event_ref", "tx_ref", "status", "signature_valid", "received_at"]
    list_filter = ["provider", "status", "signature_valid"]
    search_fields = ["event_ref", "tx_ref", "payload_hash"]
    readonly_fields = [field.name for field in PaymentWebhookEvent._meta.fields]
    actions = None
    list_per_page = 25

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ["id", "action", "entity_type", "entity_id", "actor", "actor_role", "request_id", "created_at"]
    list_filter = ["action", "entity_type", "actor_role", "created_at"]
    search_fields = ["request_id", "entity_type", "entity_id", "actor__username"]
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
    actions = None
    list_per_page = 25

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
