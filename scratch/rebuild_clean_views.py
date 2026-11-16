import ast
import re

with open("apps/inventory/views.py", "r", encoding="utf-8") as f:
    text = f.read()

# Verify existing class starts
class_matches = list(re.finditer(r'^(class [A-Za-z0-9_]+[^\n]*:)', text, re.MULTILINE))

slices = {}
for i, m in enumerate(class_matches):
    start = m.start()
    end = class_matches[i+1].start() if i+1 < len(class_matches) else len(text)
    header = m.group(1)
    cname = re.match(r'class ([A-Za-z0-9_]+)', header).group(1)
    body = text[start:end]
    if cname not in slices:
        slices[cname] = body

print("Captured unique slices count:", len(slices))

header_code = '''"""Inventory API views extracted from the legacy facade."""
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
    HasStocktakeLocationPermission,
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

stocktake_session_code = '''
class StocktakeSessionViewSet(viewsets.ModelViewSet):
    """
    Authoritative ViewSet for Dual-Mode Physical Stocktaking Sessions.
    Implements counting, recounting, approval, cancellation, and audit preservation.
    """
    queryset = StocktakeSession.objects.all().select_related(
        "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
    ).prefetch_related("items__item")
    serializer_class = StocktakeSessionSerializer
    permission_classes = [HasStocktakeLocationPermission]

    def create(self, request, *args, **kwargs):
        location_id = request.data.get("location") or request.data.get("location_id")
        category_id = request.data.get("category") or request.data.get("category_id")
        counting_mode = request.data.get("counting_mode", "blind")
        title = request.data.get("title")

        if not location_id:
            return Response({"error": "location is required."}, status=status.HTTP_400_BAD_REQUEST)

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
'''

stocktake_schedule_code = '''
class StocktakeScheduleViewSet(viewsets.ModelViewSet):
    """
    Configurable Automated Stocktake Schedules ViewSet.
    Supports Daily, Weekly, and Monthly automated stocktaking session creation.
    Enforces location-level object permissions.
    """
    serializer_class = StocktakeScheduleSerializer
    permission_classes = [HasStocktakeLocationPermission]

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

expiry_alert_code = '''
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
'''

# Standard classes in proper order
ordered_class_names = [
    "InventoryCategoryViewSet",
    "SupplierViewSet",
    "InventoryItemViewSet",
    "StockTransactionViewSet",
    "RecipeBOMViewSet",
    "InventoryDashboardStatsView",
    "InventoryWasteRecordViewSet",
    "StockLocationViewSet",
    "StockBatchViewSet",
    "BatchLocationBalanceViewSet",
    "ItemLocationBalanceViewSet",
    "StockTransferViewSet",
    "ProcurementApprovalPolicyViewSet",
    "PurchaseRequisitionViewSet",
    "PurchaseOrderViewSet",
    "GoodsReceiptNoteViewSet",
    "SupplierInvoiceViewSet",
    "RequestForQuotationViewSet",
    "SupplierQuotationViewSet",
]

content = header_code + "\n"

for cname in ordered_class_names:
    if cname in slices:
        content += slices[cname].strip() + "\n\n"
    else:
        print(f"ERROR: missing slice for {cname}")

content += stocktake_session_code.strip() + "\n\n"
content += stocktake_schedule_code.strip() + "\n\n"
content += expiry_alert_code.strip() + "\n"

# Verify AST parse
try:
    tree = ast.parse(content)
    classes_in_result = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    print(f"Validation SUCCESS! Total classes: {len(classes_in_result)}")
    from collections import Counter
    counts = Counter(classes_in_result)
    print("Class frequency:", dict(counts))
    assert len(classes_in_result) == 22
    assert all(cnt == 1 for cnt in counts.values())

    with open("apps/inventory/views.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully wrote cleaned apps/inventory/views.py! Total lines:", len(content.splitlines()))
except Exception as e:
    print("AST validation failed:", e)

