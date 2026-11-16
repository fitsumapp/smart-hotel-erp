with open("apps/inventory/views.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_header = '''"""Inventory API views extracted from the legacy facade."""
from decimal import Decimal, ROUND_HALF_UP
import datetime

TWOPLACES = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
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
    IsAdminOrReadOnly,
    IsBatchOperator,
    IsFinanceStaff,
    IsHotelAdmin,
    IsInventoryManager,
    IsProcurementOperator,
    IsProcurementOrFinanceOperator,
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
'''

# Find where class InventoryCategoryViewSet begins in lines
idx = 0
for i, l in enumerate(lines):
    if "class InventoryCategoryViewSet" in l:
        idx = i
        break

code = new_header + "".join(lines[idx:])

# Now append InventoryExpiryAlertViewSet and StocktakeScheduleViewSet at the end
trailing_views = '''

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


class StocktakeScheduleViewSet(viewsets.ModelViewSet):
    """
    Configurable Automated Stocktake Schedules ViewSet.
    Supports Daily, Weekly, and Monthly automated stocktaking session creation.
    """
    serializer_class = StocktakeScheduleSerializer
    permission_classes = [IsInventoryManager]

    def get_queryset(self):
        qs = StocktakeSchedule.objects.select_related("location", "category", "assigned_staff", "created_by").all()
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
'''

code += trailing_views

with open("apps/inventory/views.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated apps/inventory/views.py successfully! Total lines:", len(code.splitlines()))

