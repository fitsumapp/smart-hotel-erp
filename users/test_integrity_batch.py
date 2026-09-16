"""Regression coverage for payment, booking and stock integrity services."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from hotel.integrity import (
    create_reservation_safely,
    get_or_create_payment_attempt,
    mark_payment_attempt_verified,
    record_stock_change,
)
from hotel.models import (
    InventoryCategory,
    InventoryItem,
    Order,
    PaymentAttempt,
    RestaurantTable,
    Room,
    StockTransaction,
)


class IntegrityBatchTests(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            name="Integrity Room", room_number="I-101", room_type="Standard",
            base_price=Decimal("100.00"), is_available_online=True,
        )
        self.table = RestaurantTable.objects.create(table_code="I-1", label_name="Integrity")
        self.order = Order.objects.create(table=self.table, total_amount=Decimal("100.00"))
        category = InventoryCategory.objects.create(name="Integrity Stock")
        self.item = InventoryItem.objects.create(
            item_code="INT-1", name="Locked stock", category=category,
            current_stock=Decimal("10.00"), unit_cost=Decimal("2.00"),
        )

    def test_payment_idempotency_reuses_exact_attempt(self):
        first, created = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("100.00"), idempotency_key="same-request",
        )
        retry, retry_created = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("100.00"), idempotency_key="same-request",
        )
        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(first.pk, retry.pk)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_idempotency_key_cannot_be_reused_for_changed_amount(self):
        get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("100.00"), idempotency_key="fixed-input",
        )
        with self.assertRaises(ValidationError):
            get_or_create_payment_attempt(
                target=self.order, expected_amount=Decimal("101.00"), idempotency_key="fixed-input",
            )

    def test_payment_identity_and_history_are_immutable(self):
        attempt, _ = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("100.00"), idempotency_key="immutable-payment",
        )
        attempt.expected_amount = Decimal("1.00")
        with self.assertRaises(ValidationError):
            attempt.save()
        with self.assertRaises(ValidationError):
            attempt.delete()

    def test_payment_verification_is_idempotent(self):
        attempt, _ = get_or_create_payment_attempt(
            target=self.order, expected_amount=Decimal("100.00"), idempotency_key="verify-once",
        )
        first, changed = mark_payment_attempt_verified(tx_ref=attempt.provider_tx_ref, provider_event_ref="evt-1")
        retry, retry_changed = mark_payment_attempt_verified(tx_ref=attempt.provider_tx_ref, provider_event_ref="evt-1")
        self.assertTrue(changed)
        self.assertFalse(retry_changed)
        self.assertEqual(first.pk, retry.pk)

    def test_overlapping_reservation_is_rejected_inside_room_lock(self):
        values = dict(
            guest_name="First", check_in_date=date(2027, 1, 10),
            check_out_date=date(2027, 1, 12), adults=1, children=0,
            total_amount=Decimal("200.00"), deposit_amount=Decimal("100.00"),
        )
        create_reservation_safely(room_id=self.room.pk, **values)
        values.update(guest_name="Second", check_in_date=date(2027, 1, 11), check_out_date=date(2027, 1, 13))
        with self.assertRaises(ValidationError):
            create_reservation_safely(room_id=self.room.pk, **values)
        self.assertEqual(self.room.reservations.count(), 1)

    def test_stock_updates_and_ledger_are_transactional(self):
        item, ledger = record_stock_change(
            item_id=self.item.pk, transaction_type="issuance",
            quantity=Decimal("4.00"), unit_cost=Decimal("2.00"),
        )
        self.assertEqual(item.current_stock, Decimal("6.00"))
        self.assertEqual(ledger.quantity, Decimal("4.00"))
        with self.assertRaises(ValidationError):
            record_stock_change(
                item_id=self.item.pk, transaction_type="issuance",
                quantity=Decimal("7.00"), unit_cost=Decimal("2.00"),
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("6.00"))
        self.assertEqual(StockTransaction.objects.count(), 1)
        with self.assertRaises(ValidationError):
            ledger.delete()
