"""Transaction boundaries for booking, payment and inventory integrity."""
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

import datetime
from .models import (
    AuditEvent,
    BatchLocationBalance,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    PaymentAttempt,
    Reservation,
    Room,
    StockBatch,
    StockBatchConsumption,
    StockLocation,
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
    "pending": {"preparing", "ready", "served", "paid", "cancelled"},
    "preparing": {"ready", "served", "paid", "cancelled"},
    "ready": {"preparing", "served", "paid", "cancelled"},
    "served": {"preparing", "bill_requested", "paid", "cancelled"},
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
def transition_order(*, order_id, to_status, user_id=None):
    from .models import Order
    now = timezone.now()
    order = Order.objects.select_for_update().select_related("table").get(pk=order_id)
    if to_status == order.status:
        return order, False
    if to_status not in ORDER_STATUS_TRANSITIONS.get(order.status, set()):
        raise ValidationError(f"Cannot transition order from {order.status} to {to_status}.")
    order.status = to_status
    update_fields = {"status", "updated_at"}
    if to_status == "served" and not order.served_at:
        order.served_at = now
        update_fields.add("served_at")
        if user_id:
            order.served_by_id_ref = user_id
            update_fields.add("served_by_id_ref")
    elif to_status == "ready" and not order.ready_at:
        order.ready_at = now
        update_fields.add("ready_at")
    elif to_status == "preparing" and not order.preparation_started_at:
        order.preparation_started_at = now
        update_fields.add("preparation_started_at")
    order.save(update_fields=list(update_fields))
    return order, True


@transaction.atomic
def recalculate_order_lifecycle(order_id, user_id=None):
    """
    Indivisibly recalculate overall Order status and milestone timestamps
    based strictly on its constituent non-cancelled OrderItems.
    """
    from .models import Order
    now = timezone.now()
    order = Order.objects.select_for_update().prefetch_related("items").get(pk=order_id)

    # Post-service terminal states (paid, cancelled, bill_requested, finalized) must not regress
    if (
        order.status in ["paid", "cancelled", "bill_requested"]
        or order.payment_status == "paid"
        or order.financials_finalized_at is not None
        or getattr(order, "bill_prepared_at", None) is not None
        or order.cash_handovers.filter(status__in=["pending", "confirmed"]).exists()
    ):
        return order

    all_items = list(order.items.all())
    items = [it for it in all_items if it.status != "cancelled"]

    update_fields = {"updated_at"}

    if not items and all_items:
        # All items were cancelled
        if order.payment_status != "paid" and order.status not in ["paid", "cancelled"]:
            if not order.cash_handovers.filter(status="pending").exists():
                old_status = order.status
                order.status = "cancelled"
                update_fields.add("status")
                order.save(update_fields=list(update_fields))
                try:
                    from apps.audit.services import record_audit_event
                    record_audit_event(
                        action="order_cancelled",
                        entity_type="order",
                        entity_id=str(order.id),
                        before={"status": old_status},
                        after={"status": "cancelled", "reason": "all_items_cancelled"},
                    )
                except Exception:
                    pass
                try:
                    from apps.orders.services import sync_order_financials
                    sync_order_financials(order)
                except Exception:
                    pass
                if order.waiter_id_ref:
                    try:
                        from hotel.models import Notification
                        Notification.objects.create(
                            user_id_ref=order.waiter_id_ref,
                            message=f"Order #ORD-{order.id} (Table {order.table.table_code if order.table else ''}) was cancelled because all items were cancelled.",
                        )
                    except Exception:
                        pass
        return order

    if not items:
        return order

    all_served = all(it.status == "served" for it in items)
    all_ready_or_served = all(it.status in ["ready", "served"] for it in items)
    any_preparing = any(it.status == "preparing" for it in items)
    any_served = any(it.status == "served" for it in items)
    any_ready = any(it.status == "ready" for it in items)

    new_status = order.status

    if all_served:
        new_status = "served"
        if not order.served_at:
            order.served_at = now
            update_fields.add("served_at")
        if not order.served_by_id_ref:
            serving_staff = user_id or next((it.served_by_id_ref for it in reversed(items) if it.served_by_id_ref), None)
            if serving_staff:
                order.served_by_id_ref = serving_staff
                update_fields.add("served_by_id_ref")
    elif all_ready_or_served and any_ready:
        new_status = "ready"
        if not order.ready_at:
            order.ready_at = now
            update_fields.add("ready_at")
    elif any_preparing or any_served or any_ready:
        new_status = "preparing"
        if not order.preparation_started_at:
            prep_starts = [it.preparation_started_at for it in items if it.preparation_started_at]
            order.preparation_started_at = min(prep_starts) if prep_starts else now
            update_fields.add("preparation_started_at")
    else:
        new_status = "pending"

    if not order.received_at:
        earliest_rcv = min((it.received_at for it in items if it.received_at), default=order.created_at)
        order.received_at = earliest_rcv or now
        update_fields.add("received_at")

    if new_status != order.status:
        order.status = new_status
        update_fields.add("status")

    order.save(update_fields=list(update_fields))
    return order


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


def resolve_stock_location(location_val=None):
    """Resolve a location parameter to a StockLocation instance, defaulting to STORE-MAIN."""
    if location_val is None:
        loc = StockLocation.objects.filter(code="STORE-MAIN").first()
        if not loc:
            loc, _ = StockLocation.objects.get_or_create(
                code="STORE-MAIN",
                defaults={"name": "Main Central Store", "location_type": "warehouse", "is_active": True},
            )
        return loc
    if isinstance(location_val, StockLocation):
        return location_val
    if isinstance(location_val, int):
        return StockLocation.objects.get(pk=location_val)
    if isinstance(location_val, str):
        loc = StockLocation.objects.filter(code=location_val).first()
        if loc:
            return loc
        if location_val.isdigit():
            return StockLocation.objects.get(pk=int(location_val))
    return StockLocation.objects.get(pk=location_val)


def compute_stock_payload_hash(
    *,
    item_id,
    transaction_type,
    quantity,
    unit_cost,
    adjustment_direction=None,
    supplier_id=None,
    reference_number=None,
    destination_dept=None,
    destination_room=None,
    location_id=None,
    batch_id=None,
):
    import hashlib
    from decimal import Decimal

    item_id_str = str(item_id).strip()
    tx_type_str = str(transaction_type or "").strip().lower()
    qty_norm = f"{Decimal(str(quantity)).quantize(Decimal('0.01'))}"
    cost_norm = f"{Decimal(str(unit_cost)).quantize(Decimal('0.01'))}"
    adj_dir = str(adjustment_direction or "").strip().lower()
    supp_str = str(supplier_id or "").strip()
    ref_str = str(reference_number or "").strip()
    dept_str = str(destination_dept or "").strip()
    room_str = str(destination_room or "").strip()

    payload_str = f"{item_id_str}:{tx_type_str}:{qty_norm}:{cost_norm}:{adj_dir}:{supp_str}:{ref_str}:{dept_str}:{room_str}"
    if location_id is not None or batch_id is not None:
        loc_str = str(location_id or "").strip()
        b_str = str(batch_id or "").strip()
        payload_str += f":{loc_str}:{b_str}"
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


@transaction.atomic
def record_stock_change(
    *, item_id, transaction_type, quantity, unit_cost,
    adjustment_direction=None, idempotency_key=None, **ledger_values
):
    """
    Authoritative stock mutation service with FEFO/FIFO batch allocation,
    multi-layer StockBatchConsumption breakdown, atomic balance synchronization,
    and strict expired/quarantined batch lockout.
    """
    quantity = Decimal(str(quantity))
    unit_cost = Decimal(str(unit_cost))
    if quantity <= 0 or unit_cost < 0:
        raise ValidationError("Quantity must be positive and unit cost cannot be negative.")

    supplier_val = ledger_values.get("supplier")
    supplier_id = getattr(supplier_val, "pk", supplier_val)

    location_val = ledger_values.pop("location", None)
    batch_val = ledger_values.pop("batch", None)
    batch_number_val = ledger_values.pop("batch_number", None)
    supplier_batch_val = ledger_values.pop("supplier_batch_number", None)
    expiry_date_val = ledger_values.pop("expiry_date", None)

    location = resolve_stock_location(location_val)

    payload_hash = None
    if idempotency_key:
        idempotency_key = str(idempotency_key).strip()
        payload_hash = compute_stock_payload_hash(
            item_id=item_id,
            transaction_type=transaction_type,
            quantity=quantity,
            unit_cost=unit_cost,
            adjustment_direction=adjustment_direction,
            supplier_id=supplier_id,
            reference_number=ledger_values.get("reference_number"),
            destination_dept=ledger_values.get("destination_dept"),
            destination_room=ledger_values.get("destination_room"),
            location_id=getattr(location, "pk", None) if location_val is not None else None,
            batch_id=getattr(batch_val, "pk", batch_val) if batch_val is not None else None,
        )
        existing = StockTransaction.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.payload_hash and existing.payload_hash != payload_hash:
                raise ValidationError("Idempotency key was already used for a different stock payload.")
            item = InventoryItem.objects.select_for_update().get(pk=item_id)
            existing._is_replay = True
            return item, existing

    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    today = timezone.now().date()

    if transaction_type == "adjustment":
        notes = str(ledger_values.get("notes") or "").strip()
        if not notes:
            raise ValidationError("A meaningful adjustment reason is required.")
        if adjustment_direction not in ("increase", "decrease"):
            raise ValidationError("Stock adjustment must specify direction as 'increase' or 'decrease'.")
        is_incoming = (adjustment_direction == "increase")
        delta = quantity if is_incoming else -quantity
    elif transaction_type == "purchase":
        is_incoming = True
        delta = quantity
        adjustment_direction = None
    else:  # issuance, loss, sale_deduction
        is_incoming = False
        delta = -quantity
        adjustment_direction = None

    new_balance = item.current_stock + delta
    if new_balance < 0:
        raise ValidationError(
            f"Insufficient stock for {item.name}. Available: {item.current_stock} {item.unit}, requested: {quantity} {item.unit}."
        )

    # Legacy unbatched stock fallback:
    # If the item has positive aggregate stock but zero batches exist in the system
    # (e.g. created in unit tests or directly via InventoryItem.objects.create),
    # seed the initial legacy batch so allocation can proceed safely.
    if not StockBatch.objects.filter(item=item).exists() and item.current_stock > Decimal("0.00"):
        legacy_status = "unverified_quarantine" if item.is_perishable else "active"
        legacy_batch = StockBatch.objects.create(
            item=item,
            batch_number=f"LEGACY-INITIAL-{item.item_code}",
            initial_quantity=item.current_stock,
            current_quantity=item.current_stock,
            unit_cost=item.unit_cost if item.unit_cost is not None else Decimal("0.00"),
            received_date=today,
            expiry_date=None,
            status=legacy_status,
            is_legacy=True,
        )
        BatchLocationBalance.objects.get_or_create(
            batch=legacy_batch, location=location, defaults={"quantity": item.current_stock}
        )
        ItemLocationBalance.objects.get_or_create(
            item=item, location=location, defaults={"quantity": item.current_stock}
        )

    consumption_records = []
    primary_batch = None
    effective_unit_cost = unit_cost

    try:
        with transaction.atomic():
            if is_incoming:
                # INCOMING: Purchase or Adjustment Increase
                if batch_val:
                    if isinstance(batch_val, StockBatch):
                        batch = StockBatch.objects.select_for_update().get(pk=batch_val.pk)
                    else:
                        batch = StockBatch.objects.select_for_update().get(pk=batch_val)
                    batch.current_quantity += quantity
                    if batch.status == "depleted":
                        batch.status = "active"
                    batch.save(update_fields=["current_quantity", "status"])
                else:
                    bn = batch_number_val or f"BAT-{item.item_code}-{today.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
                    exp_d = expiry_date_val
                    if exp_d is None and item.is_perishable and item.shelf_life_days and item.shelf_life_days > 0:
                        exp_d = today + datetime.timedelta(days=item.shelf_life_days)
                    batch = StockBatch.objects.create(
                        item=item,
                        batch_number=bn,
                        supplier=ledger_values.get("supplier"),
                        supplier_batch_number=supplier_batch_val,
                        initial_quantity=quantity,
                        current_quantity=quantity,
                        unit_cost=unit_cost,
                        received_date=today,
                        expiry_date=exp_d,
                        status="active",
                        is_legacy=False,
                    )
                primary_batch = batch

                # Increment BatchLocationBalance
                blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
                    batch=batch, location=location, defaults={"quantity": Decimal("0.00")}
                )
                blb.quantity += quantity
                blb.save(update_fields=["quantity"])

                # Increment ItemLocationBalance
                ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
                    item=item, location=location, defaults={"quantity": Decimal("0.00")}
                )
                ilb.quantity += quantity
                ilb.save(update_fields=["quantity"])

                # Increment aggregate stock
                InventoryItem.objects.filter(pk=item.pk).update(current_stock=F("current_stock") + quantity)
                if transaction_type == "purchase" and unit_cost > 0:
                    InventoryItem.objects.filter(pk=item.pk).update(unit_cost=unit_cost)

            else:
                # OUTGOING: Issuance, Loss, Sale Deduction, Adjustment Decrease
                if batch_val:
                    # Explicit manual batch selection
                    if isinstance(batch_val, StockBatch):
                        manual_batch = StockBatch.objects.select_for_update().get(pk=batch_val.pk)
                    else:
                        manual_batch = StockBatch.objects.select_for_update().get(pk=batch_val)

                    if manual_batch.item_id != item.pk:
                        raise ValidationError("Specified batch does not belong to this inventory item.")

                    is_waste_disposal = (transaction_type == "loss")
                    if not is_waste_disposal:
                        if manual_batch.expiry_date and manual_batch.expiry_date < today:
                            raise ValidationError(
                                f"Batch '{manual_batch.batch_number}' has expired ({manual_batch.expiry_date}) "
                                f"and cannot be used for {transaction_type}. Expired stock must be routed to waste."
                            )
                        if manual_batch.status == "unverified_quarantine":
                            raise ValidationError(
                                f"Batch '{manual_batch.batch_number}' is in unverified quarantine "
                                f"and cannot be used for {transaction_type} until physically verified."
                            )
                        if manual_batch.status in ("recalled", "depleted"):
                            raise ValidationError(
                                f"Batch '{manual_batch.batch_number}' status is '{manual_batch.status}' and cannot be consumed."
                            )

                    blb = BatchLocationBalance.objects.select_for_update().filter(batch=manual_batch, location=location).first()
                    avail = min(manual_batch.current_quantity, blb.quantity if blb else Decimal("0.00"))
                    if avail < quantity:
                        raise ValidationError(
                            f"Insufficient stock in batch {manual_batch.batch_number} at {location.name}. "
                            f"Available: {avail} {item.unit}, requested: {quantity} {item.unit}."
                        )

                    manual_batch.current_quantity -= quantity
                    if manual_batch.current_quantity == Decimal("0.00"):
                        manual_batch.status = "depleted"
                    manual_batch.save(update_fields=["current_quantity", "status"])

                    if blb:
                        blb.quantity -= quantity
                        blb.save(update_fields=["quantity"])

                    primary_batch = manual_batch
                    layer_cost = (quantity * manual_batch.unit_cost).quantize(Decimal("0.01"))
                    consumption_records.append((manual_batch, quantity, manual_batch.unit_cost, layer_cost))
                    effective_unit_cost = manual_batch.unit_cost

                else:
                    # Authoritative FEFO / FIFO automatic allocation
                    is_waste = transaction_type in ("loss", "waste_disposal")

                    candidate_qs = StockBatch.objects.select_for_update().filter(
                        item=item,
                        current_quantity__gt=Decimal("0.00"),
                    )
                    if is_waste:
                        candidate_qs = candidate_qs.filter(status__in=["active", "expired"])
                    else:
                        candidate_qs = candidate_qs.filter(status="active")

                    if location:
                        candidate_qs = candidate_qs.filter(
                            location_balances__location=location,
                            location_balances__quantity__gt=Decimal("0.00"),
                        )

                    if item.is_perishable:
                        if is_waste:
                            # Waste disposal: write off expired stock first (or nearest to expiry)
                            candidate_qs = candidate_qs.order_by("expiry_date", "received_date", "id")
                        else:
                            # FEFO: Must have known valid expiry date >= today
                            candidate_qs = candidate_qs.filter(
                                expiry_date__isnull=False,
                                expiry_date__gte=today,
                            ).order_by("expiry_date", "received_date", "id")
                    else:
                        if is_waste:
                            candidate_qs = candidate_qs.order_by("received_date", "id")
                        else:
                            # FIFO: Exclude expired if any expiry is recorded, order by received_date
                            candidate_qs = candidate_qs.exclude(
                                expiry_date__lt=today
                            ).order_by("received_date", "id")

                    candidate_batches = list(candidate_qs)

                    # Check available stock across valid candidate batches
                    total_available_valid = Decimal("0.00")
                    for b in candidate_batches:
                        if location:
                            blb_check = BatchLocationBalance.objects.filter(batch=b, location=location).first()
                            b_qty = min(b.current_quantity, blb_check.quantity if blb_check else Decimal("0.00"))
                        else:
                            b_qty = b.current_quantity
                        total_available_valid += max(Decimal("0.00"), b_qty)

                    if total_available_valid < quantity:
                        err_label = "Available" if is_waste else "Available (Unexpired & Verified)"
                        raise ValidationError(
                            f"Insufficient valid stock for {item.name}. Required: {quantity} {item.unit}, "
                            f"{err_label}: {total_available_valid} {item.unit}."
                        )

                    remaining_to_consume = quantity
                    total_cost_layers = Decimal("0.00")

                    for b in candidate_batches:
                        if remaining_to_consume <= Decimal("0.00"):
                            break

                        blb = None
                        if location:
                            blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
                                batch=b, location=location, defaults={"quantity": Decimal("0.00")}
                            )
                            allocatable = min(b.current_quantity, blb.quantity)
                        else:
                            blb = b.location_balances.select_for_update().filter(quantity__gt=Decimal("0.00")).first()
                            allocatable = min(b.current_quantity, blb.quantity) if blb else b.current_quantity

                        if allocatable <= Decimal("0.00"):
                            continue

                        take = min(remaining_to_consume, allocatable)
                        l_cost = (take * b.unit_cost).quantize(Decimal("0.01"))
                        total_cost_layers += l_cost

                        b.current_quantity -= take
                        if b.current_quantity == Decimal("0.00"):
                            b.status = "depleted"
                        b.save(update_fields=["current_quantity", "status"])

                        if blb:
                            blb.quantity -= take
                            blb.save(update_fields=["quantity"])
                            if not location:
                                ilb = ItemLocationBalance.objects.select_for_update().filter(item=item, location=blb.location).first()
                                if ilb:
                                    ilb.quantity = max(Decimal("0.00"), ilb.quantity - take)
                                    ilb.save(update_fields=["quantity"])

                        if primary_batch is None:
                            primary_batch = b

                        consumption_records.append((b, take, b.unit_cost, l_cost))
                        remaining_to_consume -= take

                    if remaining_to_consume > Decimal("0.00"):
                        err_label = "Available" if is_waste else "Available (Unexpired & Verified)"
                        raise ValidationError(
                            f"Insufficient valid stock for {item.name}. Required: {quantity} {item.unit}, "
                            f"{err_label}: {quantity - remaining_to_consume} {item.unit}."
                        )

                    effective_unit_cost = (total_cost_layers / quantity).quantize(Decimal("0.01")) if quantity > 0 else unit_cost

                # Decrement ItemLocationBalance
                if location:
                    ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
                        item=item, location=location, defaults={"quantity": Decimal("0.00")}
                    )
                    ilb.quantity = max(Decimal("0.00"), ilb.quantity - quantity)
                    ilb.save(update_fields=["quantity"])

                # Decrement aggregate stock
                InventoryItem.objects.filter(pk=item.pk).update(current_stock=F("current_stock") - quantity)

            # Create parent StockTransaction ledger record
            ledger = StockTransaction.objects.create(
                item=item,
                transaction_type=transaction_type,
                quantity=quantity,
                unit_cost=effective_unit_cost,
                adjustment_direction=adjustment_direction,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                location=location,
                batch=primary_batch,
                **ledger_values,
            )
            ledger._is_replay = False

            # Create child StockBatchConsumption rows
            for c_batch, c_qty, c_unit_cost, c_total_cost in consumption_records:
                StockBatchConsumption.objects.create(
                    transaction=ledger,
                    batch=c_batch,
                    quantity_consumed=c_qty,
                    unit_cost=c_unit_cost,
                    total_cost=c_total_cost,
                )

    except IntegrityError as exc:
        if idempotency_key and "idempotency_key" in str(exc).lower():
            existing = StockTransaction.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                if existing.payload_hash and existing.payload_hash != payload_hash:
                    raise ValidationError("Idempotency key was already used for a different stock payload.")
                item.refresh_from_db()
                existing._is_replay = True
                return item, existing
        raise

    item.refresh_from_db()
    return item, ledger


