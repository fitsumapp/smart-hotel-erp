from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Category, MenuItem, Room, Reservation, RestaurantTable, DiningSession,
    Order, OrderItem, Notification, PaymentAttempt, PaymentWebhookEvent,
    SystemSettings, AuditEvent, MaintenanceLog, RoomHistory, GuestProfile,
    FolioCharge, DayAuditLog, InventoryCategory, Supplier, InventoryItem,
    StockTransaction, RecipeBOM, Account, JournalEntry, JournalEntryItem,
    ExpenseTransaction, Budget, PayrollEntry,
    HousekeepingTask, MinibarItem, LostAndFoundItem,
    StockLocation, StockBatch, BatchLocationBalance, ItemLocationBalance,
    StockTransfer, StockTransferItem,
    RequestForQuotation, RequestForQuotationItem,
    SupplierQuotation, SupplierQuotationItem,
    ProcurementApprovalPolicy, ProcurementApprovalTier,
    PurchaseRequisition, PurchaseRequisitionItem,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceiptNote, GoodsReceiptNoteItem,
    SupplierInvoice, SupplierInvoiceItem,
    StocktakeSession, StocktakeItem,
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
        "no_show": "danger",
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


@admin.register(DayAuditLog)
class DayAuditLogAdmin(ModelAdmin):
    list_display = ["audit_date", "is_closed", "total_revenue", "total_room_revenue", "total_cash", "total_card", "closed_by", "closed_at"]
    list_filter = ["is_closed", "audit_date"]
    search_fields = ["audit_date", "closed_by", "notes"]
    ordering = ["-audit_date"]
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


