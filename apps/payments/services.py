"""Payments transactional and business services."""
import hashlib
import hmac
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from hotel.models import PaymentAttempt, PaymentWebhookEvent
from core.observability import metrics
from apps.audit.services import record_audit_event


logger = logging.getLogger("smart_hotel.alert")

CENT = Decimal("0.01")


def to_decimal(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)

def chapa_request(path, payload=None, method="POST"):
    secret_key = settings.CHAPA_SECRET_KEY
    if not secret_key:
        raise ValueError("CHAPA_SECRET_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        f"{settings.CHAPA_BASE_URL.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(detail or str(exc)) from exc
    except urllib_error.URLError as exc:
        raise ValueError(str(exc)) from exc


def verify_chapa_transaction(tx_ref):
    return chapa_request(f"transaction/verify/{tx_ref}", payload=None, method="GET")


def validate_chapa_payment(
    verification_data,
    *,
    expected_tx_ref,
    expected_amount,
    expected_currency="ETB",
):
    """Bind a successful provider response to the exact local payment."""
    returned_tx_ref = (
        verification_data.get("tx_ref")
        or verification_data.get("trx_ref")
        or verification_data.get("reference")
    )
    if not returned_tx_ref or not hmac.compare_digest(
        str(returned_tx_ref), str(expected_tx_ref)
    ):
        raise ValueError("Payment transaction reference does not match this record.")

    returned_currency = str(verification_data.get("currency", "")).upper()
    if returned_currency != str(expected_currency).upper():
        raise ValueError("Payment currency does not match the expected currency.")

    if "amount" not in verification_data:
        raise ValueError("Payment provider response is missing the amount.")
    returned_amount = to_decimal(verification_data["amount"])
    expected_amount = to_decimal(expected_amount)
    if returned_amount != expected_amount:
        raise ValueError("Payment amount does not match the expected amount.")

    return returned_amount


def is_valid_chapa_signature(request):
    secret = settings.CHAPA_WEBHOOK_SECRET
    if not secret:
        return False
    raw_body = request.body or b""
    secret_bytes = secret.encode("utf-8")
    payload_hash = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()
    secret_hash = hmac.new(secret_bytes, secret_bytes, hashlib.sha256).hexdigest()
    signature = request.headers.get("chapa-signature") or request.headers.get("Chapa-Signature")
    payload_signature = request.headers.get("x-chapa-signature")
    return bool(
        (payload_signature and hmac.compare_digest(payload_signature.strip(), payload_hash))
        or (signature and (
            hmac.compare_digest(signature.strip(), secret_hash)
            or hmac.compare_digest(signature.strip(), payload_hash)
        ))
    )





def validate_tip_amount(value):
    try:
        tip = to_decimal(value)
    except Exception as exc:
        raise ValidationError("Tip must be a valid monetary amount.") from exc
    if not tip.is_finite() or tip < 0 or tip > Decimal("100000.00"):
        raise ValidationError("Tip must be between 0 and 100000 ETB.")
    return tip

def validate_customer_fields(*, email, first_name, last_name):
    email = str(email or "").strip()
    first_name = str(first_name or "").strip()
    last_name = str(last_name or "").strip()
    if len(email) > 254 or len(first_name) > 80 or len(last_name) > 80:
        raise ValidationError("Customer payment fields exceed the allowed length.")
    validate_email(email)
    if not first_name or not last_name:
        raise ValidationError("Customer first and last name are required.")
    return email, first_name, last_name


def webhook_event_identity(payload, raw_body):
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_ref = (
        payload.get("event_id") or payload.get("id") or payload.get("reference")
        or nested.get("event_id") or nested.get("id") or nested.get("reference")
    )
    payload_hash = hashlib.sha256(raw_body or b"").hexdigest()
    return str(event_ref or payload_hash), payload_hash


@transaction.atomic
def record_webhook_event(*, payload, raw_body, tx_ref):
    event_ref, payload_hash = webhook_event_identity(payload, raw_body)
    event, created = PaymentWebhookEvent.objects.select_for_update().get_or_create(
        provider="chapa", event_ref=event_ref,
        defaults={
            "tx_ref": str(tx_ref or "")[:120], "payload_hash": payload_hash,
            "signature_valid": True, "safe_summary": {
                "event": str(payload.get("event") or "")[:80],
                "status": str(payload.get("status") or "")[:30],
            },
        },
    )
    if not created and event.payload_hash != payload_hash:
        raise ValidationError("Webhook event reference was reused with a different payload.")
    return event, created


def mark_webhook_event(event, *, status, attempt=None, error_code=""):
    event.status = status
    event.error_code = str(error_code or "")[:80]
    event.processed_at = timezone.now()
    if attempt and not event.attempt_id:
        event.attempt = attempt
    event.save(update_fields=["status", "error_code", "processed_at", "attempt"])
    return event


def verification_status(verification_data):
    return str(verification_data.get("status") or "").strip().lower()


def reconcile_payment_attempt(attempt):
    """Fetch provider truth and persist a safe reconciliation result."""
    try:
        verification = verify_chapa_transaction(attempt.provider_tx_ref)
        data = verification.get("data", verification)
        status = verification_status(data) or "unknown"
        mismatch = ""
        if status in {"success", "successful"}:
            try:
                validate_chapa_payment(
                    data, expected_tx_ref=attempt.provider_tx_ref,
                    expected_amount=attempt.expected_amount,
                    expected_currency=attempt.currency,
                )
            except ValueError:
                mismatch = "value_mismatch"
        local_status = attempt.status
        if mismatch:
            result = mismatch
        elif status in {"success", "successful"} and local_status != "verified":
            result = "provider_paid_local_unverified"
        elif status not in {"success", "successful"} and local_status == "verified":
            result = "local_verified_provider_not_paid"
        else:
            result = "matched"
    except ValueError:
        result = "provider_error"
    PaymentAttempt.objects.filter(pk=attempt.pk).update(
        last_reconciled_at=timezone.now(), reconciliation_status=result,
    )
    metrics.increment("payment_reconciliations_total")
    if result != "matched":
        metrics.increment("payment_reconciliation_mismatches_total")
        logger.critical("payment_reconciliation_mismatch", extra={"event": {"attempt_id": attempt.pk, "result": result}})
    record_audit_event(
        action="payment.reconciled", entity_type="hotel.PaymentAttempt",
        entity_id=attempt.pk, before={"status": attempt.reconciliation_status},
        after={"status": result},
    )
    return result


@transaction.atomic
def settle_reservation_stay_payment(attempt):
    from apps.finance.services import post_journal_entry
    from hotel.integrity import transition_reservation
    from hotel.models import Reservation, Room, RoomHistory

    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    reservation = Reservation.objects.select_for_update().select_related("room").get(pk=attempt.reservation_id)
    room = Room.objects.select_for_update().get(pk=reservation.room_id)
    if attempt.purpose == "checkin":
        reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_in")
        room_status = "Occupied"
        event_type = "checkin"
    elif attempt.purpose == "checkout":
        reservation, _ = transition_reservation(reservation_id=reservation.pk, to_status="checked_out")
        room_status = "Cleaning"
        event_type = "checkout"
    else:
        raise ValidationError("Unsupported reservation payment purpose.")
    reservation.payment_status = "paid"
    reservation.payment_reference = f"Chapa - {attempt.provider_tx_ref}"
    reservation.save(update_fields=["payment_status", "payment_reference", "updated_at"])
    room.status = room_status
    room.booking_source = "front_desk"
    room.save(update_fields=["status", "booking_source"])
    RoomHistory.objects.get_or_create(
        room=room, event_type=event_type, guest_name=reservation.guest_name,
        check_in_date=reservation.check_in_date, check_out_date=reservation.check_out_date,
        defaults={"revenue": attempt.expected_amount, "payment_method": "Chapa", "notes": f"Payment attempt #{attempt.pk}"},
    )
    if not attempt.accounting_entry_id and attempt.expected_amount > 0:
        entry = post_journal_entry(
            description=f"Auto JV: Reservation #{reservation.pk} {attempt.purpose} payment attempt #{attempt.pk}",
            items=[
                {"account_code": "1010", "debit": attempt.expected_amount, "credit": Decimal("0")},
                {"account_code": "4000", "debit": Decimal("0"), "credit": attempt.expected_amount},
            ],
        )
        PaymentAttempt.objects.filter(pk=attempt.pk, accounting_entry__isnull=True).update(accounting_entry=entry)
    return reservation
