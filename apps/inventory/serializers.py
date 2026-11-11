"""Inventory serializers."""
from users.serializers import *  # noqa: F401,F403
from hotel.models import (
    BatchLocationBalance,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
    InventoryExpiryAlert,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    RecipeBOM,
    RequestForQuotation,
    RequestForQuotationItem,
    StockBatch,
    StockBatchConsumption,
    StockLocation,
    StocktakeItem,
    StocktakeSchedule,
    StocktakeSession,
    StockTransaction,
    StockTransfer,
    StockTransferItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierQuotation,
    SupplierQuotationItem,
)


class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    supplied_category_names = serializers.SerializerMethodField(read_only=True)

    def get_supplied_category_names(self, obj):
        return [cat.name for cat in obj.supplied_categories.all()]

    class Meta:
        model = Supplier
        fields = [
            "id", "name", "contact_person", "phone", "email",
            "address", "tin_number",
            "supplied_categories", "supplied_category_names",
            "supply_items",
            "created_at"
        ]


class StockLocationSerializer(serializers.ModelSerializer):
    custodian_username = serializers.ReadOnlyField(source="custodian.username")

    class Meta:
        model = StockLocation
        fields = [
            "id", "code", "name", "location_type", "is_active",
            "custodian", "custodian_username", "created_at"
        ]


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    category_type = serializers.ReadOnlyField(source="category.category_type")
    supplier_name = serializers.ReadOnlyField(source="last_supplier.name")

    class Meta:
        model = InventoryItem
        fields = [
            "id", "item_code", "name", "category", "category_name", "category_type", "unit",
            "current_stock", "min_reorder_level", "unit_cost", "selling_price",
            "last_supplier", "supplier_name", "units_per_pack",
            "is_perishable", "shelf_life_days",
            "last_stocked_at", "created_at"
        ]
        read_only_fields = ["current_stock", "last_stocked_at", "created_at"]


class StockBatchSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    verified_by_username = serializers.ReadOnlyField(source="verified_by.username")

    class Meta:
        model = StockBatch
        fields = [
            "id", "item", "item_name", "item_code", "item_unit",
            "batch_number", "supplier_batch_number", "supplier", "supplier_name",
            "initial_quantity", "current_quantity", "unit_cost",
            "received_date", "expiry_date", "is_legacy", "status",
            "verified_by", "verified_by_username", "verified_at", "verification_notes",
            "created_at"
        ]
        read_only_fields = [
            "initial_quantity", "current_quantity", "is_legacy",
            "verified_by", "verified_by_username", "verified_at", "created_at"
        ]


class BatchLocationBalanceSerializer(serializers.ModelSerializer):
    batch_number = serializers.ReadOnlyField(source="batch.batch_number")
    item_name = serializers.ReadOnlyField(source="batch.item.name")
    item_code = serializers.ReadOnlyField(source="batch.item.item_code")
    item_unit = serializers.ReadOnlyField(source="batch.item.unit")
    location_code = serializers.ReadOnlyField(source="location.code")
    location_name = serializers.ReadOnlyField(source="location.name")

    class Meta:
        model = BatchLocationBalance
        fields = [
            "id", "batch", "batch_number", "item_name", "item_code", "item_unit",
            "location", "location_code", "location_name", "quantity"
        ]
        read_only_fields = ["quantity"]


class ItemLocationBalanceSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    location_code = serializers.ReadOnlyField(source="location.code")
    location_name = serializers.ReadOnlyField(source="location.name")

    class Meta:
        model = ItemLocationBalance
        fields = [
            "id", "item", "item_name", "item_code", "item_unit",
            "location", "location_code", "location_name", "quantity"
        ]
        read_only_fields = ["quantity"]


class StockBatchConsumptionSerializer(serializers.ModelSerializer):
    batch_number = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = StockBatchConsumption
        fields = [
            "id", "transaction", "batch", "batch_number",
            "quantity_consumed", "unit_cost", "total_cost", "created_at"
        ]
        read_only_fields = ["created_at"]


class StockTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    location_name = serializers.ReadOnlyField(source="location.name")
    batch_number = serializers.ReadOnlyField(source="batch.batch_number")
    batch_number_input = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    expiry_date_input = serializers.DateField(write_only=True, required=False, allow_null=True)
    batch_consumptions = StockBatchConsumptionSerializer(many=True, read_only=True)

    class Meta:
        model = StockTransaction
        fields = [
            "id", "idempotency_key", "payload_hash", "item", "item_name", "item_unit", "transaction_type",
            "quantity", "unit_cost", "adjustment_direction", "supplier", "supplier_name",
            "location", "location_code", "location_name", "batch", "batch_number",
            "batch_number_input", "expiry_date_input",
            "batch_consumptions",
            "reference_number", "notes", "destination_dept", "destination_room",
            "logged_by_username", "timestamp", "reversal_of"
        ]
        read_only_fields = ["reversal_of", "logged_by_username", "timestamp", "payload_hash", "batch_consumptions"]


class RecipeBOMSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.ReadOnlyField(source="menu_item.name")
    ingredient_name = serializers.ReadOnlyField(source="ingredient.name")
    ingredient_unit = serializers.ReadOnlyField(source="ingredient.unit")

    class Meta:
        model = RecipeBOM
        fields = [
            "id", "menu_item", "menu_item_name", "ingredient",
            "ingredient_name", "ingredient_unit", "quantity_required"
        ]


class InventoryWasteRecordSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    source_dispatch_reference = serializers.ReadOnlyField(source="source_dispatch.reference_number")

    class Meta:
        model = InventoryWasteRecord
        fields = [
            "id", "idempotency_key", "item", "item_name", "item_code", "item_unit",
            "entered_quantity", "entered_unit", "base_quantity",
            "waste_category", "waste_source", "unit_cost_snapshot", "total_cost_loss",
            "stock_deducted", "stock_transaction", "source_dispatch", "source_dispatch_reference",
            "journal_entry", "notes", "storage_area", "reported_by_username", "recorded_at",
            "is_reversed", "reversal_of", "reversal_reason", "reversed_at", "reversed_by_username",
            "status", "reviewed_by", "reviewed_by_username", "reviewed_at", "rejection_reason",
            "is_self_reviewed", "self_review_justification"
        ]
        read_only_fields = [
            "base_quantity", "unit_cost_snapshot", "total_cost_loss", "stock_deducted",
            "stock_transaction", "journal_entry", "reported_by_username", "recorded_at",
            "is_reversed", "reversal_of", "reversal_reason", "reversed_at", "reversed_by_username",
            "status", "reviewed_by", "reviewed_by_username", "reviewed_at", "rejection_reason",
            "is_self_reviewed", "self_review_justification"
        ]


class StockTransferItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    batch_number = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = StockTransferItem
        fields = [
            "id",
            "transfer",
            "item",
            "item_name",
            "item_code",
            "item_unit",
            "batch",
            "batch_number",
            "quantity_requested",
            "quantity_dispatched",
            "quantity_received",
            "quantity_damaged",
            "unit_cost",
            "waste_record",
            "notes",
        ]
        read_only_fields = [
            "quantity_dispatched",
            "quantity_received",
            "quantity_damaged",
            "unit_cost",
            "waste_record",
        ]


class StockTransferSerializer(serializers.ModelSerializer):
    source_location_code = serializers.ReadOnlyField(source="source_location.code")
    source_location_name = serializers.ReadOnlyField(source="source_location.name")
    destination_location_code = serializers.ReadOnlyField(source="destination_location.code")
    destination_location_name = serializers.ReadOnlyField(source="destination_location.name")
    requested_by_username = serializers.ReadOnlyField(source="requested_by.username")
    dispatched_by_username = serializers.ReadOnlyField(source="dispatched_by.username")
    received_by_username = serializers.ReadOnlyField(source="received_by.username")
    items = StockTransferItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            "id",
            "transfer_number",
            "source_location",
            "source_location_code",
            "source_location_name",
            "destination_location",
            "destination_location_code",
            "destination_location_name",
            "status",
            "requested_by",
            "requested_by_username",
            "dispatched_by",
            "dispatched_by_username",
            "received_by",
            "received_by_username",
            "requested_at",
            "dispatched_at",
            "received_at",
            "notes",
            "rejection_reason",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "transfer_number",
            "status",
            "requested_by",
            "requested_by_username",
            "dispatched_by",
            "dispatched_by_username",
            "received_by",
            "received_by_username",
            "requested_at",
            "dispatched_at",
            "received_at",
            "items",
            "created_at",
            "updated_at",
        ]


class ProcurementApprovalTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementApprovalTier
        fields = [
            "id", "policy", "tier_level", "name", "min_amount", "max_amount", "required_role", "created_at"
        ]


class ProcurementApprovalPolicySerializer(serializers.ModelSerializer):
    tiers = ProcurementApprovalTierSerializer(many=True, read_only=True)

    class Meta:
        model = ProcurementApprovalPolicy
        fields = [
            "id", "name", "description", "is_active", "currency", "price_tolerance_percentage", "tiers", "created_at", "updated_at"
        ]


class PurchaseRequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseRequisitionItem
        fields = [
            "id", "requisition", "item", "item_name", "item_code", "item_unit",
            "quantity_requested", "estimated_unit_cost", "notes"
        ]


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.ReadOnlyField(source="requested_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    approval_tier_name = serializers.ReadOnlyField(source="approval_tier.name")
    items = PurchaseRequisitionItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id", "requisition_number", "department", "status",
            "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name",
            "approved_by", "approved_by_username", "approved_at",
            "rejection_reason", "total_estimated_amount", "notes",
            "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "requisition_number", "status", "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name", "approved_by", "approved_by_username", "approved_at",
            "total_estimated_amount", "items", "created_at", "updated_at"
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id", "purchase_order", "item", "item_name", "item_code", "item_unit",
            "quantity_ordered", "quantity_received", "unit_price", "line_total", "notes"
        ]
        read_only_fields = ["quantity_received", "line_total"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    delivery_location_name = serializers.ReadOnlyField(source="delivery_location.name")
    delivery_location_code = serializers.ReadOnlyField(source="delivery_location.code")
    issued_by_username = serializers.ReadOnlyField(source="issued_by.username")
    requisition_number = serializers.ReadOnlyField(source="requisition.requisition_number")
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "requisition", "requisition_number",
            "supplier", "supplier_name",
            "delivery_location", "delivery_location_code", "delivery_location_name",
            "status", "issued_by", "issued_by_username", "issued_at",
            "delivery_due_date", "payment_terms",
            "subtotal", "tax_amount", "total_amount",
            "notes", "cancellation_reason", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "po_number", "status", "issued_by", "issued_by_username", "issued_at",
            "subtotal", "tax_amount", "total_amount", "items", "created_at", "updated_at"
        ]


class GoodsReceiptNoteItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    batch_number_display = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = GoodsReceiptNoteItem
        fields = [
            "id", "grn", "po_item", "item", "item_name", "item_code", "item_unit",
            "quantity_received", "quantity_rejected", "rejection_reason",
            "batch", "batch_number_display", "batch_number", "supplier_batch_number",
            "expiry_date", "unit_cost", "total_cost", "notes"
        ]
        read_only_fields = ["batch", "batch_number_display", "total_cost"]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    received_by_username = serializers.ReadOnlyField(source="received_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = GoodsReceiptNoteItemSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "id", "grn_number", "purchase_order", "po_number",
            "supplier", "supplier_name",
            "location", "location_code", "location_name",
            "delivery_note_number", "status",
            "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number",
            "total_received_cost", "notes", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "grn_number", "status", "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number", "total_received_cost", "items",
            "created_at", "updated_at"
        ]


class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = SupplierInvoiceItem
        fields = [
            "id", "invoice", "po_item", "grn_item", "item", "item_name", "item_code", "item_unit",
            "billed_quantity", "billed_unit_price", "line_total", "price_variance", "is_matched"
        ]
        read_only_fields = ["line_total", "price_variance", "is_matched"]


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    matched_by_username = serializers.ReadOnlyField(source="matched_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id", "internal_number", "vendor_invoice_number",
            "supplier", "supplier_name",
            "purchase_order", "po_number",
            "invoice_date", "due_date",
            "subtotal", "tax_amount", "total_amount",
            "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "variance_notes", "journal_entry", "journal_entry_number",
            "is_paid", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "internal_number", "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "journal_entry", "journal_entry_number", "is_paid", "items", "created_at", "updated_at"
        ]


class ProcurementApprovalTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementApprovalTier
        fields = [
            "id", "policy", "tier_level", "name", "min_amount", "max_amount", "required_role", "created_at"
        ]


class ProcurementApprovalPolicySerializer(serializers.ModelSerializer):
    tiers = ProcurementApprovalTierSerializer(many=True, read_only=True)

    class Meta:
        model = ProcurementApprovalPolicy
        fields = [
            "id", "name", "description", "is_active", "currency", "price_tolerance_percentage", "tiers", "created_at", "updated_at"
        ]


class PurchaseRequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseRequisitionItem
        fields = [
            "id", "requisition", "item", "item_name", "item_code", "item_unit",
            "quantity_requested", "estimated_unit_cost", "notes"
        ]


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.ReadOnlyField(source="requested_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    approval_tier_name = serializers.ReadOnlyField(source="approval_tier.name")
    items = PurchaseRequisitionItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id", "requisition_number", "department", "status",
            "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name",
            "approved_by", "approved_by_username", "approved_at",
            "rejection_reason", "total_estimated_amount", "notes",
            "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "requisition_number", "status", "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name", "approved_by", "approved_by_username", "approved_at",
            "total_estimated_amount", "items", "created_at", "updated_at"
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id", "purchase_order", "item", "item_name", "item_code", "item_unit",
            "quantity_ordered", "quantity_received", "unit_price", "line_total", "notes"
        ]
        read_only_fields = ["quantity_received", "line_total"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    delivery_location_name = serializers.ReadOnlyField(source="delivery_location.name")
    delivery_location_code = serializers.ReadOnlyField(source="delivery_location.code")
    issued_by_username = serializers.ReadOnlyField(source="issued_by.username")
    requisition_number = serializers.ReadOnlyField(source="requisition.requisition_number")
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "requisition", "requisition_number",
            "supplier", "supplier_name",
            "delivery_location", "delivery_location_code", "delivery_location_name",
            "status", "issued_by", "issued_by_username", "issued_at",
            "delivery_due_date", "payment_terms",
            "subtotal", "tax_amount", "total_amount",
            "notes", "cancellation_reason", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "po_number", "status", "issued_by", "issued_by_username", "issued_at",
            "subtotal", "tax_amount", "total_amount", "items", "created_at", "updated_at"
        ]


class GoodsReceiptNoteItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    batch_number_display = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = GoodsReceiptNoteItem
        fields = [
            "id", "grn", "po_item", "item", "item_name", "item_code", "item_unit",
            "quantity_received", "quantity_rejected", "rejection_reason",
            "batch", "batch_number_display", "batch_number", "supplier_batch_number",
            "expiry_date", "unit_cost", "total_cost", "notes"
        ]
        read_only_fields = ["batch", "batch_number_display", "total_cost"]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    received_by_username = serializers.ReadOnlyField(source="received_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = GoodsReceiptNoteItemSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "id", "grn_number", "purchase_order", "po_number",
            "supplier", "supplier_name",
            "location", "location_code", "location_name",
            "delivery_note_number", "status",
            "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number",
            "total_received_cost", "notes", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "grn_number", "status", "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number", "total_received_cost", "items",
            "created_at", "updated_at"
        ]


class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = SupplierInvoiceItem
        fields = [
            "id", "invoice", "po_item", "grn_item", "item", "item_name", "item_code", "item_unit",
            "billed_quantity", "billed_unit_price", "line_total", "price_variance", "is_matched"
        ]
        read_only_fields = ["line_total", "price_variance", "is_matched"]


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    matched_by_username = serializers.ReadOnlyField(source="matched_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id", "internal_number", "vendor_invoice_number",
            "supplier", "supplier_name",
            "purchase_order", "po_number",
            "invoice_date", "due_date",
            "subtotal", "tax_amount", "total_amount",
            "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "variance_notes", "journal_entry", "journal_entry_number",
            "is_paid", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "internal_number", "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "journal_entry", "journal_entry_number", "is_paid", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "transfer_number",
            "status",
            "requested_by",
            "requested_by_username",
            "dispatched_by",
            "dispatched_by_username",
            "received_by",
            "received_by_username",
            "requested_at",
            "dispatched_at",
            "received_at",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "transfer_number",
            "status",
            "requested_by",
            "requested_by_username",
            "dispatched_by",
            "dispatched_by_username",
            "received_by",
            "received_by_username",
            "requested_at",
            "dispatched_at",
            "received_at",
            "items",
            "created_at",
            "updated_at",
        ]


class ProcurementApprovalTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementApprovalTier
        fields = [
            "id", "policy", "tier_level", "name", "min_amount", "max_amount", "required_role", "created_at"
        ]


class ProcurementApprovalPolicySerializer(serializers.ModelSerializer):
    tiers = ProcurementApprovalTierSerializer(many=True, read_only=True)

    class Meta:
        model = ProcurementApprovalPolicy
        fields = [
            "id", "name", "description", "is_active", "currency", "price_tolerance_percentage", "tiers", "created_at", "updated_at"
        ]


class PurchaseRequisitionItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseRequisitionItem
        fields = [
            "id", "requisition", "item", "item_name", "item_code", "item_unit",
            "quantity_requested", "estimated_unit_cost", "notes"
        ]


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.ReadOnlyField(source="requested_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    approval_tier_name = serializers.ReadOnlyField(source="approval_tier.name")
    items = PurchaseRequisitionItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id", "requisition_number", "department", "status",
            "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name",
            "approved_by", "approved_by_username", "approved_at",
            "rejection_reason", "total_estimated_amount", "notes",
            "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "requisition_number", "status", "requested_by", "requested_by_username", "requested_at",
            "approval_tier", "approval_tier_name", "approved_by", "approved_by_username", "approved_at",
            "total_estimated_amount", "items", "created_at", "updated_at"
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id", "purchase_order", "item", "item_name", "item_code", "item_unit",
            "quantity_ordered", "quantity_received", "unit_price", "line_total", "notes"
        ]
        read_only_fields = ["quantity_received", "line_total"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    delivery_location_name = serializers.ReadOnlyField(source="delivery_location.name")
    delivery_location_code = serializers.ReadOnlyField(source="delivery_location.code")
    issued_by_username = serializers.ReadOnlyField(source="issued_by.username")
    requisition_number = serializers.ReadOnlyField(source="requisition.requisition_number")
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "requisition", "requisition_number",
            "supplier", "supplier_name",
            "delivery_location", "delivery_location_code", "delivery_location_name",
            "status", "issued_by", "issued_by_username", "issued_at",
            "delivery_due_date", "payment_terms",
            "subtotal", "tax_amount", "total_amount",
            "notes", "cancellation_reason", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "po_number", "status", "issued_by", "issued_by_username", "issued_at",
            "subtotal", "tax_amount", "total_amount", "items", "created_at", "updated_at"
        ]


class GoodsReceiptNoteItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    batch_number_display = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = GoodsReceiptNoteItem
        fields = [
            "id", "grn", "po_item", "item", "item_name", "item_code", "item_unit",
            "quantity_received", "quantity_rejected", "rejection_reason",
            "batch", "batch_number_display", "batch_number", "supplier_batch_number",
            "expiry_date", "unit_cost", "total_cost", "notes"
        ]
        read_only_fields = ["batch", "batch_number_display", "total_cost"]


