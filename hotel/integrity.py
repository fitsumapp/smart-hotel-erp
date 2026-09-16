"""Transaction boundaries for booking, payment and inventory integrity."""
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import InventoryItem, PaymentAttempt, Reservation, Room, StockTransaction


ACTIVE_RESERVATION_STATUSES = ("pending", "confirmed", "checked_in")
RESERVATION_STATUS_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"checked_in", "cancelled"},
    "checked_in": {"checked_out"},
    "checked_out": set(),
    "cancelled": set(),
}
ORDER_STATUS_TRANSITIONS = {
    "pending": {"preparing", "paid", "cancelled"},
    "preparing": {"ready", "paid", "cancelled"},
    "ready": {"served", "paid", "cancelled"},
    "served": {"bill_requested", "paid"},
    "bill_requested": {"paid"},
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
