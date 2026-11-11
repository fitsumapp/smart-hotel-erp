"""
hotel/transfers.py
Authoritative Stock Transfer Management Service.
Handles two-phase custody transfers across locations:
  Phase 1: Source Storekeeper Dispatch (Batch allocation & source balance deduction)
  Phase 2: Destination Physical Inspection & Receiving (Destination balance increment & breakage write-off)
"""
import datetime
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from hotel.integrity import resolve_stock_location
from hotel.models import (
    BatchLocationBalance,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    StockBatch,
    StockLocation,
    StockTransfer,
    StockTransferItem,
)


def generate_transfer_number():
    """Generates a human-readable, unique stock transfer code."""
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"TRF-{today_str}-{suffix}"


@transaction.atomic
def request_stock_transfer(
    *,
    source_location,
    destination_location,
    requested_by,
    items,
    notes="",
):
    """
    Creates a new stock transfer requisition in 'requested' status.
    items: list of dicts with keys: 'item_id' (or 'item'), 'quantity_requested' (or 'quantity'), optional 'notes'
    """
    source_loc = resolve_stock_location(source_location)
    dest_loc = resolve_stock_location(destination_location)

    if source_loc.pk == dest_loc.pk:
        raise ValidationError("Source and destination locations cannot be identical.")

    if not items or len(items) == 0:
        raise ValidationError("Transfer request must contain at least one line item.")

    transfer_num = generate_transfer_number()
    transfer = StockTransfer.objects.create(
        transfer_number=transfer_num,
        source_location=source_loc,
        destination_location=dest_loc,
        status="requested",
        requested_by=requested_by,
        requested_at=timezone.now(),
        notes=str(notes or "").strip(),
    )

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

        StockTransferItem.objects.create(
            transfer=transfer,
            item=inv_item,
            quantity_requested=qty_req,
            notes=str(it_data.get("notes") or "").strip(),
        )

    return transfer


@transaction.atomic
def dispatch_stock_transfer(
    *,
    transfer_id,
    dispatcher,
    items_dispatch=None,
    notes="",
):
    """
    Phase 1: Source Storekeeper Dispatches goods into in-transit custody.
    Allocates batches authoritatively via FEFO/FIFO, decrements source location balances,
    and locks stock into in-transit state.
    """
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status != "requested":
        raise ValidationError(f"Cannot dispatch transfer #{transfer.transfer_number}: status is '{transfer.status}', expected 'requested'.")

    dispatcher_role = getattr(dispatcher, "role", "")
    is_superuser = getattr(dispatcher, "is_superuser", False)
    if dispatcher_role not in ("admin", "inventory") and not is_superuser:
        raise PermissionDenied("Only inventory managers or administrators may dispatch stock transfers.")

    today = timezone.now().date()
    source_loc = transfer.source_location

    dispatch_map = {}
    if items_dispatch:
        for d in items_dispatch:
            it_id = d.get("item_id") or d.get("id")
            dispatch_map[it_id] = d

    transfer_items = list(transfer.items.select_for_update().select_related("item").all())
    for it in transfer_items:
        disp_info = dispatch_map.get(it.item_id) or dispatch_map.get(it.id)
        if disp_info and "quantity_dispatched" in disp_info:
            qty_to_dispatch = Decimal(str(disp_info["quantity_dispatched"]))
        else:
            qty_to_dispatch = it.quantity_requested

        if qty_to_dispatch <= Decimal("0.00"):
            raise ValidationError(f"Dispatched quantity for '{it.item.name}' must be greater than zero.")

        # Batch allocation logic at source location
        chosen_batch = None
        if disp_info and disp_info.get("batch_id"):
            b_id = disp_info["batch_id"]
            chosen_batch = StockBatch.objects.select_for_update().get(pk=b_id)
            if chosen_batch.item_id != it.item.pk:
                raise ValidationError(f"Batch '{chosen_batch.batch_number}' does not belong to {it.item.name}.")
        else:
            # Automatic FEFO / FIFO allocation from source location
            candidate_qs = StockBatch.objects.select_for_update().filter(
                item=it.item,
                status="active",
                current_quantity__gt=Decimal("0.00"),
                location_balances__location=source_loc,
                location_balances__quantity__gt=Decimal("0.00"),
            )
            if it.item.is_perishable:
                candidate_qs = candidate_qs.filter(
                    expiry_date__isnull=False,
                    expiry_date__gte=today,
                ).order_by("expiry_date", "received_date", "id")
            else:
                candidate_qs = candidate_qs.exclude(
                    expiry_date__lt=today
                ).order_by("received_date", "id")

            chosen_batch = candidate_qs.first()

        if not chosen_batch:
            raise ValidationError(
                f"Insufficient valid, unexpired stock for '{it.item.name}' at {source_loc.name} to fulfill transfer."
            )

        blb = BatchLocationBalance.objects.select_for_update().filter(
            batch=chosen_batch, location=source_loc
        ).first()
        available_at_source = min(chosen_batch.current_quantity, blb.quantity if blb else Decimal("0.00"))

        if available_at_source < qty_to_dispatch:
            raise ValidationError(
                f"Insufficient stock in batch '{chosen_batch.batch_number}' at {source_loc.name}. "
                f"Available: {available_at_source} {it.item.unit}, requested dispatch: {qty_to_dispatch} {it.item.unit}."
            )

        # Decrement source balances into in-transit custody
        blb.quantity -= qty_to_dispatch
        blb.save(update_fields=["quantity"])

        ilb = ItemLocationBalance.objects.select_for_update().filter(
            item=it.item, location=source_loc
        ).first()
        if ilb:
            ilb.quantity = max(Decimal("0.00"), ilb.quantity - qty_to_dispatch)
            ilb.save(update_fields=["quantity"])

        it.batch = chosen_batch
        it.quantity_dispatched = qty_to_dispatch
        it.unit_cost = chosen_batch.unit_cost
        it.save(update_fields=["batch", "quantity_dispatched", "unit_cost"])

    transfer.status = "in_transit"
    transfer.dispatched_by = dispatcher
    transfer.dispatched_at = timezone.now()
    if notes:
        transfer.notes = f"{transfer.notes}\n[Dispatch]: {notes}".strip()
    transfer.save(update_fields=["status", "dispatched_by", "dispatched_at", "notes", "updated_at"])

    return transfer


