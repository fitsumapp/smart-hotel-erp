from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import Category, DiningSession, MenuItem, Order, OrderItem, RestaurantTable, CashHandover
from users.models import User
from apps.orders.services import create_order_idempotently, sync_order_financials
from apps.finance.models import JournalEntry, JournalEntryItem


class RestaurantBillRequestAndHandoverTestCase(APITestCase):
    def setUp(self):
        # Users
        self.admin = User.objects.create_user(
            username="admin-btest",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.manager = User.objects.create_user(
            username="manager-btest",
            password="test-password",
            role="manager",
            is_active=True,
        )
        self.waiter1 = User.objects.create_user(
            username="waiter1-btest",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.waiter2 = User.objects.create_user(
            username="waiter2-btest",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.cashier = User.objects.create_user(
            username="cashier-btest",
            password="test-password",
            role=User.CASHIER,
            is_active=True,
        )

        # Setup Table, Menu Category & Item
        self.table = RestaurantTable.objects.create(table_code="T-10", status="available")
        self.category = Category.objects.create(name="Hot Kitchen", station="Kitchen")
        self.item = MenuItem.objects.create(
            name="Grilled Steak",
            category=self.category,
            price=Decimal("400.00"),
            is_available=True,
        )

    def _create_order_for_waiter(self, waiter=None, order_status="served", table=None):
        target_table = table or self.table
        w_id = waiter.id if waiter else None
        w_name = waiter.username if waiter else ""
        order = Order.objects.create(
            table=target_table,
            waiter_id_ref=w_id,
            waiter_username=w_name,
            status=order_status,
            payment_status="pending",
        )
        OrderItem.objects.create(
            order=order,
            menu_item=self.item,
            quantity=1,
            price_at_order=Decimal("400.00"),
            status="served" if order_status in ["served", "bill_requested", "paid"] else "pending",
        )
        sync_order_financials(order)
        return order

    # -------------------------------------------------------------------------
    # 1. API and Lifecycle Tests
    # -------------------------------------------------------------------------
    def test_served_order_can_request_bill(self):
        """A served order can transition to bill_requested status."""
        order = self._create_order_for_waiter(self.waiter1, order_status="served")
        self.client.force_authenticate(user=self.waiter1)

        url = f"/users/orders/{order.id}/request-bill/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "bill_requested")
        self.assertEqual(order.payment_status, "pending")

    def test_repeated_bill_request_is_idempotent(self):
        """Submitting a bill request again for an order already in bill_requested returns 200 without error."""
        order = self._create_order_for_waiter(self.waiter1, order_status="bill_requested")
        self.client.force_authenticate(user=self.waiter1)

        url = f"/users/orders/{order.id}/request-bill/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "bill_requested")

    def test_ineligible_order_statuses_cannot_request_bill(self):
        """Orders in pending, preparing, or ready status cannot request a bill, returning controlled 400."""
        self.client.force_authenticate(user=self.waiter1)
        for bad_status in ["pending", "preparing", "ready"]:
            order = self._create_order_for_waiter(self.waiter1, order_status=bad_status)
            url = f"/users/orders/{order.id}/request-bill/"
            response = self.client.post(url)
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Status {bad_status} should have returned 400",
            )
            order.refresh_from_db()
            self.assertEqual(order.status, bad_status, f"Order status should not have mutated from {bad_status}")

    def test_paid_and_cancelled_orders_cannot_request_bill(self):
        """Paid and cancelled orders return controlled 400 when requesting a bill."""
        self.client.force_authenticate(user=self.waiter1)

        paid_order = self._create_order_for_waiter(self.waiter1, order_status="paid")
        paid_order.payment_status = "paid"
        paid_order.save()
        res_paid = self.client.post(f"/users/orders/{paid_order.id}/request-bill/")
        self.assertEqual(res_paid.status_code, status.HTTP_400_BAD_REQUEST)

        cancelled_order = self._create_order_for_waiter(self.waiter1, order_status="cancelled")
        res_cancelled = self.client.post(f"/users/orders/{cancelled_order.id}/request-bill/")
        self.assertEqual(res_cancelled.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 2. Authorization Tests
    # -------------------------------------------------------------------------
    def test_assigned_waiter_can_request_bill(self):
        """Assigned waiter is authorized to request the bill for their own order."""
        order = self._create_order_for_waiter(self.waiter1, order_status="served")
        self.client.force_authenticate(user=self.waiter1)
        res = self.client.post(f"/users/orders/{order.id}/request-bill/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_unauthorized_waiter_cannot_request_bill(self):
        """A waiter cannot request a bill for an order assigned to a different waiter (403 Forbidden)."""
        order = self._create_order_for_waiter(self.waiter1, order_status="served")
        self.client.force_authenticate(user=self.waiter2)
        res = self.client.post(f"/users/orders/{order.id}/request-bill/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        order.refresh_from_db()
        self.assertEqual(order.status, "served")

    def test_admin_and_manager_supervisory_access(self):
        """Admin or manager can request a bill supervisory for any waiter's order."""
        order = self._create_order_for_waiter(self.waiter1, order_status="served")
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f"/users/orders/{order.id}/request-bill/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "bill_requested")

    def test_unassigned_order_claimed_by_requesting_waiter(self):
        """When a bill is requested for an unassigned order (e.g. self-service QR), the waiter claims ownership."""
        order = self._create_order_for_waiter(waiter=None, order_status="served")
        self.assertIsNone(order.waiter_id_ref)

        self.client.force_authenticate(user=self.waiter2)
        res = self.client.post(f"/users/orders/{order.id}/request-bill/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.waiter_id_ref, self.waiter2.id)
        self.assertEqual(order.status, "bill_requested")

    # -------------------------------------------------------------------------
    # 3. Bill Preparation (Cashier) Tests
    # -------------------------------------------------------------------------
    def test_cashier_can_prepare_bill(self):
        """Cashier prepares bill, recording timestamp and cashier ID, making it ready for presentation."""
        order = self._create_order_for_waiter(self.waiter1, order_status="bill_requested")
        self.client.force_authenticate(user=self.cashier)

        url = f"/users/orders/{order.id}/prepare-bill/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertIsNotNone(order.bill_prepared_at)
        self.assertEqual(order.bill_prepared_by_id_ref, self.cashier.id)

    # -------------------------------------------------------------------------
    # 4. Cash Handover & Canonical Payment Tests
    # -------------------------------------------------------------------------
    def test_waiter_records_cash_handover(self):
        """Waiter records collected cash, creating an auditable CashHandover in pending status."""
        order = self._create_order_for_waiter(self.waiter1, order_status="bill_requested")
        self.client.force_authenticate(user=self.waiter1)

        url = f"/users/orders/{order.id}/cash-handover/"
        res = self.client.post(url, {"tip_amount": "20.00", "notes": "Handing over to cashier Abebe"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        handover = CashHandover.objects.get(order=order)
        self.assertEqual(handover.status, "pending")
        self.assertEqual(handover.waiter_id_ref, self.waiter1.id)
        self.assertEqual(handover.amount, Decimal(str(order.total_amount)))
        self.assertEqual(handover.tip_amount, Decimal("20.00"))

        # Order must not be marked paid merely because cash handover is pending
        order.refresh_from_db()
        self.assertNotEqual(order.payment_status, "paid")

    def test_unauthorized_waiter_cannot_record_handover(self):
        """Another waiter cannot record cash handover for an order assigned to a different waiter."""
        order = self._create_order_for_waiter(self.waiter1, order_status="bill_requested")
        self.client.force_authenticate(user=self.waiter2)

        url = f"/users/orders/{order.id}/cash-handover/"
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(CashHandover.objects.filter(order=order).exists())

    def test_cashier_confirms_handover_and_settles_atomically_with_gl(self):
        """
        Cashier verifies cash, confirms handover, marks order paid,
        releases table, and posts canonical GL entries exactly once.
        """
        order = self._create_order_for_waiter(self.waiter1, order_status="bill_requested")
        self.table.status = "occupied"
        self.table.save()

        # Step 1: Waiter records cash collection
        self.client.force_authenticate(user=self.waiter1)
        self.client.post(f"/users/orders/{order.id}/cash-handover/", {"tip_amount": "10.00"})

        # Step 2: Cashier confirms handover
        self.client.force_authenticate(user=self.cashier)
        url = f"/users/orders/{order.id}/confirm-handover/"
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify Order state
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.payment_method, "Cash")

        # Verify CashHandover state
        handover = CashHandover.objects.get(order=order)
        self.assertEqual(handover.status, "confirmed")
        self.assertEqual(handover.cashier_id_ref, self.cashier.id)
        self.assertIsNotNone(handover.confirmed_at)

        # Verify Table released
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")

        # Verify General Ledger entries created exactly once
        gl_entries = JournalEntry.objects.filter(description__contains=f"Order #{order.id}")
        self.assertEqual(gl_entries.count(), 1)
        entry = gl_entries.first()
        self.assertGreater(entry.items.count(), 0)

        # Step 3: Duplicate settlement attempt returns controlled 400 and does NOT create duplicate GL entries
        dup_res = self.client.post(url)
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(JournalEntry.objects.filter(description__contains=f"Order #{order.id}").count(), 1)

    def test_dining_session_bill_request_synchronizes_all_served_orders(self):
        """
        Requesting a bill on an order belonging to an active dining session
        synchronizes all served orders in that session to bill_requested.
        """
        session = DiningSession.objects.create(
            table=self.table,
            opened_by_id_ref=self.waiter1.id,
            opened_by_username=self.waiter1.username,
            status="active",
        )
        # Order 1: served
        order1 = self._create_order_for_waiter(self.waiter1, order_status="served")
        order1.session = session
        order1.save()

        # Order 2: also served
        order2 = self._create_order_for_waiter(self.waiter1, order_status="served")
        order2.session = session
        order2.save()

        self.client.force_authenticate(user=self.waiter1)
        res = self.client.post(f"/users/orders/{order1.id}/request-bill/")
        self.assertEqual(res.status_code, status.HTTP_200_OK, getattr(res, "data", None))

        order1.refresh_from_db()
        order2.refresh_from_db()
        self.assertEqual(order1.status, "bill_requested")
        self.assertEqual(order2.status, "bill_requested")
