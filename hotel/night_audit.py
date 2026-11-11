"""
hotel/night_audit.py
Authoritative PMS Night Audit & Business Date Rollover Engine.

Handles:
- Operational Business Date decoupling and progression.
- Automated daily room rate accruals for all in-house checked-in guests.
- Lodging VAT and Service Charge posting to Guest Folios.
- Balanced double-entry General Ledger postings:
    Dr 1200 (Accounts Receivable / Guest Folio)
    Cr 4000 (Room Revenue)
    Cr 2200 (VAT Payable - if applicable)
    Cr 2300 (Service Charge Payable - if applicable)
- Pre-audit integrity validation (unsettled dining orders, arrivals/departures).
- Financial day closure via DayAuditLog snapshot.
- Atomic business date advance with immutable AuditEvent logging.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.finance.services import post_journal_entry
from hotel.models import (
    AuditEvent,
    DayAuditLog,
    FolioCharge,
    Order,
    Reservation,
    Room,
    RoomHistory,
    SystemSettings,
)

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


def _money(val):
    return Decimal(str(val or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def get_current_business_date():
    """Returns the active operational business date from SystemSettings."""
    settings = SystemSettings.get_settings()
    if not settings.current_business_date:
        settings.current_business_date = timezone.now().date()
        settings.save(update_fields=["current_business_date"])
    return settings.current_business_date


def get_night_audit_status():
    """
    Returns the comprehensive pre-audit operational status and readiness checklist.
    """
    settings = SystemSettings.get_settings()
    biz_date = get_current_business_date()
    next_date = biz_date + timedelta(days=1)

    # 1. In-House Guests
    in_house_reservations = list(
        Reservation.objects.filter(status="checked_in")
        .select_related("room")
        .order_by("room__room_number")
    )
    in_house_count = len(in_house_reservations)

    # Calculate projected daily room revenue to accrue
    projected_room_rev = Decimal("0.00")
    for res in in_house_reservations:
        rate = _money(res.room.base_price if res.room else 0)
        projected_room_rev += rate

    # 2. Pending Restaurant Orders & Sessions
    pending_orders = Order.objects.filter(
        payment_status="pending"
    ).exclude(status="cancelled")
    unsettled_orders_count = pending_orders.count()

    # 3. Pending Arrivals (confirmed for today or earlier, not yet checked-in)
    pending_arrivals = Reservation.objects.filter(
        status="confirmed",
        check_in_date__lte=biz_date,
    ).count()

    # 4. Pending Departures (checked-in with checkout scheduled for today or earlier)
    pending_departures = Reservation.objects.filter(
        status="checked_in",
        check_out_date__lte=biz_date,
    ).count()

    # 5. Housekeeping Cleaning Queue
    cleaning_rooms_count = Room.objects.filter(status="Cleaning").count()

    # 6. Audit status for today
    today_audit = DayAuditLog.objects.filter(audit_date=biz_date).first()
    is_day_closed = bool(today_audit and today_audit.is_closed)

    # 7. Recent closed audits
    recent_audits = list(
        DayAuditLog.objects.filter(is_closed=True)
        .order_by("-audit_date")[:7]
        .values("audit_date", "closed_at", "closed_by", "total_revenue", "total_room_revenue")
    )

    can_rollover = unsettled_orders_count == 0

    return {
        "current_business_date": biz_date.isoformat(),
        "next_business_date": next_date.isoformat(),
        "is_day_closed": is_day_closed,
        "can_rollover": can_rollover,
        "in_house_guests_count": in_house_count,
        "projected_room_revenue": float(projected_room_rev),
        "unsettled_orders_count": unsettled_orders_count,
        "pending_arrivals_count": pending_arrivals,
        "pending_departures_count": pending_departures,
        "cleaning_rooms_count": cleaning_rooms_count,
        "recent_audits": recent_audits,
        "hotel_name": settings.hotel_name,
        "currency": settings.currency_symbol,
    }


def validate_night_audit_prerequisites(*, force=False):
    """
    Validates operational prerequisites before Night Audit can execute.
    Raises ValidationError if strict blocking conditions fail and force is False.
    """
    pending_orders = Order.objects.filter(
        payment_status="pending"
    ).exclude(status="cancelled")

    if pending_orders.exists() and not force:
        unsettled_count = pending_orders.count()
        raise ValidationError(
            f"Cannot execute Night Audit: {unsettled_count} unsettled restaurant order(s) remain open. "
            "Please settle or cancel pending orders at cashier desk before date rollover."
        )


@transaction.atomic
def accrue_daily_room_charges(*, business_date, user=None):
    """
    Accrues room charges, lodging VAT, and service charge for all checked-in reservations.
    Enforces idempotency: does not duplicate charges if already posted for business_date.
    Returns: (list of created FolioCharges, total_accrued_amount)
    """
    settings = SystemSettings.get_settings()
    checked_in_reservations = list(
        Reservation.objects.select_for_update()
        .filter(status="checked_in")
        .select_related("room")
    )

    accrued_charges = []
    total_accrued = Decimal("0.00")
    total_base_revenue = Decimal("0.00")
    total_vat = Decimal("0.00")
    total_sc = Decimal("0.00")

    vat_enabled = settings.vat_enabled
    vat_rate = Decimal(str(settings.vat_percentage)) / Decimal("100") if vat_enabled else Decimal("0.00")

    sc_enabled = settings.service_charge_enabled
    sc_rate = Decimal(str(settings.service_charge_percentage)) / Decimal("100") if sc_enabled else Decimal("0.00")

    date_marker = f"({business_date.isoformat()})"

    for res in checked_in_reservations:
        if not res.room:
            continue

        # Idempotency check: has room rate already been posted for this reservation on this business date?
        already_accrued = FolioCharge.objects.filter(
            reservation=res,
            description__icontains="Room Rate Accrual",
        ).filter(description__contains=date_marker).exists()

        if already_accrued:
            logger.info("Room rate already accrued for Reservation #%s on %s. Skipping.", res.id, business_date)
            continue

        base_rate = _money(res.room.base_price)
        line_vat = _money(base_rate * vat_rate) if vat_enabled else Decimal("0.00")
        line_sc = _money(base_rate * sc_rate) if sc_enabled else Decimal("0.00")
        line_total = base_rate + line_vat + line_sc

        desc = f"Room Rate Accrual {date_marker} - Room {res.room.room_number}"
        if line_vat > Decimal("0.00") or line_sc > Decimal("0.00"):
            desc += f" (Base: {base_rate}"
            if line_vat > Decimal("0.00"):
                desc += f" + VAT: {line_vat}"
            if line_sc > Decimal("0.00"):
                desc += f" + SC: {line_sc}"
            desc += ")"

        charge = FolioCharge.objects.create(
            reservation=res,
            description=desc,
            amount=line_total,
            added_by=user.username if user else "Night Audit",
        )
        accrued_charges.append(charge)
        total_accrued += line_total
        total_base_revenue += base_rate
        total_vat += line_vat
        total_sc += line_sc

    # Post balanced General Ledger Journal Entry for all accrued rooms
    gl_entry = None
    if accrued_charges and total_accrued > Decimal("0.00"):
        gl_lines = [
            {
                "account_code": "1200",  # Accounts Receivable / Guest Folio
                "debit": total_accrued,
                "credit": Decimal("0.00"),
            },
            {
                "account_code": "4000",  # Room Revenue
                "debit": Decimal("0.00"),
                "credit": total_base_revenue,
            },
        ]
        if total_vat > Decimal("0.00"):
            gl_lines.append({
                "account_code": "2200",  # VAT Payable
                "debit": Decimal("0.00"),
                "credit": total_vat,
            })
        if total_sc > Decimal("0.00"):
            gl_lines.append({
                "account_code": "2300",  # Service Charge Payable
                "debit": Decimal("0.00"),
                "credit": total_sc,
            })

        gl_entry = post_journal_entry(
            description=f"Night Audit Room Revenue Accrual - {business_date.isoformat()} ({len(accrued_charges)} rooms)",
            items=gl_lines,
            date=business_date,
        )

    return accrued_charges, total_accrued, gl_entry


@transaction.atomic
def execute_night_audit(*, user, notes="", force=False):
    """
    Executes the full PMS Night Audit:
    1. Locks SystemSettings and retrieves current_business_date.
    2. Validates operational prerequisites (open dining orders).
    3. Accrues daily room rate and taxes for all in-house checked-in guests.
    4. Posts balanced GL journal entry for room revenue.
    5. Finalizes and closes DayAuditLog snapshot for the day.
    6. Advances current_business_date to the next calendar date.
    7. Creates immutable AuditEvent.
    """
    settings = SystemSettings.objects.select_for_update().first()
    if not settings:
        settings = SystemSettings.objects.create()

    old_business_date = settings.current_business_date or timezone.now().date()
    new_business_date = old_business_date + timedelta(days=1)

    # 1. Validate prerequisites
    validate_night_audit_prerequisites(force=force)

    # 2. Accrue daily room charges
    accrued_charges, total_room_revenue, gl_entry = accrue_daily_room_charges(
        business_date=old_business_date,
        user=user,
    )

    # 3. Snapshot and finalize DayAuditLog
    audit_log, _ = DayAuditLog.objects.select_for_update().get_or_create(
        audit_date=old_business_date,
    )

    # Compute restaurant payments closed on this day
    from hotel.models import Order
    paid_orders = Order.objects.filter(
        payment_status="paid",
        financials_finalized_at__date=old_business_date,
    )
    cash_total = sum((_money(o.total_amount) + _money(o.tip_amount)) for o in paid_orders if o.payment_method == "Cash")
    chapa_total = sum((_money(o.total_amount) + _money(o.tip_amount)) for o in paid_orders if o.payment_method in ["Chapa", "Digital Payment"])
    telebirr_total = sum((_money(o.total_amount) + _money(o.tip_amount)) for o in paid_orders if o.payment_method == "Telebirr")
    card_total = sum((_money(o.total_amount) + _money(o.tip_amount)) for o in paid_orders if o.payment_method in ["Card", "Credit Card", "Debit Card"])

    # Checkout revenue
    checkout_history = RoomHistory.objects.filter(
        event_type="checkout",
        created_at__date=old_business_date,
    )
    checkout_rev = sum(_money(h.revenue) for h in checkout_history)
    combined_room_rev = total_room_revenue + checkout_rev
    restaurant_rev = cash_total + chapa_total + telebirr_total + card_total
    grand_total_rev = restaurant_rev + combined_room_rev

    audit_log.is_closed = True
    audit_log.closed_at = timezone.now()
    audit_log.closed_by = user.username if user else "Night Audit"
    audit_log.total_cash = cash_total
    audit_log.total_chapa = chapa_total
    audit_log.total_telebirr = telebirr_total
    audit_log.total_card = card_total
    audit_log.total_room_revenue = combined_room_rev
    audit_log.total_revenue = grand_total_rev
    audit_log.notes = (notes or "").strip()
    audit_log.save()

    # 4. Advance Business Date
    settings.current_business_date = new_business_date
    settings.save(update_fields=["current_business_date"])

    # 5. Immutable Audit Event
    AuditEvent.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        actor_role=getattr(user, "role", "admin"),
        action="night_audit.date_rollover",
        entity_type="SystemSettings",
        entity_id=str(settings.id),
        before_summary={
            "business_date": old_business_date.isoformat(),
        },
        after_summary={
            "business_date": new_business_date.isoformat(),
            "accrued_rooms_count": len(accrued_charges),
            "total_room_revenue_accrued": str(total_room_revenue),
            "gl_journal_entry": gl_entry.entry_number if gl_entry else None,
            "day_audit_closed": True,
            "grand_total_revenue": str(grand_total_rev),
        },
        reason=notes or f"PMS Night Audit date rollover from {old_business_date} to {new_business_date}",
        client_metadata={
            "accrued_charges_count": len(accrued_charges),
            "old_date": old_business_date.isoformat(),
            "new_date": new_business_date.isoformat(),
            "forced": force,
        },
    )

    return {
        "status": "success",
        "previous_business_date": old_business_date.isoformat(),
        "new_business_date": new_business_date.isoformat(),
        "accrued_rooms_count": len(accrued_charges),
        "total_room_revenue_accrued": float(total_room_revenue),
        "gl_journal_entry": gl_entry.entry_number if gl_entry else None,
        "day_audit_closed": True,
        "grand_total_revenue": float(grand_total_rev),
        "closed_by": user.username if user else "Night Audit",
        "closed_at": audit_log.closed_at.isoformat(),
    }