@admin.register(DiningSession)
class DiningSessionAdmin(ModelAdmin):
    list_display = ["id", "table", "status", "opened_by_username", "created_at", "closed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["table__table_code", "opened_by_username"]
    ordering = ["-created_at"]
    list_per_page = 25


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


@admin.register(StockLocation)
class StockLocationAdmin(ModelAdmin):
    list_display = ["code", "name", "location_type", "is_active", "custodian"]
    list_filter = ["location_type", "is_active"]
    search_fields = ["code", "name"]


@admin.register(StockBatch)
class StockBatchAdmin(ModelAdmin):
    list_display = ["batch_number", "item", "current_quantity", "initial_quantity", "unit_cost", "received_date", "expiry_date", "display_status", "is_legacy"]
    list_filter = ["status", "is_legacy", "expiry_date"]
    search_fields = ["batch_number", "item__name", "item__item_code", "supplier_batch_number"]
    readonly_fields = ["verified_at", "verified_by", "created_at"]
    list_per_page = 25

    @display(description="Status", label={
        "active": "success",
        "expired": "danger",
        "unverified_quarantine": "warning",
        "depleted": "secondary",
    })
    def display_status(self, obj):
        return obj.status


@admin.register(BatchLocationBalance)
class BatchLocationBalanceAdmin(ModelAdmin):
    list_display = ["batch", "location", "quantity"]
    list_filter = ["location"]
    search_fields = ["batch__batch_number", "batch__item__name"]


@admin.register(ItemLocationBalance)
class ItemLocationBalanceAdmin(ModelAdmin):
    list_display = ["item", "location", "quantity"]
    list_filter = ["location"]
    search_fields = ["item__name", "item__item_code"]


class StockTransferItemInline(TabularInline):
    model = StockTransferItem
    extra = 0
    fields = ["item", "batch", "requested_quantity", "dispatched_quantity", "received_quantity", "damaged_quantity"]


@admin.register(StockTransfer)
class StockTransferAdmin(ModelAdmin):
    list_display = ["transfer_number", "source_location", "destination_location", "display_status", "requested_by", "created_at"]
    list_filter = ["status", "source_location", "destination_location"]
    search_fields = ["transfer_number", "requested_by__username"]
    inlines = [StockTransferItemInline]
    list_per_page = 25

    @display(description="Status", label={
        "draft": "secondary",
        "dispatched": "warning",
        "completed": "success",
        "partially_received": "info",
        "cancelled": "danger",
    })
    def display_status(self, obj):
        return obj.status


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


# ── Procurement Inlines & ModelAdmins ────────────────────────────────────────

class ProcurementApprovalTierInline(TabularInline):
    model = ProcurementApprovalTier
    extra = 0
    fields = ["tier_level", "name", "min_amount", "max_amount", "required_role"]


@admin.register(ProcurementApprovalPolicy)
class ProcurementApprovalPolicyAdmin(ModelAdmin):
    list_display = ["name", "is_active", "currency", "price_tolerance_percentage", "created_at"]
    list_filter = ["is_active", "currency"]
    inlines = [ProcurementApprovalTierInline]


class PurchaseRequisitionItemInline(TabularInline):
    model = PurchaseRequisitionItem
    extra = 0
    fields = ["item", "quantity_requested", "estimated_unit_cost", "notes"]


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(ModelAdmin):
    list_display = [
        "requisition_number", "department", "status", "total_estimated_amount",
        "requested_by", "requested_at", "approved_by", "approved_at"
    ]
    list_filter = ["status", "department", "requested_at"]
    search_fields = ["requisition_number", "department", "requested_by__username"]
    inlines = [PurchaseRequisitionItemInline]


class RequestForQuotationItemInline(TabularInline):
    model = RequestForQuotationItem
    extra = 0
    fields = ["item", "target_quantity", "requisition_item", "specifications"]


@admin.register(RequestForQuotation)
class RequestForQuotationAdmin(ModelAdmin):
    list_display = [
        "rfq_number", "title", "status", "delivery_location",
        "submission_deadline", "is_public_bidding", "created_by", "created_at"
    ]
    list_filter = ["status", "is_public_bidding", "delivery_location"]
    search_fields = ["rfq_number", "title"]
    filter_horizontal = ["requisitions", "invited_suppliers"]
    inlines = [RequestForQuotationItemInline]


class SupplierQuotationItemInline(TabularInline):
    model = SupplierQuotationItem
    extra = 0
    fields = [
        "item", "quoted_quantity", "quoted_unit_price", "discount_percentage",
        "line_total", "offered_brand_or_spec", "award_status", "is_converted_to_po", "converted_quantity"
    ]
    readonly_fields = ["line_total", "converted_quantity"]

    def has_change_permission(self, request, obj=None):
        if obj and obj.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
            return False
        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
            return False
        return super().has_add_permission(request, obj)


@admin.register(SupplierQuotation)
class SupplierQuotationAdmin(ModelAdmin):
    list_display = [
        "quotation_number", "supplier", "rfq", "status",
        "total_quoted_amount", "currency", "total_landed_cost_etb",
        "valid_until", "quotation_date"
    ]
    list_filter = ["status", "currency", "quotation_date", "valid_until"]
    search_fields = ["quotation_number", "supplier_reference", "supplier__name"]
    inlines = [SupplierQuotationItemInline]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
            return [field.name for field in self.model._meta.fields]
        return self.readonly_fields


class PurchaseOrderItemInline(TabularInline):
    model = PurchaseOrderItem
    extra = 0
    fields = ["item", "quantity_ordered", "quantity_received", "unit_price", "line_total", "originating_quote_item"]
    readonly_fields = ["line_total", "originating_quote_item"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(ModelAdmin):
    list_display = [
        "po_number", "supplier", "status", "total_amount",
        "delivery_location", "originating_quotation", "delivery_due_date", "issued_by", "issued_at"
    ]
    list_filter = ["status", "supplier", "delivery_location"]
    search_fields = ["po_number", "supplier__name"]
    inlines = [PurchaseOrderItemInline]


class GoodsReceiptNoteItemInline(TabularInline):
    model = GoodsReceiptNoteItem
    extra = 0
    fields = ["item", "quantity_received", "quantity_rejected", "batch_number", "expiry_date", "unit_cost", "total_cost"]


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(ModelAdmin):
    list_display = ["grn_number", "purchase_order", "supplier", "location", "status", "received_by", "received_at"]
    list_filter = ["status", "location", "received_at"]
    search_fields = ["grn_number", "delivery_note_number", "supplier__name"]
    inlines = [GoodsReceiptNoteItemInline]


class SupplierInvoiceItemInline(TabularInline):
    model = SupplierInvoiceItem
    extra = 0
    fields = ["item", "billed_quantity", "billed_unit_price", "line_total", "price_variance", "is_matched"]
    readonly_fields = ["line_total", "price_variance", "is_matched"]


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(ModelAdmin):
    list_display = [
        "internal_number", "vendor_invoice_number", "supplier", "purchase_order",
        "total_amount", "match_status", "is_paid", "invoice_date", "due_date"
    ]
    list_filter = ["match_status", "is_paid", "invoice_date"]
    search_fields = ["internal_number", "vendor_invoice_number", "supplier__name"]
    inlines = [SupplierInvoiceItemInline]


class StocktakeItemInline(TabularInline):
    model = StocktakeItem
    extra = 0
    fields = ["item", "batch", "theoretical_quantity", "counted_quantity", "variance_quantity", "variance_value"]
    readonly_fields = ["theoretical_quantity", "variance_quantity", "variance_value"]


@admin.register(StocktakeSession)
class StocktakeSessionAdmin(ModelAdmin):
    list_display = [
        "session_number", "title", "location", "counting_mode", "status",
        "total_theoretical_value", "total_counted_value", "total_variance_value", "snapshot_at"
    ]
    list_filter = ["status", "counting_mode", "location"]
    search_fields = ["session_number", "title"]
    inlines = [StocktakeItemInline]
