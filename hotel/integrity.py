"""Transaction boundaries for booking, payment and inventory integrity."""
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    AuditEvent,
    InventoryItem,
    InventoryWasteRecord,
    PaymentAttempt,
    Reservation,
    Room,
    StockTransaction,
    SystemSettings,
)


ACTIVE_RESERVATION_STATUSES = ("pending", "confirmed", "checked_in")
RESERVATION_STATUS_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"checked_in", "cancelled", "no_show"},
    "checked_in": {"checked_out"},
    "checked_out": set(),
    "cancelled": set(),
    "no_show": set(),
}
ORDER_STATUS_TRANSITIONS = {
    "pending": {"preparing", "paid", "cancelled"},
    "preparing": {"ready", "paid", "cancelled"},
    "ready": {"served", "paid", "cancelled"},
    "served": {"bill_requested", "paid", "cancelled"},
    "bill_requested": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


@transaction.atomic
def create_reservation_safely(*, room_id, **values):
    """Serialize reservations per room so overlap check and insert are indivisible."""
    room = Room.objects.select_for_update().get(pk=room_id)
    overlaps = Reservation.objects.filter(
        room=room,
        status__in=ACTIVE_RESERVATION_STATUSES,
        check_in_date__lt=values["check_out_date"],
        check_out_date__gt=values["check_in_date"],
    ).exists()
    if overlaps:
        raise ValidationError("This room is already reserved for the selected dates.")
    reservation = Reservation(room=room, **values)
    reservation.full_clean()
    reservation.save()
    return reservation


@transaction.atomic
def transition_reservation(*, reservation_id, to_status, **updates):
    reservation = Reservation.objects.select_for_update().select_related("room").get(pk=reservation_id)
    Room.objects.select_for_update().get(pk=reservation.room_id)
    if to_status == reservation.status:
        return reservation, False
    if to_status not in RESERVATION_STATUS_TRANSITIONS.get(reservation.status, set()):
        raise ValidationError(f"Cannot transition reservation from {reservation.status} to {to_status}.")
    reservation.status = to_status
    for field, value in updates.items():
        setattr(reservation, field, value)
    timestamp_fields = {"checked_in": "checked_in_at", "checked_out": "checked_out_at"}
    if to_status in timestamp_fields and not getattr(reservation, timestamp_fields[to_status]):
        setattr(reservation, timestamp_fields[to_status], timezone.now())
    update_fields = {"status", "updated_at", *updates.keys()}
    if to_status in timestamp_fields:
        update_fields.add(timestamp_fields[to_status])
    reservation.full_clean()
    reservation.save(update_fields=list(update_fields))
    return reservation, True


@transaction.atomic
def transition_order(*, order_id, to_status):
    from .models import Order
    order = Order.objects.select_for_update().select_related("table").get(pk=order_id)
    if to_status == order.status:
        return order, False
    if to_status not in ORDER_STATUS_TRANSITIONS.get(order.status, set()):
        raise ValidationError(f"Cannot transition order from {order.status} to {to_status}.")
    order.status = to_status
    order.save(update_fields=["status", "updated_at"])
    return order, True


@transaction.atomic
def get_or_create_payment_attempt(*, target, expected_amount, idempotency_key, currency="ETB", purpose=None):
    """Return the same attempt for a retry; reject reuse against different input."""
    if not idempotency_key or len(idempotency_key) > 120:
        raise ValidationError("A valid Idempotency-Key header is required.")
    target_field = "order" if target.__class__.__name__ == "Order" else "reservation"
    purpose = purpose or ("order" if target_field == "order" else "reservation_deposit")
    if purpose not in dict(PaymentAttempt.PURPOSE_CHOICES):
        raise ValidationError("Invalid payment purpose.")
    try:
        attempt, created = PaymentAttempt.objects.select_for_update().get_or_create(
            provider="chapa",
            idempotency_key=idempotency_key,
            defaults={
                target_field: target,
                "purpose": purpose,
                "expected_amount": expected_amount,
                "currency": currency,
                "provider_tx_ref": f"{target_field}-{target.pk}-{uuid4().hex[:20]}",
            },
        )
    except IntegrityError:
        attempt = PaymentAttempt.objects.select_for_update().get(provider="chapa", idempotency_key=idempotency_key)
        created = False
    if getattr(attempt, f"{target_field}_id") != target.pk or attempt.purpose != purpose or attempt.expected_amount != Decimal(str(expected_amount)) or attempt.currency != currency:
        raise ValidationError("Idempotency key was already used for a different payment request.")
    return attempt, created


@transaction.atomic
def mark_payment_attempt_verified(*, tx_ref, provider_event_ref=None, safe_metadata=None):
    attempt = PaymentAttempt.objects.select_for_update().get(provider_tx_ref=tx_ref)
    if attempt.status == "verified":
        return attempt, False
    if provider_event_ref and PaymentAttempt.objects.exclude(pk=attempt.pk).filter(provider_event_ref=provider_event_ref).exists():
        raise ValidationError("Provider event was already assigned to another payment.")
    attempt.status = "verified"
    attempt.provider_event_ref = provider_event_ref or attempt.provider_event_ref
    attempt.verified_at = timezone.now()
    attempt.safe_metadata = safe_metadata or {}
    attempt.save(update_fields=["status", "provider_event_ref", "verified_at", "safe_metadata", "updated_at"])
    return attempt, True


@transaction.atomic
def record_stock_change(*, item_id, transaction_type, quantity, unit_cost, **ledger_values):
    """Lock balance, enforce no-negative-stock policy, then append ledger entry."""
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))
    if quantity <= 0 or unit_cost < 0:
        raise ValidationError("Quantity must be positive and unit cost cannot be negative.")
    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    delta = quantity if transaction_type in ("purchase", "adjustment") else -quantity
    new_balance = item.current_stock + delta
    if new_balance < 0:
        raise ValidationError(f"Insufficient stock for {item.name}.")
    InventoryItem.objects.filter(pk=item.pk).update(current_stock=F("current_stock") + delta)
    if transaction_type == "purchase" and unit_cost > 0:
        InventoryItem.objects.filter(pk=item.pk).update(unit_cost=unit_cost)
    ledger = StockTransaction.objects.create(
        item=item, transaction_type=transaction_type, quantity=quantity,
        unit_cost=unit_cost, **ledger_values,
    )
    item.refresh_from_db()
    return item, ledger

