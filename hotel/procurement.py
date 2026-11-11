"""
Phase 1.4 Configurable Procurement Management & 3-Way Match GRNI Service Layer.
Enforces:
1. Dynamic configurable approval tiers and thresholds (Owner Decision 3).
2. Separation-of-duties on requisition approvals.
3. PO conversion and supplier contract pricing.
4. GRN receipt into STORE-MAIN with verified StockBatch creation and mandatory perishable expiry dates.
5. Interim GRNI accrual accounting entry: Dr 1300 (Inventory Asset) / Cr 2010 (GRNI).
6. 3-Way Matching against PO and GRN with tolerance checking.
7. Final AP settlement and Purchase Price Variance (PPV): Dr 2010, Dr/Cr 5040, Cr 2000.
"""
import datetime
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.finance.services import post_journal_entry
from hotel.integrity import record_stock_change, resolve_stock_location
from hotel.models import (
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryItem,
    JournalEntry,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    RequestForQuotation,
    RequestForQuotationItem,
    StockBatch,
    StockLocation,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierQuotation,
    SupplierQuotationItem,
)


def generate_pr_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"PR-{today_str}-{suffix}"


def generate_rfq_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"RFQ-{today_str}-{suffix}"


def generate_quotation_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"SQ-{today_str}-{suffix}"


def generate_po_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"PO-{today_str}-{suffix}"


def generate_grn_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"GRN-{today_str}-{suffix}"


def generate_sinv_number():
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"SINV-{today_str}-{suffix}"


def _validate_procurement_role(user, allowed_roles, action_name="perform this operation"):
    """
    Validates that the calling user is authenticated, active, and holds an allowed role.
    Superusers bypass role checks.
    """
    if not user:
        raise ValidationError(f"A valid user is required to {action_name}.")
    if getattr(user, "is_superuser", False):
        return True
    user_role = getattr(user, "role", "")
    if user_role not in allowed_roles:
        raise PermissionDenied(
            f"User '{getattr(user, 'username', 'anonymous')}' with role '{user_role}' "
            f"is not authorized to {action_name}. Required role: {', '.join(sorted(allowed_roles))}."
        )
    return True


def ensure_default_procurement_policy():
    """
    Ensures an active default procurement approval policy exists with 3 standard tiers.
    Configurable via API/UI; never hardcoded in approval evaluation.
    """
    policy, created = ProcurementApprovalPolicy.objects.get_or_create(
        name="Standard Hotel Procurement Policy",
        defaults={
            "description": "Standard multi-tier threshold policy for hotel departmental procurement.",
            "is_active": True,
            "currency": "ETB",
            "price_tolerance_percentage": Decimal("2.00"),  # 2% default variance tolerance
        },
    )
    if created or policy.tiers.count() == 0:
        ProcurementApprovalTier.objects.get_or_create(
            policy=policy,
            tier_level=1,
            defaults={
                "name": "Tier 1: Department Head / F&B Manager",
                "min_amount": Decimal("0.00"),
                "max_amount": Decimal("10000.00"),
                "required_role": "inventory",
            },
        )
        ProcurementApprovalTier.objects.get_or_create(
            policy=policy,
            tier_level=2,
            defaults={
                "name": "Tier 2: Finance Controller",
                "min_amount": Decimal("10000.01"),
                "max_amount": Decimal("50000.00"),
                "required_role": "finance",
            },
        )
        ProcurementApprovalTier.objects.get_or_create(
            policy=policy,
            tier_level=3,
            defaults={
                "name": "Tier 3: General Manager",
                "min_amount": Decimal("50000.01"),
                "max_amount": None,
                "required_role": "admin",
            },
        )
    return policy


def resolve_approval_tier(amount, policy=None, department=None):
    """Dynamically resolves the applicable approval tier based on total requisition value."""
    if policy is None:
        policy = ProcurementApprovalPolicy.objects.filter(is_active=True).first()
        if not policy:
            policy = ensure_default_procurement_policy()

    amount_dec = Decimal(str(amount))
    tiers = policy.tiers.order_by("tier_level").all()

    matching_tier = None
    for t in tiers:
        if amount_dec >= t.min_amount:
            if t.max_amount is None or amount_dec <= t.max_amount:
                matching_tier = t
                break

    if not matching_tier and tiers.exists():
        matching_tier = tiers.last()

    return matching_tier


@transaction.atomic
def request_purchase_requisition(
    *,
    requested_by=None,
    requester=None,
    department="general",
    delivery_location=None,
    delivery_location_id=None,
    items=None,
    notes="",
    submit_for_approval=True,
):
    """
    Creates a new Purchase Requisition with line items.
    Dynamically resolves approval tier based on active policy thresholds.
    """
    actual_requester = requested_by or requester
    if not actual_requester:
        raise ValidationError("Requester is required.")

    if not items or len(items) == 0:
        raise ValidationError("Purchase requisition must contain at least one line item.")

    loc = None
    if delivery_location:
        loc = delivery_location if isinstance(delivery_location, StockLocation) else resolve_stock_location(delivery_location)
    elif delivery_location_id:
        loc = resolve_stock_location(delivery_location_id)

    notes_text = str(notes or "").strip()
    if loc:
        notes_text = f"{notes_text}\n[Requested Delivery Location]: {loc.code} - {loc.name}".strip()

    req_num = generate_pr_number()
    pr = PurchaseRequisition.objects.create(
        requisition_number=req_num,
        department=str(department or "general").strip(),
        status="draft",
        requested_by=actual_requester,
        requested_at=timezone.now(),
        notes=notes_text,
    )

    total_est = Decimal("0.00")
    for it_data in items:
        item_val = it_data.get("item_id") or it_data.get("item")
        if isinstance(item_val, InventoryItem):
            inv_item = item_val
        else:
            try:
                inv_item = InventoryItem.objects.get(pk=item_val)
            except InventoryItem.DoesNotExist:
                raise ValidationError(f"Inventory item ID '{item_val}' does not exist.")

        qty_raw = it_data.get("quantity_requested") or it_data.get("quantity")
        if qty_raw is None:
            raise ValidationError(f"Quantity requested is required for item '{inv_item.name}'.")
        qty_req = Decimal(str(qty_raw))
        if qty_req <= Decimal("0.00"):
            raise ValidationError(f"Quantity requested for '{inv_item.name}' must be positive.")

        est_cost_raw = it_data.get("estimated_unit_cost", inv_item.unit_cost)
        est_cost = Decimal(str(est_cost_raw)) if est_cost_raw is not None else Decimal("0.00")
        if est_cost < Decimal("0.00"):
            raise ValidationError(f"Estimated unit cost for '{inv_item.name}' cannot be negative.")

        PurchaseRequisitionItem.objects.create(
            requisition=pr,
            item=inv_item,
            quantity_requested=qty_req,
            estimated_unit_cost=est_cost,
            notes=str(it_data.get("notes") or "").strip(),
        )
        total_est += (qty_req * est_cost).quantize(Decimal("0.01"))

    pr.total_estimated_amount = total_est
    pr.approval_tier = resolve_approval_tier(total_est, department=department)
    if submit_for_approval:
        pr.status = "pending_approval"
    pr.save(update_fields=["total_estimated_amount", "approval_tier", "status", "updated_at"])

    return pr


