from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.exceptions import ValidationError

from hotel.models import Category, DiningSession, MenuItem, Order, OrderItem, RestaurantTable, SystemSettings
from users.models import User
from apps.orders.services import (
    create_order_idempotently,
    finalize_paid_order,
    settle_dining_session,
    calculate_order_financials,
)
from hotel.integrity import recalculate_order_lifecycle


class OrderLifecycleTimingTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-timing-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.waiter1 = User.objects.create_user(
            username="waiter1-timing-test",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.waiter2 = User.objects.create_user(
            username="waiter2-timing-test",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.cashier = User.objects.create_user(
            username="cashier-timing-test",
            password="test-password",
            role=User.CASHIER,
            is_active=True,
        )
        self.kitchen_user = User.objects.create_user(
            username="kitchen-timing-test",
            password="test-password",
            role=User.KITCHEN,
            is_active=True,
        )
        self.bar_user = User.objects.create_user(
            username="bar-timing-test",
            password="test-password",
            role=User.BAR,
            is_active=True,
        )

        self.table = RestaurantTable.objects.create(table_code="T-301", status="available")
        self.kitchen_cat = Category.objects.create(name="Kitchen-Main", station="Kitchen")
        self.bar_cat = Category.objects.create(name="Bar-Beverages", station="Bar")

        self.burger = MenuItem.objects.create(
            name="Timing Burger",
            category=self.kitchen_cat,
            price=Decimal("150.00"),
        )
        self.pizza = MenuItem.objects.create(
            name="Timing Pizza",
            category=self.kitchen_cat,
            price=Decimal("200.00"),
        )
        self.cocktail = MenuItem.objects.create(
            name="Timing Cocktail",
            category=self.bar_cat,
            price=Decimal("100.00"),
        )

    def test_creation_timestamps(self):
        """
        Verify that order and order item creation initializes received_at
        and leaves preparation/ready/served timestamps null.
        """
        order, created = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 2},
            ],
            waiter=self.waiter1,
        )
        self.assertTrue(created)
        self.assertIsNotNone(order.received_at)
        self.assertIsNone(order.preparation_started_at)
        self.assertIsNone(order.ready_at)
        self.assertIsNone(order.served_at)

        items = list(order.items.all())
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertEqual(it.status, "pending")
            self.assertIsNotNone(it.received_at)
            self.assertIsNone(it.preparation_started_at)
            self.assertIsNone(it.ready_at)
            self.assertIsNone(it.served_at)
            self.assertIsNone(it.prepared_by_id_ref)
            self.assertIsNone(it.ready_by_id_ref)
            self.assertIsNone(it.served_by_id_ref)

    def test_kitchen_item_lifecycle(self):
        """
        Full lifecycle for a kitchen item: pending -> preparing -> ready -> served.
        Verifies staff attribution and timestamp progression.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item = order.items.first()

        # 1. Kitchen staff marks preparing
        self.client.force_authenticate(self.kitchen_user)
        url = reverse("update-order-status", kwargs={"order_id": order.id})
        res = self.client.post(url, {"status": "preparing", "item_id": item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.status, "preparing")
        self.assertIsNotNone(item.preparation_started_at)
        self.assertEqual(item.prepared_by_id_ref, self.kitchen_user.id)
        self.assertEqual(order.status, "preparing")
        self.assertIsNotNone(order.preparation_started_at)

        # 2. Kitchen staff marks ready
        res = self.client.post(url, {"status": "ready", "item_id": item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.status, "ready")
        self.assertIsNotNone(item.ready_at)
        self.assertEqual(item.ready_by_id_ref, self.kitchen_user.id)
        self.assertEqual(order.status, "ready")
        self.assertIsNotNone(order.ready_at)

        # 3. Waiter marks item served
        self.client.force_authenticate(self.waiter1)
        serve_url = reverse("mark-item-served", kwargs={"item_id": item.id})
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.status, "served")
        self.assertIsNotNone(item.served_at)
        self.assertEqual(item.served_by_id_ref, self.waiter1.id)
        self.assertEqual(order.status, "served")
        self.assertIsNotNone(order.served_at)
        self.assertEqual(order.served_by_id_ref, self.waiter1.id)

    def test_bar_item_lifecycle_direct_ready(self):
        """
        Bar item lifecycle: pending -> ready -> served without preparation_started_at.
        Bar items fulfill directly without prep start timestamp.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.cocktail.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item = order.items.first()

        # Bar staff marks directly as ready
        self.client.force_authenticate(self.bar_user)
        url = reverse("update-order-status", kwargs={"order_id": order.id})
        res = self.client.post(url, {"status": "ready", "item_id": item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.status, "ready")
        self.assertIsNotNone(item.ready_at)
        self.assertIsNone(item.preparation_started_at)
        self.assertEqual(item.ready_by_id_ref, self.bar_user.id)
        self.assertEqual(order.status, "ready")

        # Waiter serves bar item
        self.client.force_authenticate(self.waiter1)
        serve_url = reverse("mark-item-served", kwargs={"item_id": item.id})
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.status, "served")
        self.assertIsNotNone(item.served_at)
        self.assertIsNone(item.preparation_started_at)
        self.assertEqual(order.status, "served")

    def test_partial_serving_and_order_aggregation(self):
        """
        Order with 1 Bar item and 1 Kitchen item.
        Bar item marked ready and served immediately.
        Kitchen item remains pending/preparing.
        Parent order must remain in 'preparing' with is_partially_served=True.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.cocktail.id, "quantity": 1},
                {"id": self.burger.id, "quantity": 1},
            ],
            waiter=self.waiter1,
        )
        bar_item = order.items.get(menu_item=self.cocktail)
        kitchen_item = order.items.get(menu_item=self.burger)

        # 1. Bar marks cocktail ready
        self.client.force_authenticate(self.bar_user)
        url = reverse("update-order-status", kwargs={"order_id": order.id})
        res = self.client.post(url, {"status": "ready", "item_id": bar_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        bar_item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(bar_item.status, "ready")
        self.assertEqual(kitchen_item.status, "pending")
        self.assertEqual(order.status, "preparing")

        # 2. Waiter serves cocktail while burger is still pending
        self.client.force_authenticate(self.waiter1)
        serve_url = reverse("mark-item-served", kwargs={"item_id": bar_item.id})
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        bar_item.refresh_from_db()
        kitchen_item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(bar_item.status, "served")
        self.assertEqual(kitchen_item.status, "pending")
        self.assertEqual(order.status, "preparing")
        self.assertTrue(order.is_partially_served())

        # Check serialization
        waiter_orders_res = self.client.get(reverse("waiter-orders"))
        self.assertEqual(waiter_orders_res.status_code, status.HTTP_200_OK)
        order_json = next((o for o in waiter_orders_res.data if o["id"] == order.id), None)
        self.assertIsNotNone(order_json)
        self.assertTrue(order_json["is_partially_served"])
        self.assertEqual(order_json["served_items_count"], 1)

        # 3. Kitchen marks burger preparing then ready
        self.client.force_authenticate(self.kitchen_user)
        self.client.post(url, {"status": "preparing", "item_id": kitchen_item.id}, format="json")
        res = self.client.post(url, {"status": "ready", "item_id": kitchen_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")

        # 4. Waiter serves burger -> whole order served
        self.client.force_authenticate(self.waiter1)
        res = self.client.post(reverse("mark-item-served", kwargs={"item_id": kitchen_item.id}), format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, "served")
        self.assertFalse(order.is_partially_served())
        self.assertIsNotNone(order.served_at)

    def test_bulk_mark_items_served(self):
        """
        Verify bulk marking items served across single or multiple orders.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.pizza.id, "quantity": 1},
            ],
            waiter=self.waiter1,
        )
        items = list(order.items.all())
        for it in items:
            it.status = "ready"
            it.ready_at = timezone.now()
            it.save()
        recalculate_order_lifecycle(order.id)
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")

        self.client.force_authenticate(self.waiter1)
        bulk_url = reverse("mark-items-served-bulk")
        res = self.client.post(bulk_url, {"item_ids": [items[0].id, items[1].id]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["served_item_ids"]), 2)

        order.refresh_from_db()
        self.assertEqual(order.status, "served")

    def test_bulk_mark_items_served_atomicity(self):
        """
        If any item in bulk list is unready, entire transaction must fail and roll back.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.pizza.id, "quantity": 1},
            ],
            waiter=self.waiter1,
        )
        items = list(order.items.all())
        items[0].status = "ready"
        items[0].ready_at = timezone.now()
        items[0].save()
        # items[1] remains pending

        self.client.force_authenticate(self.waiter1)
        bulk_url = reverse("mark-items-served-bulk")
        res = self.client.post(bulk_url, {"item_ids": [items[0].id, items[1].id]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        items[0].refresh_from_db()
        self.assertEqual(items[0].status, "ready")

    def test_cannot_serve_unready_or_cancelled_items(self):
        """
        Attempting to mark pending, preparing, or cancelled items as served must return 400.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item = order.items.first()

        self.client.force_authenticate(self.waiter1)
        serve_url = reverse("mark-item-served", kwargs={"item_id": item.id})

        # Pending -> 400
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Preparing -> 400
        item.status = "preparing"
        item.save()
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Cancelled -> 400
        item.status = "cancelled"
        item.save()
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_idempotent_mark_served_preserves_original_timestamp(self):
        """
        Calling mark-served on an already served item is idempotent and does not overwrite timestamps.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item = order.items.first()
        item.status = "ready"
        item.ready_at = timezone.now()
        item.save()
        order.status = "ready"
        order.save()

        self.client.force_authenticate(self.waiter1)
        serve_url = reverse("mark-item-served", kwargs={"item_id": item.id})
        res1 = self.client.post(serve_url, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        orig_served_at = item.served_at
        self.assertIsNotNone(orig_served_at)

        res2 = self.client.post(serve_url, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        self.assertEqual(item.served_at, orig_served_at)

    def test_reopen_order_when_new_item_added(self):
        """
        When all items are served, but an item is added to the order,
        the order status safely reverts to 'preparing' via recalculate_order_lifecycle.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item1 = order.items.first()
        item1.status = "served"
        item1.served_at = timezone.now()
        item1.save()

        order.status = "ready"
        order.save()
        order.status = "served"
        order.served_at = timezone.now()
        order.save()

        # Add new item to this order
        item2 = OrderItem.objects.create(
            order=order,
            menu_item=self.cocktail,
            quantity=1,
            price_at_order=self.cocktail.price,
            status="pending",
            received_at=timezone.now(),
        )

        recalculate_order_lifecycle(order.id)
        order.refresh_from_db()
        self.assertEqual(order.status, "preparing")
        self.assertTrue(order.is_partially_served())

    def test_all_items_cancelled(self):
        """
        When all items in an order are cancelled, the parent order status transitions to 'cancelled'.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 1},
            ],
            waiter=self.waiter1,
        )
        for it in order.items.all():
            it.status = "cancelled"
            it.save()

        recalculate_order_lifecycle(order.id)
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")

    def test_cancelled_items_excluded_from_financials(self):
        """
        Cancelled items must be excluded from order financials.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},   # 150.00
                {"id": self.cocktail.id, "quantity": 1}, # 100.00
            ],
            waiter=self.waiter1,
        )
        # Cancel the cocktail
        cocktail_item = order.items.get(menu_item=self.cocktail)
        cocktail_item.status = "cancelled"
        cocktail_item.save()

        financials = calculate_order_financials(order)
        self.assertEqual(financials["sub_total"], Decimal("150.00"))

    def test_role_authorization_and_cross_waiter_prevention(self):
        """
        Test authorization safeguards:
        - Kitchen cannot update Bar items.
        - Bar cannot update Kitchen items.
        - Waiter cannot mark another waiter's order items as served.
        - Admin can mark any waiter's order items as served.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 1},
            ],
            waiter=self.waiter1,
        )
        burger_item = order.items.get(menu_item=self.burger)
        cocktail_item = order.items.get(menu_item=self.cocktail)

        # 1. Kitchen attempts to update bar item -> 403
        self.client.force_authenticate(self.kitchen_user)
        url = reverse("update-order-status", kwargs={"order_id": order.id})
        res = self.client.post(url, {"status": "ready", "item_id": cocktail_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Bar attempts to update kitchen item -> 403
        self.client.force_authenticate(self.bar_user)
        res = self.client.post(url, {"status": "ready", "item_id": burger_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Make burger preparing then ready
        self.client.force_authenticate(self.kitchen_user)
        self.client.post(url, {"status": "preparing", "item_id": burger_item.id}, format="json")
        res = self.client.post(url, {"status": "ready", "item_id": burger_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # 3. Waiter 2 attempts to serve Waiter 1's order item -> 403
        self.client.force_authenticate(self.waiter2)
        serve_url = reverse("mark-item-served", kwargs={"item_id": burger_item.id})
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Admin has supervisory override -> 200
        self.client.force_authenticate(self.admin)
        res = self.client.post(serve_url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_dining_session_settlement_safeguards(self):
        """
        Dining table orders cannot be settled while items are still unserved:
        - CompleteOrderView returns 400
        - settle_dining_session(..., enforce_served=True) raises ValidationError
        - Standalone counter POS (session is None) allows payment while pending
        """
        # 1. Dining table order with pending items
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        self.assertIsNotNone(order.session)

        self.client.force_authenticate(self.cashier)
        complete_url = reverse("complete-order", kwargs={"order_id": order.id})
        res = self.client.post(complete_url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items are still in preparation", res.data["error"])

        # 2. settle_dining_session with enforce_served=True
        with self.assertRaises(ValidationError):
            settle_dining_session(order.session, cashier=self.cashier, enforce_served=True)

        # 3. Standalone counter POS (session is None)
        counter_order = Order.objects.create(
            table=self.table,
            session=None,
            waiter_id_ref=self.cashier.id,
            waiter_username=self.cashier.username,
            sub_total=Decimal("150.00"),
            total_amount=Decimal("150.00"),
            status="pending",
            received_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=counter_order,
            menu_item=self.burger,
            quantity=1,
            price_at_order=self.burger.price,
            status="pending",
            received_at=timezone.now(),
        )
        res = self.client.post(reverse("complete-order", kwargs={"order_id": counter_order.id}), {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        counter_order.refresh_from_db()
        self.assertEqual(counter_order.payment_status, "paid")

    def test_system_settings_performance_targets(self):
        """
        Verify that SystemSettings default target fields exist and can be queried.
        """
        settings = SystemSettings.objects.first() or SystemSettings.objects.create()
        self.assertEqual(settings.kds_prep_target_minutes, 15)
        self.assertEqual(settings.kds_delay_warning_minutes, 20)
        self.assertEqual(settings.bar_fulfillment_target_minutes, 5)
        self.assertEqual(settings.bar_delay_warning_minutes, 10)

        self.client.force_authenticate(self.admin)
        res = self.client.get(reverse("system-settings"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["kds_prep_target_minutes"], 15)
        self.assertEqual(res.data["bar_fulfillment_target_minutes"], 5)

    def test_dining_session_settlement_rejected_with_pending_items(self):
        """
        Dining session settlement must be rejected with 400 / ValidationError
        when items are still in pending status.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        session = order.session

        # API view rejection
        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items in preparation or awaiting service", res.data["error"])

        # Service level rejection
        with self.assertRaises(ValidationError):
            settle_dining_session(session, cashier=self.cashier)

        # Direct finalize_paid_order rejection for dining order
        with self.assertRaises(ValidationError):
            finalize_paid_order(order, payment_method="Cash", cashier=self.cashier)

    def test_dining_session_settlement_rejected_with_preparing_items(self):
        """
        Dining session settlement must be rejected when kitchen items are preparing.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        session = order.session
        burger_item = order.items.first()
        burger_item.status = "preparing"
        burger_item.save(update_fields=["status"])

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items in preparation or awaiting service", res.data["error"])

    def test_dining_session_settlement_rejected_with_ready_unserved_items(self):
        """
        Dining session settlement must be rejected when items are ready but not yet served.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.cocktail.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        session = order.session
        wine_item = order.items.first()
        wine_item.status = "ready"
        wine_item.ready_at = timezone.now()
        wine_item.save(update_fields=["status", "ready_at"])

        self.client.force_authenticate(self.cashier)
        url = reverse("settle-dining-session", kwargs={"session_id": session.id})
        res = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items in preparation or awaiting service", res.data["error"])

        # Once marked served, settlement succeeds
        wine_item.status = "served"
        wine_item.served_at = timezone.now()
        wine_item.save(update_fields=["status", "served_at"])

        res_ok = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

    def test_cashier_order_process_view_safeguards(self):
        """
        CashierOrderProcessView must reject settlement for dining orders with unserved items
        both when settle_session=True and settle_session=False.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        self.client.force_authenticate(self.cashier)
        process_url = reverse("process_payment", kwargs={"order_id": order.id})

        # 1. settle_session=True fails
        res_sess = self.client.post(process_url, {"payment_method": "Cash", "settle_session": True}, format="json")
        self.assertEqual(res_sess.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. settle_session=False fails
        res_indiv = self.client.post(process_url, {"payment_method": "Cash", "settle_session": False}, format="json")
        self.assertEqual(res_indiv.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Mark item served -> both pathways succeed
        order.items.update(status="served")
        res_ok = self.client.post(process_url, {"payment_method": "Cash", "settle_session": True}, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

    def test_room_charge_process_view_dining_vs_nondining(self):
        """
        RoomChargeProcessView:
        - Dining order with unserved items returns 400.
        - Dining order with served items succeeds (200).
        - Non-dining order (session is None) allows room charge without unserved restriction.
        """
        from hotel.models import Room, Reservation

        room = Room.objects.create(name="Room 101", room_number="101", room_type="Standard", base_price=Decimal("1000.00"), status="Occupied")
        res = Reservation.objects.create(
            guest_name="Tadesse", guest_phone="0911223344", room=room, check_in_date="2026-10-25", check_out_date="2026-10-28", status="checked_in", total_amount=Decimal("3000.00")
        )

        # 1. Dining order with unserved items
        dining_order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        self.client.force_authenticate(self.waiter1)
        charge_url = reverse("order-charge-to-room", kwargs={"order_id": dining_order.id})
        res_fail = self.client.post(charge_url, {"room_number": "101"}, format="json")
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Mark dining order served -> room charge succeeds
        dining_order.items.update(status="served")
        res_ok = self.client.post(charge_url, {"room_number": "101"}, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

        # 3. Non-dining order (room service direct counter order without dining session)
        nondining_order = Order.objects.create(
            table=self.table,
            session=None,
            waiter_id_ref=self.waiter1.id,
            status="pending",
            sub_total=Decimal("200.00"),
            total_amount=Decimal("200.00"),
        )
        OrderItem.objects.create(
            order=nondining_order,
            menu_item=self.burger,
            quantity=1,
            price_at_order=Decimal("200.00"),
            status="pending",
        )
        charge_nd_url = reverse("order-charge-to-room", kwargs={"order_id": nondining_order.id})
        res_nd = self.client.post(charge_nd_url, {"room_number": "101"}, format="json")
        self.assertEqual(res_nd.status_code, status.HTTP_200_OK)

    def test_confirm_cash_handover_multi_order_session_safeguard(self):
        """
        When confirming a cash handover with settle_session=True, if other unpaid orders
        in the session have unserved items, the session settlement must be rejected.
        """
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        order2, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.cocktail.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        # Order 1 is served
        order1.items.update(status="served")
        order1.status = "served"
        order1.save(update_fields=["status"])

        # Order 2 is still cooking (preparing)
        order2.items.update(status="preparing")
        order2.status = "preparing"
        order2.save(update_fields=["status"])

        # Waiter records handover for Order 1
        self.client.force_authenticate(self.waiter1)
        self.client.post(reverse("record-cash-handover", kwargs={"order_id": order1.id}), format="json")

        # Cashier confirms handover with settle_session=True -> rejected because order2 has unserved items!
        self.client.force_authenticate(self.cashier)
        handover_url = reverse("confirm-cash-handover", kwargs={"order_id": order1.id})
        res_rej = self.client.post(handover_url, {"settle_session": True}, format="json")
        self.assertEqual(res_rej.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items in preparation", res_rej.data["error"])

        # Now mark order2 served -> confirm handover succeeds
        order2.items.update(status="served")
        order2.status = "served"
        order2.save(update_fields=["status"])
        res_ok = self.client.post(handover_url, {"settle_session": True}, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

    def test_waiter_cash_payment_safeguards(self):
        """
        WaiterCashPaymentView must reject payment for dining order with unserved items.
        """
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        self.client.force_authenticate(self.waiter1)
        url = reverse("order-cash-payment", kwargs={"order_id": order.id})
        res_fail = self.client.post(url, format="json")
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)

        order.items.update(status="served")
        res_ok = self.client.post(url, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

    def test_lifecycle_regression_protection_comprehensive(self):
        """
        recalculate_order_lifecycle must not regress orders to 'preparing' if:
        - bill_prepared_at is set
        - financials_finalized_at is set
        - confirmed cash handover exists
        """
        # 1. Order with bill_prepared_at
        order1, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        order1.items.update(status="served")
        order1.status = "served"
        order1.bill_prepared_at = timezone.now()
        order1.save(update_fields=["status", "bill_prepared_at"])

        # Add a new pending item
        OrderItem.objects.create(
            order=order1,
            menu_item=self.cocktail,
            quantity=1,
            price_at_order=Decimal("150.00"),
            status="pending",
        )
        recalculated1 = recalculate_order_lifecycle(order1.id)
        self.assertEqual(recalculated1.status, "served")  # Did not regress to preparing!

        # 2. Order with financials_finalized_at
        order2 = Order.objects.create(
            table=self.table,
            waiter_id_ref=self.waiter1.id,
            status="served",
            financials_finalized_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=order2,
            menu_item=self.burger,
            quantity=1,
            price_at_order=Decimal("200.00"),
            status="pending",
        )
        recalculated2 = recalculate_order_lifecycle(order2.id)
        self.assertEqual(recalculated2.status, "served")  # Did not regress!

    def test_all_items_cancelled_records_audit_event(self):
        """
        When all items in an order are cancelled, recalculate_order_lifecycle must:
        - Transition order.status to 'cancelled'
        - Record an audit event with action='order_cancelled'
        """
        from hotel.models import AuditEvent

        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter1,
        )
        item = order.items.first()
        item.status = "cancelled"
        item.save(update_fields=["status"])

        recalculated = recalculate_order_lifecycle(order.id)
        self.assertEqual(recalculated.status, "cancelled")

        # Verify AuditEvent
        audit_exists = AuditEvent.objects.filter(
            action="order_cancelled",
            entity_type="order",
            entity_id=str(order.id),
        ).exists()
        self.assertTrue(audit_exists, "Expected an AuditEvent for automatic order cancellation.")