@transaction.atomic
def reverse_stock_transaction(*, transaction_id, reason, logged_by_username=""):
    if not reason or not str(reason).strip():
        raise ValidationError("A reversal reason is required.")
    original = StockTransaction.objects.select_for_update().select_related("item").get(pk=transaction_id)
    if hasattr(original, "reversed_by"):
        return original.reversed_by, False
    item = InventoryItem.objects.select_for_update().get(pk=original.item_id)
    incoming = original.transaction_type in ("purchase", "adjustment")
    delta = -original.quantity if incoming else original.quantity
    if item.current_stock + delta < 0:
        raise ValidationError("Reversal would make stock negative.")
    InventoryItem.objects.filter(pk=item.pk).update(current_stock=F("current_stock") + delta)
    reversal = StockTransaction.objects.create(
        item=item, transaction_type="adjustment", quantity=original.quantity,
        unit_cost=original.unit_cost, reversal_of=original,
        reference_number=f"REV-{original.pk}", notes=str(reason).strip(),
        logged_by_username=logged_by_username,
    )
    return reversal, True


def normalize_waste_quantity(item, entered_qty, entered_unit):
    from decimal import Decimal
    try:
        entered_qty = Decimal(str(entered_qty))
    except Exception:
        raise ValidationError("Invalid waste quantity.")

    if entered_qty <= Decimal("0.00"):
        raise ValidationError("Waste quantity must be greater than zero.")

    base_unit = str(item.unit or "").strip().lower()
    entered_unit = str(entered_unit or "").strip().lower()

    # Discrete units check: pcs, bottle
    if entered_unit in ("pcs", "bottle"):
        if entered_qty % Decimal("1") != Decimal("0"):
            raise ValidationError(
                f"Quantity for discrete unit '{entered_unit}' must be a whole number (no fractional or decimal values)."
            )

    if base_unit == entered_unit:
        if base_unit in ("pcs", "bottle"):
            return entered_qty.quantize(Decimal("1.00"))

        if entered_qty != entered_qty.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} {base_unit} exceeds supported precision of 2 decimal places (0.01 {base_unit}). Exact resolution cannot be represented without rounding loss."
            )
        return entered_qty.quantize(Decimal("0.01"))

    # Mass dimension: kg <-> g
    if base_unit == "kg" and entered_unit == "g":
        converted = entered_qty / Decimal("1000")
        if converted != converted.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} g ({converted} kg) results in fractional precision beyond supported 0.01 kg. Submissions in grams must be in multiples of 10 g."
            )
        return converted.quantize(Decimal("0.01"))

    if base_unit == "g" and entered_unit == "kg":
        converted = entered_qty * Decimal("1000")
        if converted != converted.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} kg exceeds supported precision for base unit gram."
            )
        return converted.quantize(Decimal("0.01"))

    # Volume dimension: l <-> ml
    if base_unit == "l" and entered_unit == "ml":
        converted = entered_qty / Decimal("1000")
        if converted != converted.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} ml ({converted} l) results in fractional precision beyond supported 0.01 L. Submissions in milliliters must be in multiples of 10 ml."
            )
        return converted.quantize(Decimal("0.01"))

    if base_unit == "ml" and entered_unit == "l":
        converted = entered_qty * Decimal("1000")
        if converted != converted.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} L exceeds supported precision for base unit milliliter."
            )
        return converted.quantize(Decimal("0.01"))

    # Discrete packaging: pack <-> pcs/bottle via units_per_pack
    multiplier = Decimal(str(getattr(item, "units_per_pack", 1.00) or 1.00))
    if multiplier <= Decimal("0.00"):
        multiplier = Decimal("1.00")

    if base_unit in ("pcs", "bottle") and entered_unit == "pack":
        converted = entered_qty * multiplier
        if converted % Decimal("1") != Decimal("0"):
            raise ValidationError(
                f"Quantity {entered_qty} pack ({converted} {base_unit}) does not result in a whole number of items for pack size {multiplier}."
            )
        return converted.quantize(Decimal("1.00"))

    if base_unit == "pack" and entered_unit in ("pcs", "bottle"):
        converted = entered_qty / multiplier
        if converted != converted.quantize(Decimal("0.01")):
            raise ValidationError(
                f"Quantity {entered_qty} {entered_unit} ({converted} packs) exceeds supported 0.01 pack precision for pack size {multiplier}."
            )
        return converted.quantize(Decimal("0.01"))

    raise ValidationError(
        f"Incompatible unit conversion: Cannot convert '{entered_unit}' to item base unit '{base_unit}' for '{item.name}'. "
        "Conversions across Mass (kg/g), Volume (L/ml), and Count (pcs/bottle/pack) are not permitted."
    )