class GoodsReceiptNoteSerializer(serializers.ModelSerializer):
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    received_by_username = serializers.ReadOnlyField(source="received_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = GoodsReceiptNoteItemSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceiptNote
        fields = [
            "id", "grn_number", "purchase_order", "po_number",
            "supplier", "supplier_name",
            "location", "location_code", "location_name",
            "delivery_note_number", "status",
            "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number",
            "total_received_cost", "notes", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "grn_number", "status", "received_by", "received_by_username", "received_at",
            "journal_entry", "journal_entry_number", "total_received_cost", "items",
            "created_at", "updated_at"
        ]


class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")

    class Meta:
        model = SupplierInvoiceItem
        fields = [
            "id", "invoice", "po_item", "grn_item", "item", "item_name", "item_code", "item_unit",
            "billed_quantity", "billed_unit_price", "line_total", "price_variance", "is_matched"
        ]
        read_only_fields = ["line_total", "price_variance", "is_matched"]


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    po_number = serializers.ReadOnlyField(source="purchase_order.po_number")
    matched_by_username = serializers.ReadOnlyField(source="matched_by.username")
    approved_by_username = serializers.ReadOnlyField(source="approved_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id", "internal_number", "vendor_invoice_number",
            "supplier", "supplier_name",
            "purchase_order", "po_number",
            "invoice_date", "due_date",
            "subtotal", "tax_amount", "total_amount",
            "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "variance_notes", "journal_entry", "journal_entry_number",
            "is_paid", "items", "created_at", "updated_at"
        ]
        read_only_fields = [
            "internal_number", "match_status", "matched_by", "matched_by_username", "matched_at",
            "approved_by", "approved_by_username", "approved_at",
            "journal_entry", "journal_entry_number", "is_paid", "items", "created_at", "updated_at"
        ]


class StocktakeItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    batch_number = serializers.ReadOnlyField(source="batch.batch_number")

    class Meta:
        model = StocktakeItem
        fields = [
            "id",
            "session",
            "item",
            "item_name",
            "item_code",
            "item_unit",
            "batch",
            "batch_number",
            "theoretical_quantity",
            "counted_quantity",
            "recounted_quantity",
            "final_quantity",
            "unit_cost_snapshot",
            "variance_quantity",
            "variance_value",
            "requires_recount",
            "notes",
            "counted_at",
        ]
        read_only_fields = [
            "session",
            "theoretical_quantity",
            "recounted_quantity",
            "final_quantity",
            "unit_cost_snapshot",
            "variance_quantity",
            "variance_value",
            "requires_recount",
            "counted_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_admin = bool(
            user and (
                user.is_superuser
                or getattr(user, "role", "") in ("admin", "hotel_manager")
            )
        )
        if (
            instance.session.counting_mode == "blind"
            and instance.session.status in ("draft", "in_progress")
            and not is_admin
        ):
            data["theoretical_quantity"] = None
            data["variance_quantity"] = None
            data["variance_value"] = None
        return data


class StocktakeSessionSerializer(serializers.ModelSerializer):
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    category_name = serializers.ReadOnlyField(source="category.name")
    created_by_username = serializers.ReadOnlyField(source="created_by.username")
    counted_by_username = serializers.ReadOnlyField(source="counted_by.username")
    reviewed_by_username = serializers.ReadOnlyField(source="reviewed_by.username")
    journal_entry_number = serializers.ReadOnlyField(source="journal_entry.entry_number")
    items = StocktakeItemSerializer(many=True, read_only=True)

    class Meta:
        model = StocktakeSession
        fields = [
            "id",
            "session_number",
            "title",
            "location",
            "location_name",
            "location_code",
            "category",
            "category_name",
            "counting_mode",
            "is_mode_locked",
            "status",
            "snapshot_at",
            "created_by",
            "created_by_username",
            "counted_by",
            "counted_by_username",
            "counted_at",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "variance_approval_notes",
            "total_theoretical_value",
            "total_counted_value",
            "total_variance_value",
            "journal_entry",
            "journal_entry_number",
            "schedule",
            "scheduled_date",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "session_number",
            "is_mode_locked",
            "status",
            "snapshot_at",
            "created_by",
            "created_by_username",
            "counted_by",
            "counted_by_username",
            "counted_at",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "total_theoretical_value",
            "total_counted_value",
            "total_variance_value",
            "journal_entry",
            "journal_entry_number",
            "schedule",
            "scheduled_date",
            "items",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_admin = bool(
            user and (
                user.is_superuser
                or getattr(user, "role", "") in ("admin", "hotel_manager")
            )
        )
        if (
            instance.counting_mode == "blind"
            and instance.status in ("draft", "in_progress")
            and not is_admin
        ):
            data["total_theoretical_value"] = None
            data["total_variance_value"] = None
        return data

    def validate(self, attrs):
        if self.instance and self.instance.is_mode_locked:
            new_mode = attrs.get("counting_mode") or self.initial_data.get("counting_mode")
            if new_mode and new_mode != self.instance.counting_mode:
                raise serializers.ValidationError(
                    {"counting_mode": "Counting mode is locked and cannot be changed once counting has begun."}
                )
        return attrs


# ── Request for Quotation (RFQ) & Supplier Quotation Serializers ─────────────

class RequestForQuotationItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    requisition_number = serializers.ReadOnlyField(source="requisition_item.requisition.requisition_number")

    class Meta:
        model = RequestForQuotationItem
        fields = [
            "id", "rfq", "item", "item_name", "item_code", "item_unit",
            "requisition_item", "requisition_number", "target_quantity", "specifications"
        ]


class RequestForQuotationSerializer(serializers.ModelSerializer):
    delivery_location_name = serializers.ReadOnlyField(source="delivery_location.name")
    delivery_location_code = serializers.ReadOnlyField(source="delivery_location.code")
    created_by_username = serializers.ReadOnlyField(source="created_by.username")
    items = RequestForQuotationItemSerializer(many=True, read_only=True)
    requisition_numbers = serializers.SerializerMethodField(read_only=True)
    invited_supplier_names = serializers.SerializerMethodField(read_only=True)

    def get_requisition_numbers(self, obj):
        return [req.requisition_number for req in obj.requisitions.all()]

    def get_invited_supplier_names(self, obj):
        return [supp.name for supp in obj.invited_suppliers.all()]

    class Meta:
        model = RequestForQuotation
        fields = [
            "id", "rfq_number", "title",
            "requisitions", "requisition_numbers",
            "is_public_bidding", "invited_suppliers", "invited_supplier_names",
            "status", "submission_deadline",
            "delivery_location", "delivery_location_name", "delivery_location_code",
            "terms_and_conditions",
            "created_by", "created_by_username", "items",
            "created_at", "updated_at"
        ]
        read_only_fields = [
            "rfq_number", "status", "created_by", "created_by_username", "items",
            "created_at", "updated_at"
        ]


class SupplierQuotationItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    converted_po_number = serializers.ReadOnlyField(source="converted_purchase_order.po_number")

    class Meta:
        model = SupplierQuotationItem
        fields = [
            "id", "quotation", "item", "item_name", "item_code", "item_unit",
            "rfq_item", "quoted_quantity", "quoted_unit_price", "discount_percentage",
            "line_total", "offered_brand_or_spec", "lead_time_days",
            "award_status", "is_converted_to_po", "converted_purchase_order", "converted_po_number",
            "converted_quantity", "notes"
        ]
        read_only_fields = [
            "line_total", "award_status", "is_converted_to_po", "converted_purchase_order",
            "converted_po_number", "converted_quantity"
        ]

    def validate(self, attrs):
        if self.instance and self.instance.quotation.status in (
            "accepted", "partially_awarded", "converted_to_po", "rejected", "expired"
        ):
            raise serializers.ValidationError("Quotation item is locked and cannot be modified.")
        return attrs


class SupplierQuotationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source="supplier.name")
    rfq_number = serializers.ReadOnlyField(source="rfq.rfq_number")
    requisition_number = serializers.ReadOnlyField(source="requisition.requisition_number")
    evaluated_by_username = serializers.ReadOnlyField(source="evaluated_by.username")
    accepted_by_username = serializers.ReadOnlyField(source="accepted_by.username")
    created_by_username = serializers.ReadOnlyField(source="created_by.username")
    items = SupplierQuotationItemSerializer(many=True, read_only=True)
    purchase_order_numbers = serializers.SerializerMethodField(read_only=True)

    def get_purchase_order_numbers(self, obj):
        return [po.po_number for po in obj.purchase_orders.all()]

    class Meta:
        model = SupplierQuotation
        fields = [
            "id", "quotation_number", "supplier_reference",
            "rfq", "rfq_number", "requisition", "requisition_number",
            "sole_source_justification",
            "supplier", "supplier_name",
            "quotation_date", "valid_until", "delivery_lead_time_days",
            "payment_terms", "warranty_terms",
            "currency", "exchange_rate",
            "subtotal", "tax_amount", "shipping_and_handling", "customs_and_duties",
            "total_quoted_amount", "total_landed_cost_etb",
            "status",
            "evaluated_by", "evaluated_by_username", "evaluated_at", "evaluation_notes",
            "accepted_by", "accepted_by_username", "accepted_at", "acceptance_justification",
            "rejection_reason", "rejected_at",
            "purchase_order_numbers", "items",
            "created_by", "created_by_username", "created_at", "updated_at"
        ]
        read_only_fields = [
            "quotation_number", "subtotal", "total_quoted_amount", "total_landed_cost_etb",
            "status", "evaluated_by", "evaluated_by_username", "evaluated_at",
            "accepted_by", "accepted_by_username", "accepted_at",
            "rejection_reason", "rejected_at",
            "purchase_order_numbers", "items",
            "created_by", "created_by_username", "created_at", "updated_at"
        ]

    def validate(self, attrs):
        if self.instance and self.instance.status in (
            "accepted", "partially_awarded", "converted_to_po", "rejected", "expired"
        ):
            raise serializers.ValidationError(
                f"Quotation #{self.instance.quotation_number} is locked in status '{self.instance.status}' and cannot be modified via API."
            )
        return attrs


class InventoryExpiryAlertSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source="item.name")
    item_code = serializers.ReadOnlyField(source="item.item_code")
    item_unit = serializers.ReadOnlyField(source="item.unit")
    is_perishable = serializers.ReadOnlyField(source="item.is_perishable")
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = InventoryExpiryAlert
        fields = [
            "id", "batch", "item", "item_name", "item_code", "item_unit", "is_perishable",
            "location", "location_name", "location_code",
            "alert_type", "alert_type_display", "threshold_days", "batch_number",
            "expiry_date", "days_left", "current_quantity",
            "status", "status_display", "resolved_at", "resolution_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "batch", "item", "location", "alert_type", "threshold_days",
            "batch_number", "expiry_date", "current_quantity",
            "resolved_at", "resolution_reason", "created_at", "updated_at",
        ]

    def get_days_left(self, obj):
        if not obj.expiry_date:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        return (obj.expiry_date - today).days