@transaction.atomic
def approve_purchase_requisition(
    *,
    requisition_id,
    approver,
    notes="",
):
    """
    Approves a Purchase Requisition.
    Enforces separation of duties (requester cannot self-approve unless superuser)
    and validates approval tier role authority.
    """
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)
    if pr.status != "pending_approval":
        raise ValidationError(f"Cannot approve requisition #{pr.requisition_number}: status is '{pr.status}', expected 'pending_approval'.")

    is_superuser = getattr(approver, "is_superuser", False)
    approver_role = getattr(approver, "role", "")
    approver_id = getattr(approver, "pk", approver)
    requester_id = getattr(pr.requested_by, "pk", pr.requested_by_id)

    # Separation of duties (robust PK comparison preventing ID mismatch bypass)
    if approver_id == requester_id and not is_superuser:
        raise ValidationError("Separation of duties violation: Requisitioner cannot approve their own requisition. Independent managerial sign-off is required.")

    # Role validation against approval tier
    required_role = pr.approval_tier.required_role if pr.approval_tier else "admin"
    valid_roles = {"admin"}
    if required_role == "inventory":
        valid_roles.update({"inventory", "kitchen", "f_and_b", "hotel_manager"})
    elif required_role == "finance":
        valid_roles.update({"finance"})
    else:
        valid_roles.add(required_role)

    if approver_role not in valid_roles and not is_superuser:
        raise PermissionDenied(
            f"User role '{approver_role}' is not authorized to approve at {pr.approval_tier.name if pr.approval_tier else 'this tier'}. "
            f"Required role: {required_role}."
        )

    pr.status = "approved"
    pr.approved_by = approver
    pr.approved_at = timezone.now()
    if notes:
        pr.notes = f"{pr.notes}\n[Approval]: {notes}".strip()
    pr.save(update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"])

    return pr


@transaction.atomic
def reject_purchase_requisition(
    *,
    requisition_id,
    rejecter=None,
    user=None,
    reason="",
):
    """Rejects a Purchase Requisition with a documented reason."""
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)
    if pr.status != "pending_approval":
        raise ValidationError(f"Cannot reject requisition #{pr.requisition_number}: status is '{pr.status}', expected 'pending_approval'.")

    actual_rejecter = rejecter or user
    if actual_rejecter:
        _validate_procurement_role(
            actual_rejecter,
            allowed_roles={"admin", "hotel_manager", "inventory", "kitchen", "bar", "housekeeping"},
            action_name="reject requisitions",
        )
        if not (actual_rejecter.is_superuser or getattr(actual_rejecter, "role", "") in {"admin", "hotel_manager", "inventory"}):
            dept = (pr.department or "").lower()
            user_role = getattr(actual_rejecter, "role", "").lower()
            if pr.requested_by_id != getattr(actual_rejecter, "id", None) and dept != user_role:
                raise PermissionDenied(f"User with role '{user_role}' cannot reject requisition for department '{dept}'.")

    pr.status = "rejected"
    pr.rejection_reason = str(reason or "Rejected by reviewer").strip()
    pr.save(update_fields=["status", "rejection_reason", "updated_at"])
    return pr


@transaction.atomic
def convert_requisition_to_purchase_order(
    *,
    requisition_id,
    user=None,
    issuer=None,
    supplier_id,
    delivery_location_id=None,
    delivery_due_date=None,
    payment_terms="Net 30",
    tax_rate=Decimal("0.00"),
    item_prices=None,
    notes="",
):
    """
    Converts an approved Purchase Requisition into an issued Purchase Order.
    Allows supplier contract prices to override estimated prices.
    """
    actual_issuer = user or issuer
    _validate_procurement_role(
        actual_issuer,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="issue purchase orders",
    )
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)
    if pr.status != "approved":
        raise ValidationError(f"Cannot convert requisition #{pr.requisition_number}: status is '{pr.status}', expected 'approved'.")

    try:
        supplier = Supplier.objects.get(pk=supplier_id)
    except Supplier.DoesNotExist:
        raise ValidationError(f"Supplier ID '{supplier_id}' does not exist.")

    location = resolve_stock_location(delivery_location_id or getattr(pr, "delivery_location", None))

    po_num = generate_po_number()
    po = PurchaseOrder.objects.create(
        po_number=po_num,
        requisition=pr,
        supplier=supplier,
        delivery_location=location,
        status="issued",
        issued_by=actual_issuer,
        issued_at=timezone.now(),
        delivery_due_date=delivery_due_date,
        payment_terms=payment_terms,
        notes=str(notes or "").strip(),
    )

    subtotal = Decimal("0.00")
    for pr_item in pr.items.select_related("item").all():
        if item_prices and pr_item.item_id in item_prices:
            unit_price = Decimal(str(item_prices[pr_item.item_id]))
        elif item_prices and str(pr_item.item_id) in item_prices:
            unit_price = Decimal(str(item_prices[str(pr_item.item_id)]))
        else:
            unit_price = pr_item.estimated_unit_cost or pr_item.item.unit_cost or Decimal("0.00")

        line_tot = (pr_item.quantity_requested * unit_price).quantize(Decimal("0.01"))
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=pr_item.item,
            quantity_ordered=pr_item.quantity_requested,
            quantity_received=Decimal("0.00"),
            unit_price=unit_price,
            line_total=line_tot,
            notes=pr_item.notes,
        )
        subtotal += line_tot

    tax_amount = (subtotal * Decimal(str(tax_rate))).quantize(Decimal("0.01"))
    total_amount = subtotal + tax_amount

    po.subtotal = subtotal
    po.tax_amount = tax_amount
    po.total_amount = total_amount
    po.save(update_fields=["subtotal", "tax_amount", "total_amount", "updated_at"])

    pr.status = "converted_to_po"
    pr.save(update_fields=["status", "updated_at"])

    return po