@transaction.atomic
def record_waste_entry(
    *,
    item_id,
    entered_quantity,
    entered_unit,
    waste_category,
    waste_source,
    idempotency_key,
    notes="",
    storage_area="",
    source_dispatch_id=None,
    logged_by_username="",
):
    import hashlib
    from decimal import Decimal
    from django.db.models import Sum

    if not idempotency_key or len(str(idempotency_key).strip()) == 0 or len(str(idempotency_key)) > 120:
        raise ValidationError("A valid Idempotency-Key header is required.")

    idempotency_key = str(idempotency_key).strip()

    # Calculate payload fingerprint
    payload_str = f"{item_id}:{entered_quantity}:{entered_unit}:{waste_category}:{waste_source}:{source_dispatch_id or ''}"
    payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    # Idempotency check with select_for_update
    existing = InventoryWasteRecord.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValidationError("Idempotency key was already used for a different waste payload.")
        return existing, False

    try:
        item = InventoryItem.objects.select_for_update().get(pk=item_id)
    except InventoryItem.DoesNotExist:
        raise ValidationError("Inventory item not found.")

    base_qty = normalize_waste_quantity(item, entered_quantity, entered_unit)
    if base_qty <= Decimal("0.00"):
        raise ValidationError("Effective waste quantity after normalization must be greater than zero.")

    unit_cost_snapshot = item.unit_cost if item.unit_cost is not None else Decimal("0.00")
    total_cost_loss = (base_qty * unit_cost_snapshot).quantize(Decimal("0.01"))

    # Settings threshold
    settings_obj = SystemSettings.objects.first()
    threshold = getattr(settings_obj, "waste_approval_threshold", Decimal("1000.00")) if settings_obj else Decimal("1000.00")
    if threshold is None:
        threshold = Decimal("1000.00")

    # Approved Decision 2.2: Positive waste with missing or zero unit cost requires manager review regardless of threshold
    requires_approval = False
    if unit_cost_snapshot <= Decimal("0.00"):
        requires_approval = True
    elif total_cost_loss > threshold:
        requires_approval = True

    stock_deducted = False
    stock_transaction = None
    source_dispatch = None
    journal_entry = None
    initial_status = "pending_review" if requires_approval else "approved"

    if waste_source == "direct_loss":
        if item.current_stock < base_qty:
            raise ValidationError(
                f"Insufficient stock for {item.name}. Available: {item.current_stock} {item.unit}, requested waste: {base_qty} {item.unit}."
            )
        if not requires_approval:
            updated_item, stx = record_stock_change(
                item_id=item.pk,
                transaction_type="loss",
                quantity=base_qty,
                unit_cost=unit_cost_snapshot,
                notes=f"Waste Loss [{waste_category}]: {notes}".strip(),
                destination_dept=storage_area or "Waste / Scrap",
                logged_by_username=logged_by_username,
            )
            stock_deducted = True
            stock_transaction = stx

            # Post General Ledger JV if module_finance is enabled
            try:
                from apps.finance.services import post_journal_entry
                if total_cost_loss > Decimal("0.00"):
                    jv = post_journal_entry(
                        description=f"Auto JV: Inventory Waste - {item.name} ({base_qty} {item.unit}) - {waste_category}",
                        items=[
                            {
                                "account_code": "5000",
                                "debit": total_cost_loss,
                                "credit": Decimal("0.00"),
                            },
                            {
                                "account_code": "1300",
                                "debit": Decimal("0.00"),
                                "credit": total_cost_loss,
                            },
                        ],
                    )
                    journal_entry = jv
            except Exception as e:
                raise ValidationError(f"Accounting entry failed for waste loss: {e}") from e
        else:
            stock_deducted = False
            stock_transaction = None
            journal_entry = None

    elif waste_source == "kitchen_prep_waste":
        if not source_dispatch_id:
            raise ValidationError("A valid source dispatch ID is required for kitchen preparation waste.")
        try:
            source_dispatch = StockTransaction.objects.select_for_update().get(
                pk=source_dispatch_id, transaction_type="issuance", item_id=item.pk
            )
        except StockTransaction.DoesNotExist:
            raise ValidationError(f"No matching kitchen issuance transaction found for {item.name} with ID #{source_dispatch_id}.")

        # Pending kitchen prep waste reserves quantity against source issuance
        prev_waste = (
            InventoryWasteRecord.objects.filter(
                source_dispatch=source_dispatch, is_reversed=False
            ).exclude(status="rejected").aggregate(total=Sum("base_quantity"))["total"]
            or Decimal("0.00")
        )

        remaining_issuance = source_dispatch.quantity - prev_waste
        if base_qty > remaining_issuance:
            raise ValidationError(
                f"Cumulative preparation waste ({prev_waste + base_qty} {item.unit}) exceeds issued quantity "
                f"({source_dispatch.quantity} {item.unit}) for Issuance #{source_dispatch.pk}. "
                f"Maximum remaining allowable waste is {remaining_issuance} {item.unit}."
            )
        stock_deducted = False
    else:
        raise ValidationError(f"Invalid waste source: '{waste_source}'. Must be 'direct_loss' or 'kitchen_prep_waste'.")

    waste_record = InventoryWasteRecord.objects.create(
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        item=item,
        entered_quantity=entered_quantity,
        entered_unit=entered_unit,
        base_quantity=base_qty,
        waste_category=waste_category,
        waste_source=waste_source,
        unit_cost_snapshot=unit_cost_snapshot,
        total_cost_loss=total_cost_loss,
        stock_deducted=stock_deducted,
        stock_transaction=stock_transaction,
        source_dispatch=source_dispatch,
        journal_entry=journal_entry,
        notes=notes,
        storage_area=storage_area,
        reported_by_username=logged_by_username,
        recorded_at=timezone.now(),
        status=initial_status,
    )
    return waste_record, True


