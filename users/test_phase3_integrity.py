from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.orders.services import create_order_idempotently
from hotel.integrity import (
    create_reservation_safely,
    record_stock_change,
    reverse_stock_transaction,
    transition_order,
    transition_reservation,
)
from hotel.inventory import reconcile_stock
from hotel.models import (
    Category, InventoryCategory, InventoryItem, MenuItem, Order,
    Reservation, RestaurantTable, Room,
)
from users.models import User


class Phase3ServiceIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="phase3@example.com", username="phase3", password="test-pass", role="waiter"
        )
        self.room = Room.objects.create(
            name="Integrity Room", room_number="P301", room_type="Standard",
            base_price=Decimal("100.00"),
        )
        self.table = RestaurantTable.objects.create(table_code="P3", label_name="Phase 3")
        category = Category.objects.create(name="Food", station="Kitchen")
        self.menu_item = MenuItem.objects.create(
            name="Meal", category=category, price=Decimal("50.00"), is_available=True,
        )
        inventory_category = InventoryCategory.objects.create(name="Phase 3 Stock", category_type="f_and_b")
        self.stock = InventoryItem.objects.create(
            item_code="P3-STOCK", name="Stock", category=inventory_category,
            current_stock=Decimal("10.00"), opening_stock=Decimal("10.00"), unit_cost=Decimal("2.00"),
        )

    def reservation(self, status="pending"):
        return Reservation.objects.create(
            room=self.room, guest_name="Guest", check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=2), status=status,
        )

    def test_reservation_state_machine_rejects_backwards_transition(self):
        reservation = self.reservation("confirmed")
        with self.assertRaises(ValidationError):
            transition_reservation(reservation_id=reservation.pk, to_status="pending")
        reservation.status = "pending"
        with self.assertRaises(ValidationError):
            reservation.save(update_fields=["status", "updated_at"])

    def test_order_state_machine_rejects_invalid_transition(self):
        order = Order.objects.create(table=self.table)
        with self.assertRaises(ValidationError):
            transition_order(order_id=order.pk, to_status="ready")

    def test_order_creation_is_idempotent_and_binds_request(self):
        items = [{"id": self.menu_item.pk, "quantity": 2}]
        first, created = create_order_idempotently(
            table_id=self.table.pk, items=items, waiter=self.user, idempotency_key="create-1"
        )
        second, created_again = create_order_idempotently(
            table_id=self.table.pk, items=items, waiter=self.user, idempotency_key="create-1"
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(ValidationError):
            create_order_idempotently(
                table_id=self.table.pk,
                items=[{"id": self.menu_item.pk, "quantity": 3}],
                waiter=self.user,
                idempotency_key="create-1",
            )

    def test_finalized_order_financial_snapshot_is_immutable(self):
        order = Order.objects.create(
            table=self.table, sub_total=Decimal("10"), total_amount=Decimal("10"),
            financials_finalized_at=timezone.now(),
        )
        order.total_amount = Decimal("11")
        with self.assertRaises(ValidationError):
            order.save(update_fields=["total_amount", "updated_at"])

    def test_stock_reversal_is_idempotent_and_reconciles(self):
        _, entry = record_stock_change(
            item_id=self.stock.pk, transaction_type="issuance",
            quantity=Decimal("3"), unit_cost=Decimal("2"),
        )
        reversal, created = reverse_stock_transaction(
            transaction_id=entry.pk, reason="Count correction", logged_by_username="phase3"
        )
        again, created_again = reverse_stock_transaction(
            transaction_id=entry.pk, reason="Retry", logged_by_username="phase3"
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(reversal.pk, again.pk)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.current_stock, Decimal("10.00"))
        self.assertEqual(reconcile_stock(), [])


class PostgreSQLPhase3ConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency test")
        self.room = Room.objects.create(
            name="Concurrent Room", room_number="P3C", room_type="Standard", base_price=Decimal("100")
        )
        category = InventoryCategory.objects.create(name="Concurrent Stock", category_type="f_and_b")
        self.stock = InventoryItem.objects.create(
            item_code="P3-CON", name="Concurrent", category=category,
            current_stock=Decimal("10"), opening_stock=Decimal("10"), unit_cost=Decimal("1"),
        )

    def test_concurrent_overlapping_booking_creates_only_one(self):
        def book(index):
            close_old_connections()
            try:
                return create_reservation_safely(
                    room_id=self.room.pk, guest_name=f"Guest {index}",
                    check_in_date=date.today() + timedelta(days=1),
                    check_out_date=date.today() + timedelta(days=3),
                ).pk
            except (ValidationError, IntegrityError):
                return None
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(book, range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_concurrent_stock_deductions_do_not_lose_updates(self):
        def deduct(index):
            close_old_connections()
            try:
                record_stock_change(
                    item_id=self.stock.pk, transaction_type="issuance",
                    quantity=Decimal("3"), unit_cost=Decimal("1"), reference_number=f"C-{index}",
                )
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(deduct, range(2)))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.current_stock, Decimal("4.00"))
        self.assertEqual(self.stock.transactions.count(), 2)