@transaction.atomic
def reverse_stock_transaction(*, transaction_id, reason, logged_by_username="", post_gl_reversal=True):
    if not reason or not str(reason).strip():
        raise ValidationError("A reversal reason is required.")
    original = StockTransaction.objects.select_for_update().select_related("item").get(pk=transaction_id)
    if hasattr(original, "reversed_by"):
        return original.reversed_by, False
    item = InventoryItem.objects.select_for_update().get(pk=original.item_id)
    location = original.location or resolve_stock_location(None)

    # Determine direction of original transaction
    if original.transaction_type == "adjustment":
        original_incoming = (getattr(original, "adjustment_direction", "") != "decrease")
    else:
        original_incoming = original.transaction_type in ("purchase",)

    delta = -original.quantity if original_incoming else original.quantity
    if item.current_stock + delta < 0:
        raise ValidationError("Reversal would make stock negative.")

    # Multi-batch layer restoration if original was a deduction
    consumptions = list(original.batch_consumptions.select_related("batch").all())
    if consumptions:
        for c in consumptions:
            batch = StockBatch.objects.select_for_update().get(pk=c.batch_id)
            batch.current_quantity += c.quantity_consumed
            if batch.status == "depleted":
                batch.status = "active"
            batch.save(update_fields=["current_quantity", "status"])

            blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
                batch=batch, location=location, defaults={"quantity": Decimal("0.00")}
            )
            blb.quantity += c.quantity_consumed
            blb.save(update_fields=["quantity"])
    elif not original_incoming and original.batch:
        batch = StockBatch.objects.select_for_update().get(pk=original.batch_id)
        batch.current_quantity += original.quantity
        if batch.status == "depleted":
            batch.status = "active"
        batch.save(update_fields=["current_quantity", "status"])
        blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
            batch=batch, location=location, defaults={"quantity": Decimal("0.00")}
        )
        blb.quantity += original.quantity
        blb.save(update_fields=["quantity"])

    # If original was incoming, decrement batch
    if original_incoming and original.batch:
        batch = StockBatch.objects.select_for_update().get(pk=original.batch_id)
        if batch.current_quantity < original.quantity:
            raise ValidationError("Cannot reverse transaction: batch stock has already been partially or fully consumed.")
        batch.current_quantity -= original.quantity
        if batch.current_quantity == Decimal("0.00"):
            batch.status = "depleted"
        batch.save(update_fields=["current_quantity", "status"])
        blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
            batch=batch, location=location, defaults={"quantity": Decimal("0.00")}
        )
        blb.quantity = max(Decimal("0.00"), blb.quantity - original.quantity)
        blb.save(update_fields=["quantity"])

    # Update ItemLocationBalance
    ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
        item=item, location=location, defaults={"quantity": Decimal("0.00")}
    )
    ilb.quantity = max(Decimal("0.00"), ilb.quantity + delta)
    ilb.save(update_fields=["quantity"])

    # Update aggregate stock
    InventoryItem.objects.filter(pk=item.pk).update(current_stock=F("current_stock") + delta)
    reversal_direction = "decrease" if original_incoming else "increase"

    reversal = StockTransaction.objects.create(
        item=item,
        transaction_type="adjustment",
        quantity=original.quantity,
        unit_cost=original.unit_cost,
        adjustment_direction=reversal_direction,
        reversal_of=original,
        reference_number=f"REV-{original.pk}",
        notes=str(reason).strip(),
        logged_by_username=logged_by_username,
        location=location,
        batch=original.batch,
    )

    # General Ledger compensating entries
    if post_gl_reversal and original.transaction_type != "loss":
        try:
            from hotel.accounting import post_entry
            if consumptions:
                total_cost = sum(c.total_cost for c in consumptions)
            else:
                total_cost = (original.quantity * original.unit_cost).quantize(Decimal("0.01"))

            if total_cost > Decimal("0.00"):
                if original.transaction_type == "purchase":
                    pay_acct = "2000" if original.supplier else "1000"
                    post_entry(
                        description=f"Auto Reversal JV: Purchase #{original.pk} ({item.name}) - {str(reason).strip()}",
                        lines=[
                            {"account_code": pay_acct, "debit": total_cost, "credit": Decimal("0.00")},
                            {"account_code": "1300", "debit": Decimal("0.00"), "credit": total_cost},
                        ],
                    )
                elif original.transaction_type == "issuance":
                    post_entry(
                        description=f"Auto Reversal JV: Issuance #{original.pk} ({item.name}) - {str(reason).strip()}",
                        lines=[
                            {"account_code": "1300", "debit": total_cost, "credit": Decimal("0.00")},
                            {"account_code": "5000", "debit": Decimal("0.00"), "credit": total_cost},
                        ],
                    )
                elif original.transaction_type == "adjustment":
                    if getattr(original, "adjustment_direction", "") == "increase":
                        post_entry(
                            description=f"Auto Reversal JV: Adjustment Increase #{original.pk} ({item.name}) - {str(reason).strip()}",
                            lines=[
                                {"account_code": "5000", "debit": total_cost, "credit": Decimal("0.00")},
                                {"account_code": "1300", "debit": Decimal("0.00"), "credit": total_cost},
                            ],
                        )
                    else:
                        post_entry(
                            description=f"Auto Reversal JV: Adjustment Decrease #{original.pk} ({item.name}) - {str(reason).strip()}",
                            lines=[
                                {"account_code": "1300", "debit": total_cost, "credit": Decimal("0.00")},
                                {"account_code": "5000", "debit": Decimal("0.00"), "credit": total_cost},
                            ],
                        )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Failed to post GL reversal entry for stock transaction #%s: %s", original.pk, e)
            raise ValidationError(f"Accounting reversal failed: {e}") from e

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
                                "account_code": "5010",
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
def approve_waste_entry(*, waste_id=None, waste_record_id=None, reviewer, justification=""):
    from decimal import Decimal
    from django.db.models import Sum

    actual_id = waste_id if waste_id is not None else waste_record_id
    if actual_id is None:
        raise ValidationError("waste_id or waste_record_id is required.")

    try:
        waste = InventoryWasteRecord.objects.select_for_update().get(pk=actual_id)
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

        # Resolve location from storage_area if possible
        target_waste_location = None
        if waste.storage_area:
            from django.db.models import Q
            from hotel.models import StockLocation
            target_waste_location = StockLocation.objects.filter(
                Q(name__icontains=waste.storage_area) | Q(code__iexact=waste.storage_area),
                is_active=True
            ).first()

        updated_item, stx = record_stock_change(
            item_id=item.pk,
            transaction_type="loss",
            quantity=waste.base_quantity,
            unit_cost=waste.unit_cost_snapshot,
            location=target_waste_location,
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
                            "account_code": "5010",
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
