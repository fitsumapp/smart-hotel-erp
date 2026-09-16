import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from users.views import ensure_default_accounts
from apps.orders.services import finalize_paid_order
from apps.payments.services import is_valid_chapa_signature, reconcile_payment_attempt
from hotel.integrity import get_or_create_payment_attempt, mark_payment_attempt_verified
from hotel.models import (
    Category, JournalEntry, MenuItem, Order, OrderItem, PaymentAttempt,
    PaymentWebhookEvent, Reservation, RestaurantTable, Room, SystemSettings,
)


@override_settings(CHAPA_WEBHOOK_SECRET="phase2-webhook-secret", CHAPA_SECRET_KEY="")
class ChapaSignatureCompatibilityTests(TestCase):
    def request(self, body, **headers):
        from rest_framework.test import APIRequestFactory
        return APIRequestFactory().post("/webhook/", body, content_type="application/json", **headers)

    def test_x_chapa_signature_verifies_payload_hmac(self):
        body = b'{"tx_ref":"phase2"}'
        signature = hmac.new(b"phase2-webhook-secret", body, hashlib.sha256).hexdigest()
        request = self.request(body, HTTP_X_CHAPA_SIGNATURE=signature)
        self.assertTrue(is_valid_chapa_signature(request))

    def test_chapa_signature_verifies_secret_hmac(self):
        secret = b"phase2-webhook-secret"
        signature = hmac.new(secret, secret, hashlib.sha256).hexdigest()
        request = self.request(b"{}", HTTP_CHAPA_SIGNATURE=signature)
        self.assertTrue(is_valid_chapa_signature(request))

    def test_invalid_signature_is_rejected(self):
        request = self.request(b"{}", HTTP_X_CHAPA_SIGNATURE="0" * 64)
        self.assertFalse(is_valid_chapa_signature(request))


class Phase2EndpointSecurityTests(APITestCase):
    def setUp(self):
        SystemSettings.objects.create(vat_enabled=False, service_charge_enabled=False)
        self.table = RestaurantTable.objects.create(table_code="P2")
        category = Category.objects.create(name="P2", station="Kitchen")
        menu = MenuItem.objects.create(name="P2 Meal", category=category, price=Decimal("50"))
        self.order = Order.objects.create(table=self.table, payment_page_token="p2-token", chapa_tx_ref="p2-tx")
        OrderItem.objects.create(order=self.order, menu_item=menu, quantity=1, price_at_order=menu.price)
        self.attempt, _ = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("50"), idempotency_key="p2-attempt"
        )
        self.order.chapa_tx_ref = self.attempt.provider_tx_ref
        self.order.save(update_fields=["chapa_tx_ref", "updated_at"])

    def test_qr_code_cannot_authorize_checkin(self):
        room = Room.objects.create(name="P2 Room", room_number="P2R", room_type="Standard", base_price=Decimal("100"))
        reservation = Reservation.objects.create(
            room=room, guest_name="P2 Guest", check_in_date="2027-01-01", check_out_date="2027-01-02", status="confirmed"
        )
        response = self.client.post(reverse("public-qr-checkin"), {"qr_token": reservation.qr_token}, format="json")
        self.assertIn(response.status_code, (401, 403))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "confirmed")

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    @patch("users.views.is_valid_chapa_signature", return_value=True)
    def test_duplicate_webhook_receipt_is_idempotent(self, signature, verify, finalize):
        verify.return_value = {"data": {"status": "success", "tx_ref": self.attempt.provider_tx_ref, "amount": "50.00", "currency": "ETB", "reference": "provider-event-p2"}}
        payload = {"event": "charge.success", "reference": "provider-event-p2", "tx_ref": self.attempt.provider_tx_ref}
        first = self.client.post(reverse("chapa-webhook"), payload, format="json")
        second = self.client.post(reverse("chapa-webhook"), payload, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        finalize.assert_called_once()
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "verified")


class PaymentReconciliationTests(TestCase):
    def setUp(self):
        table = RestaurantTable.objects.create(table_code="P2-REC")
        order = Order.objects.create(table=table)
        self.attempt, _ = get_or_create_payment_attempt(
            target=order, expected_amount=Decimal("25"), idempotency_key="p2-reconcile"
        )

    @patch("apps.payments.services.verify_chapa_transaction")
    def test_reconciliation_detects_provider_paid_local_unverified(self, verify):
        verify.return_value = {"data": {"status": "success", "tx_ref": self.attempt.provider_tx_ref, "amount": "25.00", "currency": "ETB"}}
        self.assertEqual(reconcile_payment_attempt(self.attempt), "provider_paid_local_unverified")
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.reconciliation_status, "provider_paid_local_unverified")

    @patch("apps.payments.services.verify_chapa_transaction")
    def test_reconciliation_detects_provider_value_mismatch(self, verify):
        verify.return_value = {"data": {"status": "success", "tx_ref": self.attempt.provider_tx_ref, "amount": "24.99", "currency": "ETB"}}
        self.assertEqual(reconcile_payment_attempt(self.attempt), "value_mismatch")


class PostgreSQLConcurrentPaymentTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific payment concurrency test")
        ensure_default_accounts()
        SystemSettings.objects.create(vat_enabled=False, service_charge_enabled=False)
        table = RestaurantTable.objects.create(table_code="P2-CON")
        category = Category.objects.create(name="P2 Concurrent", station="Kitchen")
        menu = MenuItem.objects.create(name="Concurrent Meal", category=category, price=Decimal("75"))
        self.order = Order.objects.create(table=table)
        OrderItem.objects.create(order=self.order, menu_item=menu, quantity=1, price_at_order=menu.price)
        self.attempt, _ = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("75"), idempotency_key="p2-concurrent"
        )

    def test_concurrent_finalization_creates_one_payment_journal(self):
        def settle(index):
            close_old_connections()
            try:
                attempt = PaymentAttempt.objects.get(pk=self.attempt.pk)
                order = Order.objects.get(pk=self.order.pk)
                finalize_paid_order(
                    order, payment_method="Chapa", payment_reference=attempt.provider_tx_ref,
                    payment_attempt=attempt,
                )
                mark_payment_attempt_verified(tx_ref=attempt.provider_tx_ref, provider_event_ref=f"event-{index}")
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(settle, range(2)))
        self.attempt.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.attempt.status, "verified")
        self.assertIsNotNone(self.attempt.accounting_entry_id)
        self.assertEqual(JournalEntry.objects.filter(description__contains=f"Order #{self.order.pk} payment").count(), 1)