@transaction.atomic
def receive_goods_receipt_note(
    *,
    po_id=None,
    purchase_order_id=None,
    received_by=None,
    receiver=None,
    items=None,
    receipt_items=None,
    delivery_note_number="",
    location_id=None,
    notes="",
):
    """
    Receives goods at the physical receiving dock (default STORE-MAIN).
    Validates perishable expiry date, seeds stock authoritatively via record_stock_change,
    creates verified StockBatch records, updates PO line received quantities,
    and posts interim accrual GL entry: Dr 1300 (Inventory Asset) / Cr 2010 (GRNI).
    """
    actual_po_id = po_id or purchase_order_id
    actual_receiver = received_by or receiver
    actual_items = items if items is not None else (receipt_items or [])

    _validate_procurement_role(
        actual_receiver,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="receive goods receipt notes",
    )

    po = PurchaseOrder.objects.select_for_update().get(pk=actual_po_id)
    if po.status not in ("issued", "partially_received"):
        raise ValidationError(f"Cannot receive goods against PO #{po.po_number}: status is '{po.status}', expected 'issued' or 'partially_received'.")

    location = resolve_stock_location(location_id or po.delivery_location)
    today = timezone.now().date()

    if not actual_items or len(actual_items) == 0:
        raise ValidationError("GRN must contain at least one line item.")

    grn_num = generate_grn_number()
    grn = GoodsReceiptNote.objects.create(
        grn_number=grn_num,
        purchase_order=po,
        supplier=po.supplier,
        location=location,
        delivery_note_number=str(delivery_note_number or "").strip(),
        status="draft",
        received_by=actual_receiver,
        received_at=timezone.now(),
        notes=str(notes or "").strip(),
    )

    po_items_map = {pi.id: pi for pi in po.items.select_for_update().select_related("item").all()}
    po_items_by_item = {pi.item_id: pi for pi in po_items_map.values()}

    total_grn_cost = Decimal("0.00")

    for it_data in actual_items:
        po_item_id = it_data.get("po_item_id") or it_data.get("po_item")
        item_id = it_data.get("item_id") or it_data.get("item")

        po_item = po_items_map.get(po_item_id) or po_items_by_item.get(item_id)
        if not po_item:
            raise ValidationError(f"Invalid PO line item reference for '{item_id}'.")

        inv_item = po_item.item

        qty_recv_raw = it_data.get("quantity_received", 0)
        qty_rej_raw = it_data.get("quantity_rejected", 0)
        qty_recv = Decimal(str(qty_recv_raw))
        qty_rej = Decimal(str(qty_rej_raw))

        if qty_recv < Decimal("0.00") or qty_rej < Decimal("0.00"):
            raise ValidationError(f"Received and rejected quantities for '{inv_item.name}' cannot be negative.")

        if qty_recv + qty_rej <= Decimal("0.00"):
            raise ValidationError(f"At least one unit must be received or rejected for '{inv_item.name}'.")

        unit_cost = po_item.unit_price
        line_total = (qty_recv * unit_cost).quantize(Decimal("0.01"))

        # Expiry date validation for perishable items
        expiry_date = it_data.get("expiry_date")
        if inv_item.is_perishable:
            if not expiry_date:
                raise ValidationError(f"Mandatory expiry date is required for perishable item '{inv_item.name}' on delivery.")
            if isinstance(expiry_date, str):
                try:
                    expiry_date = datetime.date.fromisoformat(expiry_date)
                except ValueError:
                    raise ValidationError(f"Invalid expiry date format for '{inv_item.name}'. Use YYYY-MM-DD.")
            if expiry_date < today:
                raise ValidationError(f"Cannot receive batch with a past expiry date for '{inv_item.name}' (Expiry: {expiry_date}).")
        elif expiry_date and isinstance(expiry_date, str):
            try:
                expiry_date = datetime.date.fromisoformat(expiry_date)
            except ValueError:
                expiry_date = None

        batch_number = str(it_data.get("batch_number") or f"BAT-{today.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}").strip()
        supp_batch = str(it_data.get("supplier_batch_number") or "").strip()

        created_batch = None
        if qty_recv > Decimal("0.00"):
            # Authoritatively record incoming purchase stock (returns (item, stock_transaction))
            _, stx = record_stock_change(
                item_id=inv_item.pk,
                transaction_type="purchase",
                quantity=qty_recv,
                unit_cost=unit_cost,
                supplier=po.supplier,
                location=location,
                batch_number=batch_number,
                supplier_batch_number=supp_batch,
                expiry_date=expiry_date,
                reference_number=f"GRN #{grn_num}",
                logged_by_username=actual_receiver.username if actual_receiver else "system",
                notes=f"GRN #{grn_num} against PO #{po.po_number}",
            )
            created_batch = stx.batch
            po_item.quantity_received += qty_recv
            po_item.save(update_fields=["quantity_received"])
            total_grn_cost += line_total

        GoodsReceiptNoteItem.objects.create(
            grn=grn,
            po_item=po_item,
            item=inv_item,
            quantity_received=qty_recv,
            quantity_rejected=qty_rej,
            rejection_reason=str(it_data.get("rejection_reason") or "").strip(),
            batch=created_batch,
            batch_number=batch_number,
            supplier_batch_number=supp_batch,
            expiry_date=expiry_date,
            unit_cost=unit_cost,
            total_cost=line_total,
            notes=str(it_data.get("notes") or "").strip(),
        )

    # Determine PO overall completion
    all_po_items = po.items.all()
    all_fulfilled = all(pi.quantity_received >= pi.quantity_ordered for pi in all_po_items)
    po.status = "received" if all_fulfilled else "partially_received"
    po.save(update_fields=["status", "updated_at"])

    grn.status = "approved"
    grn.total_received_cost = total_grn_cost

    # Post Interim Accrual General Ledger Entry: Dr 1300 (Asset) / Cr 2010 (GRNI)
    if total_grn_cost > Decimal("0.00"):
        try:
            je = post_journal_entry(
                description=f"Auto JV: GRN #{grn_num} - PO #{po.po_number} ({po.supplier.name})",
                items=[
                    {"account_code": "1300", "debit": total_grn_cost, "credit": Decimal("0.00")},
                    {"account_code": "2010", "debit": Decimal("0.00"), "credit": total_grn_cost},
                ],
            )
            grn.journal_entry = je
        except Exception as gl_err:
            import logging
            logging.getLogger(__name__).warning("Failed to auto-post GL for GRN #%s: %s", grn_num, gl_err)

    grn.save(update_fields=["status", "total_received_cost", "journal_entry", "updated_at"])
    return grn