class StocktakeScheduleSerializer(serializers.ModelSerializer):
    location_name = serializers.ReadOnlyField(source="location.name")
    location_code = serializers.ReadOnlyField(source="location.code")
    category_name = serializers.ReadOnlyField(source="category.name")
    assigned_staff_username = serializers.ReadOnlyField(source="assigned_staff.username")
    created_by_username = serializers.ReadOnlyField(source="created_by.username")
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = StocktakeSchedule
        fields = [
            "id", "name", "frequency", "frequency_display",
            "location", "location_name", "location_code",
            "category", "category_name",
            "counting_mode", "assigned_staff", "assigned_staff_username",
            "is_active", "scheduled_time", "day_of_week", "day_of_month",
            "last_run_at", "last_run_status", "last_error_message",
            "next_run_at", "is_overdue",
            "created_by", "created_by_username", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "last_run_at", "last_run_status", "last_error_message",
            "next_run_at", "created_by", "created_by_username",
            "created_at", "updated_at",
        ]

    def get_is_overdue(self, obj):
        if not obj.is_active or not obj.next_run_at:
            return False
        from django.utils import timezone
        return obj.next_run_at < timezone.now()

    def create(self, validated_data):
        from hotel.stocktaking import compute_next_run
        req = self.context.get("request")
        user = req.user if req else validated_data.get("created_by")
        validated_data["created_by"] = user
        next_run = compute_next_run(
            frequency=validated_data.get("frequency", "daily"),
            scheduled_time=validated_data.get("scheduled_time", "06:00"),
            day_of_week=validated_data.get("day_of_week"),
            day_of_month=validated_data.get("day_of_month"),
        )
        validated_data["next_run_at"] = next_run
        return super().create(validated_data)

    def update(self, instance, validated_data):
        from hotel.stocktaking import compute_next_run
        freq = validated_data.get("frequency", instance.frequency)
        sched_time = validated_data.get("scheduled_time", instance.scheduled_time)
        dow = validated_data.get("day_of_week", instance.day_of_week)
        dom = validated_data.get("day_of_month", instance.day_of_month)

        if (freq != instance.frequency or sched_time != instance.scheduled_time or
            dow != instance.day_of_week or dom != instance.day_of_month):
            validated_data["next_run_at"] = compute_next_run(
                frequency=freq,
                scheduled_time=sched_time,
                day_of_week=dow,
                day_of_month=dom,
            )
        return super().update(instance, validated_data)

