from decimal import Decimal, ROUND_HALF_UP
import datetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.finance.services import post_journal_entry
from hotel.integrity import (
    approve_waste_entry,
    normalize_waste_quantity,
    record_stock_change,
    record_waste_entry,
    reject_waste_entry,
    resolve_stock_location,
    reverse_stock_transaction,
    reverse_waste_entry,
)
from hotel.models import (
    BatchLocationBalance,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    PurchaseOrder,
    PurchaseOrderItem,
    StockBatch,
    StockLocation,
    StockTransaction,
    Supplier,
)
from hotel.procurement import generate_grn_number, generate_po_number


def convert_item_quantity(item, quantity, from_unit, to_unit=None):
    """
    Authoritative unit conversion engine across inventory operations.
    Converts between mass (kg <-> g), volume (liters/l <-> ml),
    and discrete packaging (pack <-> pcs/bottle) using item.units_per_pack.
    """
    quantity = Decimal(str(quantity))
    base_unit = str(to_unit or item.unit or "").strip().lower()
    from_unit = str(from_unit or base_unit).strip().lower()

    if from_unit == base_unit:
        return quantity

    # Mass conversion
    if base_unit in ("kg", "kilogram", "kilograms") and from_unit in ("g", "gram", "grams"):
        return (quantity / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if base_unit in ("g", "gram", "grams") and from_unit in ("kg", "kilogram", "kilograms"):
        return (quantity * Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Volume conversion
    if base_unit in ("l", "liter", "liters") and from_unit in ("ml", "milliliter", "milliliters"):
        return (quantity / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if base_unit in ("ml", "milliliter", "milliliters") and from_unit in ("l", "liter", "liters"):
        return (quantity * Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Discrete packaging conversion
    units_per_pack = Decimal(str(getattr(item, "units_per_pack", 1.00) or 1.00))
    if units_per_pack <= Decimal("0.00"):
        units_per_pack = Decimal("1.00")

    if base_unit in ("pcs", "piece", "pieces", "bottle", "bottles") and from_unit in ("pack", "packs", "case", "box", "carton"):
        return (quantity * units_per_pack).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
    if base_unit in ("pack", "packs", "case", "box", "carton") and from_unit in ("pcs", "piece", "pieces", "bottle", "bottles"):
        return (quantity / units_per_pack).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    raise ValidationError(
        f"Incompatible unit conversion from '{from_unit}' to base unit '{base_unit}' for item '{item.name}'."
    )


@transaction.atomic
def import_opening_stock_records(records, user, default_location=None, overwrite=False):
    """
    Imports opening stock entries from CSV/Excel or JSON payload.
    - Validates required fields, non-negative costs, and positive quantities.
    - Resolves item, category, location, batch, and expiry date.
    - Prevents accidental double-import unless overwrite=True.
    - Authoritatively updates item.opening_stock, current_stock, batch balances, location balances,
      and writes initial 'purchase' StockTransaction with reference 'OPENING-STOCK'.
    - Posts balancing Opening Equity journal entry: Dr 1300 (Inventory Asset) / Cr 3000 (Retained Earnings).
    """
    if not records or len(records) == 0:
        raise ValidationError("No stock records provided for opening stock import.")

    resolved_default_loc = resolve_stock_location(default_location)
    today = timezone.now().date()
    today_str = today.strftime("%Y%m%d")

    imported_items = []
    total_valuation = Decimal("0.00")

    for idx, r in enumerate(records):
        item_code = str(r.get("item_code") or "").strip()
        item_name = str(r.get("item_name") or r.get("name") or "").strip()
        if not item_name:
            raise ValidationError(f"Row #{idx + 1}: Item name is required.")

        raw_qty = r.get("quantity") or r.get("opening_stock")
        if raw_qty is None:
            raise ValidationError(f"Row #{idx + 1} ('{item_name}'): Opening stock quantity is required.")
        qty = Decimal(str(raw_qty))
        if qty <= Decimal("0.00"):
            raise ValidationError(f"Row #{idx + 1} ('{item_name}'): Opening stock quantity must be greater than zero.")

        raw_cost = r.get("unit_cost", 0.00)
        unit_cost = Decimal(str(raw_cost))
        if unit_cost < Decimal("0.00"):
            raise ValidationError(f"Row #{idx + 1} ('{item_name}'): Unit cost cannot be negative.")

        unit = str(r.get("unit") or "pcs").strip().lower()
        cat_name = str(r.get("category") or r.get("category_name") or "General Inventory").strip()
        category, _ = InventoryCategory.objects.get_or_create(
            name=cat_name, defaults={"category_type": "f_and_b"}
        )

        # Resolve or create InventoryItem
        inv_item = None
        if item_code:
            inv_item = InventoryItem.objects.filter(item_code=item_code).first()
        if not inv_item:
            inv_item = InventoryItem.objects.filter(name__iexact=item_name).first()

        if inv_item:
            if inv_item.opening_stock > Decimal("0.00") and not overwrite:
                raise ValidationError(
                    f"Item '{inv_item.name}' (Code: {inv_item.item_code}) already has an established opening stock of "
                    f"{inv_item.opening_stock} {inv_item.unit}. Pass overwrite=true to adjust."
                )
            inv_item.opening_stock = qty
            inv_item.current_stock = qty
            inv_item.unit_cost = unit_cost
            inv_item.category = category
            inv_item.unit = unit
            inv_item.save(update_fields=["opening_stock", "current_stock", "unit_cost", "category", "unit"])
        else:
            if not item_code:
                item_code = f"ITEM-{today_str}-{idx + 1:04d}"
            inv_item = InventoryItem.objects.create(
                item_code=item_code,
                name=item_name,
                category=category,
                unit=unit,
                opening_stock=qty,
                current_stock=qty,
                unit_cost=unit_cost,
                min_reorder_level=Decimal(str(r.get("min_reorder_level") or 5.00)),
            )

        # Resolve location
        loc_val = r.get("location_code") or r.get("location")
        location = resolve_stock_location(loc_val) if loc_val else resolved_default_loc

        # Parse expiry date
        expiry_date = None
        raw_expiry = r.get("expiry_date")
        if raw_expiry:
            try:
                expiry_date = datetime.date.fromisoformat(str(raw_expiry).strip())
            except ValueError:
                pass

        # Batch creation
        batch_num = str(r.get("batch_number") or f"BAT-OPN-{inv_item.item_code}-{today_str}").strip()
        batch, _ = StockBatch.objects.get_or_create(
            batch_number=batch_num,
            item=inv_item,
            defaults={
                "initial_quantity": qty,
                "current_quantity": qty,
                "unit_cost": unit_cost,
                "received_date": today,
                "expiry_date": expiry_date,
                "status": "active",
                "verified_by": user,
                "verified_at": timezone.now(),
                "verification_notes": "Opening stock import verified.",
            },
        )

        # Update location balances
        blb, _ = BatchLocationBalance.objects.get_or_create(
            batch=batch, location=location, defaults={"quantity": Decimal("0.00")}
        )
        blb.quantity = qty
        blb.save(update_fields=["quantity"])

        ilb, _ = ItemLocationBalance.objects.get_or_create(
            item=inv_item, location=location, defaults={"quantity": Decimal("0.00")}
        )
        ilb.quantity = qty
        ilb.save(update_fields=["quantity"])

        # Audit ledger entry
        StockTransaction.objects.create(
            item=inv_item,
            transaction_type="purchase",
            quantity=qty,
            unit_cost=unit_cost,
            location=location,
            batch=batch,
            reference_number="OPENING-STOCK",
            notes=f"Opening stock intake imported by {user.username}.",
            logged_by_username=user.username,
        )

        row_val = (qty * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_valuation += row_val

        imported_items.append({
            "item_id": inv_item.id,
            "item_code": inv_item.item_code,
            "name": inv_item.name,
            "quantity": str(qty),
            "unit": inv_item.unit,
            "unit_cost": str(unit_cost),
            "valuation": str(row_val),
            "location_code": location.code,
            "batch_number": batch.batch_number,
        })

    # Balance opening inventory in General Ledger
    if total_valuation > Decimal("0.00"):
        try:
            post_journal_entry(
                description=f"Auto Opening Stock Equity: {len(imported_items)} items ({total_valuation} ETB)",
                items=[
                    {"account_code": "1300", "debit": total_valuation, "credit": Decimal("0.00")},
                    {"account_code": "3000", "debit": Decimal("0.00"), "credit": total_valuation},
                ],
            )
        except Exception as gl_err:
            import logging
            logging.getLogger(__name__).warning("Opening stock GL posting skipped: %s", gl_err)

    return {
        "imported_count": len(imported_items),
        "total_valuation": str(total_valuation),
        "items": imported_items,
    }


@transaction.atomic
def execute_spot_purchase(
    *,
    user,
    supplier_id=None,
    supplier_name=None,
    delivery_location=None,
    items,
    payment_method="cash",
    invoice_number=None,
    notes="",
):
    """
    Streamlined spot purchase intake for urgent market purchases.
    - Creates PurchaseOrder with status='completed'.
    - Creates GoodsReceiptNote with status='received'.
    - Invokes authoritative record_stock_change() for each item.
    - Posts balanced GL entry: Dr 1300 (Inventory Asset) / Cr 1000 (Cash) or Cr 2000 (Accounts Payable).
    """
    if not items or len(items) == 0:
        raise ValidationError("Spot purchase must contain at least one line item.")

    location = resolve_stock_location(delivery_location)

    supplier = None
    if supplier_id:
        supplier = Supplier.objects.get(pk=supplier_id)
    elif supplier_name:
        supplier, _ = Supplier.objects.get_or_create(name=str(supplier_name).strip())
    if not supplier:
        supplier, _ = Supplier.objects.get_or_create(name="Direct Market Vendor")

    today = timezone.now().date()
    po_num = generate_po_number()
    grn_num = generate_grn_number()

    po = PurchaseOrder.objects.create(
        po_number=po_num,
        supplier=supplier,
        delivery_location=location,
        status="received",
        issued_by=user,
        issued_at=timezone.now(),
        notes=str(notes or "").strip(),
    )

    grn = GoodsReceiptNote.objects.create(
        grn_number=grn_num,
        purchase_order=po,
        supplier=supplier,
        received_by=user,
        location=location,
        status="approved",
        delivery_note_number=str(invoice_number or "").strip(),
        notes=f"Spot purchase intake: {notes}".strip(),
    )

    total_amount = Decimal("0.00")
    created_lines = []

    for it_data in items:
        inv_item = InventoryItem.objects.get(pk=it_data["item_id"])
        qty = Decimal(str(it_data["quantity"]))
        unit_cost = Decimal(str(it_data.get("unit_cost", inv_item.unit_cost)))

        if qty <= Decimal("0.00") or unit_cost < Decimal("0.00"):
            raise ValidationError("Quantity must be positive and unit cost cannot be negative.")

        line_total = (qty * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += line_total

        poi = PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=inv_item,
            quantity_ordered=qty,
            quantity_received=qty,
            unit_price=unit_cost,
            line_total=line_total,
            notes=str(it_data.get("notes") or "").strip(),
        )

        expiry_date = None
        if it_data.get("expiry_date"):
            try:
                expiry_date = datetime.date.fromisoformat(str(it_data["expiry_date"]))
            except ValueError:
                pass

        # Record stock change authoritatively
        _, stx = record_stock_change(
            item_id=inv_item.pk,
            transaction_type="purchase",
            quantity=qty,
            unit_cost=unit_cost,
            supplier=supplier,
            location=location,
            expiry_date=expiry_date,
            batch_number=it_data.get("batch_number"),
            reference_number=invoice_number or po_num,
            notes=f"Spot purchase on PO #{po_num}.",
            logged_by_username=user.username,
        )

        GoodsReceiptNoteItem.objects.create(
            grn=grn,
            po_item=poi,
            item=inv_item,
            quantity_received=qty,
            quantity_rejected=Decimal("0.00"),
            unit_cost=unit_cost,
            total_cost=line_total,
            batch=stx.batch,
            batch_number=stx.batch.batch_number if stx.batch else "SPOT-BATCH",
        )

        created_lines.append({
            "item_id": inv_item.id,
            "item_name": inv_item.name,
            "quantity": str(qty),
            "unit": inv_item.unit,
            "unit_cost": str(unit_cost),
            "line_total": str(line_total),
        })

    po.subtotal = total_amount
    po.total_amount = total_amount
    po.save(update_fields=["subtotal", "total_amount"])

    grn.total_received_cost = total_amount
    grn.save(update_fields=["total_received_cost"])

    # General ledger entry: Dr 1300 / Cr 1000 (Cash) or 2000 (Accounts Payable)
    credit_account = "1000" if payment_method == "cash" else "2000"
    if total_amount > Decimal("0.00"):
        try:
            post_journal_entry(
                description=f"Spot Purchase #{po_num} - {supplier.name if supplier else 'Direct Market'} ({total_amount} ETB)",
                items=[
                    {"account_code": "1300", "debit": total_amount, "credit": Decimal("0.00")},
                    {"account_code": credit_account, "debit": Decimal("0.00"), "credit": total_amount},
                ],
            )
        except Exception as gl_err:
            import logging
            logging.getLogger(__name__).warning("Spot purchase GL posting skipped: %s", gl_err)

    return {
        "purchase_order_id": po.id,
        "po_number": po.po_number,
        "grn_id": grn.id,
        "grn_number": grn.grn_number,
        "total_amount": str(total_amount),
        "payment_method": payment_method,
        "lines": created_lines,
    }


def generate_stock_movement_report(start_date=None, end_date=None, location_id=None, category_id=None):
    """
    Computes deterministic period stock movement per item and aggregate hotel totals:
    Opening Stock + Purchases + Transfers In - Transfers Out - Issuances/Sales - Waste/Loss +/- Adjustments = Closing Stock.
    """
    from datetime import date, datetime, time
    from django.utils import timezone
    from django.db.models import Q
    from hotel.inventory import transaction_delta

    today = date.today()
    if not start_date:
        start_date = today.replace(day=1)
    elif isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if not end_date:
        end_date = today
    elif isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    # Convert to timezone-aware datetimes
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max))

    items_qs = InventoryItem.objects.all().select_related("category")
    if category_id:
        items_qs = items_qs.filter(category_id=category_id)

    location = None
    if location_id:
        try:
            location = StockLocation.objects.get(id=location_id)
        except StockLocation.DoesNotExist:
            location = None

    rows = []
    tot_opening_val = Decimal("0.00")
    tot_purchases_val = Decimal("0.00")
    tot_transfers_in_val = Decimal("0.00")
    tot_transfers_out_val = Decimal("0.00")
    tot_issuances_val = Decimal("0.00")
    tot_waste_val = Decimal("0.00")
    tot_adjustments_val = Decimal("0.00")
    tot_closing_val = Decimal("0.00")

    for it in items_qs:
        unit_cost = it.unit_cost or Decimal("0.00")

        # 1. Opening stock: cumulative delta prior to start_dt
        prior_txs = it.transactions.filter(timestamp__lt=start_dt)
        if location:
            prior_txs = prior_txs.filter(location=location)
            base_opening = Decimal("0.00")
        else:
            base_opening = Decimal(str(it.opening_stock or "0.00"))

        prior_delta = sum((transaction_delta(t) for t in prior_txs), Decimal("0.00"))
        opening_qty = max(Decimal("0.00"), base_opening + prior_delta)

        # 2. Period transactions
        period_txs = it.transactions.filter(timestamp__gte=start_dt, timestamp__lte=end_dt)
        if location:
            period_txs = period_txs.filter(location=location)

        purchases_qty = Decimal("0.00")
        transfers_in_qty = Decimal("0.00")
        transfers_out_qty = Decimal("0.00")
        issuances_qty = Decimal("0.00")
        waste_qty = Decimal("0.00")
        adjustments_qty = Decimal("0.00")

        for tx in period_txs:
            qty = tx.quantity
            ttype = tx.transaction_type
            if ttype == "purchase":
                purchases_qty += qty
            elif ttype == "transfer_in":
                transfers_in_qty += qty
            elif ttype == "transfer_out":
                transfers_out_qty += qty
            elif ttype in ("issuance", "sale_deduction"):
                issuances_qty += qty
            elif ttype in ("loss", "waste_disposal"):
                waste_qty += qty
            elif ttype == "adjustment":
                adjustments_qty += transaction_delta(tx)

        # 3. Closing Stock
        closing_qty = (
            opening_qty + purchases_qty + transfers_in_qty
            - transfers_out_qty - issuances_qty - waste_qty + adjustments_qty
        )

        # Valuations
        opening_val = (opening_qty * unit_cost).quantize(Decimal("0.01"))
        purchases_val = (purchases_qty * unit_cost).quantize(Decimal("0.01"))
        transfers_in_val = (transfers_in_qty * unit_cost).quantize(Decimal("0.01"))
        transfers_out_val = (transfers_out_qty * unit_cost).quantize(Decimal("0.01"))
        issuances_val = (issuances_qty * unit_cost).quantize(Decimal("0.01"))
        waste_val = (waste_qty * unit_cost).quantize(Decimal("0.01"))
        adjustments_val = (adjustments_qty * unit_cost).quantize(Decimal("0.01"))
        closing_val = (closing_qty * unit_cost).quantize(Decimal("0.01"))

        tot_opening_val += opening_val
        tot_purchases_val += purchases_val
        tot_transfers_in_val += transfers_in_val
        tot_transfers_out_val += transfers_out_val
        tot_issuances_val += issuances_val
        tot_waste_val += waste_val
        tot_adjustments_val += adjustments_val
        tot_closing_val += closing_val

        rows.append({
            "item_id": it.id,
            "item_code": it.item_code,
            "item_name": it.name,
            "category_name": it.category.name if it.category else "Uncategorized",
            "unit": it.unit,
            "unit_cost": str(unit_cost),
            "opening_stock": str(opening_qty),
            "opening_valuation": str(opening_val),
            "purchases": str(purchases_qty),
            "purchases_valuation": str(purchases_val),
            "transfers_in": str(transfers_in_qty),
            "transfers_in_valuation": str(transfers_in_val),
            "transfers_out": str(transfers_out_qty),
            "transfers_out_valuation": str(transfers_out_val),
            "issuances": str(issuances_qty),
            "issuances_valuation": str(issuances_val),
            "waste": str(waste_qty),
            "waste_valuation": str(waste_val),
            "adjustments": str(adjustments_qty),
            "adjustments_valuation": str(adjustments_val),
            "closing_stock": str(closing_qty),
            "closing_valuation": str(closing_val),
        })

    return {
        "period": {
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        "location": {
            "id": location.id if location else None,
            "name": location.name if location else "All Locations (Consolidated)",
            "code": location.code if location else "ALL",
        },
        "item_count": len(rows),
        "totals": {
            "total_opening_valuation": str(tot_opening_val),
            "total_purchases_valuation": str(tot_purchases_val),
            "total_transfers_in_valuation": str(tot_transfers_in_val),
            "total_transfers_out_valuation": str(tot_transfers_out_val),
            "total_issuances_valuation": str(tot_issuances_val),
            "total_waste_valuation": str(tot_waste_val),
            "total_adjustments_valuation": str(tot_adjustments_val),
            "total_closing_valuation": str(tot_closing_val),
            "net_movement_valuation": str((tot_closing_val - tot_opening_val).quantize(Decimal("0.01"))),
        },
        "items": rows,
    }


def generate_gl_reconciliation_report():
    """
    Authoritative reconciliation between Inventory Sub-ledger and General Ledger:
    1. Batch Sub-ledger Valuation by Status (Active, Quarantined, Expired)
    2. Item Master Valuation: sum(item.current_stock * item.unit_cost)
    3. GL Account 1300 Net: sum(debits) - sum(credits)
    4. Discrepancy: GL Balance - Sub-ledger Valuation
    """
    from hotel.models import Account, JournalEntryItem, StockBatch, InventoryItem
    from django.db.models import Sum

    today = timezone.now().date()

    # 1. Sub-ledger batch valuation by status
    batches = StockBatch.objects.filter(current_quantity__gt=Decimal("0.00")).select_related("item")
    subledger_valuation = Decimal("0.00")
    active_batch_valuation = Decimal("0.00")
    quarantined_batch_valuation = Decimal("0.00")
    expired_batch_valuation = Decimal("0.00")

    for b in batches:
        b_val = (b.current_quantity * b.unit_cost).quantize(Decimal("0.01"))
        subledger_valuation += b_val
        if b.status == "active":
            if b.expiry_date and b.expiry_date < today:
                expired_batch_valuation += b_val
            else:
                active_batch_valuation += b_val
        elif b.status in ("quarantined", "unverified_quarantine"):
            quarantined_batch_valuation += b_val
        elif b.status == "expired":
            expired_batch_valuation += b_val

    # 2. Item Master valuation
    items = InventoryItem.objects.filter(current_stock__gt=Decimal("0.00")).select_related("category")
    item_master_valuation = Decimal("0.00")
    category_summary = {}
    for it in items:
        val = (it.current_stock * (it.unit_cost or Decimal("0.00"))).quantize(Decimal("0.01"))
        item_master_valuation += val
        cat_name = it.category.name if it.category else "Uncategorized"
        category_summary[cat_name] = category_summary.get(cat_name, Decimal("0.00")) + val

    # 3. GL Account 1300 (Inventory Asset)
    inv_account = Account.objects.filter(code="1300").first()
    gl_debits = Decimal("0.00")
    gl_credits = Decimal("0.00")
    if inv_account:
        debit_agg = JournalEntryItem.objects.filter(account=inv_account).aggregate(s=Sum("amount_debit"))
        credit_agg = JournalEntryItem.objects.filter(account=inv_account).aggregate(s=Sum("amount_credit"))
        gl_debits = debit_agg["s"] or Decimal("0.00")
        gl_credits = credit_agg["s"] or Decimal("0.00")
    gl_balance = (gl_debits - gl_credits).quantize(Decimal("0.01"))

    # 4. Variance analysis
    gl_subledger_variance = (gl_balance - subledger_valuation).quantize(Decimal("0.01"))
    gl_vs_active_batch_variance = (gl_balance - active_batch_valuation).quantize(Decimal("0.01"))
    master_subledger_variance = (item_master_valuation - subledger_valuation).quantize(Decimal("0.01"))
    is_reconciled = abs(gl_subledger_variance) < Decimal("0.01") and abs(master_subledger_variance) < Decimal("0.01")

    # Recent 10 journal entries affecting Account 1300
    recent_entries = []
    if inv_account:
        recent_items = (
            JournalEntryItem.objects.filter(account=inv_account)
            .select_related("entry")
            .order_by("-entry__created_at")[:10]
        )
        for ji in recent_items:
            recent_entries.append({
                "entry_number": ji.entry.entry_number,
                "created_at": ji.entry.created_at,
                "description": ji.entry.description,
                "debit": str(ji.amount_debit),
                "credit": str(ji.amount_credit),
            })

    return {
        "is_reconciled": is_reconciled,
        "status": "reconciled" if is_reconciled else "discrepancy_detected",
        "subledger_batch_valuation": str(subledger_valuation),
        "active_batch_valuation": str(active_batch_valuation),
        "quarantined_batch_valuation": str(quarantined_batch_valuation),
        "expired_batch_valuation": str(expired_batch_valuation),
        "item_master_valuation": str(item_master_valuation),
        "general_ledger_1300_balance": str(gl_balance),
        "gl_debits_total": str(gl_debits),
        "gl_credits_total": str(gl_credits),
        "gl_vs_subledger_variance": str(gl_subledger_variance),
        "gl_vs_active_batch_variance": str(gl_vs_active_batch_variance),
        "master_vs_subledger_variance": str(master_subledger_variance),
        "category_breakdown": {k: str(v) for k, v in category_summary.items()},
        "recent_journal_entries": recent_entries,
    }


def calculate_authoritative_item_quantities(item_val):
    """
    Computes authoritative inventory quantities and relational integrity metrics for an item.
    Accounts for:
    - Active, quarantined, expired, and depleted batch statuses.
    - Transfers currently in-transit across locations.
    - Multi-location stock distribution.
    - Physical on-hand stock vs available-to-issue stock.
    - Mathematical invariant: (Location Balances Sum + In-Transit Stock == On-Hand Batch Stock).
    """
    from hotel.models import InventoryItem, StockBatch, ItemLocationBalance, StockTransferItem
    from django.db.models import Sum

    if isinstance(item_val, InventoryItem):
        item = item_val
    else:
        try:
            item = InventoryItem.objects.get(pk=item_val)
        except (InventoryItem.DoesNotExist, ValueError):
            item = InventoryItem.objects.get(item_code=str(item_val))

    today = timezone.now().date()

    # 1. Batch sub-ledger quantities
    batches = StockBatch.objects.filter(item=item, current_quantity__gt=Decimal("0.00"))
    on_hand_physical_stock = Decimal("0.00")
    active_stock = Decimal("0.00")
    quarantined_stock = Decimal("0.00")
    expired_stock = Decimal("0.00")

    for b in batches:
        on_hand_physical_stock += b.current_quantity
        if b.status == "active":
            if b.expiry_date and b.expiry_date < today:
                expired_stock += b.current_quantity
            else:
                active_stock += b.current_quantity
        elif b.status in ("quarantined", "unverified_quarantine"):
            quarantined_stock += b.current_quantity
        elif b.status == "expired":
            expired_stock += b.current_quantity

    # 2. Location balances
    loc_balances = ItemLocationBalance.objects.filter(item=item).select_related("location")
    location_breakdown = {}
    location_stock_sum = Decimal("0.00")
    for lb in loc_balances:
        location_breakdown[lb.location.code] = lb.quantity
        location_stock_sum += lb.quantity

    # 3. In-transit custody transfers
    in_transit_items = StockTransferItem.objects.filter(
        item=item, transfer__status="in_transit"
    ).aggregate(s=Sum("quantity_dispatched"))
    in_transit_stock = in_transit_items["s"] or Decimal("0.00")

    # 4. Invariant check: (Location Balances + In-Transit == On-Hand Batch Stock)
    expected_located_stock = location_stock_sum + in_transit_stock
    variance_location_vs_batches = (expected_located_stock - on_hand_physical_stock).quantize(Decimal("0.01"))
    variance_master_vs_batches = (item.current_stock - on_hand_physical_stock).quantize(Decimal("0.01"))
    is_consistent = (abs(variance_location_vs_batches) < Decimal("0.01")) and (abs(variance_master_vs_batches) < Decimal("0.01"))

    # 5. Available to issue: unexpired active stock currently located at a store (excluding in-transit)
    available_to_issue = max(Decimal("0.00"), active_stock - in_transit_stock)

    reconciliation_flags = []
    if expired_stock > Decimal("0.00"):
        reconciliation_flags.append(f"Contains {expired_stock} {item.unit} expired stock pending disposal.")
    if quarantined_stock > Decimal("0.00"):
        reconciliation_flags.append(f"Contains {quarantined_stock} {item.unit} quarantined stock.")
    if in_transit_stock > Decimal("0.00"):
        reconciliation_flags.append(f"{in_transit_stock} {item.unit} currently in transit across locations.")
    if abs(variance_location_vs_batches) >= Decimal("0.01"):
        reconciliation_flags.append(
            f"Location mismatch: sum of locations ({location_stock_sum}) + in-transit ({in_transit_stock}) != batches ({on_hand_physical_stock})."
        )
    if abs(variance_master_vs_batches) >= Decimal("0.01"):
        reconciliation_flags.append(
            f"Master cache mismatch: master ({item.current_stock}) != batches ({on_hand_physical_stock})."
        )

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.name,
        "unit": item.unit,
        "unit_cost": str(item.unit_cost or Decimal("0.00")),
        "master_current_stock": str(item.current_stock),
        "on_hand_physical_stock": str(on_hand_physical_stock),
        "active_stock": str(active_stock),
        "quarantined_stock": str(quarantined_stock),
        "expired_stock": str(expired_stock),
        "in_transit_stock": str(in_transit_stock),
        "location_stock_sum": str(location_stock_sum),
        "location_breakdown": {k: str(v) for k, v in location_breakdown.items()},
        "available_to_issue": str(available_to_issue),
        "is_consistent": is_consistent,
        "variance_location_vs_batches": str(variance_location_vs_batches),
        "variance_master_vs_batches": str(variance_master_vs_batches),
        "reconciliation_flags": reconciliation_flags,
    }


__all__ = [
    "approve_waste_entry",
    "calculate_authoritative_item_quantities",
    "convert_item_quantity",
    "execute_spot_purchase",
    "generate_gl_reconciliation_report",
    "generate_stock_movement_report",
    "import_opening_stock_records",
    "normalize_waste_quantity",
    "record_stock_change",
    "record_waste_entry",
    "reject_waste_entry",
    "reverse_stock_transaction",
    "reverse_waste_entry",
]