@transaction.atomic
def receive_stock_transfer(
    *,
    transfer_id,
    receiver,
    receipt_items=None,
    notes="",
):
    """
    Phase 2: Destination Custodian confirms physical receipt at receiving door.
    Increments destination location balances for intact quantities.
    If transit damage/breakage is recorded, auto-generates InventoryWasteRecord and posts GL loss JV.
    """
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status != "in_transit":
        raise ValidationError(f"Cannot receive transfer #{transfer.transfer_number}: status is '{transfer.status}', expected 'in_transit'.")

    # Separation of duties: Dispatcher cannot confirm receipt for the destination department
    is_superuser = getattr(receiver, "is_superuser", False)
    if receiver == transfer.dispatched_by and not is_superuser:
        raise ValidationError(
            "Storekeeper who dispatched this transfer cannot confirm receipt for the destination department. "
            "Independent destination custodian sign-off is required."
        )

    dest_loc = transfer.destination_location
    today = timezone.now().date()

    receipt_map = {}
    if receipt_items:
        for r in receipt_items:
            it_id = r.get("transfer_item_id") or r.get("item_id") or r.get("id")
            if it_id is not None:
                receipt_map[str(it_id)] = r

    any_damage = False
    transfer_items = list(transfer.items.select_for_update().select_related("item").all())

    for it in transfer_items:
        r_info = receipt_map.get(str(it.id)) or receipt_map.get(str(it.item_id))
        if r_info:
            qty_recv = Decimal(str(r_info.get("quantity_received", it.quantity_dispatched)))
            qty_dam = Decimal(str(r_info.get("quantity_damaged", 0.00)))
        else:
            qty_recv = it.quantity_dispatched
            qty_dam = Decimal("0.00")

        if qty_recv < Decimal("0.00") or qty_dam < Decimal("0.00"):
            raise ValidationError(f"Received and damaged quantities for '{it.item.name}' cannot be negative.")

        if qty_recv + qty_dam != it.quantity_dispatched:
            raise ValidationError(
                f"Quantity reconciliation mismatch for '{it.item.name}'. "
                f"Received ({qty_recv}) + Damaged ({qty_dam}) must equal Dispatched ({it.quantity_dispatched})."
            )

        # 1. Increment intact goods into destination balances
        if qty_recv > Decimal("0.00"):
            blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
                batch=it.batch, location=dest_loc, defaults={"quantity": Decimal("0.00")}
            )
            blb.quantity += qty_recv
            blb.save(update_fields=["quantity"])

            ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
                item=it.item, location=dest_loc, defaults={"quantity": Decimal("0.00")}
            )
            ilb.quantity += qty_recv
            ilb.save(update_fields=["quantity"])

        # 2. Record transit damage / breakage if any
        if qty_dam > Decimal("0.00"):
            any_damage = True
            # Stock was destroyed in transit: reduce aggregate stock and batch stock
            batch = StockBatch.objects.select_for_update().get(pk=it.batch_id)
            batch.current_quantity -= qty_dam
            if batch.current_quantity == Decimal("0.00"):
                batch.status = "depleted"
            batch.save(update_fields=["current_quantity", "status"])

            InventoryItem.objects.filter(pk=it.item.pk).update(current_stock=F("current_stock") - qty_dam)

            damage_cost = (qty_dam * it.unit_cost).quantize(Decimal("0.01"))
            waste_rec = InventoryWasteRecord.objects.create(
                idempotency_key=f"TRF-DAMAGE-{transfer.transfer_number}-{it.id}",
                payload_hash=f"trf-damage:{transfer.pk}:{it.pk}:{qty_dam}:{damage_cost}",
                item=it.item,
                entered_quantity=qty_dam,
                entered_unit=it.item.unit,
                base_quantity=qty_dam,
                waste_category="breakage_or_damage",
                waste_source="direct_loss",
                unit_cost_snapshot=it.unit_cost,
                total_cost_loss=damage_cost,
                stock_deducted=True,
                reported_by_username=getattr(receiver, "username", "system"),
                recorded_at=timezone.now(),
                storage_area=dest_loc.name,
                notes=f"Transit damage on Transfer #{transfer.transfer_number} to {dest_loc.name}.",
            )
            it.waste_record = waste_rec

            # Post General Ledger Spoilage & Waste entry (Dr 5010, Cr 1300)
            if damage_cost > Decimal("0.00"):
                try:
                    from apps.finance.services import post_journal_entry
                    jv = post_journal_entry(
                        description=f"Auto JV: Transit Damage Transfer #{transfer.transfer_number} - {it.item.name} ({qty_dam} {it.item.unit})",
                        items=[
                            {"account_code": "5010", "debit": damage_cost, "credit": Decimal("0.00")},
                            {"account_code": "1300", "debit": Decimal("0.00"), "credit": damage_cost},
                        ],
                    )
                    waste_rec.journal_entry = jv
                    waste_rec.save(update_fields=["journal_entry"])
                except Exception as gl_err:
                    import logging
                    logging.getLogger(__name__).warning("Failed to auto-post GL for transit damage: %s", gl_err)

        it.quantity_received = qty_recv
        it.quantity_damaged = qty_dam
        it.save(update_fields=["quantity_received", "quantity_damaged", "waste_record"])

    transfer.status = "partially_received" if any_damage else "completed"
    transfer.received_by = receiver
    transfer.received_at = timezone.now()
    if notes:
        transfer.notes = f"{transfer.notes}\n[Receipt]: {notes}".strip()
    transfer.save(update_fields=["status", "received_by", "received_at", "notes", "updated_at"])

    return transfer