@transaction.atomic
def approve_waste_entry(*, waste_id, reviewer, justification=""):
    from decimal import Decimal
    from django.db.models import Sum

    try:
        waste = InventoryWasteRecord.objects.select_for_update().get(pk=waste_id)
    except InventoryWasteRecord.DoesNotExist:
        raise ValidationError("Waste record not found.")

    if waste.status != "pending_review":
        raise ValidationError(f"Waste record #{waste.id} is already '{waste.status}' and cannot be approved.")

    reviewer_role = getattr(reviewer, "role", "")
    is_superuser = getattr(reviewer, "is_superuser", False)

    if reviewer_role != "admin" and not is_superuser:
        raise PermissionDenied("Only administrators may approve waste records.")

    # Self-approval check
    is_self = bool(reviewer.username and reviewer.username == waste.reported_by_username)
    if is_self:
        if not is_superuser:
            raise ValidationError("Users cannot approve their own waste submissions. An independent administrator review is required.")
        # Superuser self-approval exception: persistent audit
        waste.is_self_reviewed = True
        waste.self_review_justification = justification.strip() or "Superuser self-approval exception exercised."
        AuditEvent.objects.create(
            actor=reviewer,
            actor_role=reviewer_role or "superuser",
            action="inventory_waste.self_review_exception",
            entity_type="InventoryWasteRecord",
            entity_id=str(waste.id),
            before_summary={"status": waste.status, "reported_by": waste.reported_by_username},
            after_summary={"status": "approved", "reviewed_by": reviewer.username, "is_self_reviewed": True},
            reason=waste.self_review_justification,
            client_metadata={
                "submitting_user": waste.reported_by_username,
                "reviewer": reviewer.username,
                "decision": "approved",
                "self_approval_exception": True,
            },
        )

    # Revalidation for direct loss
    if waste.waste_source == "direct_loss":
        item = InventoryItem.objects.select_for_update().get(pk=waste.item_id)
        effective_cost = waste.unit_cost_snapshot
        if effective_cost <= Decimal("0.00"):
            if item.unit_cost > Decimal("0.00"):
                effective_cost = item.unit_cost
                waste.unit_cost_snapshot = effective_cost
                waste.total_cost_loss = (waste.base_quantity * effective_cost).quantize(Decimal("0.01"))
            else:
                raise ValidationError(
                    f"Cannot approve waste record #{waste.id}: Item '{item.name}' has no valid unit cost (ETB 0.00). "
                    "Update the inventory item's unit cost before approving, or reject the record."
                )

        if item.current_stock < waste.base_quantity:
            raise ValidationError(
                f"Insufficient stock for {item.name}. Available: {item.current_stock} {item.unit}, required waste: {waste.base_quantity} {item.unit}."
            )

        updated_item, stx = record_stock_change(
            item_id=item.pk,
            transaction_type="loss",
            quantity=waste.base_quantity,
            unit_cost=waste.unit_cost_snapshot,
            notes=f"Approved Waste Loss [{waste.waste_category}]: {waste.notes}".strip(),
            destination_dept=waste.storage_area or "Waste / Scrap",
            logged_by_username=reviewer.username,
        )
        waste.stock_deducted = True
        waste.stock_transaction = stx

        try:
            from apps.finance.services import post_journal_entry
            if waste.total_cost_loss > Decimal("0.00"):
                jv = post_journal_entry(
                    description=f"Auto JV: Approved Inventory Waste - {item.name} ({waste.base_quantity} {item.unit}) - {waste.waste_category}",
                    items=[
                        {
                            "account_code": "5000",
                            "debit": waste.total_cost_loss,
                            "credit": Decimal("0.00"),
                        },
                        {
                            "account_code": "1300",
                            "debit": Decimal("0.00"),
                            "credit": waste.total_cost_loss,
                        },
                    ],
                )
                waste.journal_entry = jv
        except Exception as e:
            raise ValidationError(f"Accounting entry failed for approved waste loss: {e}") from e

    elif waste.waste_source == "kitchen_prep_waste":
        source_dispatch = StockTransaction.objects.select_for_update().get(
            pk=waste.source_dispatch_id, transaction_type="issuance", item_id=waste.item_id
        )
        prev_waste = (
            InventoryWasteRecord.objects.filter(
                source_dispatch=source_dispatch, is_reversed=False
            ).exclude(pk=waste.pk).exclude(status="rejected").aggregate(total=Sum("base_quantity"))["total"]
            or Decimal("0.00")
        )
        if prev_waste + waste.base_quantity > source_dispatch.quantity:
            raise ValidationError(
                f"Cumulative preparation waste ({prev_waste + waste.base_quantity} {waste.item.unit}) exceeds issued quantity "
                f"({source_dispatch.quantity} {waste.item.unit}) for Issuance #{source_dispatch.pk}."
            )

    waste.status = "approved"
    waste.reviewed_by = reviewer
    waste.reviewed_by_username = reviewer.username
    waste.reviewed_at = timezone.now()
    waste.save(update_fields=[
        "status", "reviewed_by", "reviewed_by_username", "reviewed_at",
        "is_self_reviewed", "self_review_justification", "unit_cost_snapshot",
        "total_cost_loss", "stock_deducted", "stock_transaction", "journal_entry"
    ])
    return waste


