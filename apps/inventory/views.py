"""Inventory API views extracted from the legacy facade."""
from decimal import Decimal, ROUND_HALF_UP
import datetime

TWOPLACES = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hotel.models import (
    BatchLocationBalance,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
    InventoryExpiryAlert,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    MenuItem,
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
from hotel.inventory import evaluate_inventory_expiry_alerts
from hotel.procurement import (
    approve_purchase_requisition,
    approve_supplier_invoice,
    close_request_for_quotation,
    convert_awarded_quotations_to_purchase_orders,
    convert_requisition_to_purchase_order,
    create_request_for_quotation,
    ensure_default_procurement_policy,
    evaluate_and_award_quotations,
    evaluate_quotation,
    match_and_record_supplier_invoice,
    publish_request_for_quotation,
    receive_goods_receipt_note,
    reject_purchase_requisition,
    request_purchase_requisition,
    submit_supplier_quotation,
)
from hotel.stocktaking import (
    approve_stocktake_session,
    cancel_stocktake_session,
    compute_next_run,
    create_stocktake_session,
    process_due_stocktake_schedules,
    record_counts,
    request_recount,
    submit_recount,
)
from hotel.transfers import (
    cancel_stock_transfer,
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.permissions import (
    HasStocktakeLocationPermission,
    IsAdminOrReadOnly,
    IsBatchOperator,
    IsFinanceStaff,
    IsHotelAdmin,
    IsInventoryManager,
    IsProcurementOperator,
    IsProcurementOrFinanceOperator,
    IsPurchaseRequisitionStaff,
    IsSupplierOperator,
)
from apps.finance.services import post_journal_entry

from .selectors import select_inventory_items, select_stock_transactions
from .serializers import (
    BatchLocationBalanceSerializer,
    GoodsReceiptNoteItemSerializer,
    GoodsReceiptNoteSerializer,
    InventoryCategorySerializer,
    InventoryExpiryAlertSerializer,
    InventoryItemSerializer,
    InventoryWasteRecordSerializer,
    ItemLocationBalanceSerializer,
    ProcurementApprovalPolicySerializer,
    ProcurementApprovalTierSerializer,
    PurchaseOrderItemSerializer,
    PurchaseOrderSerializer,
    PurchaseRequisitionItemSerializer,
    PurchaseRequisitionSerializer,
    RecipeBOMSerializer,
    RequestForQuotationItemSerializer,
    RequestForQuotationSerializer,
    StockBatchSerializer,
    StockLocationSerializer,
    StocktakeItemSerializer,
    StocktakeScheduleSerializer,
    StocktakeSessionSerializer,
    StockTransactionSerializer,
    StockTransferItemSerializer,
    StockTransferSerializer,
    SupplierInvoiceItemSerializer,
    SupplierInvoiceSerializer,
    SupplierQuotationItemSerializer,
    SupplierQuotationSerializer,
    SupplierSerializer,
)
from .services import (
    approve_waste_entry,
    record_stock_change,
    record_waste_entry,
    reject_waste_entry,
    reverse_stock_transaction,
    reverse_waste_entry,
)

class InventoryCategoryViewSet(viewsets.ModelViewSet):
    queryset = InventoryCategory.objects.all()
    serializer_class = InventoryCategorySerializer
    permission_classes = [IsInventoryManager]

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsSupplierOperator]

class InventoryItemViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return select_inventory_items(self.request.query_params)

    serializer_class = InventoryItemSerializer
    permission_classes = [IsInventoryManager]

class StockTransactionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return select_stock_transactions(self.request.query_params)

    serializer_class = StockTransactionSerializer
    permission_classes = [IsInventoryManager]

    def update(self, request, *args, **kwargs):
        return Response({"error": "Stock history is immutable."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Stock history is immutable; reverse it instead."}, status=405)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        if request.user.role not in ("admin", "inventory", "hotel_manager") and not request.user.is_superuser:
            return Response({"error": "Inventory manager, hotel manager, or administrator role required."}, status=403)
        try:
            reversal, created = reverse_stock_transaction(
                transaction_id=pk,
                reason=request.data.get("reason"),
                logged_by_username=request.user.username,
            )
        except StockTransaction.DoesNotExist:
            return Response({"error": "Stock transaction not found."}, status=404)
        return Response(StockTransactionSerializer(reversal).data, status=201 if created else 200)

    def create(self, request, *args, **kwargs):
        idempotency_key = (
            request.headers.get("Idempotency-Key")
            or request.META.get("HTTP_IDEMPOTENCY_KEY")
            or request.data.get("idempotency_key")
        )
        if idempotency_key:
            idempotency_key = str(idempotency_key).strip()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with transaction.atomic():
                item, transaction_inst = record_stock_change(
                    item_id=data["item"].pk,
                    transaction_type=data["transaction_type"],
                    quantity=data["quantity"],
                    unit_cost=data["unit_cost"],
                    adjustment_direction=data.get("adjustment_direction"),
                    idempotency_key=idempotency_key,
                    supplier=data.get("supplier"),
                    location=data.get("location"),
                    batch=data.get("batch"),
                    batch_number=data.get("batch_number_input") or request.data.get("batch_number"),
                    expiry_date=data.get("expiry_date_input") or request.data.get("expiry_date"),
                    reference_number=data.get("reference_number"),
                    notes=data.get("notes"),
                    destination_dept=data.get("destination_dept"),
                    destination_room=data.get("destination_room"),
                    logged_by_username=request.user.username if request.user else "system",
                )

                is_replay = getattr(transaction_inst, "_is_replay", False)

                # Post General Ledger Journal Entry only on initial creation
                if not is_replay:
                    consumptions = list(transaction_inst.batch_consumptions.all())
                    if consumptions:
                        total_cost = sum((c.total_cost for c in consumptions), Decimal("0.00"))
                    else:
                        total_cost = to_decimal(transaction_inst.quantity * transaction_inst.unit_cost)
                    qty = transaction_inst.quantity
                    if total_cost > 0:
                        try:
                            if transaction_inst.transaction_type == "purchase":
                                pay_acct = "2000" if transaction_inst.supplier else "1000"
                                post_journal_entry(
                                    description=f"Auto JV: Inventory Purchase - {item.name} ({qty} {item.unit})",
                                    items=[
                                        {
                                            "account_code": "1300",  # Inventory Asset
                                            "debit": total_cost,
                                            "credit": Decimal("0.00"),
                                        },
                                        {
                                            "account_code": pay_acct,  # Cash or Accounts Payable
                                            "debit": Decimal("0.00"),
                                            "credit": total_cost,
                                        },
                                    ],
                                )
                            elif transaction_inst.transaction_type == "issuance":
                                post_journal_entry(
                                    description=f"Auto JV: Inventory Issuance - {item.name} ({qty} {item.unit})",
                                    items=[
                                        {
                                            "account_code": "5000",  # COGS
                                            "debit": total_cost,
                                            "credit": Decimal("0.00"),
                                        },
                                        {
                                            "account_code": "1300",  # Inventory Asset
                                            "debit": Decimal("0.00"),
                                            "credit": total_cost,
                                        },
                                    ],
                                )
                            elif transaction_inst.transaction_type == "adjustment":
                                if transaction_inst.adjustment_direction == "increase":
                                    post_journal_entry(
                                        description=f"Auto JV: Inventory Adjustment (Increase) - {item.name} ({qty} {item.unit})",
                                        items=[
                                            {
                                                "account_code": "1300",  # Inventory Asset
                                                "debit": total_cost,
                                                "credit": Decimal("0.00"),
                                            },
                                            {
                                                "account_code": "5000",  # COGS / Gain
                                                "debit": Decimal("0.00"),
                                                "credit": total_cost,
                                            },
                                        ],
                                    )
                                elif transaction_inst.adjustment_direction == "decrease":
                                    post_journal_entry(
                                        description=f"Auto JV: Inventory Adjustment (Decrease) - {item.name} ({qty} {item.unit})",
                                        items=[
                                            {
                                                "account_code": "5000",  # COGS / Shrinkage
                                                "debit": total_cost,
                                                "credit": Decimal("0.00"),
                                            },
                                            {
                                                "account_code": "1300",  # Inventory Asset
                                                "debit": Decimal("0.00"),
                                                "credit": total_cost,
                                            },
                                        ],
                                    )
                        except Exception as e:
                            print(f"GL Auto-post error for stock transaction: {e}")

        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "Idempotency key was already used for a different" in msg:
                return Response({"error": msg}, status=status.HTTP_409_CONFLICT)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = self.get_serializer(transaction_inst)
        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK if is_replay else status.HTTP_201_CREATED,
        )

class RecipeBOMViewSet(viewsets.ModelViewSet):
    queryset = RecipeBOM.objects.all()
    serializer_class = RecipeBOMSerializer
    permission_classes = [IsInventoryManager]

    @action(detail=False, methods=["post"], url_path="bulk-save")
    def bulk_save(self, request):
        menu_item_id = request.data.get("menu_item")
        ingredients = request.data.get("ingredients", [])

        if not menu_item_id:
            return Response({"error": "menu_item is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            menu_item = MenuItem.objects.get(id=menu_item_id)
        except MenuItem.DoesNotExist:
            return Response({"error": "Menu item not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            RecipeBOM.objects.filter(menu_item=menu_item).delete()
            for ing_data in ingredients:
                ing_id = ing_data.get("ingredient")
                qty = ing_data.get("quantity_required")
                if not ing_id or qty is None or float(qty) <= 0:
                    continue
                try:
                    ingredient = InventoryItem.objects.get(id=ing_id)
                    RecipeBOM.objects.create(
                        menu_item=menu_item,
                        ingredient=ingredient,
                        quantity_required=Decimal(str(qty)),
                    )
                except InventoryItem.DoesNotExist:
                    pass

        return Response({"status": "success", "message": "Recipe mapped successfully"})

class InventoryDashboardStatsView(APIView):
    permission_classes = [IsInventoryManager]

    def get(self, request):
        items = InventoryItem.objects.select_related("category")
        total_items = items.count()
        total_valuation = (
            items.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("current_stock") * F("unit_cost"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                )
            )["total"]
            or 0
        )
        low_stock_items = items.filter(current_stock__lt=F("min_reorder_level"))
        low_stock_count = low_stock_items.count()
        suppliers_count = Supplier.objects.count()

        low_stock_list = []
        for item in low_stock_items:
            low_stock_list.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "item_code": item.item_code,
                    "current_stock": float(item.current_stock),
                    "min_reorder_level": float(item.min_reorder_level),
                    "unit": item.unit,
                    "category_name": item.category.name,
                }
            )

        return Response(
            {
                "total_items": total_items,
                "total_valuation": float(total_valuation),
                "low_stock_count": low_stock_count,
                "suppliers_count": suppliers_count,
                "low_stock_items": low_stock_list,
            },
            status=status.HTTP_200_OK,
        )

class InventoryWasteRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInventoryManager]
    serializer_class = InventoryWasteRecordSerializer

    def get_queryset(self):
        qs = InventoryWasteRecord.objects.select_related("item", "source_dispatch", "stock_transaction").all()
        item_id = self.request.query_params.get("item")
        category = self.request.query_params.get("category")
        source = self.request.query_params.get("source")
        status_param = self.request.query_params.get("status")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if category:
            qs = qs.filter(waste_category=category)
        if source:
            qs = qs.filter(waste_source=source)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs.order_by("-recorded_at")

    def create(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key") or request.data.get("idempotency_key")
        if not idempotency_key or not str(idempotency_key).strip():
            return Response({"error": "An Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)

        item_id = request.data.get("item")
        entered_qty = request.data.get("entered_quantity")
        entered_unit = request.data.get("entered_unit")
        waste_category = request.data.get("waste_category")
        waste_source = request.data.get("waste_source")
        notes = request.data.get("notes", "")
        storage_area = request.data.get("storage_area", "")
        source_dispatch_id = request.data.get("source_dispatch")

        if not item_id or entered_qty is None or not entered_unit or not waste_category or not waste_source:
            return Response(
                {"error": "item, entered_quantity, entered_unit, waste_category, and waste_source are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record, created = record_waste_entry(
                item_id=item_id,
                entered_quantity=entered_qty,
                entered_unit=entered_unit,
                waste_category=waste_category,
                waste_source=waste_source,
                idempotency_key=str(idempotency_key).strip(),
                notes=notes,
                storage_area=storage_area,
                source_dispatch_id=source_dispatch_id,
                logged_by_username=request.user.username if request.user else "system",
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "Idempotency key was already used for a different" in msg:
                return Response({"error": msg}, status=status.HTTP_409_CONFLICT)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return Response({"error": "Waste records are immutable; reverse them instead."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Waste records are immutable; reverse them instead."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin" and not getattr(request.user, "is_superuser", False):
            return Response({"error": "Administrator role required to approve waste."}, status=status.HTTP_403_FORBIDDEN)

        justification = request.data.get("justification", "")
        try:
            waste = approve_waste_entry(
                waste_id=pk,
                reviewer=request.user,
                justification=justification,
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "independent administrator review is required" in msg or "cannot approve their own" in msg:
                return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(waste)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin" and not getattr(request.user, "is_superuser", False):
            return Response({"error": "Administrator role required to reject waste."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get("reason")
        if not reason or not str(reason).strip():
            return Response({"error": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        justification = request.data.get("justification", "")
        try:
            waste = reject_waste_entry(
                waste_id=pk,
                reviewer=request.user,
                reason=reason,
                justification=justification,
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            if "independent administrator review is required" in msg or "cannot reject their own" in msg:
                return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(waste)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        if request.user.role not in ("admin", "inventory", "hotel_manager") and not request.user.is_superuser:
            return Response({"error": "Inventory manager, hotel manager, or administrator role required."}, status=status.HTTP_403_FORBIDDEN)
        reason = request.data.get("reason")
        if not reason or not str(reason).strip():
            return Response({"error": "A reversal reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reversal, created = reverse_waste_entry(
                waste_id=pk,
                reason=reason,
                logged_by_username=request.user.username if request.user else "system",
            )
        except InventoryWasteRecord.DoesNotExist:
            return Response({"error": "Waste record not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(reversal)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class StockLocationViewSet(viewsets.ModelViewSet):
    queryset = StockLocation.objects.all()
    serializer_class = StockLocationSerializer
    permission_classes = [IsInventoryManager]

class StockBatchViewSet(viewsets.ModelViewSet):
    serializer_class = StockBatchSerializer
    permission_classes = [IsBatchOperator]

    def get_queryset(self):
        qs = StockBatch.objects.select_related("item", "supplier", "verified_by").all()
        item_id = self.request.query_params.get("item")
        status_param = self.request.query_params.get("status")
        is_legacy = self.request.query_params.get("is_legacy")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if is_legacy is not None:
            qs = qs.filter(is_legacy=is_legacy.lower() in ("true", "1"))
        return qs

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        """Verify an unverified legacy perishable batch with physical inspection and verified expiry."""
        if getattr(request.user, "role", "") not in ("admin", "inventory", "kitchen") and not getattr(request.user, "is_superuser", False):
            return Response({"error": "Inventory manager, chef, or administrator role required to verify batches."}, status=status.HTTP_403_FORBIDDEN)

        batch = self.get_object()
        expiry_date = request.data.get("expiry_date")
        notes = request.data.get("verification_notes", "").strip()

        if not expiry_date:
            return Response({"error": "A verified expiry date is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            exp_d = datetime.date.fromisoformat(str(expiry_date))
        except ValueError:
            return Response({"error": "Invalid expiry date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        if exp_d < timezone.now().date():
            return Response({"error": "Cannot verify batch with a past expiry date. Expired stock must be routed to waste."}, status=status.HTTP_400_BAD_REQUEST)

        batch.expiry_date = exp_d
        batch.status = "active"
        batch.verified_by = request.user
        batch.verified_at = timezone.now()
        batch.verification_notes = notes or f"Verified by {request.user.username} on {timezone.now().date()}."
        batch.save(update_fields=["expiry_date", "status", "verified_by", "verified_at", "verification_notes"])

        return Response(self.get_serializer(batch).data, status=status.HTTP_200_OK)

class BatchLocationBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BatchLocationBalance.objects.select_related("batch__item", "location").all()
    serializer_class = BatchLocationBalanceSerializer
    permission_classes = [IsInventoryManager]

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get("location")
        item_id = self.request.query_params.get("item")
        if location_id:
            qs = qs.filter(location_id=location_id)
        if item_id:
            qs = qs.filter(batch__item_id=item_id)
        return qs

class ItemLocationBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ItemLocationBalance.objects.select_related("item", "location").all()
    serializer_class = ItemLocationBalanceSerializer
    permission_classes = [IsInventoryManager]

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get("location")
        item_id = self.request.query_params.get("item")
        if location_id:
            qs = qs.filter(location_id=location_id)
        if item_id:
            qs = qs.filter(item_id=item_id)
        return qs

class StockTransferViewSet(viewsets.ModelViewSet):
    """
    Authoritative ViewSet for two-phase custody stock transfers.
    Requisition -> Dispatch (FEFO/FIFO source balance lock) -> Destination Receipt (Breakage write-off).
    """

    queryset = (
        StockTransfer.objects.select_related(
            "source_location",
            "destination_location",
            "requested_by",
            "dispatched_by",
            "received_by",
        )
        .prefetch_related("items__item", "items__batch", "items__waste_record")
        .order_by("-created_at")
    )
    serializer_class = StockTransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        source = self.request.query_params.get("source") or self.request.query_params.get("source_location")
        dest = self.request.query_params.get("destination") or self.request.query_params.get("destination_location")
        status_param = self.request.query_params.get("status")

        if source:
            if str(source).isdigit():
                qs = qs.filter(source_location_id=source)
            else:
                qs = qs.filter(source_location__code=source)
        if dest:
            if str(dest).isdigit():
                qs = qs.filter(destination_location_id=dest)
            else:
                qs = qs.filter(destination_location__code=dest)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        """Creates a stock transfer requisition in 'requested' status."""
        source = request.data.get("source_location") or request.data.get("source")
        dest = request.data.get("destination_location") or request.data.get("destination")
        items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        if not source or not dest:
            return Response(
                {"error": "Both source_location and destination_location are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            transfer = request_stock_transfer(
                source_location=source,
                destination_location=dest,
                requested_by=request.user,
                items=items,
                notes=notes,
            )
            serializer = self.get_serializer(transfer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {"error": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        transfer = self.get_object()
        if transfer.status not in ("draft", "requested"):
            return Response(
                {"error": f"Cannot modify transfer #{transfer.transfer_number} in '{transfer.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        transfer = self.get_object()
        if transfer.status not in ("draft", "requested"):
            return Response(
                {"error": f"Cannot modify transfer #{transfer.transfer_number} in '{transfer.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "Stock transfers cannot be deleted; cancel or reject the transfer instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_transfer(self, request, pk=None):
        """Phase 1: Source Storekeeper Dispatches items into in-transit custody."""
        items_dispatch = request.data.get("items")
        notes = request.data.get("notes", "")
        try:
            transfer = dispatch_stock_transfer(
                transfer_id=pk,
                dispatcher=request.user,
                items_dispatch=items_dispatch,
                notes=notes,
            )
            return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)
        except PermissionDenied as pe:
            return Response({"error": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as ve:
            return Response(
                {"error": ve.messages if hasattr(ve, "messages") else str(ve)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="receive")
    def receive_transfer(self, request, pk=None):
        """Phase 2: Destination Custodian confirms physical receipt at receiving door."""
        receipt_items = request.data.get("items")
        notes = request.data.get("notes", "")
        try:
            transfer = receive_stock_transfer(
                transfer_id=pk,
                receiver=request.user,
                receipt_items=receipt_items,
                notes=notes,
            )
            return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)
        except ValidationError as ve:
            return Response(
                {"error": ve.messages if hasattr(ve, "messages") else str(ve)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_transfer(self, request, pk=None):
        """Cancels a requested transfer or rejects in-transit delivery back to source."""
        reason = request.data.get("reason", "")
        try:
            transfer = cancel_stock_transfer(
                transfer_id=pk,
                user=request.user,
                reason=reason,
            )
            return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)
        except ValidationError as ve:
            return Response(
                {"error": ve.messages if hasattr(ve, "messages") else str(ve)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProcurementApprovalPolicyViewSet(viewsets.ModelViewSet):
    queryset = ProcurementApprovalPolicy.objects.prefetch_related("tiers").order_by("-is_active", "name")
    serializer_class = ProcurementApprovalPolicySerializer
    permission_classes = [IsInventoryManager]

class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requested_by", "approved_by", "approval_tier")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsPurchaseRequisitionStaff]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # Privileged staff: global property-wide visibility
        if user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory", "finance"}:
            status_param = self.request.query_params.get("status")
            dept = self.request.query_params.get("department")
            if status_param:
                qs = qs.filter(status=status_param)
            if dept:
                qs = qs.filter(department=dept)
            return qs

        # Departmental staff (kitchen, bar, housekeeping): strictly row-scoped
        user_role = getattr(user, "role", "").lower()
        return qs.filter(Q(requested_by=user) | Q(department__iexact=user_role))

    def create(self, request, *args, **kwargs):
        user = request.user
        user_role = getattr(user, "role", "").lower()
        department = request.data.get("department")
        delivery_location = request.data.get("delivery_location")
        items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        is_privileged = user.is_superuser or user_role in {"admin", "hotel_manager", "inventory"}

        # Departmental validation: non-privileged users cannot request for another department
        if not is_privileged:
            if department and department.lower() != user_role:
                return Response(
                    {"error": f"Staff with role '{user_role}' cannot submit requisitions for department '{department}'."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not department:
                department = user_role

        if not department:
            return Response({"error": "Department is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not items:
            return Response({"error": "Requisition items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req = request_purchase_requisition(
                requester=request.user,
                department=department,
                delivery_location=delivery_location,
                items=items,
                notes=notes,
            )
            serializer = self.get_serializer(req)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        req_obj = self.get_object()
        if req_obj.status not in ("draft", "rejected"):
            return Response(
                {"error": f"Cannot modify requisition #{req_obj.requisition_number} in '{req_obj.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "Purchase requisitions cannot be deleted; cancel or reject instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req_obj = self.get_object()
        notes = request.data.get("notes", "")
        try:
            req = approve_purchase_requisition(requisition_id=pk, approver=request.user, notes=notes)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        req_obj = self.get_object()
        reason = request.data.get("reason", "")
        if not reason or not str(reason).strip():
            return Response({"error": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            req = reject_purchase_requisition(requisition_id=req_obj.pk, rejecter=request.user, reason=reason)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="convert-to-po", permission_classes=[IsProcurementOperator])
    def convert_to_po(self, request, pk=None):
        supplier_id = request.data.get("supplier")
        delivery_location_id = request.data.get("delivery_location")
        delivery_due_date = request.data.get("delivery_due_date")
        payment_terms = request.data.get("payment_terms", "")
        item_prices = request.data.get("item_prices")
        notes = request.data.get("notes", "")

        if not supplier_id:
            return Response({"error": "Supplier is required to issue a Purchase Order."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            po = convert_requisition_to_purchase_order(
                requisition_id=pk,
                issuer=request.user,
                supplier_id=supplier_id,
                delivery_location_id=delivery_location_id,
                delivery_due_date=delivery_due_date,
                payment_terms=payment_terms,
                item_prices=item_prices,
                notes=notes,
            )
            serializer = PurchaseOrderSerializer(po)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.select_related("requisition", "supplier", "delivery_location", "issued_by")
        .prefetch_related("items__item", "grns")
        .order_by("-created_at")
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        supplier_id = self.request.query_params.get("supplier")
        status_param = self.request.query_params.get("status")
        po_number = self.request.query_params.get("po_number")
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if po_number:
            qs = qs.filter(po_number__icontains=po_number)
        return qs

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only inventory and procurement managers can create purchase orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only inventory and procurement managers can modify purchase orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        po = self.get_object()
        if po.status not in ("draft", "issued"):
            return Response(
                {"error": f"Cannot modify purchase order #{po.po_number} in '{po.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"error": "Purchase orders cannot be deleted; cancel instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="receive-grn", permission_classes=[IsProcurementOperator])
    def receive_grn(self, request, pk=None):
        delivery_note = request.data.get("delivery_note_number", "")
        location_id = request.data.get("location")
        receipt_items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        if not receipt_items:
            return Response({"error": "Receipt items are required for goods receipt."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grn = receive_goods_receipt_note(
                purchase_order_id=pk,
                receiver=request.user,
                delivery_note_number=delivery_note,
                location_id=location_id,
                receipt_items=receipt_items,
                notes=notes,
            )
            serializer = GoodsReceiptNoteSerializer(grn)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class GoodsReceiptNoteViewSet(viewsets.ModelViewSet):
    queryset = (
        GoodsReceiptNote.objects.select_related("purchase_order", "supplier", "location", "received_by", "journal_entry")
        .prefetch_related("items__item", "items__batch")
        .order_by("-created_at")
    )
    serializer_class = GoodsReceiptNoteSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        po_id = self.request.query_params.get("purchase_order")
        supplier_id = self.request.query_params.get("supplier")
        location_id = self.request.query_params.get("location")
        status_param = self.request.query_params.get("status")
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if location_id:
            qs = qs.filter(location_id=location_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Goods receiving is restricted to warehouse and inventory staff."},
                status=status.HTTP_403_FORBIDDEN,
            )
        po_id = request.data.get("purchase_order")
        delivery_note = request.data.get("delivery_note_number", "")
        location_id = request.data.get("location")
        receipt_items = request.data.get("items", [])
        notes = request.data.get("notes", "")

        if not po_id:
            return Response({"error": "purchase_order is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not receipt_items:
            return Response({"error": "Receipt items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grn = receive_goods_receipt_note(
                purchase_order_id=po_id,
                receiver=request.user,
                delivery_note_number=delivery_note,
                location_id=location_id,
                receipt_items=receipt_items,
                notes=notes,
            )
            serializer = self.get_serializer(grn)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierInvoice.objects.select_related("supplier", "purchase_order", "matched_by", "approved_by", "journal_entry")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = SupplierInvoiceSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        po_id = self.request.query_params.get("purchase_order")
        supplier_id = self.request.query_params.get("supplier")
        match_status_param = self.request.query_params.get("match_status")
        is_paid = self.request.query_params.get("is_paid")
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if match_status_param:
            qs = qs.filter(match_status=match_status_param)
        if is_paid is not None:
            qs = qs.filter(is_paid=is_paid.lower() in ("true", "1"))
        return qs

    def create(self, request, *args, **kwargs):
        po_id = request.data.get("purchase_order")
        vendor_inv_num = request.data.get("vendor_invoice_number")
        inv_date = request.data.get("invoice_date")
        due_date = request.data.get("due_date")
        billed_items = request.data.get("items", [])
        tax_amount = request.data.get("tax_amount", Decimal("0.00"))
        notes = request.data.get("notes", "")

        if not po_id or not vendor_inv_num or not inv_date or not billed_items:
            return Response(
                {"error": "purchase_order, vendor_invoice_number, invoice_date, and items are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            inv = match_and_record_supplier_invoice(
                purchase_order_id=po_id,
                vendor_invoice_number=vendor_inv_num,
                invoice_date=inv_date,
                due_date=due_date,
                billed_items=billed_items,
                matched_by=request.user,
                tax_amount=tax_amount,
                notes=notes,
            )
            serializer = self.get_serializer(inv)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="match-and-record")
    def match_and_record(self, request):
        return self.create(request)

    @action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsFinanceStaff])
    def approve(self, request, pk=None):
        override_variance = request.data.get("override_variance", False)
        if isinstance(override_variance, str):
            override_variance = override_variance.lower() in ("true", "1")
        justification = request.data.get("variance_justification", "")
        try:
            inv = approve_supplier_invoice(
                invoice_id=pk,
                approver=request.user,
                override_variance=override_variance,
                variance_justification=justification,
            )
            return Response(self.get_serializer(inv).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RequestForQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        RequestForQuotation.objects.select_related("delivery_location", "created_by")
        .prefetch_related("requisitions", "invited_suppliers", "items__item", "quotations")
        .order_by("-created_at")
    )
    serializer_class = RequestForQuotationSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only procurement officers can create RFQs."},
                status=status.HTTP_403_FORBIDDEN,
            )
        title = request.data.get("title")
        delivery_location_id = request.data.get("delivery_location")
        submission_deadline_str = request.data.get("submission_deadline")
        requisition_ids = request.data.get("requisition_ids") or request.data.get("requisitions", [])
        items_data = request.data.get("items", [])
        is_public_bidding = request.data.get("is_public_bidding", False)
        if isinstance(is_public_bidding, str):
            is_public_bidding = is_public_bidding.lower() in ("true", "1")
        invited_supplier_ids = request.data.get("invited_supplier_ids") or request.data.get("invited_suppliers", [])
        terms = request.data.get("terms_and_conditions", "")

        if not title:
            return Response({"error": "RFQ title is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not delivery_location_id:
            return Response({"error": "delivery_location is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not submission_deadline_str:
            return Response({"error": "submission_deadline is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            import dateutil.parser
            submission_deadline = dateutil.parser.isoparse(submission_deadline_str)
            if timezone.is_naive(submission_deadline):
                submission_deadline = timezone.make_aware(submission_deadline)
        except Exception:
            try:
                from django.utils.dateparse import parse_datetime
                submission_deadline = parse_datetime(submission_deadline_str)
                if not submission_deadline:
                    raise ValueError()
                if timezone.is_naive(submission_deadline):
                    submission_deadline = timezone.make_aware(submission_deadline)
            except Exception:
                return Response({"error": "Invalid submission_deadline ISO format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rfq = create_request_for_quotation(
                user=request.user,
                title=title,
                delivery_location_id=delivery_location_id,
                submission_deadline=submission_deadline,
                requisition_ids=requisition_ids,
                items_data=items_data,
                is_public_bidding=is_public_bidding,
                invited_supplier_ids=invited_supplier_ids,
                terms_and_conditions=terms,
            )
            serializer = self.get_serializer(rfq)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="publish", permission_classes=[IsProcurementOperator])
    def publish(self, request, pk=None):
        try:
            rfq = publish_request_for_quotation(rfq_id=pk, user=request.user)
            serializer = self.get_serializer(rfq)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="close", permission_classes=[IsProcurementOperator])
    def close_rfq(self, request, pk=None):
        notes = request.data.get("notes", "")
        try:
            rfq = close_request_for_quotation(rfq_id=pk, user=request.user, notes=notes)
            serializer = self.get_serializer(rfq)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SupplierQuotationViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierQuotation.objects.select_related("supplier", "rfq", "requisition", "evaluated_by", "accepted_by")
        .prefetch_related("items__item", "items__converted_purchase_order", "purchase_orders")
        .order_by("-created_at")
    )
    serializer_class = SupplierQuotationSerializer
    permission_classes = [IsProcurementOrFinanceOperator]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        rfq_param = self.request.query_params.get("rfq")
        supplier_param = self.request.query_params.get("supplier")
        if status_param:
            qs = qs.filter(status=status_param)
        if rfq_param:
            qs = qs.filter(rfq_id=rfq_param)
        if supplier_param:
            qs = qs.filter(supplier_id=supplier_param)
        return qs

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            return Response(
                {"error": "Only procurement officers can log supplier quotations."},
                status=status.HTTP_403_FORBIDDEN,
            )
        supplier_id = request.data.get("supplier") or request.data.get("supplier_id")
        rfq_id = request.data.get("rfq") or request.data.get("rfq_id")
        requisition_id = request.data.get("requisition") or request.data.get("requisition_id")
        sole_source = request.data.get("sole_source_justification", "")
        supplier_reference = request.data.get("supplier_reference", "")
        quotation_date = request.data.get("quotation_date")
        valid_until = request.data.get("valid_until")
        lead_time = request.data.get("delivery_lead_time_days", 1)
        payment_terms = request.data.get("payment_terms", "Net 30")
        warranty_terms = request.data.get("warranty_terms", "")
        currency = request.data.get("currency", "ETB")
        exchange_rate = request.data.get("exchange_rate", "1.0000")
        shipping = request.data.get("shipping_and_handling", "0.00")
        customs = request.data.get("customs_and_duties", "0.00")
        tax = request.data.get("tax_amount", "0.00")
        items_data = request.data.get("items", [])

        if not supplier_id:
            return Response({"error": "supplier is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not valid_until:
            return Response({"error": "valid_until date is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not items_data:
            return Response({"error": "Quotation must contain at least one line item."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quotation = submit_supplier_quotation(
                user=request.user,
                supplier_id=supplier_id,
                rfq_id=rfq_id,
                requisition_id=requisition_id,
                sole_source_justification=sole_source,
                supplier_reference=supplier_reference,
                quotation_date=quotation_date,
                valid_until=valid_until,
                delivery_lead_time_days=int(lead_time),
                payment_terms=payment_terms,
                warranty_terms=warranty_terms,
                currency=currency,
                exchange_rate=Decimal(str(exchange_rate)),
                shipping_and_handling=Decimal(str(shipping)),
                customs_and_duties=Decimal(str(customs)),
                tax_amount=Decimal(str(tax)),
                items_data=items_data,
            )
            serializer = self.get_serializer(quotation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="evaluate", permission_classes=[IsProcurementOperator])
    def evaluate(self, request, pk=None):
        notes = request.data.get("evaluation_notes", "")
        try:
            quotation = evaluate_quotation(quotation_id=pk, user=request.user, evaluation_notes=notes)
            serializer = self.get_serializer(quotation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="award", permission_classes=[IsProcurementOperator])
    def award_quotations(self, request):
        rfq_id = request.data.get("rfq_id")
        awards_data = request.data.get("awards_data") or request.data.get("awards", [])
        justification = request.data.get("justification", "")

        if not awards_data:
            return Response({"error": "awards_data is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not justification or not justification.strip():
            return Response(
                {"error": "A detailed managerial justification is mandatory when awarding quotations."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            affected = evaluate_and_award_quotations(
                rfq_id=rfq_id,
                awards_data=awards_data,
                user=request.user,
                justification=justification,
            )
            serializer = self.get_serializer(affected, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="convert-to-po", permission_classes=[IsProcurementOperator])
    def convert_to_po(self, request):
        quotation_ids = request.data.get("quotation_ids", [])
        if not quotation_ids and request.data.get("quotation_id"):
            quotation_ids = [request.data.get("quotation_id")]

        if not quotation_ids:
            return Response({"error": "quotation_ids is required."}, status=status.HTTP_400_BAD_REQUEST)

        delivery_location_id = request.data.get("delivery_location_id")

        try:
            pos = convert_awarded_quotations_to_purchase_orders(
                quotation_ids=quotation_ids,
                user=request.user,
                delivery_location_id=delivery_location_id,
            )
            from .serializers import PurchaseOrderSerializer
            serializer = PurchaseOrderSerializer(pos, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class StocktakeSessionViewSet(viewsets.ModelViewSet):
    """
    Authoritative ViewSet for Dual-Mode Physical Stocktaking Sessions.
    Implements counting, recounting, approval, cancellation, and audit preservation.
    """
    serializer_class = StocktakeSessionSerializer
    permission_classes = [HasStocktakeLocationPermission]

    def get_queryset(self):
        user = self.request.user
        qs = StocktakeSession.objects.all().select_related(
            "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
        ).prefetch_related("items__item")

        # Enforce location scoping for non-admin/management/inventory users
        if user and user.is_authenticated and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            from django.db.models import Q
            qs = qs.filter(
                Q(location__custodian=user)
                | Q(created_by=user)
                | Q(counted_by=user)
                | Q(schedule__assigned_staff=user)
            ).distinct()

        location_id = self.request.query_params.get("location")
        status_param = self.request.query_params.get("status")
        counting_mode = self.request.query_params.get("counting_mode")

        if location_id:
            qs = qs.filter(location_id=location_id)
        if status_param:
            qs = qs.filter(status=status_param)
        if counting_mode:
            qs = qs.filter(counting_mode=counting_mode)
        return qs

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location") or request.data.get("location_id")
        category_id = request.data.get("category") or request.data.get("category_id")
        counting_mode = request.data.get("counting_mode", "blind")
        title = request.data.get("title")

        if not location_id:
            return Response({"error": "location is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce location authorization on creation for non-admin/management/inventory staff
        user = request.user
        if user and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            try:
                loc = StockLocation.objects.get(pk=location_id)
                if loc.custodian_id and loc.custodian_id != user.id:
                    return Response(
                        {"error": "You do not have permission to initiate stocktaking for this location."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except StockLocation.DoesNotExist:
                return Response({"error": "Stock location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = create_stocktake_session(
                location=location_id,
                category=category_id,
                counting_mode=counting_mode,
                title=title,
                created_by=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="record-counts")
    def record_counts(self, request, pk=None):
        session_obj = self.get_object()
        counts = request.data.get("counts") or request.data.get("items") or request.data.get("counts_data")
        if counts is None and isinstance(request.data, list):
            counts = request.data

        if not counts:
            return Response({"error": "counts data is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = record_counts(
                session_id=pk,
                counts_data=counts,
                user=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="request-recount")
    def request_recount(self, request, pk=None):
        session_obj = self.get_object()
        item_ids = request.data.get("item_ids") or request.data.get("items")
        reason = request.data.get("reason", "")
        if not item_ids:
            return Response({"error": "item_ids is required for recount."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = request_recount(
                session_id=pk,
                item_ids=item_ids,
                reason=reason,
                supervisor=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="submit-recount")
    def submit_recount(self, request, pk=None):
        session_obj = self.get_object()
        recounts = (
            request.data.get("recounts")
            or request.data.get("recount_data")
            or request.data.get("counts")
            or request.data.get("items")
        )
        if recounts is None and isinstance(request.data, list):
            recounts = request.data

        if not recounts:
            return Response({"error": "recount data is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = submit_recount(
                session_id=pk,
                recount_data=recounts,
                user=request.user,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        session_obj = self.get_object()
        notes = request.data.get("notes", "")
        try:
            session = approve_stocktake_session(
                session_id=pk,
                supervisor=request.user,
                notes=notes,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        session_obj = self.get_object()
        reason = request.data.get("reason", "")
        try:
            session = cancel_stocktake_session(
                session_id=pk,
                user=request.user,
                reason=reason,
            )
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """
        DEF-02: Prevent destructive deletion of stocktake sessions and their historical audit trail.
        Only uncounted, unlocked draft sessions can be deleted. In-progress, completed,
        reviewed, or approved sessions must be cancelled via the cancel action.
        """
        instance = self.get_object()
        if instance.status != "draft":
            return Response(
                {
                    "error": f"Cannot delete stocktake session in '{instance.status}' status. "
                    "Historical inventory audits cannot be deleted. Use the cancel action instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.is_mode_locked or instance.counted_by is not None:
            return Response(
                {
                    "error": "Cannot delete stocktake session with recorded counts or locked mode. "
                    "Use the cancel action instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.items.filter(counted_quantity__isnull=False).exists():
            return Response(
                {
                    "error": "Cannot delete stocktake session with count entries. "
                    "Use the cancel action instead."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

class StocktakeScheduleViewSet(viewsets.ModelViewSet):
    """
    Configurable Automated Stocktake Schedules ViewSet.
    Supports Daily, Weekly, and Monthly automated stocktaking session creation.
    Enforces location-level object permissions.
    """
    serializer_class = StocktakeScheduleSerializer
    permission_classes = [HasStocktakeLocationPermission]

    def get_queryset(self):
        user = self.request.user
        qs = StocktakeSchedule.objects.select_related("location", "category", "assigned_staff", "created_by").all()

        # Enforce location scoping for non-admin/management/inventory users
        if user and user.is_authenticated and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            from django.db.models import Q
            qs = qs.filter(
                Q(location__custodian=user)
                | Q(assigned_staff=user)
                | Q(created_by=user)
            ).distinct()

        frequency = self.request.query_params.get("frequency")
        is_active = self.request.query_params.get("is_active")
        location_id = self.request.query_params.get("location")

        if frequency:
            qs = qs.filter(frequency=frequency)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("true", "1"))
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location")
        user = request.user
        if user and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}):
            if location_id:
                try:
                    loc = StockLocation.objects.get(pk=location_id)
                    if loc.custodian_id and loc.custodian_id != user.id:
                        return Response(
                            {"error": "You do not have permission to schedule stocktaking for this location."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except StockLocation.DoesNotExist:
                    return Response({"error": "Stock location not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, pk=None):
        schedule = self.get_object()
        schedule.is_active = False
        schedule.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(schedule).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        schedule = self.get_object()
        schedule.is_active = True
        schedule.next_run_at = compute_next_run(
            frequency=schedule.frequency,
            scheduled_time=schedule.scheduled_time,
            day_of_week=schedule.day_of_week,
            day_of_month=schedule.day_of_month,
        )
        schedule.save(update_fields=["is_active", "next_run_at", "updated_at"])
        return Response(self.get_serializer(schedule).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="trigger-now")
    def trigger_now(self, request, pk=None):
        """Immediately triggers a scheduled run for this specific schedule."""
        schedule = self.get_object()
        now = timezone.now()
        target_date = now.date()

        # Idempotency check for period
        existing = StocktakeSession.objects.filter(
            schedule=schedule,
            scheduled_date=target_date,
        ).first()

        if existing:
            return Response(
                {"error": f"Session #{existing.session_number} has already been generated for {target_date}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            title = f"Manual Trigger: {schedule.name} - {target_date.strftime('%Y-%m-%d')}"
            session = create_stocktake_session(
                location=schedule.location,
                category=schedule.category,
                counting_mode=schedule.counting_mode,
                title=title,
                created_by=request.user,
            )
            session.schedule = schedule
            session.scheduled_date = target_date
            if schedule.assigned_staff:
                session.counted_by = schedule.assigned_staff
            session.save(update_fields=["schedule", "scheduled_date", "counted_by", "updated_at"])

            schedule.last_run_at = now
            schedule.last_run_status = "success"
            schedule.last_error_message = ""
            schedule.next_run_at = compute_next_run(
                frequency=schedule.frequency,
                scheduled_time=schedule.scheduled_time,
                day_of_week=schedule.day_of_week,
                day_of_month=schedule.day_of_month,
            )
            schedule.save(update_fields=["last_run_at", "last_run_status", "last_error_message", "next_run_at", "updated_at"])

            return Response(
                {
                    "message": f"Successfully created session #{session.session_number}.",
                    "session_id": session.id,
                    "session_number": session.session_number,
                    "schedule": self.get_serializer(schedule).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            schedule.last_run_status = "failed"
            schedule.last_error_message = str(exc)
            schedule.save(update_fields=["last_run_status", "last_error_message", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        """Returns active upcoming and overdue stocktaking schedules."""
        active_schedules = StocktakeSchedule.objects.filter(is_active=True).select_related(
            "location", "category", "assigned_staff"
        ).order_by("next_run_at")
        serializer = self.get_serializer(active_schedules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class InventoryExpiryAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Persistent Inventory Expiry & Near-Expiry Alerts ViewSet.
    Provides listing, filtering, dismissal, and manual evaluation.
    """
    serializer_class = InventoryExpiryAlertSerializer
    permission_classes = [IsBatchOperator]

    def get_queryset(self):
        qs = InventoryExpiryAlert.objects.select_related("batch", "item", "location").all()
        alert_type = self.request.query_params.get("alert_type")
        status_param = self.request.query_params.get("status")
        item_id = self.request.query_params.get("item")
        location_id = self.request.query_params.get("location")
        search = self.request.query_params.get("search")

        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        if status_param:
            qs = qs.filter(status=status_param)
        if item_id:
            qs = qs.filter(item_id=item_id)
        if location_id:
            qs = qs.filter(location_id=location_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(batch_number__icontains=search)
                | Q(item__name__icontains=search)
                | Q(item__item_code__icontains=search)
            )
        return qs

    @action(detail=False, methods=["post"], url_path="evaluate")
    def evaluate(self, request):
        """Manually trigger an idempotent re-evaluation of all batch expiry alerts."""
        res = evaluate_inventory_expiry_alerts()
        return Response(res, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dismiss")
    def dismiss(self, request, pk=None):
        """Staff acknowledgment/dismissal of an alert."""
        alert = self.get_object()
        if alert.status == "dismissed":
            return Response({"message": "Alert already dismissed."}, status=status.HTTP_200_OK)
        alert.status = "dismissed"
        alert.resolved_at = timezone.now()
        reason = request.data.get("reason", "").strip() or f"Dismissed by {request.user.username}"
        alert.resolution_reason = reason
        alert.save(update_fields=["status", "resolved_at", "resolution_reason", "updated_at"])
        return Response(self.get_serializer(alert).data, status=status.HTTP_200_OK)