@transaction.atomic
def match_and_record_supplier_invoice(
    *,
    po_id=None,
    purchase_order_id=None,
    vendor_invoice_number,
    invoice_date,
    due_date=None,
    subtotal=None,
    tax_amount=Decimal("0.00"),
    items=None,
    billed_items=None,
    user=None,
    matched_by=None,
    variance_notes="",
    notes="",
):
    """
    Records a vendor invoice and executes automated 3-Way Matching against PO and GRN.
    Validates billed quantity against physically received quantity.
    Evaluates unit price variance against active policy price tolerance.
    """
    actual_po_id = po_id or purchase_order_id
    actual_user = user or matched_by
    actual_items = items if items is not None else (billed_items or [])

    _validate_procurement_role(
        actual_user,
        allowed_roles={"admin", "hotel_manager", "inventory", "finance"},
        action_name="match and record supplier invoices",
    )

    po = PurchaseOrder.objects.select_for_update().get(pk=actual_po_id)
    policy = ProcurementApprovalPolicy.objects.filter(is_active=True).first() or ensure_default_procurement_policy()

    if isinstance(invoice_date, str):
        invoice_date = datetime.date.fromisoformat(invoice_date)

    if not due_date:
        due_date = invoice_date + datetime.timedelta(days=30)
    elif isinstance(due_date, str):
        due_date = datetime.date.fromisoformat(due_date)

    tax_amount = Decimal(str(tax_amount or "0.00"))

    po_items_map = {pi.id: pi for pi in po.items.select_related("item").all()}
    po_items_by_item = {pi.item_id: pi for pi in po_items_map.values()}

    # Calculate subtotal from items if not explicitly provided
    calc_subtotal = Decimal("0.00")
    for it_data in actual_items:
        po_item_id = it_data.get("po_item_id") or it_data.get("po_item")
        item_id = it_data.get("item_id") or it_data.get("item")
        po_item = po_items_map.get(po_item_id) or po_items_by_item.get(item_id)
        if not po_item:
            raise ValidationError(f"Invalid PO line item reference for '{item_id}'.")

        b_qty = Decimal(str(it_data.get("billed_quantity", po_item.quantity_received)))
        b_price = Decimal(str(it_data.get("billed_unit_price", po_item.unit_price)))
        calc_subtotal += (b_qty * b_price).quantize(Decimal("0.01"))

    subtotal = Decimal(str(subtotal)) if subtotal is not None else calc_subtotal
    total_amount = subtotal + tax_amount

    inv_num = generate_sinv_number()
    invoice = SupplierInvoice.objects.create(
        internal_number=inv_num,
        vendor_invoice_number=str(vendor_invoice_number).strip(),
        supplier=po.supplier,
        purchase_order=po,
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        match_status="unmatched",
        variance_notes=str(variance_notes or notes or "").strip(),
    )

    any_variance = False

    for it_data in actual_items:
        po_item_id = it_data.get("po_item_id") or it_data.get("po_item")
        item_id = it_data.get("item_id") or it_data.get("item")
        po_item = po_items_map.get(po_item_id) or po_items_by_item.get(item_id)

        billed_qty = Decimal(str(it_data.get("billed_quantity", po_item.quantity_received)))
        billed_price = Decimal(str(it_data.get("billed_unit_price", po_item.unit_price)))

        # Rule 1: Cannot bill more quantity than physically received
        if billed_qty > po_item.quantity_received:
            raise ValidationError(
                f"Over-billing rejected for '{po_item.item.name}'. "
                f"Billed quantity ({billed_qty}) exceeds GRN received quantity ({po_item.quantity_received})."
            )

        line_tot = (billed_qty * billed_price).quantize(Decimal("0.01"))
        price_var = ((billed_price - po_item.unit_price) * billed_qty).quantize(Decimal("0.01"))

        # Rule 2: Evaluate price variance against tolerance
        tolerance_pct = policy.price_tolerance_percentage
        is_matched = True
        if po_item.unit_price > Decimal("0.00"):
            diff_pct = (abs(billed_price - po_item.unit_price) / po_item.unit_price) * Decimal("100.00")
            if diff_pct > tolerance_pct:
                is_matched = False
                any_variance = True
        elif billed_price > Decimal("0.00"):
            is_matched = False
            any_variance = True

        SupplierInvoiceItem.objects.create(
            invoice=invoice,
            po_item=po_item,
            grn_item=po_item.grn_items.first(),
            item=po_item.item,
            billed_quantity=billed_qty,
            billed_unit_price=billed_price,
            line_total=line_tot,
            price_variance=price_var,
            is_matched=is_matched,
        )

    invoice.match_status = "variance_flagged" if any_variance else "matched"
    invoice.matched_by = actual_user
    invoice.matched_at = timezone.now()
    invoice.save(update_fields=["match_status", "matched_by", "matched_at", "updated_at"])

    return invoice


