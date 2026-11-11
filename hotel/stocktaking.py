"""
hotel/stocktaking.py
Authoritative Dual-Mode Physical Stocktaking Management Service.

Handles physical inventory counts under 'blind' and 'visible' modes,
enforcing:
- Zero-leak blind count security (theoretical stock hidden from counters)
- Permanent mode locking upon count submission (Owner Decision D-4)
- Strict separation of duties (counted_by != approved_by)
- Two-phase recount discrepancy workflow
- Authoritative stock mutation via record_stock_change()
- Balanced General Ledger posting to Account 5020 (Variance Expense) and 1300 (Inventory Asset)
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.finance.services import post_journal_entry
from hotel.integrity import record_stock_change, resolve_stock_location
from hotel.models import (
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    StockLocation,
    StocktakeItem,
    StocktakeSession,
)

CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def generate_stocktake_session_number():
    """Generates a human-readable, unique stocktake session code (STK-YYYYMMDD-XXXX)."""
    today_str = timezone.now().strftime("%Y%m%d")
    suffix = uuid4().hex[:6].upper()
    return f"STK-{today_str}-{suffix}"


@transaction.atomic
def create_stocktake_session(
    *,
    location,
    category=None,
    counting_mode="blind",
    title=None,
    created_by,
):
    """
    Creates a new physical stocktake session and snapshots theoretical inventory balances.
    
    counting_mode: 'blind' (default) or 'visible'
    category: optional InventoryCategory instance or pk to scope the stocktake
    """
    loc = resolve_stock_location(location)
    if not loc.is_active:
        raise ValidationError(f"Stock location '{loc.name}' is inactive.")

    if counting_mode not in ("blind", "visible"):
        raise ValidationError(f"Invalid counting mode '{counting_mode}'. Must be 'blind' or 'visible'.")

    category_obj = None
    if category:
        if isinstance(category, InventoryCategory):
            category_obj = category
        else:
            category_obj = InventoryCategory.objects.get(pk=category)

    session_num = generate_stocktake_session_number()
    session_title = (
        title.strip()
        if title and str(title).strip()
        else f"Stocktake {loc.name} ({counting_mode.capitalize()}) - {timezone.now().strftime('%Y-%m-%d')}"
    )

    session = StocktakeSession.objects.create(
        session_number=session_num,
        title=session_title,
        location=loc,
        category=category_obj,
        counting_mode=counting_mode,
        is_mode_locked=False,
        status="draft",
        created_by=created_by,
    )

    # Snapshot theoretical balances from ItemLocationBalance
    balances_map = {
        ilb.item_id: ilb.quantity
        for ilb in ItemLocationBalance.objects.filter(location=loc)
    }

    if category_obj:
        items = list(InventoryItem.objects.filter(category=category_obj).order_by("name"))
    else:
        if balances_map:
            items = list(InventoryItem.objects.filter(id__in=balances_map.keys()).order_by("name"))
        else:
            items = list(InventoryItem.objects.all().order_by("name"))

    total_theoretical_val = Decimal("0.00")
    stocktake_items = []

    for item in items:
        theor_qty = balances_map.get(item.pk)
        if theor_qty is None:
            # Fallback for MAIN_STORE if legacy stock is present on item.current_stock
            if loc.code == "STORE-MAIN" and item.current_stock > Decimal("0.00"):
                theor_qty = item.current_stock
                ItemLocationBalance.objects.get_or_create(
                    item=item, location=loc, defaults={"quantity": item.current_stock}
                )
            else:
                theor_qty = Decimal("0.00")

        unit_cost = item.unit_cost if item.unit_cost is not None else Decimal("0.00")
        line_theor_val = _money(theor_qty * unit_cost)
        total_theoretical_val += line_theor_val

        stocktake_items.append(
            StocktakeItem(
                session=session,
                item=item,
                theoretical_quantity=theor_qty,
                counted_quantity=None,
                recounted_quantity=None,
                final_quantity=None,
                unit_cost_snapshot=unit_cost,
                variance_quantity=Decimal("0.00"),
                variance_value=Decimal("0.00"),
                requires_recount=False,
            )
        )

    StocktakeItem.objects.bulk_create(stocktake_items)
    session.total_theoretical_value = total_theoretical_val
    session.save(update_fields=["total_theoretical_value"])

    return session


@transaction.atomic
def record_counts(
    *,
    session_id,
    counts_data,
    user,
):
    """
    Submits physical count data for a stocktake session.
    Permanently locks the counting mode (Owner Decision D-4).
    Transitions status -> 'under_review'.
    
    counts_data: list of dicts:
      [{'item_id': 1, 'counted_quantity': Decimal('10.00'), 'notes': ''}]
      or [{'id': <stocktake_item_id>, 'counted_quantity': Decimal('10.00')}]
    """
    session = StocktakeSession.objects.select_for_update().get(pk=session_id)
    if session.status not in ("draft", "in_progress", "recount_required"):
        raise ValidationError(f"Cannot record counts for session in '{session.status}' status.")

    if not counts_data:
        raise ValidationError("Count submission must contain at least one item count.")

    # Permanent mode locking on first count submission (Owner Decision D-4)
    session.is_mode_locked = True

    items_map_by_id = {it.pk: it for it in session.items.select_for_update().all()}
    items_map_by_item_id = {it.item_id: it for it in items_map_by_id.values()}

    now = timezone.now()
    updated_items = []

    for entry in counts_data:
        stk_item = None
        if "id" in entry and entry["id"] in items_map_by_id:
            stk_item = items_map_by_id[entry["id"]]
        elif "stocktake_item_id" in entry and entry["stocktake_item_id"] in items_map_by_id:
            stk_item = items_map_by_id[entry["stocktake_item_id"]]
        elif "item_id" in entry and entry["item_id"] in items_map_by_item_id:
            stk_item = items_map_by_item_id[entry["item_id"]]
        elif "item" in entry and getattr(entry["item"], "pk", entry["item"]) in items_map_by_item_id:
            stk_item = items_map_by_item_id[getattr(entry["item"], "pk", entry["item"])]

        if not stk_item:
            continue

        raw_count = entry.get("counted_quantity")
        if raw_count is None:
            continue

        counted_qty = Decimal(str(raw_count))
        if counted_qty < Decimal("0.00"):
            raise ValidationError(f"Counted quantity cannot be negative for item {stk_item.item.name}.")

        stk_item.counted_quantity = counted_qty
        stk_item.final_quantity = counted_qty
        stk_item.variance_quantity = stk_item.final_quantity - stk_item.theoretical_quantity
        stk_item.variance_value = _money(stk_item.variance_quantity * stk_item.unit_cost_snapshot)
        stk_item.counted_at = now
        if "notes" in entry and entry["notes"]:
            stk_item.notes = str(entry["notes"]).strip()
        stk_item.save(
            update_fields=[
                "counted_quantity",
                "final_quantity",
                "variance_quantity",
                "variance_value",
                "counted_at",
                "notes",
            ]
        )
        updated_items.append(stk_item)

    if not updated_items:
        raise ValidationError("No matching stocktake items were found in the submitted count data.")

    # Recompute session totals
    all_items = list(session.items.all())
    total_counted_val = sum(
        _money((it.final_quantity if it.final_quantity is not None else Decimal("0.00")) * it.unit_cost_snapshot)
        for it in all_items
    )
    total_var_val = sum(it.variance_value for it in all_items if it.final_quantity is not None)

    session.total_counted_value = total_counted_val
    session.total_variance_value = total_var_val
    session.status = "under_review"
    session.counted_by = user
    session.counted_at = now
    session.save(
        update_fields=[
            "is_mode_locked",
            "total_counted_value",
            "total_variance_value",
            "status",
            "counted_by",
            "counted_at",
            "updated_at",
        ]
    )

    return session


@transaction.atomic
def request_recount(
    *,
    session_id,
    item_ids,
    reason,
    supervisor,
):
    """
    Supervisor flags specific items requiring a physical recount due to excessive variance.
    Transitions status -> 'recount_required'.
    """
    session = StocktakeSession.objects.select_for_update().get(pk=session_id)
    if session.status != "under_review":
        raise ValidationError(f"Cannot request recount for session in '{session.status}' status. Must be 'under_review'.")

    if not item_ids:
        raise ValidationError("At least one item must be specified for recount.")

    items_to_recount = session.items.filter(id__in=item_ids)
    if not items_to_recount.exists():
        items_to_recount = session.items.filter(item_id__in=item_ids)

    if not items_to_recount.exists():
        raise ValidationError("No valid items found for recount.")

    for stk_item in items_to_recount:
        stk_item.requires_recount = True
        if reason:
            existing_notes = stk_item.notes or ""
            stk_item.notes = f"{existing_notes}\n[Recount requested: {reason}]".strip()
        stk_item.save(update_fields=["requires_recount", "notes"])

    session.status = "recount_required"
    session.save(update_fields=["status", "updated_at"])
    return session


@transaction.atomic
def submit_recount(
    *,
    session_id,
    recount_data,
    user,
):
    """
    Submits recounted physical quantities, clears requires_recount flag,
    and returns session to 'under_review'.
    """
    session = StocktakeSession.objects.select_for_update().get(pk=session_id)
    if session.status != "recount_required":
        raise ValidationError(f"Cannot submit recount for session in '{session.status}' status.")

    if not recount_data:
        raise ValidationError("Recount submission must contain recount data.")

    items_map_by_id = {it.pk: it for it in session.items.select_for_update().all()}
    items_map_by_item_id = {it.item_id: it for it in items_map_by_id.values()}

    now = timezone.now()
    updated_items = []

    for entry in recount_data:
        stk_item = None
        if "id" in entry and entry["id"] in items_map_by_id:
            stk_item = items_map_by_id[entry["id"]]
        elif "stocktake_item_id" in entry and entry["stocktake_item_id"] in items_map_by_id:
            stk_item = items_map_by_id[entry["stocktake_item_id"]]
        elif "item_id" in entry and entry["item_id"] in items_map_by_item_id:
            stk_item = items_map_by_item_id[entry["item_id"]]
        elif "item" in entry and getattr(entry["item"], "pk", entry["item"]) in items_map_by_item_id:
            stk_item = items_map_by_item_id[getattr(entry["item"], "pk", entry["item"])]

        if not stk_item:
            continue

        raw_count = entry.get("recounted_quantity", entry.get("counted_quantity"))
        if raw_count is None:
            continue

        recounted_qty = Decimal(str(raw_count))
        if recounted_qty < Decimal("0.00"):
            raise ValidationError(f"Recounted quantity cannot be negative for item {stk_item.item.name}.")

        stk_item.recounted_quantity = recounted_qty
        stk_item.final_quantity = recounted_qty
        stk_item.variance_quantity = stk_item.final_quantity - stk_item.theoretical_quantity
        stk_item.variance_value = _money(stk_item.variance_quantity * stk_item.unit_cost_snapshot)
        stk_item.requires_recount = False
        stk_item.counted_at = now
        if "notes" in entry and entry["notes"]:
            stk_item.notes = f"{stk_item.notes}\n[Recounted: {entry['notes']}]".strip()
        stk_item.save(
            update_fields=[
                "recounted_quantity",
                "final_quantity",
                "variance_quantity",
                "variance_value",
                "requires_recount",
                "counted_at",
                "notes",
            ]
        )
        updated_items.append(stk_item)

    if not updated_items:
        raise ValidationError("No matching stocktake items were found for recount.")

    # Recompute session totals
    all_items = list(session.items.all())
    total_counted_val = sum(
        _money((it.final_quantity if it.final_quantity is not None else Decimal("0.00")) * it.unit_cost_snapshot)
        for it in all_items
    )
    total_var_val = sum(it.variance_value for it in all_items if it.final_quantity is not None)

    session.total_counted_value = total_counted_val
    session.total_variance_value = total_var_val
    session.status = "under_review"
    session.save(
        update_fields=[
            "total_counted_value",
            "total_variance_value",
            "status",
            "updated_at",
        ]
    )

    return session


@transaction.atomic
def approve_stocktake_session(
    *,
    session_id,
    supervisor,
    notes="",
    emergency_self_approval=False,
    justification="",
):
    """
    Supervisor approves physical stocktake variances:
    1. Enforces strict separation of duties (counted_by != approved_by).
       Superuser self-approval requires explicit emergency flag & justification,
       and logs an immutable AuditEvent.
    2. Invokes authoritative record_stock_change() for each non-zero variance.
       - Surplus: adjustment increase
       - Deficit: adjustment decrease
    3. Posts balanced General Ledger JournalEntry against Account 5020 and 1300.
    4. Transitions status -> 'approved'.
    5. Fully idempotent (safe replay if already approved).
    """
    session = StocktakeSession.objects.select_for_update().get(pk=session_id)

    # Idempotent replay safety
    if session.status == "approved":
        return session

    if session.status not in ("under_review", "in_progress", "recount_required"):
        raise ValidationError(f"Cannot approve stocktake session in '{session.status}' status.")

    # Separation of Duties check
    if session.counted_by and supervisor.username == session.counted_by.username:
        if not (supervisor.is_superuser and emergency_self_approval):
            raise PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")
        justification_clean = (justification or notes or "").strip()
        if len(justification_clean) < 15:
            raise ValidationError("A detailed justification (minimum 15 characters) is required for superuser emergency self-approval.")
        from hotel.models import AuditEvent
        AuditEvent.objects.create(
            actor=supervisor,
            actor_role="superuser",
            action="stocktake.emergency_self_approval",
            entity_type="StocktakeSession",
            entity_id=str(session.id),
            before_summary={"status": session.status, "counted_by": session.counted_by.username},
            after_summary={"status": "approved", "reviewed_by": supervisor.username, "emergency_self_approval": True},
            reason=justification_clean,
            client_metadata={
                "counted_by": session.counted_by.username,
                "approved_by": supervisor.username,
                "emergency_self_approval": True,
            },
        )

    items = list(session.items.select_related("item").all())
    if not items:
        raise ValidationError("Cannot approve an empty stocktake session.")

    # Validate all items have counts recorded
    for it in items:
        if it.final_quantity is None:
            if it.counted_quantity is not None:
                it.final_quantity = it.counted_quantity
            else:
                raise ValidationError(f"Item '{it.item.name}' has not been counted.")

    if any(it.requires_recount for it in items):
        raise ValidationError("Cannot approve session while items are still pending recount.")

    total_surplus_value = Decimal("0.00")
    total_deficit_value = Decimal("0.00")

    for it in items:
        variance = it.final_quantity - it.theoretical_quantity
        it.variance_quantity = variance
        it.variance_value = _money(variance * it.unit_cost_snapshot)
        it.save(update_fields=["variance_quantity", "variance_value", "final_quantity"])

        if variance > Decimal("0.00"):
            # Surplus -> Increase stock
            record_stock_change(
                item_id=it.item.pk,
                transaction_type="adjustment",
                adjustment_direction="increase",
                quantity=variance,
                unit_cost=it.unit_cost_snapshot,
                location=session.location,
                notes=f"Stocktake {session.session_number} surplus adjustment: +{variance} {it.item.unit}",
                idempotency_key=f"STK-ADJ-INC-{session.session_number}-{it.item.pk}",
            )
            total_surplus_value += abs(it.variance_value)
        elif variance < Decimal("0.00"):
            # Deficit / Shrinkage -> Decrease stock
            record_stock_change(
                item_id=it.item.pk,
                transaction_type="adjustment",
                adjustment_direction="decrease",
                quantity=abs(variance),
                unit_cost=it.unit_cost_snapshot,
                location=session.location,
                notes=f"Stocktake {session.session_number} shrinkage adjustment: -{abs(variance)} {it.item.unit}",
                idempotency_key=f"STK-ADJ-DEC-{session.session_number}-{it.item.pk}",
            )
            total_deficit_value += abs(it.variance_value)

    # Balanced General Ledger Journal Entry
    # Account 5020: Inventory Stocktake Variance Expense
    # Account 1300: Inventory Asset
    gl_lines = []
    if total_deficit_value > Decimal("0.00"):
        gl_lines.append({
            "account_code": "5020",
            "debit": total_deficit_value,
            "credit": Decimal("0.00"),
        })
        gl_lines.append({
            "account_code": "1300",
            "debit": Decimal("0.00"),
            "credit": total_deficit_value,
        })
    if total_surplus_value > Decimal("0.00"):
        gl_lines.append({
            "account_code": "1300",
            "debit": total_surplus_value,
            "credit": Decimal("0.00"),
        })
        gl_lines.append({
            "account_code": "5020",
            "debit": Decimal("0.00"),
            "credit": total_surplus_value,
        })

    if gl_lines:
        entry = post_journal_entry(
            description=f"Stocktake Variance: {session.session_number} ({session.location.name})",
            items=gl_lines,
            date=timezone.now().date(),
        )
        session.journal_entry = entry

    now = timezone.now()
    session.status = "approved"
    session.reviewed_by = supervisor
    session.reviewed_at = now
    session.variance_approval_notes = notes or ""
    session.total_counted_value = sum(_money(it.final_quantity * it.unit_cost_snapshot) for it in items)
    session.total_variance_value = sum(it.variance_value for it in items)
    session.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "variance_approval_notes",
            "total_counted_value",
            "total_variance_value",
            "journal_entry",
            "updated_at",
        ]
    )

    return session


@transaction.atomic
def cancel_stocktake_session(
    *,
    session_id,
    user,
    reason="",
):
    """
    Cancels a stocktake session without modifying stock or posting GL entries.
    """
    session = StocktakeSession.objects.select_for_update().get(pk=session_id)
    if session.status == "approved":
        raise ValidationError("Cannot cancel an already approved stocktake session.")

    if session.status == "cancelled":
        return session

    session.status = "cancelled"
    if reason:
        existing_notes = session.variance_approval_notes or ""
        session.variance_approval_notes = f"[Cancelled: {reason}] {existing_notes}".strip()
    session.save(update_fields=["status", "variance_approval_notes", "updated_at"])
    return session


def compute_next_run(frequency, scheduled_time, day_of_week=None, day_of_month=None, from_time=None):
    """
    Computes the next local execution timestamp for a schedule in Africa/Addis_Ababa timezone.
    frequency: 'daily' | 'weekly' | 'monthly'
    scheduled_time: datetime.time or str 'HH:MM'
    day_of_week: 0=Monday..6=Sunday (for weekly)
    day_of_month: 1..31 (for monthly)
    from_time: datetime (optional baseline)
    """
    import datetime
    import calendar
    import zoneinfo
    from django.conf import settings
    from django.utils import timezone

    hotel_tz = zoneinfo.ZoneInfo(getattr(settings, "TIME_ZONE", "Africa/Addis_Ababa"))
    base_dt = (from_time or timezone.now()).astimezone(hotel_tz)

    if isinstance(scheduled_time, str):
        parts = [int(p) for p in scheduled_time.split(":")[:2]]
        t = datetime.time(parts[0], parts[1])
    else:
        t = scheduled_time

    if frequency == "daily":
        candidate = datetime.datetime.combine(base_dt.date(), t, tzinfo=hotel_tz)
        if candidate <= base_dt:
            candidate += datetime.timedelta(days=1)
        return candidate

    elif frequency == "weekly":
        target_dow = day_of_week if day_of_week is not None else 0
        days_ahead = (target_dow - base_dt.weekday()) % 7
        candidate = datetime.datetime.combine(base_dt.date() + datetime.timedelta(days=days_ahead), t, tzinfo=hotel_tz)
        if candidate <= base_dt:
            candidate += datetime.timedelta(days=7)
        return candidate

    elif frequency == "monthly":
        target_dom = day_of_month if day_of_month is not None else 1
        year = base_dt.year
        month = base_dt.month
        max_days = calendar.monthrange(year, month)[1]
        dom = min(target_dom, max_days)
        candidate = datetime.datetime.combine(datetime.date(year, month, dom), t, tzinfo=hotel_tz)
        if candidate <= base_dt:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            max_days = calendar.monthrange(year, month)[1]
            dom = min(target_dom, max_days)
            candidate = datetime.datetime.combine(datetime.date(year, month, dom), t, tzinfo=hotel_tz)
        return candidate

    return base_dt + datetime.timedelta(days=1)


@transaction.atomic
def process_due_stocktake_schedules(now=None):
    """
    Evaluates active StocktakeSchedule records and generates draft stocktake sessions for due schedules.
    Ensures:
      - Period idempotency: prevents duplicate sessions for the same schedule and target date.
      - Safe recovery after service downtime: creates at most 1 session per missed schedule and rolls forward.
      - Zero automated counting, variance approval, or accounting posting.
      - Proper assigned staff and counting mode inheritance.
    """
    import zoneinfo
    from django.conf import settings
    from django.utils import timezone
    from hotel.models import StocktakeSchedule, StocktakeSession, Notification

    hotel_tz = zoneinfo.ZoneInfo(getattr(settings, "TIME_ZONE", "Africa/Addis_Ababa"))
    current_time = (now or timezone.now()).astimezone(hotel_tz)
    today = current_time.date()

    due_schedules = list(
        StocktakeSchedule.objects.select_for_update(of=("self",)).filter(
            is_active=True,
            next_run_at__lte=current_time,
        ).select_related("location", "created_by")
    )

    executed = []
    skipped = []
    failed = []

    for sched in due_schedules:
        target_date = sched.next_run_at.astimezone(hotel_tz).date()

        # Check for existing session for this schedule and target date
        existing = StocktakeSession.objects.filter(
            schedule=sched,
            scheduled_date=target_date,
        ).first()

        if existing:
            # Already created for this target date; advance next_run_at
            next_run = compute_next_run(
                sched.frequency,
                sched.scheduled_time,
                sched.day_of_week,
                sched.day_of_month,
                from_time=current_time,
            )
            sched.next_run_at = next_run
            sched.last_run_status = "skipped"
            sched.save(update_fields=["next_run_at", "last_run_status", "updated_at"])
            skipped.append({"id": sched.id, "name": sched.name, "reason": "already_executed_for_period"})
            continue

        try:
            # Create session using the authoritative create_stocktake_session service
            title = f"Scheduled: {sched.name} - {target_date.strftime('%Y-%m-%d')}"
            session = create_stocktake_session(
                location=sched.location,
                category=sched.category,
                counting_mode=sched.counting_mode,
                title=title,
                created_by=sched.created_by,
            )

            # Link schedule and scheduled date
            session.schedule = sched
            session.scheduled_date = target_date
            session.save(update_fields=["schedule", "scheduled_date", "updated_at"])

            # Compute next run
            next_run = compute_next_run(
                sched.frequency,
                sched.scheduled_time,
                sched.day_of_week,
                sched.day_of_month,
                from_time=current_time,
            )
            sched.last_run_at = current_time
            sched.last_run_status = "success"
            sched.last_error_message = ""
            sched.next_run_at = next_run
            sched.save(update_fields=["last_run_at", "last_run_status", "last_error_message", "next_run_at", "updated_at"])

            # In-app notification to assigned counter
            if sched.assigned_staff:
                Notification.objects.create(
                    user_id_ref=sched.assigned_staff.id,
                    message=f"Stocktake Scheduled: Session #{session.session_number} for {sched.location.name} is ready for physical counting."
                )

            executed.append({
                "schedule_id": sched.id,
                "session_id": session.id,
                "session_number": session.session_number,
                "scheduled_date": str(target_date),
            })

        except Exception as exc:
            sched.last_run_status = "failed"
            sched.last_error_message = str(exc)
            sched.save(update_fields=["last_run_status", "last_error_message", "updated_at"])
            failed.append({"id": sched.id, "name": sched.name, "error": str(exc)})

    return {
        "processed_at": current_time.isoformat(),
        "executed": executed,
        "skipped": skipped,
        "failed": failed,
    }


