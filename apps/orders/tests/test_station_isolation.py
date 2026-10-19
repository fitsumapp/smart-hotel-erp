from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import Category, MenuItem, Order, OrderItem, RestaurantTable, Notification
from users.models import User
from apps.orders.services import create_order_idempotently


class StationIsolationAndNotesTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.waiter = User.objects.create_user(
            username="waiter-test",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.kitchen_user = User.objects.create_user(
            username="kitchen-test",
            password="test-password",
            role=User.KITCHEN,
            is_active=True,
        )
        self.bar_user = User.objects.create_user(
            username="bar-test",
            password="test-password",
            role=User.BAR,
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username="customer-test",
            password="test-password",
            role=User.CUSTOMER,
            is_active=True,
        )

        self.table = RestaurantTable.objects.create(table_code="T-101")
        self.food_cat = Category.objects.create(name="Food", station="Kitchen")
        self.drink_cat = Category.objects.create(name="Drinks", station="Bar")

        self.burger = MenuItem.objects.create(
            name="Classic Cheeseburger",
            category=self.food_cat,
            price=Decimal("250.00"),
        )
        self.cocktail = MenuItem.objects.create(
            name="Mojito Special",
            category=self.drink_cat,
            price=Decimal("180.00"),
        )

    def test_mixed_order_preparation_isolation(self):
        """
        DEFECT-ORD-001 regression scenario:
        Completing a beverage in BDS must not remove unfinished food items from KDS.
        """
        # 1. Create mixed order via idempotent service
        order, created = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1, "notes": "No onions, medium rare"},
                {"id": self.cocktail.id, "quantity": 2, "notes": "Extra lime, no straw"},
            ],
            waiter=self.waiter,
        )
        self.assertTrue(created)
        self.assertEqual(order.status, "pending")

        burger_item = order.items.get(menu_item=self.burger)
        cocktail_item = order.items.get(menu_item=self.cocktail)
        self.assertEqual(burger_item.status, "pending")
        self.assertEqual(cocktail_item.status, "pending")
        self.assertEqual(burger_item.get_station(), "Kitchen")
        self.assertEqual(cocktail_item.get_station(), "Bar")

        # 2. Both stations see the order initially
        self.client.force_authenticate(self.kitchen_user)
        k_res = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        self.assertEqual(k_res.status_code, status.HTTP_200_OK)
        k_ids = [o["id"] for o in k_res.data]
        self.assertIn(order.id, k_ids)
        k_order = next(o for o in k_res.data if o["id"] == order.id)
        self.assertEqual(len(k_order["items"]), 1)
        self.assertEqual(k_order["items"][0]["menu_item_name"], "Classic Cheeseburger")
        self.assertEqual(k_order["items"][0]["notes"], "No onions, medium rare")

        self.client.force_authenticate(self.bar_user)
        b_res = self.client.get(reverse("kitchen-orders") + "?station=Bar")
        self.assertEqual(b_res.status_code, status.HTTP_200_OK)
        b_ids = [o["id"] for o in b_res.data]
        self.assertIn(order.id, b_ids)
        b_order = next(o for o in b_res.data if o["id"] == order.id)
        self.assertEqual(len(b_order["items"]), 1)
        self.assertEqual(b_order["items"][0]["menu_item_name"], "Mojito Special")
        self.assertEqual(b_order["items"][0]["notes"], "Extra lime, no straw")

        # 3. Bar marks Cocktail preparing, then ready
        update_url = reverse("update-order-status", args=[order.id])
        prep_res = self.client.post(update_url, {"status": "preparing", "station": "Bar"}, format="json")
        self.assertEqual(prep_res.status_code, status.HTTP_200_OK)
        cocktail_item.refresh_from_db()
        self.assertEqual(cocktail_item.status, "preparing")

        ready_res = self.client.post(update_url, {"status": "ready", "station": "Bar"}, format="json")
        self.assertEqual(ready_res.status_code, status.HTTP_200_OK)
        cocktail_item.refresh_from_db()
        self.assertEqual(cocktail_item.status, "ready")

        # 4. Check order overall status and kitchen item state
        order.refresh_from_db()
        burger_item.refresh_from_db()
        self.assertEqual(order.status, "preparing")  # NOT ready, burger is still pending!
        self.assertEqual(burger_item.status, "pending")

        # No waiter notification should have fired yet
        notif_count = Notification.objects.filter(user_id_ref=self.waiter.id).count()
        self.assertEqual(notif_count, 0)

        # 5. Bar queue no longer displays order (all Bar items are ready)
        b_res2 = self.client.get(reverse("kitchen-orders") + "?station=Bar")
        b_ids2 = [o["id"] for o in b_res2.data]
        self.assertNotIn(order.id, b_ids2)

        # 6. Kitchen queue STILL DISPLAYS THE ORDER with the pending Burger!
        self.client.force_authenticate(self.kitchen_user)
        k_res2 = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        k_ids2 = [o["id"] for o in k_res2.data]
        self.assertIn(order.id, k_ids2)
        k_order2 = next(o for o in k_res2.data if o["id"] == order.id)
        self.assertEqual(len(k_order2["items"]), 1)
        self.assertEqual(k_order2["items"][0]["menu_item_name"], "Classic Cheeseburger")
        self.assertEqual(k_order2["items"][0]["status"], "pending")

        # 7. Kitchen starts cooking, then finishes
        k_prep = self.client.post(update_url, {"status": "preparing", "station": "Kitchen"}, format="json")
        self.assertEqual(k_prep.status_code, status.HTTP_200_OK)
        burger_item.refresh_from_db()
        self.assertEqual(burger_item.status, "preparing")

        k_ready = self.client.post(update_url, {"status": "ready", "station": "Kitchen"}, format="json")
        self.assertEqual(k_ready.status_code, status.HTTP_200_OK)
        burger_item.refresh_from_db()
        self.assertEqual(burger_item.status, "ready")

        # 8. All items ready -> overall order is now ready and waiter notified
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")
        self.assertTrue(Notification.objects.filter(user_id_ref=self.waiter.id).exists())

        # Kitchen queue is now empty for this order
        k_res3 = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        k_ids3 = [o["id"] for o in k_res3.data]
        self.assertNotIn(order.id, k_ids3)

    def test_kitchen_completes_first_isolation(self):
        """When Kitchen finishes first, Bar items remain pending and visible on BDS."""
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 1},
            ],
            waiter=self.waiter,
        )

        update_url = reverse("update-order-status", args=[order.id])
        self.client.force_authenticate(self.kitchen_user)
        self.client.post(update_url, {"status": "preparing", "station": "Kitchen"}, format="json")
        self.client.post(update_url, {"status": "ready", "station": "Kitchen"}, format="json")

        order.refresh_from_db()
        self.assertEqual(order.status, "preparing")  # Bar still pending

        # Kitchen queue has no more items for this order
        k_res = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        self.assertNotIn(order.id, [o["id"] for o in k_res.data])

        # Bar queue STILL shows the order
        self.client.force_authenticate(self.bar_user)
        b_res = self.client.get(reverse("kitchen-orders") + "?station=Bar")
        self.assertIn(order.id, [o["id"] for o in b_res.data])

    def test_role_based_station_security(self):
        """Kitchen cannot update Bar items; Bar cannot update Kitchen items."""
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 1},
            ],
            waiter=self.waiter,
        )
        update_url = reverse("update-order-status", args=[order.id])

        # Kitchen tries to update Bar
        self.client.force_authenticate(self.kitchen_user)
        res = self.client.post(update_url, {"status": "preparing", "station": "Bar"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Bar tries to update Kitchen
        self.client.force_authenticate(self.bar_user)
        res = self.client.post(update_url, {"status": "preparing", "station": "Kitchen"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Customer cannot update anything
        self.client.force_authenticate(self.customer)
        res = self.client.post(update_url, {"status": "preparing"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can update either station
        self.client.force_authenticate(self.admin)
        res = self.client.post(update_url, {"status": "preparing", "station": "Kitchen"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_invalid_status_transitions(self):
        """Invalid or skipped transitions are rejected with HTTP 400."""
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[{"id": self.burger.id, "quantity": 1}],
            waiter=self.waiter,
        )
        update_url = reverse("update-order-status", args=[order.id])
        self.client.force_authenticate(self.kitchen_user)

        # Skip pending -> ready directly
        res = self.client.post(update_url, {"status": "ready"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempting arbitrary status like 'paid' or 'served'
        res = self.client.post(update_url, {"status": "paid"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid transition to preparing
        res = self.client.post(update_url, {"status": "preparing"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Cannot move back to pending
        res = self.client.post(update_url, {"status": "pending"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_level_transition_by_item_id(self):
        """Updating status by item_id isolates individual items."""
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1},
                {"id": self.cocktail.id, "quantity": 1},
            ],
            waiter=self.waiter,
        )
        burger_item = order.items.get(menu_item=self.burger)
        cocktail_item = order.items.get(menu_item=self.cocktail)
        update_url = reverse("update-order-status", args=[order.id])

        # Kitchen user updates burger item specifically
        self.client.force_authenticate(self.kitchen_user)
        res = self.client.post(update_url, {"status": "preparing", "item_id": burger_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        burger_item.refresh_from_db()
        cocktail_item.refresh_from_db()
        self.assertEqual(burger_item.status, "preparing")
        self.assertEqual(cocktail_item.status, "pending")

        # Kitchen user tries to update cocktail item via item_id
        res = self.client.post(update_url, {"status": "preparing", "item_id": cocktail_item.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_item_notes_persisted_and_displayed(self):
        """DEFECT-ORD-003: Notes are saved, retrieved, bounded, and optional."""
        long_note = "A" * 300  # Exceeds 255 chars
        order, _ = create_order_idempotently(
            table_id=self.table.id,
            items=[
                {"id": self.burger.id, "quantity": 1, "notes": long_note},
                {"id": self.cocktail.id, "quantity": 1},  # No notes
            ],
            waiter=self.waiter,
        )
        burger_item = order.items.get(menu_item=self.burger)
        cocktail_item = order.items.get(menu_item=self.cocktail)

        # Bounded at 255 characters
        self.assertEqual(len(burger_item.notes), 255)
        self.assertEqual(burger_item.notes, "A" * 255)
        # Optional field defaults to empty string
        self.assertEqual(cocktail_item.notes, "")

        # Serialized correctly in API responses
        self.client.force_authenticate(self.kitchen_user)
        res = self.client.get(reverse("kitchen-orders") + "?station=Kitchen")
        k_order = next(o for o in res.data if o["id"] == order.id)
        self.assertEqual(k_order["items"][0]["notes"], "A" * 255)