@transaction.atomic
def approve_supplier_invoice(
    *,
    invoice_id,
    approver,
    override_variance=False,
    variance_justification="",
    notes="",
):
    """
    Approves a matched or flagged supplier invoice and posts financial settlement:
      - Debit 2010 (GRNI Accrued Liability)
      - Debit / Credit 5040 (Purchase Price Variance, if any)
      - Credit 2000 (Accounts Payable)
    """
    invoice = SupplierInvoice.objects.select_for_update().get(pk=invoice_id)
    if invoice.match_status not in ("matched", "variance_flagged"):
        raise ValidationError(f"Cannot approve invoice #{invoice.internal_number}: status is '{invoice.match_status}', expected 'matched' or 'variance_flagged'.")

    is_superuser = getattr(approver, "is_superuser", False)
    approver_role = getattr(approver, "role", "")

    # Role validation: only finance or admin can approve Accounts Payable settlement
    _validate_procurement_role(
        approver,
        allowed_roles={"admin", "finance"},
        action_name="approve supplier invoices for payment",
    )

    # Variance override safeguard: only admin or superuser can override flagged price variances
    if invoice.match_status == "variance_flagged":
        if not override_variance:
            raise ValidationError(f"Invoice #{invoice.internal_number} cannot be approved due to price variance without explicit override.")
        if approver_role != "admin" and not is_superuser:
            raise PermissionDenied("Only hotel administrators can authorize supplier invoice price variance overrides.")

    # Separation of duties: Dock receiver must not approve invoice settlement (fraud prevention)
    approver_id = getattr(approver, "pk", approver)
    grn_receiver_ids = set(invoice.purchase_order.grns.values_list("received_by_id", flat=True))
    if approver_id in grn_receiver_ids and not is_superuser:
        raise ValidationError("Separation of duties violation: Dock receiver cannot approve invoice payment for goods they received.")

    # Calculate GRNI and PPV
    grni_clearing = Decimal("0.00")
    total_ppv = Decimal("0.00")

    for item in invoice.items.select_related("po_item").all():
        grni_line = (item.billed_quantity * item.po_item.unit_price).quantize(Decimal("0.01"))
        grni_clearing += grni_line
        total_ppv += item.price_variance

    ap_payable = invoice.total_amount

    # Post General Ledger settlement entry
    jv_lines = [
        {"account_code": "2010", "debit": grni_clearing, "credit": Decimal("0.00")},
    ]

    # Handle tax: Dr GRNI (2010) + Dr PPV (5040) + Dr Tax (2200) = Cr AP (2000)
    if total_ppv > Decimal("0.00"):
        jv_lines.append({"account_code": "5040", "debit": total_ppv, "credit": Decimal("0.00")})
    elif total_ppv < Decimal("0.00"):
        jv_lines.append({"account_code": "5040", "debit": Decimal("0.00"), "credit": abs(total_ppv)})

    if invoice.tax_amount > Decimal("0.00"):
        jv_lines.append({"account_code": "2200", "debit": invoice.tax_amount, "credit": Decimal("0.00")})

    jv_lines.append({"account_code": "2000", "debit": Decimal("0.00"), "credit": ap_payable})

    try:
        je = post_journal_entry(
            description=f"Auto JV: Settlement Invoice #{invoice.vendor_invoice_number} - {invoice.supplier.name} (PO #{invoice.purchase_order.po_number})",
            items=jv_lines,
        )
        invoice.journal_entry = je
    except Exception as gl_err:
        import logging
        logging.getLogger(__name__).warning("Failed to auto-post settlement GL for invoice #%s: %s", invoice.internal_number, gl_err)

    invoice.match_status = "approved"
    invoice.approved_by = approver
    invoice.approved_at = timezone.now()
    approval_note = f"[Approval]: {variance_justification or notes or 'Approved for payment'}".strip()
    invoice.variance_notes = f"{invoice.variance_notes}\n{approval_note}".strip()
    invoice.save(update_fields=["match_status", "approved_by", "approved_at", "variance_notes", "journal_entry", "updated_at"])

    return invoice


# =============================================================================
# RFQ & Supplier Quotation Services (Phase 2.1 Backend Implementation)
# =============================================================================

@transaction.atomic
def create_request_for_quotation(
    *,
    user,
    title,
    delivery_location_id,
    submission_deadline,
    requisition_ids=None,
    items_data=None,
    is_public_bidding=False,
    invited_supplier_ids=None,
    terms_and_conditions="",
):
    """
    Creates a Request for Quotation (RFQ) in draft status with aggregate multi-requisition
    allocation safeguards and concurrency row-level locking.
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="create RFQs",
    )
    if not title or not title.strip():
        raise ValidationError("RFQ title is required.")

    if submission_deadline <= timezone.now():
        raise ValidationError("Submission deadline must be set in the future.")

    location = StockLocation.objects.get(pk=delivery_location_id)
    rfq_num = generate_rfq_number()

    rfq = RequestForQuotation.objects.create(
        rfq_number=rfq_num,
        title=title.strip(),
        status="draft",
        submission_deadline=submission_deadline,
        delivery_location=location,
        is_public_bidding=is_public_bidding,
        terms_and_conditions=terms_and_conditions.strip(),
        created_by=user,
    )

    if requisition_ids:
        reqs = PurchaseRequisition.objects.select_for_update().filter(pk__in=requisition_ids).all()
        for req in reqs:
            if req.status != "approved":
                raise ValidationError(
                    f"Requisition #{req.requisition_number} is in status '{req.status}' "
                    f"and cannot be included in an RFQ. Only 'approved' requisitions are eligible."
                )
            rfq.requisitions.add(req)

    if invited_supplier_ids:
        suppliers = Supplier.objects.filter(pk__in=invited_supplier_ids).all()
        for supp in suppliers:
            rfq.invited_suppliers.add(supp)

    # Process line items with SAFEGUARD 1: Concurrency row locking & allocation validation
    if items_data:
        for idx, line in enumerate(items_data):
            item_id = line.get("item_id")
            target_qty = Decimal(str(line.get("target_quantity", "0")))
            if target_qty <= Decimal("0.00"):
                raise ValidationError(f"Line #{idx + 1}: Target quantity must be greater than zero.")

            inv_item = InventoryItem.objects.get(pk=item_id)
            req_item_id = line.get("requisition_item_id")
            req_item = None

            if req_item_id:
                # Mandatory Safeguard 1: Transactional lock and aggregate allocation validation
                req_item = PurchaseRequisitionItem.objects.select_for_update().get(pk=req_item_id)
                if req_item.requisition.status != "approved":
                    raise ValidationError(
                        f"Requisition item belongs to requisition #{req_item.requisition.requisition_number} "
                        f"with status '{req_item.requisition.status}'. Only 'approved' requisitions can be sourced."
                    )
                if req_item.item_id != inv_item.id:
                    raise ValidationError(
                        f"RFQ line item '{inv_item.name}' does not match requisition line item '{req_item.item.name}'."
                    )

                already_allocated = (
                    RequestForQuotationItem.objects.filter(requisition_item=req_item)
                    .exclude(rfq__status="cancelled")
                    .aggregate(total=Sum("target_quantity"))["total"]
                    or Decimal("0.00")
                )

                remaining_unallocated = req_item.quantity_requested - already_allocated
                if target_qty > remaining_unallocated:
                    raise ValidationError(
                        f"Target quantity {target_qty} for '{inv_item.name}' exceeds remaining "
                        f"unsourced balance of {remaining_unallocated} on Requisition #{req_item.requisition.requisition_number}."
                    )

            RequestForQuotationItem.objects.create(
                rfq=rfq,
                item=inv_item,
                requisition_item=req_item,
                target_quantity=target_qty,
                specifications=line.get("specifications", "").strip(),
            )

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action="RFQ_CREATED",
            entity_type="RequestForQuotation",
            entity_id=rfq.id,
            after={"rfq_number": rfq.rfq_number, "status": rfq.status},
            reason="RFQ created in draft",
        )
    except Exception:
        pass

    return rfq


@transaction.atomic
def publish_request_for_quotation(*, rfq_id, user):
    """
    Publishes an RFQ, opening it to bidding by invited suppliers (or public suppliers).
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="publish RFQs",
    )
    rfq = RequestForQuotation.objects.select_for_update().get(pk=rfq_id)
    if rfq.status != "draft":
        raise ValidationError(f"Cannot publish RFQ #{rfq.rfq_number}: status is '{rfq.status}', expected 'draft'.")

    if rfq.items.count() == 0:
        raise ValidationError(f"Cannot publish RFQ #{rfq.rfq_number}: RFQ contains no items.")

    if not rfq.is_public_bidding and rfq.invited_suppliers.count() == 0:
        raise ValidationError(
            f"Restricted RFQ #{rfq.rfq_number} must have at least one invited supplier before publishing."
        )

    if rfq.submission_deadline <= timezone.now():
        raise ValidationError(
            f"Cannot publish RFQ #{rfq.rfq_number}: submission deadline {rfq.submission_deadline} has already passed."
        )

    rfq.status = "published"
    rfq.save(update_fields=["status", "updated_at"])

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action="RFQ_PUBLISHED",
            entity_type="RequestForQuotation",
            entity_id=rfq.id,
            after={"status": rfq.status},
            reason="RFQ published to suppliers",
        )
    except Exception:
        pass

    return rfq