@transaction.atomic
def reject_waste_entry(*, waste_id, reviewer, reason, justification=""):
    try:
        waste = InventoryWasteRecord.objects.select_for_update().get(pk=waste_id)
    except InventoryWasteRecord.DoesNotExist:
        raise ValidationError("Waste record not found.")

    if waste.status != "pending_review":
        raise ValidationError(f"Waste record #{waste.id} is already '{waste.status}' and cannot be rejected.")

    if not reason or not str(reason).strip():
        raise ValidationError("A rejection reason is required.")

    reviewer_role = getattr(reviewer, "role", "")
    is_superuser = getattr(reviewer, "is_superuser", False)

    if reviewer_role != "admin" and not is_superuser:
        raise PermissionDenied("Only administrators may reject waste records.")

    # Self-rejection check
    is_self = bool(reviewer.username and reviewer.username == waste.reported_by_username)
    if is_self:
        if not is_superuser:
            raise ValidationError("Users cannot reject their own waste submissions. An independent administrator review is required.")
        waste.is_self_reviewed = True
        waste.self_review_justification = justification.strip() or f"Superuser self-rejection: {reason.strip()}"
        AuditEvent.objects.create(
            actor=reviewer,
            actor_role=reviewer_role or "superuser",
            action="inventory_waste.self_review_exception",
            entity_type="InventoryWasteRecord",
            entity_id=str(waste.id),
            before_summary={"status": waste.status, "reported_by": waste.reported_by_username},
            after_summary={"status": "rejected", "reviewed_by": reviewer.username, "rejection_reason": reason.strip()},
            reason=reason.strip(),
            client_metadata={
                "submitting_user": waste.reported_by_username,
                "reviewer": reviewer.username,
                "decision": "rejected",
                "self_rejection_exception": True,
            },
        )

    waste.status = "rejected"
    waste.rejection_reason = reason.strip()
    waste.reviewed_by = reviewer
    waste.reviewed_by_username = reviewer.username
    waste.reviewed_at = timezone.now()
    waste.save(update_fields=[
        "status", "rejection_reason", "reviewed_by", "reviewed_by_username",
        "reviewed_at", "is_self_reviewed", "self_review_justification"
    ])
    return waste


