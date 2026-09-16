"""Payments API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403
from hotel.integrity import transition_reservation
from django.core.exceptions import ValidationError
from hotel.models import PaymentWebhookEvent
from apps.payments.services import (
    mark_webhook_event, record_webhook_event, validate_customer_fields, validate_tip_amount,
    verification_status,
)
import users.views as legacy_views


def finalize_paid_order(*args, **kwargs):
    return legacy_views.finalize_paid_order(*args, **kwargs)


def verify_chapa_transaction(*args, **kwargs):
    return legacy_views.verify_chapa_transaction(*args, **kwargs)


def is_valid_chapa_signature(*args, **kwargs):
    return legacy_views.is_valid_chapa_signature(*args, **kwargs)



class PublicPaymentDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        payload = build_payment_summary(order)
        payload["items"] = [
            {
                "menu_item_name": item.menu_item.name,
                "quantity": item.quantity,
                "price_at_order": float(item.price_at_order),
            }
            for item in order.items.all()
        ]
        # waiter_username is a denormalized field — safe cross-schema
        payload["waiter_name"] = order.waiter_username or "Waiter"
        return Response(payload)


class PublicVerifyChapaPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if order.payment_status == "paid":
            return Response({"message": "Payment already verified.", "summary": build_payment_summary(order)})

        tx_ref = request.data.get("tx_ref") or order.chapa_tx_ref
        if not tx_ref:
            return Response({"error": "No pending Chapa transaction found for this order."}, status=400)
        if not order.chapa_tx_ref or not hmac.compare_digest(
            str(tx_ref), str(order.chapa_tx_ref)
        ):
            return Response(
                {"error": "Payment transaction does not belong to this order."}, status=400
            )

        try:
            verification = verify_chapa_transaction(tx_ref)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        verification_data = verification.get("data", verification)
        status_value = str(verification_data.get("status", "")).lower()
        if status_value not in {"success", "successful"}:
            return Response({"message": "Payment is still pending.", "status": status_value or "pending"}, status=202)

        expected_amount = to_decimal(build_payment_summary(order)["amount_due"])
        try:
            attempt = PaymentAttempt.objects.get(provider_tx_ref=tx_ref, order=order)
        except PaymentAttempt.DoesNotExist:
            # One-time compatibility for transactions initiated before PaymentAttempt existed.
            attempt = PaymentAttempt.objects.create(
                provider="chapa",
                order=order,
                expected_amount=expected_amount,
                currency="ETB",
                provider_tx_ref=tx_ref,
                idempotency_key=f"legacy-order-{order.pk}-{tx_ref}"[:120],
                status="initiated",
                safe_metadata={"legacy_backfill": True},
            )

        if attempt.expected_amount != expected_amount or attempt.currency != "ETB":
            return Response({"error": "Stored payment expectation mismatch."}, status=400)
        try:
            validate_chapa_payment(
                verification_data,
                expected_tx_ref=attempt.provider_tx_ref,
                expected_amount=attempt.expected_amount,
                expected_currency=attempt.currency,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            finalize_paid_order(
                order,
                payment_method="Chapa",
                payment_reference=tx_ref,
                tip_amount=order.tip_amount,
                payment_attempt=attempt,
            )
            mark_payment_attempt_verified(
                tx_ref=tx_ref,
                provider_event_ref=str(verification_data.get("reference") or verification_data.get("id") or "") or None,
                safe_metadata={"status": status_value, "currency": "ETB"},
            )

        if order.waiter_id_ref:
            Notification.objects.create(
                user_id_ref=order.waiter_id_ref,
                message=f"Digital payment completed for Table {order.table.table_code}.",
            )

        return Response({"message": "Payment verified successfully.", "summary": build_payment_summary(order)})


class PublicInitiateChapaPaymentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            order = get_public_order_from_token(token)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=404)

        if order.payment_status == "paid":
            return Response({"error": "Order is already paid."}, status=400)

        try:
            tip_amount = validate_tip_amount(request.data.get("tip_amount", 0))
        except ValidationError as exc:
            return Response({"error": exc.messages[0]}, status=400)

        summary = build_payment_summary(order)
        amount_due = to_decimal(summary["grand_total"]) + tip_amount
        idempotency_key = request.headers.get("Idempotency-Key") or f"order-{order.pk}-{amount_due}"
        try:
            attempt, created = get_or_create_payment_attempt(
                target=order, expected_amount=amount_due,
                idempotency_key=idempotency_key, currency="ETB",
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=400)
        if not created and attempt.status == "initiated" and attempt.safe_metadata.get("checkout_url"):
            return Response({"checkout_url": attempt.safe_metadata["checkout_url"], "tx_ref": attempt.provider_tx_ref, "amount_due": float(attempt.expected_amount), "tip_amount": float(tip_amount)})
        tx_ref = attempt.provider_tx_ref
        return_url = f"{create_payment_page_url(order, request=request)}?payment=returned"
        callback_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}{reverse('chapa-webhook')}"
        try:
            customer_email, first_name, last_name = validate_customer_fields(
                email=request.data.get("email") or f"guest-order-{order.id}@example.com",
                first_name=request.data.get("first_name") or "Guest",
                last_name=request.data.get("last_name") or f"Order{order.id}",
            )
        except ValidationError as exc:
            return Response({"error": exc.messages[0]}, status=400)

        payload = {
            "amount": str(amount_due),
            "currency": "ETB",
            "email": customer_email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization": {
                "title": f"Order {order.id}",
                "description": f"Table {order.table.table_code} checkout",
            },
            "meta": {
                "order_id": order.id,
                "base_total": str(order.total_amount),
                "tip_amount": str(tip_amount),
            },
        }

        try:
            chapa_response = chapa_request("transaction/initialize", payload=payload, method="POST")
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        checkout_url = (
            chapa_response.get("data", {}).get("checkout_url")
            or chapa_response.get("data", {}).get("link")
            or chapa_response.get("checkout_url")
        )
        if not checkout_url:
            return Response({"error": "Chapa did not return a checkout URL."}, status=400)

        attempt.status = "initiated"
        attempt.safe_metadata = {"checkout_url": checkout_url}
        attempt.save(update_fields=["status", "safe_metadata", "updated_at"])

        order.tip_amount = tip_amount
        order.payment_method = "Chapa"
        order.payment_reference = tx_ref
        order.chapa_tx_ref = tx_ref
        order.chapa_checkout_url = checkout_url
        order.payment_status = "pending"
        order.save(
            update_fields=[
                "tip_amount", "payment_method", "payment_reference",
                "chapa_tx_ref", "chapa_checkout_url", "payment_status", "updated_at",
            ]
        )

        return Response(
            {
                "checkout_url": checkout_url,
                "tx_ref": tx_ref,
                "amount_due": float(amount_due),
                "tip_amount": float(tip_amount),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ChapaWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_body = request.body or b""
        if not is_valid_chapa_signature(request):
            return Response({"error": "Invalid Chapa signature"}, status=403)
        payload = request.data or {}
        nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        tx_ref = payload.get("tx_ref") or payload.get("trx_ref") or nested.get("tx_ref") or nested.get("trx_ref")
        if not tx_ref:
            return Response({"error": "Missing tx_ref"}, status=400)
        try:
            event, event_created = record_webhook_event(payload=payload, raw_body=raw_body, tx_ref=tx_ref)
        except ValidationError:
            return Response({"error": "Webhook event identity conflict"}, status=409)
        if not event_created and event.status == "processed":
            return Response({"message": "Webhook already processed"})

        attempt = PaymentAttempt.objects.select_related("order", "reservation").filter(provider_tx_ref=tx_ref).first()
        if not attempt:
            # Deployment compatibility for sessions initiated before PaymentAttempt existed.
            order = Order.objects.filter(chapa_tx_ref=tx_ref).first()
            reservation = Reservation.objects.filter(chapa_tx_ref=tx_ref).first()
            if order:
                expected = to_decimal(build_payment_summary(order)["amount_due"])
                attempt = PaymentAttempt.objects.create(
                    provider="chapa", purpose="order", order=order,
                    expected_amount=expected, currency="ETB", provider_tx_ref=tx_ref,
                    idempotency_key=f"legacy-order-{order.pk}-{tx_ref}"[:120], status="initiated",
                    safe_metadata={"legacy_backfill": True},
                )
            elif reservation:
                attempt = PaymentAttempt.objects.create(
                    provider="chapa", purpose="reservation_deposit", reservation=reservation,
                    expected_amount=reservation.deposit_amount, currency="ETB", provider_tx_ref=tx_ref,
                    idempotency_key=f"legacy-reservation-{reservation.pk}-{tx_ref}"[:120], status="initiated",
                    safe_metadata={"legacy_backfill": True},
                )
            else:
                mark_webhook_event(event, status="rejected", error_code="unknown_transaction")
                return Response({"error": "Payment record not found"}, status=404)
        try:
            verification = verify_chapa_transaction(tx_ref)
            verification_data = verification.get("data", verification)
        except ValueError:
            mark_webhook_event(event, status="failed", attempt=attempt, error_code="provider_unavailable")
            return Response({"error": "Unable to verify payment"}, status=502)
        status_value = verification_status(verification_data)
        if status_value not in {"success", "successful"}:
            mark_webhook_event(event, status="rejected", attempt=attempt, error_code="provider_not_successful")
            return Response({"message": "Payment not successful"}, status=202)
        try:
            validate_chapa_payment(
                verification_data, expected_tx_ref=attempt.provider_tx_ref,
                expected_amount=attempt.expected_amount, expected_currency=attempt.currency,
            )
        except ValueError as exc:
            logger.warning("Webhook payment value mismatch: %s", exc)
            mark_webhook_event(event, status="rejected", attempt=attempt, error_code="value_mismatch")
            return Response({"error": "Verified payment values do not match"}, status=400)

        try:
            with transaction.atomic():
                attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
                event = PaymentWebhookEvent.objects.select_for_update().get(pk=event.pk)
                if attempt.status == "verified":
                    mark_webhook_event(event, status="processed", attempt=attempt)
                    return Response({"message": "Webhook already processed"})
                if attempt.order_id:
                    finalize_paid_order(
                        attempt.order, payment_method="Chapa",
                        payment_reference=attempt.provider_tx_ref,
                        tip_amount=attempt.order.tip_amount, payment_attempt=attempt,
                    )
                elif attempt.purpose == "reservation_deposit":
                    finalize_paid_reservation(attempt.reservation, payment_reference=attempt.provider_tx_ref, payment_attempt=attempt)
                else:
                    from apps.payments.services import settle_reservation_stay_payment
                    settle_reservation_stay_payment(attempt)
                mark_payment_attempt_verified(
                    tx_ref=attempt.provider_tx_ref,
                    provider_event_ref=event.event_ref,
                    safe_metadata={"status": status_value, "currency": attempt.currency, "purpose": attempt.purpose},
                )
                attempt.refresh_from_db()
                mark_webhook_event(event, status="processed", attempt=attempt)
        except (ValidationError, ValueError):
            mark_webhook_event(event, status="failed", attempt=attempt, error_code="finalization_failed")
            return Response({"error": "Payment finalization failed"}, status=409)
        return Response({"message": "Webhook processed successfully"})