@transaction.atomic
def close_request_for_quotation(*, rfq_id, user, notes=""):
    """
    Closes bidding on an RFQ.
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="close RFQs",
    )
    rfq = RequestForQuotation.objects.select_for_update().get(pk=rfq_id)
    if rfq.status not in ("published", "draft"):
        raise ValidationError(f"Cannot close RFQ #{rfq.rfq_number}: status is '{rfq.status}'.")

    rfq.status = "closed"
    rfq.save(update_fields=["status", "updated_at"])

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action="RFQ_CLOSED",
            entity_type="RequestForQuotation",
            entity_id=rfq.id,
            after={"status": rfq.status},
            reason=notes or "RFQ bidding concluded",
        )
    except Exception:
        pass

    return rfq


def calculate_quotation_totals(quotation, save=False):
    """
    Authoritatively computes subtotal, landed cost, and normalized ETB amount for a quotation.
    """
    subtotal = Decimal("0.00")
    for item in quotation.items.all():
        line_gross = (item.quoted_quantity * item.quoted_unit_price).quantize(Decimal("0.01"))
        line_disc = (line_gross * (item.discount_percentage / Decimal("100.00"))).quantize(Decimal("0.01"))
        item.line_total = (line_gross - line_disc).quantize(Decimal("0.01"))
        subtotal += item.line_total
        item.save(update_fields=["line_total"])

    quotation.subtotal = subtotal
    total_quoted = (
        subtotal
        + quotation.shipping_and_handling
        + quotation.customs_and_duties
        + quotation.tax_amount
    ).quantize(Decimal("0.01"))
    quotation.total_quoted_amount = total_quoted
    quotation.total_landed_cost_etb = (total_quoted * quotation.exchange_rate).quantize(Decimal("0.01"))

    if save:
        quotation._allow_immutable_override = True
        quotation.save(update_fields=[
            "subtotal",
            "total_quoted_amount",
            "total_landed_cost_etb",
            "updated_at",
        ])
    return quotation.total_quoted_amount


@transaction.atomic
def submit_supplier_quotation(
    *,
    user,
    supplier_id,
    rfq_id=None,
    requisition_id=None,
    sole_source_justification="",
    supplier_reference="",
    quotation_date=None,
    valid_until=None,
    delivery_lead_time_days=1,
    payment_terms="Net 30",
    warranty_terms="",
    currency="ETB",
    exchange_rate=Decimal("1.0000"),
    shipping_and_handling=Decimal("0.00"),
    customs_and_duties=Decimal("0.00"),
    tax_amount=Decimal("0.00"),
    items_data=None,
):
    """
    Submits a supplier quotation via competitive RFQ tender or justified sole-source path.
    """
    supplier = Supplier.objects.get(pk=supplier_id)
    if isinstance(quotation_date, str):
        from django.utils.dateparse import parse_date
        quotation_date = parse_date(quotation_date)
    quote_date = quotation_date or timezone.now().date()

    if isinstance(valid_until, str):
        from django.utils.dateparse import parse_date
        valid_until = parse_date(valid_until)
    if not valid_until:
        raise ValidationError("Valid until date is required for quotations.")
    if valid_until < quote_date:
        raise ValidationError("valid_until date cannot precede quotation_date.")

    rfq = None
    req = None

    if rfq_id:
        rfq = RequestForQuotation.objects.select_for_update().get(pk=rfq_id)
        if rfq.status != "published":
            raise ValidationError(
                f"Cannot submit quotation against RFQ #{rfq.rfq_number}: RFQ is in status '{rfq.status}', expected 'published'."
            )
        if timezone.now() > rfq.submission_deadline:
            raise ValidationError(
                f"RFQ #{rfq.rfq_number} bidding closed on {rfq.submission_deadline}. Late bids are prohibited."
            )
        if not rfq.is_public_bidding and not rfq.invited_suppliers.filter(pk=supplier.id).exists():
            raise ValidationError(
                f"Supplier '{supplier.name}' is not authorized to bid on restricted RFQ #{rfq.rfq_number}."
            )
    else:
        # Direct sole-source path
        if not requisition_id or not (sole_source_justification and sole_source_justification.strip()):
            raise ValidationError(
                "Direct quotations without an RFQ require a linked Requisition and a documented Sole Source Justification."
            )
        req = PurchaseRequisition.objects.get(pk=requisition_id)
        if req.status != "approved":
            raise ValidationError(
                f"Requisition #{req.requisition_number} must be in 'approved' status for direct quoting."
            )

    if not items_data:
        raise ValidationError("Quotation must contain at least one line item.")

    quotation_num = generate_quotation_number()
    quotation = SupplierQuotation.objects.create(
        quotation_number=quotation_num,
        supplier_reference=supplier_reference.strip(),
        rfq=rfq,
        requisition=req,
        sole_source_justification=sole_source_justification.strip(),
        supplier=supplier,
        quotation_date=quote_date,
        valid_until=valid_until,
        delivery_lead_time_days=delivery_lead_time_days,
        payment_terms=payment_terms.strip(),
        warranty_terms=warranty_terms.strip(),
        currency=currency.upper(),
        exchange_rate=Decimal(str(exchange_rate)),
        shipping_and_handling=Decimal(str(shipping_and_handling)),
        customs_and_duties=Decimal(str(customs_and_duties)),
        tax_amount=Decimal(str(tax_amount)),
        status="submitted",
        created_by=user,
    )

    seen_items = set()
    for idx, line in enumerate(items_data):
        item_id = line.get("item_id")
        if item_id in seen_items:
            raise ValidationError(f"Line #{idx + 1}: Duplicate inventory item in quotation.")
        seen_items.add(item_id)

        qty = Decimal(str(line.get("quoted_quantity", "0")))
        unit_price = Decimal(str(line.get("quoted_unit_price", "0")))
        discount = Decimal(str(line.get("discount_percentage", "0")))

        if qty <= Decimal("0.00"):
            raise ValidationError(f"Line #{idx + 1}: Quoted quantity must be greater than zero.")
        if unit_price < Decimal("0.00"):
            raise ValidationError(f"Line #{idx + 1}: Quoted unit price cannot be negative.")
        if discount < Decimal("0.00") or discount > Decimal("100.00"):
            raise ValidationError(f"Line #{idx + 1}: Discount percentage must be between 0 and 100.")

        inv_item = InventoryItem.objects.get(pk=item_id)
        rfq_item_id = line.get("rfq_item_id")
        rfq_item = None
        if rfq_item_id:
            rfq_item = RequestForQuotationItem.objects.get(pk=rfq_item_id)

        gross = (qty * unit_price).quantize(Decimal("0.01"))
        disc_val = (gross * (discount / Decimal("100.00"))).quantize(Decimal("0.01"))
        line_tot = (gross - disc_val).quantize(Decimal("0.01"))

        SupplierQuotationItem.objects.create(
            quotation=quotation,
            item=inv_item,
            rfq_item=rfq_item,
            quoted_quantity=qty,
            quoted_unit_price=unit_price,
            discount_percentage=discount,
            line_total=line_tot,
            offered_brand_or_spec=line.get("offered_brand_or_spec", "").strip(),
            lead_time_days=line.get("lead_time_days"),
            award_status="pending",
        )

    calculate_quotation_totals(quotation, save=True)

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action="QUOTATION_SUBMITTED",
            entity_type="SupplierQuotation",
            entity_id=quotation.id,
            after={
                "quotation_number": quotation.quotation_number,
                "supplier": supplier.name,
                "total_landed_cost_etb": str(quotation.total_landed_cost_etb),
            },
            reason="Supplier quotation submitted",
        )
    except Exception:
        pass

    return quotation


@transaction.atomic
def evaluate_quotation(*, quotation_id, user, evaluation_notes=""):
    """
    Records committee evaluation notes and moves quotation to under_evaluation.
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory", "finance"},
        action_name="evaluate supplier quotations",
    )
    quotation = SupplierQuotation.objects.select_for_update().get(pk=quotation_id)
    if quotation.status not in ("submitted", "under_evaluation"):
        raise ValidationError(
            f"Cannot evaluate quotation #{quotation.quotation_number}: status is '{quotation.status}'."
        )

    quotation._allow_immutable_override = True
    quotation.status = "under_evaluation"
    quotation.evaluated_by = user
    quotation.evaluated_at = timezone.now()
    quotation.evaluation_notes = f"{quotation.evaluation_notes}\n{evaluation_notes}".strip()
    quotation.save(update_fields=[
        "status",
        "evaluated_by",
        "evaluated_at",
        "evaluation_notes",
        "updated_at",
    ])

    try:
        from apps.audit.services import record_audit_event
        record_audit_event(
            action="QUOTATION_EVALUATED",
            entity_type="SupplierQuotation",
            entity_id=quotation.id,
            after={"evaluation_notes": quotation.evaluation_notes},
            reason="Quotation evaluated by committee",
        )
    except Exception:
        pass

    return quotation