@transaction.atomic
def cancel_stock_transfer(*, transfer_id, user, reason=""):
    """
    Cancels a transfer request or returns an in-transit delivery to source store.
    """
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer_id)

    if transfer.status in ("draft", "requested"):
        transfer.status = "cancelled"
        transfer.rejection_reason = str(reason or "Cancelled by user").strip()
        transfer.save(update_fields=["status", "rejection_reason", "updated_at"])
        return transfer

    if transfer.status == "in_transit":
        # Delivery rejected at door: return in-transit stock back to source location
        source_loc = transfer.source_location
        transfer_items = list(transfer.items.select_for_update().select_related("item").all())
        for it in transfer_items:
            if it.quantity_dispatched > Decimal("0.00") and it.batch:
                blb, _ = BatchLocationBalance.objects.select_for_update().get_or_create(
                    batch=it.batch, location=source_loc, defaults={"quantity": Decimal("0.00")}
                )
                blb.quantity += it.quantity_dispatched
                blb.save(update_fields=["quantity"])

                ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
                    item=it.item, location=source_loc, defaults={"quantity": Decimal("0.00")}
                )
                ilb.quantity += it.quantity_dispatched
                ilb.save(update_fields=["quantity"])

        transfer.status = "rejected"
        transfer.rejection_reason = str(reason or "Delivery rejected at destination and returned to source store.").strip()
        transfer.save(update_fields=["status", "rejection_reason", "updated_at"])
        return transfer

    raise ValidationError(f"Cannot cancel or reject transfer in '{transfer.status}' status.")
