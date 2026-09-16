"""Reservations transactional and business services."""
from users.views import *  # noqa: F401,F403
from hotel.integrity import transition_reservation

def create_public_reservation_url(reservation, request=None):
    frontend_base = get_tenant_frontend_base(request=request)
    reservation.ensure_tokens()
    return f"{frontend_base}/booking/{reservation.public_token}"


def get_public_reservation_from_token(token):
    try:
        return Reservation.objects.select_related("room").get(public_token=token)
    except Reservation.DoesNotExist as exc:
        raise ValueError("Reservation session not found.") from exc


def reservation_overlaps(room, check_in_date, check_out_date, exclude_id=None):
    qs = Reservation.objects.filter(
        room=room,
        status__in=["pending", "confirmed", "checked_in"],
        check_in_date__lt=check_out_date,
        check_out_date__gt=check_in_date,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def calculate_reservation_amounts(room, check_in_date, check_out_date):
    nights = max((check_out_date - check_in_date).days, room.min_stay or 1)
    total_amount = (to_decimal(room.base_price) * nights).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    deposit_base = to_decimal(room.advance_payment_amount)
    if room.online_deposit_type == "Percentage":
        deposit_amount = (total_amount * deposit_base / Decimal("100")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    else:
        deposit_amount = deposit_base
    if deposit_amount <= Decimal("0.00"):
        deposit_amount = total_amount
    if deposit_amount > total_amount:
        deposit_amount = total_amount
    return nights, total_amount, deposit_amount


def build_reservation_summary(reservation):
    return {
        "id": reservation.id,
        "room_id": reservation.room_id,
        "room_name": reservation.room.name,
        "room_number": reservation.room.room_number,
        "room_type": reservation.room.room_type,
        "room_image": reservation.room.main_image.url if reservation.room.main_image else None,
        "guest_name": reservation.guest_name,
        "guest_email": reservation.guest_email,
        "guest_phone": reservation.guest_phone,
        "check_in_date": reservation.check_in_date.isoformat(),
        "check_out_date": reservation.check_out_date.isoformat(),
        "adults": reservation.adults,
        "children": reservation.children,
        "status": reservation.status,
        "source": reservation.source,
        "payment_status": reservation.payment_status,
        "total_amount": float(reservation.total_amount),
        "deposit_amount": float(reservation.deposit_amount),
        "confirmation_code": reservation.confirmation_code,
        "qr_token": reservation.qr_token,
        "public_token": reservation.public_token,
        "payment_reference": reservation.payment_reference,
        "paid_at": reservation.paid_at.isoformat() if reservation.paid_at else None,
    }


def send_reservation_confirmation(reservation):
    summary = build_reservation_summary(reservation)
    qr_url = f"{get_tenant_frontend_base()}/booking/{reservation.public_token}"
    message = (
        f"Reservation confirmed for Room {reservation.room.room_number}. "
        f"Code: {reservation.confirmation_code}. "
        f"Check-in: {reservation.check_in_date.isoformat()} "
        f"Check-out: {reservation.check_out_date.isoformat()}. "
        f"QR page: {qr_url}"
    )
    if reservation.guest_email:
        try:
            send_mail(
                subject=f"Booking Confirmation - Room {reservation.room.room_number}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reservation.guest_email],
                fail_silently=True,
            )
        except Exception:
            pass
    summary["confirmation_delivery"] = {
        "email_sent": bool(reservation.guest_email),
        "sms_preview": message,
        "qr_url": qr_url,
    }
    return summary


def finalize_paid_reservation(reservation, payment_reference=None, payment_attempt=None):
    if reservation.payment_status == "paid" or Reservation.objects.filter(id=reservation.id, payment_status="paid").exists():
        if reservation.source == "public":
            return {} # return dummy summary if called again
        return None

    reservation.ensure_tokens()
    reservation.payment_status = "paid"
    reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="confirmed")
    reservation.payment_reference = payment_reference or reservation.payment_reference
    reservation.paid_at = timezone.now()
    reservation.save(
        update_fields=[
            "confirmation_code", "qr_token", "public_token",
            "payment_status", "status", "payment_reference", "paid_at", "updated_at",
        ]
    )
    reservation.room.status = "Reserved"
    reservation.room.booking_source = "online" if reservation.source == "public" else "front_desk"
    reservation.room.save(update_fields=["status", "booking_source"])

    # --- Post General Ledger Journal Entry ---
    payment_entry = None
    try:
        deposit = to_decimal(reservation.deposit_amount)
        if deposit > 0:
            payment_entry = post_journal_entry(
                description=f"Auto JV: Online Reservation Booking Paid Confirmed #{reservation.id}",
                items=[
                    {
                        "account_code": "1010", # Bank Transfer
                        "debit": deposit,
                        "credit": Decimal("0.00")
                    },
                    {
                        "account_code": "4000", # Room Revenue
                        "debit": Decimal("0.00"),
                        "credit": deposit
                    }
                ]
            )
    except Exception as e:
        if payment_attempt is not None:
            raise
        print(f"GL Auto-post error for online reservation #{reservation.id}: {e}")
    if payment_attempt is not None and payment_entry is not None:
        PaymentAttempt.objects.filter(pk=payment_attempt.pk, accounting_entry__isnull=True).update(accounting_entry=payment_entry)

    return send_reservation_confirmation(reservation)