@transaction.atomic
def evaluate_and_award_quotations(
    *, rfq_id=None, awards_data, user, justification
):
    """
    Awards quotation lines or whole quotations based on multi-criteria evaluation
    with mandatory managerial justification.
    awards_data: list of dicts:
      [
        {
          "quotation_id": 12,
          "awarded_item_ids": [101, 102],
          "rejected_item_ids": [103]  # optional
        }, ...
      ]
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory", "finance"},
        action_name="award supplier quotations",
    )
    if not justification or not justification.strip():
        raise ValidationError("A detailed managerial justification is mandatory when awarding quotations.")

    today = timezone.now().date()
    affected_quotations = []

    for award_entry in awards_data:
        q_id = award_entry.get("quotation_id")
        quotation = SupplierQuotation.objects.select_for_update().get(pk=q_id)

        # Immutability & Validity safeguards
        if quotation.status in ("accepted", "converted_to_po", "rejected", "expired", "cancelled"):
            raise ValidationError(
                f"Quotation #{quotation.quotation_number} is in status '{quotation.status}' and cannot be awarded."
            )

        if quotation.valid_until < today:
            quotation._allow_immutable_override = True
            quotation.status = "expired"
            quotation.save(update_fields=["status", "updated_at"])
            raise ValidationError(
                f"Quotation #{quotation.quotation_number} expired on {quotation.valid_until} and cannot be awarded."
            )

        awarded_item_ids = set(award_entry.get("awarded_item_ids", []))
        rejected_item_ids = set(award_entry.get("rejected_item_ids", []))

        total_items = quotation.items.count()
        awarded_count = 0

        for item in quotation.items.all():
            item._allow_award_update = True
            if item.id in awarded_item_ids:
                item.award_status = "awarded"
                awarded_count += 1
            elif item.id in rejected_item_ids or (not awarded_item_ids and item.award_status != "awarded"):
                item.award_status = "rejected"
            item.save(update_fields=["award_status"])

        quotation._allow_immutable_override = True
        if awarded_count == total_items:
            quotation.status = "accepted"
        elif awarded_count > 0:
            quotation.status = "partially_awarded"
        else:
            quotation.status = "rejected"

        quotation.accepted_by = user
        quotation.accepted_at = timezone.now()
        quotation.acceptance_justification = justification.strip()
        quotation.save(update_fields=[
            "status",
            "accepted_by",
            "accepted_at",
            "acceptance_justification",
            "updated_at",
        ])
        affected_quotations.append(quotation)

        try:
            from apps.audit.services import record_audit_event
            action = "QUOTATION_ACCEPTED" if quotation.status in ("accepted", "partially_awarded") else "QUOTATION_REJECTED"
            record_audit_event(
                action=action,
                entity_type="SupplierQuotation",
                entity_id=quotation.id,
                after={
                    "status": quotation.status,
                    "awarded_count": awarded_count,
                    "total_items": total_items,
                },
                reason=justification,
            )
        except Exception:
            pass

    if rfq_id:
        rfq = RequestForQuotation.objects.select_for_update().get(pk=rfq_id)
        rfq.status = "awarded"
        rfq.save(update_fields=["status", "updated_at"])

    return affected_quotations


@transaction.atomic
def convert_awarded_quotations_to_purchase_orders(
    *, quotation_ids, user, delivery_location_id=None
):
    """
    SAFEGUARD 2: Split-award PO conversion.
    Supports multiple Purchase Orders generated from different awarded quotation lines.
    Maintains explicit, auditable award-to-PO relationships at header and line levels.
    """
    _validate_procurement_role(
        user,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="convert awarded quotations to purchase orders",
    )
    created_pos = []

    for q_id in quotation_ids:
        quotation = SupplierQuotation.objects.select_for_update().get(pk=q_id)

        if quotation.status not in ("accepted", "partially_awarded"):
            raise ValidationError(
                f"Quotation #{quotation.quotation_number} is in status '{quotation.status}'. "
                f"Only 'accepted' or 'partially_awarded' quotations can be converted to Purchase Orders."
            )

        # Check un-converted awarded items
        awarded_items = quotation.items.filter(award_status="awarded", is_converted_to_po=False)
        if not awarded_items.exists():
            raise ValidationError(
                f"Quotation #{quotation.quotation_number} has no un-converted awarded items remaining."
            )

        # Determine delivery location
        if delivery_location_id:
            delivery_loc = StockLocation.objects.get(pk=delivery_location_id)
        elif quotation.rfq and quotation.rfq.delivery_location:
            delivery_loc = quotation.rfq.delivery_location
        else:
            delivery_loc = resolve_stock_location()

        # Determine linked requisition (if any)
        orig_req = quotation.requisition
        if not orig_req and quotation.rfq:
            orig_req = quotation.rfq.requisitions.first()

        # Calculate delivery due date
        due_date = quotation.quotation_date + datetime.timedelta(days=quotation.delivery_lead_time_days)

        # Calculate financial totals for this PO from the awarded items
        po_subtotal = Decimal("0.00")
        for item in awarded_items:
            po_subtotal += item.line_total

        # Prorate tax, shipping, and customs based on awarded subtotal / quote subtotal
        ratio = (po_subtotal / quotation.subtotal) if quotation.subtotal > Decimal("0.00") else Decimal("1.00")
        po_tax = (quotation.tax_amount * ratio).quantize(Decimal("0.01"))
        po_shipping = (quotation.shipping_and_handling * ratio).quantize(Decimal("0.01"))
        po_customs = (quotation.customs_and_duties * ratio).quantize(Decimal("0.01"))
        po_total = (po_subtotal + po_tax + po_shipping + po_customs).quantize(Decimal("0.01"))

        po = PurchaseOrder.objects.create(
            po_number=generate_po_number(),
            requisition=orig_req,
            originating_quotation=quotation,
            supplier=quotation.supplier,
            delivery_location=delivery_loc,
            status="issued",
            issued_by=user,
            issued_at=timezone.now(),
            delivery_due_date=due_date,
            payment_terms=quotation.payment_terms,
            subtotal=po_subtotal,
            tax_amount=po_tax,
            total_amount=po_total,
            notes=f"Awarded from Quotation #{quotation.quotation_number} (Vendor Ref: {quotation.supplier_reference or 'N/A'})",
        )

        for item in awarded_items:
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                item=item.item,
                originating_quote_item=item,
                quantity_ordered=item.quoted_quantity,
                quantity_received=Decimal("0.00"),
                unit_price=item.quoted_unit_price,
                line_total=item.line_total,
                notes=item.offered_brand_or_spec or item.notes,
            )

            # Mark line item as converted with line-level conversion tracking
            item._allow_conversion_update = True
            item.is_converted_to_po = True
            item.converted_purchase_order = po
            item.converted_quantity = item.quoted_quantity
            item.save(update_fields=[
                "is_converted_to_po",
                "converted_purchase_order",
                "converted_quantity",
            ])

        # Check if all awarded items on the quotation are now converted
        remaining_unconverted = quotation.items.filter(
            award_status="awarded", is_converted_to_po=False
        ).count()
        if remaining_unconverted == 0:
            quotation._allow_immutable_override = True
            quotation.status = "converted_to_po"
            quotation.save(update_fields=["status", "updated_at"])

        # If linked to requisitions, check if requisition items are fully converted
        if orig_req:
            all_po_items = PurchaseOrderItem.objects.filter(purchase_order__requisition=orig_req)
            ordered_items_count = all_po_items.values("item").distinct().count()
            req_items_count = orig_req.items.count()
            if ordered_items_count >= req_items_count:
                orig_req.status = "converted_to_po"
                orig_req.save(update_fields=["status", "updated_at"])

        created_pos.append(po)

        try:
            from apps.audit.services import record_audit_event
            record_audit_event(
                action="QUOTATION_CONVERTED_TO_PO",
                entity_type="SupplierQuotation",
                entity_id=quotation.id,
                after={"purchase_order": po.po_number, "po_id": po.id},
                reason=f"Converted to Purchase Order {po.po_number}",
            )
            record_audit_event(
                action="PO_ISSUED",
                entity_type="PurchaseOrder",
                entity_id=po.id,
                after={"po_number": po.po_number, "status": po.status},
                reason="PO issued upon quote conversion",
            )
        except Exception:
            pass

    return created_pos