@transaction.atomic
def reverse_waste_entry(*, waste_id, reason, logged_by_username=""):
    from decimal import Decimal
    if not reason or not str(reason).strip():
        raise ValidationError("A reversal reason is required.")

    try:
        waste = InventoryWasteRecord.objects.select_for_update().get(pk=waste_id)
    except InventoryWasteRecord.DoesNotExist:
        raise ValidationError("Waste record not found.")

    if waste.status != "approved":
        raise ValidationError(f"Cannot reverse waste record #{waste.id} with status '{waste.status}'. Only approved records can be reversed.")

    if waste.is_reversed or hasattr(waste, "reversed_by"):
        raise ValidationError(f"Waste record #{waste.id} has already been reversed.")
    if waste.reversal_of is not None:
        raise ValidationError("Cannot reverse a reversal waste record.")

    compensating_stx = None
    compensating_jv = None

    if waste.stock_deducted and waste.stock_transaction:
        reversal_stx, created = reverse_stock_transaction(
            transaction_id=waste.stock_transaction.pk,
            reason=f"Reversal of Waste #{waste.id}: {reason.strip()}",
            logged_by_username=logged_by_username,
        )
        compensating_stx = reversal_stx

        if waste.journal_entry:
            try:
                from hotel.accounting import post_entry
                rev_jv = post_entry(
                    description=f"Reversal JV: Waste #{waste.id} ({waste.item.name}) - {reason.strip()}",
                    lines=[
                        {
                            "account_code": "1300",
                            "debit": waste.total_cost_loss,
                            "credit": Decimal("0.00"),
                        },
                        {
                            "account_code": "5000",
                            "debit": Decimal("0.00"),
                            "credit": waste.total_cost_loss,
                        },
                    ],
                    reversal_of=waste.journal_entry,
                )
                compensating_jv = rev_jv
            except Exception as e:
                raise ValidationError(f"Accounting reversal failed: {e}") from e

    waste.is_reversed = True
    waste.reversal_reason = reason.strip()
    waste.reversed_at = timezone.now()
    waste.reversed_by_username = logged_by_username
    waste.save(update_fields=["is_reversed", "reversal_reason", "reversed_at", "reversed_by_username"])

    import hashlib
    reversal_waste = InventoryWasteRecord.objects.create(
        idempotency_key=f"REV-{waste.id}-{uuid4().hex[:12]}",
        payload_hash=hashlib.sha256(f"rev-{waste.id}-{waste.payload_hash}".encode("utf-8")).hexdigest(),
        item=waste.item,
        entered_quantity=waste.entered_quantity,
        entered_unit=waste.entered_unit,
        base_quantity=waste.base_quantity,
        waste_category=waste.waste_category,
        waste_source=waste.waste_source,
        unit_cost_snapshot=waste.unit_cost_snapshot,
        total_cost_loss=waste.total_cost_loss,
        stock_deducted=waste.stock_deducted,
        stock_transaction=compensating_stx,
        source_dispatch=waste.source_dispatch,
        journal_entry=compensating_jv,
        notes=f"Compensating reversal of Waste #{waste.id}: {reason.strip()}",
        storage_area=waste.storage_area,
        reported_by_username=logged_by_username,
        recorded_at=timezone.now(),
        reversal_of=waste,
        is_reversed=True,
        reversal_reason=f"Offset for Waste #{waste.id}",
        reversed_at=timezone.now(),
        reversed_by_username=logged_by_username,
        status="approved",
    )
    return reversal_waste, True
