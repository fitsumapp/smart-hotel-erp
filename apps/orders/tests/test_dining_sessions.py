from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import Category, DiningSession, MenuItem, Order, OrderItem, RestaurantTable
from users.models import User
from apps.orders.services import create_order_idempotently, finalize_paid_order, settle_dining_session, build_session_payment_summary


class DiningSessionAndReorderingTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-session-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.waiter = User.objects.create_user(
            username="waiter-session-test",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.cashier = User.objects.create_user(
            username="cashier-session-test",
            password="test-password",
            role=User.CASHIER,
            is_active=True,
        )
        self.kitchen_user = User.objects.create_user(
            username="kitchen-session-test",
            password="test-password",
            role=User.KITCHEN,
            is_active=True,
        )
        self.bar_user = User.objects.create_user(
            username="bar-session-test",
            password="test-password",
            role=User.BAR,
            is_active=True,
        )

        self.table = RestaurantTable.objects.create(table_code="T-201", status="available")
        self.food_cat = Category.objects.create(name="Food-B1B", station="Kitchen")
        self.drink_cat = Category.objects.create(name="Drinks-B1B", station="Bar")

        self.burger = MenuItem.objects.create(
            name="Session Burger",
            category=self.food_cat,
            price=Decimal("200.00"),
        )
        self.wine = MenuItem.objects.create(
            name="House Wine",
            category=self.drink_cat,
            price=Decimal("150.00"),
        )
        self.dessert = MenuItem.objects.create(
            name="Cheesecake",
            category=self.food_cat,
            price=Decimal("100.00"),
        )

    def test_multi_round_ordering_shares_session_and_keeps_table_occupied(self):
        """
        Verify that multiple rounds of ordering on the same table link to the same
        active DiningSession, keep the table occupied, and create distinct Order rows.
        """
        # Round 1: Waiter places first order on available table
        order1, created1 = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 2, "notes": "No onions"}],
            waiter=self.waiter,
        )
        self.assertTrue(created1)
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "occupied")
        self.assertIsNotNone(order1.session)
        session = order1.session
        self.assertEqual(session.status, "active")
        self.assertEqual(session.table_id, self.table.id)
        self.assertEqual(session.opened_by_username, self.waiter.username)

        # Round 2: Waiter places second order on the NOW OCCUPIED table
        order2, created2 = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1, "notes": "Chilled"}],
            waiter=self.waiter,
        )
        self.assertTrue(created2)
        self.assertNotEqual(order1.id, order2.id)

        # Verify both orders share the identical DiningSession
        self.assertEqual(order2.session_id, session.id)
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "occupied")

        # Session should contain exactly 2 orders
        session_orders = list(session.orders.all())
        self.assertEqual(len(session_orders), 2)
        self.assertIn(order1, session_orders)
        self.assertIn(order2, session_orders)

    def test_table_occupancy_persistence_across_partial_payment(self):
        """
        Paying Round 1 individually must NOT release the table to available
        when Round 2 is still unpaid.
        """
        # Create Round 1 & Round 2
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 2}],
            waiter=self.waiter,
        )
        session = order1.session

        # Settle Round 1 only
        finalize_paid_order(order1, payment_method="Cash", cashier=self.cashier)
        order1.refresh_from_db()
        self.assertEqual(order1.payment_status, "paid")

        # Table MUST still be occupied because order2 is pending!
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "occupied")

        # Session MUST still be active
        session.refresh_from_db()
        self.assertEqual(session.status, "active")

        # Settle Round 2
        finalize_paid_order(order2, payment_method="Cash", cashier=self.cashier)
        order2.refresh_from_db()
        self.assertEqual(order2.payment_status, "paid")

        # NOW table should be released to available and session closed!
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")
        session.refresh_from_db()
        self.assertEqual(session.status, "closed")
        self.assertIsNotNone(session.closed_at)

    def test_cashier_pending_bills_groups_by_dining_session(self):
        """
        Cashier pending-bills endpoint must return a consolidated bill for an active
        dining session that aggregates all rounds.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.dessert.id, "quantity": 2}],
            waiter=self.waiter,
        )
        session = order1.session
        Order.objects.filter(id=order1.id).update(status="served")

        self.client.force_authenticate(self.cashier)
        res = self.client.get(reverse("cashier-pending-bills"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # There should be 1 consolidated entry for this table/session
        session_bills = [b for b in res.data if b.get("session_id") == session.id]
        self.assertEqual(len(session_bills), 1)
        bill = session_bills[0]
        self.assertTrue(bill.get("is_session"))
        self.assertEqual(bill.get("rounds_count"), 2)
        self.assertEqual(bill.get("table_code"), "T-201")

        # Total items: 1 burger + 2 cheesecakes = 2 item entries
        self.assertEqual(len(bill.get("items")), 2)

        # Expected subtotal: 200 + (2 * 100) = 400.00
        # Service (10%) = 40.00, VAT (15%) = 60.00 -> grand_total = 500.00
        self.assertEqual(bill.get("sub_total"), 400.0)
        self.assertEqual(bill.get("service_charge_amount"), 40.0)
        self.assertEqual(bill.get("vat_amount"), 60.0)
        self.assertEqual(bill.get("grand_total"), 500.0)

    def test_settle_dining_session_endpoint(self):
        """
        SettleDiningSessionView settles all unpaid orders atomically,
        closes the session, and releases the table.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res = self.client.post(url, {"payment_method": "Cash", "tip_amount": 25.0}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("settled successfully", res.data["message"])

        # Check DB state
        order1.refresh_from_db()
        order2.refresh_from_db()
        self.assertEqual(order1.payment_status, "paid")
        self.assertEqual(order2.payment_status, "paid")

        session.refresh_from_db()
        self.assertEqual(session.status, "closed")
        self.assertEqual(session.closed_by_id_ref, self.cashier.id)

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")

    def test_cashier_receipt_view_for_session(self):
        """
        Cashier receipt view should return consolidated bill and all items across rounds.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 2}],
            waiter=self.waiter,
        )

        self.client.force_authenticate(self.cashier)
        url = reverse("cashier-receipt", kwargs={"order_id": order1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["session_id"], order1.session_id)
        self.assertEqual(res.data["rounds_count"], 2)
        self.assertEqual(len(res.data["items"]), 2)
        # 1 burger (200) + 2 wines (300) = 500 subtotal
        self.assertEqual(res.data["sub_total"], 500.0)

    def test_batch_1a_compatibility_with_multi_round_sessions(self):
        """
        Ensure item-level preparation routing (DEFECT-ORD-001/003) works seamlessly
        when new rounds are added to an existing dining session.
        """
        # Round 1: Waiter orders Food + Drink
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1, "notes": "Well done"},
                {"id": self.wine.id, "quantity": 1, "notes": "Red"},
            ],
            waiter=self.waiter,
        )

        # Bar marks the wine preparing, then ready in Round 1
        wine_item_1 = order1.items.get(menu_item=self.wine)
        self.client.force_authenticate(self.bar_user)
        self.client.post(
            reverse("update-order-status", kwargs={"order_id": order1.id}),
            {"status": "preparing", "station": "Bar"},
            format="json",
        )
        res_bar = self.client.post(
            reverse("update-order-status", kwargs={"order_id": order1.id}),
            {"status": "ready", "station": "Bar"},
            format="json",
        )
        self.assertEqual(res_bar.status_code, status.HTTP_200_OK)
        wine_item_1.refresh_from_db()
        self.assertEqual(wine_item_1.status, "ready")

        # Kitchen food is still pending
        burger_item_1 = order1.items.get(menu_item=self.burger)
        self.assertEqual(burger_item_1.status, "pending")

        # Round 2: Waiter adds another drink to the table
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 2, "notes": "White wine round 2"}],
            waiter=self.waiter,
        )

        # Bar should now see Round 2's wine, while Round 1's completed wine remains completed
        b_res = self.client.get(reverse("kitchen-orders") + "?station=Bar")
        bar_order_ids = [o["id"] for o in b_res.data]
        self.assertIn(order2.id, bar_order_ids)
        self.assertNotIn(order1.id, bar_order_ids)  # Round 1 bar item was already completed!

        round2_bar_order = next(o for o in b_res.data if o["id"] == order2.id)
        self.assertEqual(round2_bar_order["items"][0]["notes"], "White wine round 2")
        self.assertEqual(round2_bar_order["items"][0]["status"], "pending")

        # Kitchen still sees Round 1's unfinished burger
        self.client.force_authenticate(self.kitchen_user)
        k_res = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        k_order_ids = [o["id"] for o in k_res.data]
        self.assertIn(order1.id, k_order_ids)
        round1_k_order = next(o for o in k_res.data if o["id"] == order1.id)
        self.assertEqual(round1_k_order["items"][0]["notes"], "Well done")

    def test_reordering_idempotency_prevents_duplicate_rounds(self):
        """
        Verify that reusing an idempotency key during a reordering round
        safely returns the existing order instead of duplicating items.
        """
        # Round 1
        order1, created1 = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
            idempotency_key="round-1-unique-key",
        )
        self.assertTrue(created1)

        # Retry Round 1 with same key
        order1_retry, created1_retry = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
            idempotency_key="round-1-unique-key",
        )
        self.assertFalse(created1_retry)
        self.assertEqual(order1.id, order1_retry.id)

        # Round 2 with new key
        order2, created2 = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1}],
            waiter=self.waiter,
            idempotency_key="round-2-unique-key",
        )
        self.assertTrue(created2)
        self.assertNotEqual(order1.id, order2.id)
        self.assertEqual(order1.session_id, order2.session_id)

    def test_unique_active_session_constraint_per_table(self):
        """
        Database unique partial constraint must reject creating two active
        sessions for the same table simultaneously.
        """
        from django.db import IntegrityError

        # Create first active session via order
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        self.assertIsNotNone(order1.session)

        # Direct attempt to insert a second active session for the same table
        with self.assertRaises(IntegrityError):
            DiningSession.objects.create(
                table=self.table,
                status="active",
                opened_by_id_ref=self.waiter.id,
                opened_by_username=self.waiter.username,
            )

    def test_settle_dining_session_with_room_charge(self):
        """
        Settling a dining session via room charge posts charges to the guest folio
        and releases the restaurant table.
        """
        from hotel.models import Room, Reservation, FolioCharge

        room = Room.objects.create(
            name="Room 305",
            room_number="305",
            room_type="Deluxe",
            base_price=Decimal("1500.00"),
            status="Occupied",
        )
        res = Reservation.objects.create(
            guest_name="Abebe Kebede",
            guest_phone="0911000000",
            guest_email="abebe@example.com",
            room=room,
            check_in_date="2026-10-20",
            check_out_date="2026-10-23",
            status="checked_in",
            total_amount=Decimal("4500.00"),
        )

        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 2}],
            waiter=self.waiter,
        )
        session = order1.session

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res_post = self.client.post(
            url,
            {
                "payment_method": "Room Charge",
                "reservation_id": res.id,
                "tip_amount": 0,
            },
            format="json",
        )
        self.assertEqual(res_post.status_code, status.HTTP_200_OK)

        order1.refresh_from_db()
        self.assertEqual(order1.payment_status, "paid")
        self.assertEqual(order1.payment_method, "Room Charge")

        session.refresh_from_db()
        self.assertEqual(session.status, "closed")

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")

        # Verify FolioCharge entry was created
        folio_entries = FolioCharge.objects.filter(reservation=res)
        self.assertTrue(folio_entries.exists())

    def test_settle_session_retry_is_idempotent_and_prevents_duplicate_charge(self):
        """
        Retrying settle_dining_session on an already closed session must be rejected
        and not duplicate payments, journal entries, or charges.
        """
        from apps.finance.models import JournalEntry

        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        # Settle first time
        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res1 = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        initial_journal_count = JournalEntry.objects.count()

        # Retry second time
        res2 = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already closed", str(res2.data.get("error", "")))

        # Journal entries count must not have changed
        self.assertEqual(JournalEntry.objects.count(), initial_journal_count)

    def test_order_already_paid_individually_is_not_charged_again_during_session_settlement(self):
        """
        If Round 1 was paid individually, subsequent session settlement must only
        charge Round 2, and not double-charge Round 1.
        """
        from apps.finance.models import JournalEntry

        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        # Waiter or cashier settles order1 individually
        finalize_paid_order(order1, payment_method="Cash", cashier=self.cashier)
        order1.refresh_from_db()
        self.assertEqual(order1.payment_status, "paid")

        # Check financial summary reflects partial payment
        summary_mid = build_session_payment_summary(session)
        # order1 (200) + order2 (150) = 350 subtotal
        self.assertEqual(summary_mid["sub_total"], 350.0)
        self.assertGreater(summary_mid["paid_amount"], 0)
        # outstanding balance should equal only order2 (150 subtotal)
        self.assertAlmostEqual(summary_mid["outstanding_balance"], float(order2.total_amount), places=2)

        # Now cashier settles the session
        journal_count_before = JournalEntry.objects.count()
        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["orders_settled"], [order2.id])  # Only order2 was settled!

        # Exactly 1 new settlement occurred (for order2)
        order1.refresh_from_db()
        order2.refresh_from_db()
        self.assertEqual(order1.payment_status, "paid")
        self.assertEqual(order2.payment_status, "paid")
        session.refresh_from_db()
        self.assertEqual(session.status, "closed")
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")

    def test_closed_session_rejects_new_orders_and_new_session_can_open_after_closure(self):
        """
        A closed session must refuse new rounds, but once table is available,
        a new active session can open cleanly.
        """
        from django.core.exceptions import ValidationError

        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session
        settle_dining_session(session, cashier=self.cashier)
        session.refresh_from_db()
        self.assertEqual(session.status, "closed")
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")

        # Attempting to add order pointing to the closed session
        with self.assertRaises(ValidationError) as ctx:
            create_order_idempotently(
                table_id=self.table.id,
                items=[{"id": self.wine.id, "quantity": 1}],
                waiter=self.waiter,
                session_id=session.id,
            )
        self.assertIn("cannot accept new orders", str(ctx.exception))

        # Adding new order to table with session_id=None opens brand new session
        order_new, created_new = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1}],
            waiter=self.waiter,
        )
        self.assertTrue(created_new)
        self.assertNotEqual(order_new.session_id, session.id)
        self.assertEqual(order_new.session.status, "active")
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "occupied")

    def test_order_with_mismatched_session_table_raises_validation_error(self):
        """
        Passing session_id belonging to Table A when ordering on Table B must be rejected.
        """
        from django.core.exceptions import ValidationError

        table_b = RestaurantTable.objects.create(table_code="T-202", status="available")
        order_a, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session_a = order_a.session

        # Order on Table B referencing session from Table A
        with self.assertRaises(ValidationError) as ctx:
            create_order_idempotently(
                table_id=table_b.id,
                items=[{"id": self.wine.id, "quantity": 1}],
                waiter=self.waiter,
                session_id=session_a.id,
            )
        self.assertIn("belongs to table 'T-201', not 'T-202'", str(ctx.exception))

    def test_failed_session_settlement_rolls_back_atomically(self):
        """
        If session settlement fails (e.g. invalid room charge), the transaction
        must roll back completely: no orders marked paid, session remains active,
        table remains occupied.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        # Invalid room number with no checked-in reservation
        res = self.client.post(
            url,
            {"payment_method": "Room Charge", "room_number": "999"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No active checked-in guest found", res.data["error"])

        order1.refresh_from_db()
        self.assertEqual(order1.payment_status, "pending")
        session.refresh_from_db()
        self.assertEqual(session.status, "active")
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "occupied")

    def test_cancelled_orders_excluded_from_session_totals_and_receipt(self):
        """
        Cancelled orders within a session must not be charged, must not inflate
        session payment totals, and must not appear on fiscal receipts.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.wine.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        # Cancel order2
        order2.status = "cancelled"
        order2.save(update_fields=["status"])

        summary = build_session_payment_summary(session)
        # Should only include order1 (burger @ 200)
        self.assertEqual(summary["rounds_count"], 1)
        self.assertEqual(summary["sub_total"], 200.0)

        # Receipt should only list order1 items
        self.client.force_authenticate(self.cashier)
        url = reverse("cashier-receipt", kwargs={"order_id": order1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["menu_item_name"], "Session Burger")

    def test_receipt_distinguishes_grand_total_from_paid_amount_and_outstanding_balance(self):
        """
        Receipt must clearly distinguish the total session bill from the amount already paid
        and the outstanding balance.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.dessert.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        # Settle order1 only
        finalize_paid_order(order1, payment_method="Cash", cashier=self.cashier)

        self.client.force_authenticate(self.cashier)
        url = reverse("cashier-receipt", kwargs={"order_id": order1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # 1 burger (200) + 1 cheesecake (100) = 300 subtotal
        # Service 10% (30) + VAT 15% (45) = 375 total
        # order1 = 200 + 20 + 30 = 250
        # order2 = 100 + 10 + 15 = 125
        self.assertEqual(res.data["sub_total"], 300.0)
        self.assertEqual(res.data["grand_total"], 375.0)
        self.assertEqual(res.data["paid_amount"], 250.0)
        self.assertEqual(res.data["outstanding_balance"], 125.0)
        self.assertEqual(res.data["amount_due"], 125.0)

        # Settle order2 as well
        finalize_paid_order(order2, payment_method="Cash", cashier=self.cashier)
        res_full = self.client.get(url)
        self.assertEqual(res_full.data["paid_amount"], 375.0)
        self.assertEqual(res_full.data["outstanding_balance"], 0.0)
        self.assertEqual(res_full.data["amount_due"], 0.0)

    def test_client_supplied_totals_cannot_override_server_amount_due(self):
        """
        Client sending tampered totals in request body cannot change
        the authoritative server-side charge and accounting entries.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order1.session

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        # Malicious client tries to send fake totals of 1.0 ETB
        res = self.client.post(
            url,
            {
                "payment_method": "Cash",
                "sub_total": 1.0,
                "grand_total": 1.0,
                "total_amount": 1.0,
                "amount_due": 1.0,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        order1.refresh_from_db()
        # Authoritative burger: 200 + 20 (service) + 30 (vat) = 250.00
        self.assertEqual(order1.sub_total, Decimal("200.00"))
        self.assertEqual(order1.total_amount, Decimal("250.00"))
        self.assertEqual(res.data["receipt_data"]["grand_total"], 250.0)
        self.assertEqual(res.data["receipt_data"]["paid_amount"], 250.0)
        self.assertEqual(res.data["receipt_data"]["outstanding_balance"], 0.0)


import threading
from django.test import TransactionTestCase
from django.db import connection

class DiningSessionConcurrencyTestCase(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific dining session concurrency test")
        self.waiter = User.objects.create_user(
            username="waiter-conc-test", password="test-password", role=User.WAITER, is_active=True
        )
        self.table = RestaurantTable.objects.create(table_code="T-CONC", status="available")
        cat = Category.objects.create(name="Food-Conc", station="Kitchen")
        self.item = MenuItem.objects.create(name="Conc Burger", category=cat, price=Decimal("150.00"))

    def test_concurrent_first_order_creation_results_in_single_active_session(self):
        """
        Test simultaneous first-order creation on the same unoccupied table across threads.
        """
        results = []
        errors = []

        def place_order(thread_id):
            try:
                # Close thread-local connection so thread gets fresh connection
                connection.close()
                ord_obj, created = create_order_idempotently(
                    table_id=self.table.id,
                    items=[{"id": self.item.id, "quantity": 1}],
                    waiter=self.waiter,
                    idempotency_key=f"conc-key-{thread_id}",
                )
                results.append((thread_id, ord_obj.id, ord_obj.session_id))
            except Exception as e:
                errors.append((thread_id, str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=place_order, args=(1,))
        t2 = threading.Thread(target=place_order, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both orders or 1 order + 1 round succeeded
        active_sessions = DiningSession.objects.filter(table=self.table, status="active")
        # Under all circumstances, exactly ONE active session exists for the table!
        self.assertEqual(active_sessions.count(), 1)

    def test_concurrent_duplicate_session_settlement_requests(self):
        """
        Simultaneous settlement calls on the same active session across separate threads:
        exactly ONE thread must succeed in settling; the other must receive
        'Dining session is already closed.' with 0 duplicate payments or JVs.
        """
        from apps.finance.models import JournalEntry

        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.item.id, "quantity": 1}],
            waiter=self.waiter,
        )
        session = order.session

        successes = []
        failures = []

        def settle_worker(worker_id):
            try:
                connection.close()
                sess = DiningSession.objects.get(pk=session.pk)
                settled_sess, settled_orders = settle_dining_session(
                    sess,
                    payment_method="Cash",
                    cashier=self.waiter,
                )
                successes.append((worker_id, len(settled_orders)))
            except Exception as e:
                failures.append((worker_id, str(e)))
            finally:
                connection.close()

        t1 = threading.Thread(target=settle_worker, args=(1,))
        t2 = threading.Thread(target=settle_worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly ONE thread must succeed
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        error_msg = failures[0][1].lower()
        self.assertTrue(
            "already closed" in error_msg or "locked" in error_msg,
            f"Expected 'already closed' or database lock error, got {failures[0][1]}",
        )

        session.refresh_from_db()
        self.assertEqual(session.status, "closed")
        self.table.refresh_from_db()
        self.assertEqual(self.table.status, "available")





