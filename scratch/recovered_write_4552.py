"""Inventory API views extracted from the legacy facade."""
from decimal import Decimal
import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hotel.integrity import to_decimal
from hotel.models import (
    BatchLocationBalance,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
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
    StockBatch,
    StockLocation,
    StockTransaction,
    StockTransfer,
    StockTransferItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)
from hotel.procurement import (
    approve_purchase_requisition,
    approve_supplier_invoice,
    convert_requisition_to_purchase_order,
    ensure_default_procurement_policy,
    match_and_record_supplier_invoice,
    receive_goods_receipt_note,
    reject_purchase_requisition,
    request_purchase_requisition,
)
from hotel.transfers import (
    cancel_stock_transfer,
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.permissions import (
    IsAdminOrReadOnly,
    IsBatchOperator,
    IsFinanceStaff,
    IsHotelAdmin,
    IsInventoryManager,
    IsSupplierOperator,
)
from users.services import post_journal_entry

from .selectors import select_inventory_items, select_stock_transactions
from .serializers import (
    BatchLocationBalanceSerializer,
    GoodsReceiptNoteItemSerializer,
    GoodsReceiptNoteSerializer,
    InventoryCategorySerializer,
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
    StockBatchSerializer,
    StockLocationSerializer,
    StockTransactionSerializer,
    StockTransferItemSerializer,
    StockTransferSerializer,
    SupplierInvoiceItemSerializer,
    SupplierInvoiceSerializer,
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
        if request.user.role not in ("admin", "inventory") and not request.user.is_superuser:
            return Response({"error": "Inventory manager or administrator role required."}, status=403)
        try:
            reversal, created = reverse_stock_transaction(
                transaction_id=pk,
                reason=request.data.get("reason"),
                logged_by_username=request.user.username,
            )
        except StockTransaction.DoesNotExist:
            return Response({"error": "Stock transaction not found."}, status=404)
        return Response(StockTransactionSerializer(reversal).data, status=201 if created else 200)

    def perform_create(self, serializer):
        with transaction.atomic():
            data = serializer.validated_data
            item, transaction_inst = record_stock_change(
                item_id=data["item"].pk,
                transaction_type=data["transaction_type"],
                quantity=data["quantity"],
                unit_cost=data["unit_cost"],
                supplier=data.get("supplier"),
                reference_number=data.get("reference_number"),
                notes=data.get("notes"),
                destination_dept=data.get("destination_dept"),
                destination_room=data.get("destination_room"),
                logged_by_username=self.request.user.username,
            )
            serializer.instance = transaction_inst
            qty = transaction_inst.quantity

            # --- Post General Ledger Journal Entry ---
            try:
                total_cost = to_decimal(qty * transaction_inst.unit_cost)
                if total_cost > 0:
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
            except Exception as e:
                print(f"GL Auto-post error for stock transaction: {e}")


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
        if request.user.role not in ("admin", "inventory") and not request.user.is_superuser:
            return Response({"error": "Inventory manager or administrator role required."}, status=status.HTTP_403_FORBIDDEN)
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
    permission_classes = [IsInventoryManager]

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


# ----------------------------------------------------------------------
# Phase 1.4: Configurable Procurement & 3-Way Matching ViewSets
# ----------------------------------------------------------------------

class ProcurementApprovalPolicyViewSet(viewsets.ModelViewSet):
    queryset = ProcurementApprovalPolicy.objects.prefetch_related("tiers").order_by("-is_active", "department")
    serializer_class = ProcurementApprovalPolicySerializer
    permission_classes = [IsInventoryManager]


class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseRequisition.objects.select_related("requester", "approved_by", "delivery_location")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        dept = self.request.query_params.get("department")
        if status_param:
            qs = qs.filter(status=status_param)
        if dept:
            qs = qs.filter(department=dept)
        return qs

    def create(self, request, *args, **kwargs):
        department = request.data.get("department")
        delivery_location = request.data.get("delivery_location")
        items = request.data.get("items", [])
        notes = request.data.get("notes", "")

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
        notes = request.data.get("notes", "")
        try:
            req = approve_purchase_requisition(requisition_id=pk, approver=request.user, notes=notes)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        reason = request.data.get("reason", "")
        if not reason or not str(reason).strip():
            return Response({"error": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            req = reject_purchase_requisition(requisition_id=pk, rejecter=request.user, reason=reason)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="convert-to-po")
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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.select_related("requisition", "supplier", "delivery_location", "issued_by")
        .prefetch_related("items__item", "grns")
        .order_by("-created_at")
    )
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated]

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

    def update(self, request, *args, **kwargs):
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

    @action(detail=True, methods=["post"], url_path="receive-grn")
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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GoodsReceiptNoteViewSet(viewsets.ModelViewSet):
    queryset = (
        GoodsReceiptNote.objects.select_related("purchase_order", "supplier", "location", "received_by", "journal_entry")
        .prefetch_related("items__item", "items__batch")
        .order_by("-created_at")
    )
    serializer_class = GoodsReceiptNoteSerializer
    permission_classes = [IsAuthenticated]

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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        return Response({"error": "Goods Receipt Notes are immutable physical receipts."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Goods Receipt Notes cannot be deleted."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    queryset = (
        SupplierInvoice.objects.select_related("supplier", "purchase_order", "matched_by", "approved_by", "journal_entry")
        .prefetch_related("items__item")
        .order_by("-created_at")
    )
    serializer_class = SupplierInvoiceSerializer
    permission_classes = [IsAuthenticated]

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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="match-and-record")
    def match_and_record(self, request):
        return self.create(request)

    @action(detail=True, methods=["post"], url_path="approve")
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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
