import datetime
from decimal import Decimal
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from hotel.models import (
    Room, Reservation, FolioCharge, RestaurantTable, Category, MenuItem,
    Order, OrderItem, InventoryCategory, InventoryItem, RecipeBOM,
    StockTransaction, HousekeepingTask, JournalEntry, Account
)
from hotel.integrity import transition_reservation, record_stock_change, reverse_stock_transaction


class Milestone2EndToEndWorkflowsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create staff roles
        self.reception = User.objects.create_user(
            username="test_reception", email="reacp@test.com", password="Password123!", role=User.RECEPTION, is_active=True
        )
        self.waiter = User.objects.create_user(
            username="test_waiter", email="waiter@test.com", password="Password123!", role=User.WAITER, is_active=True
        )
        self.kitchen = User.objects.create_user(
            username="test_kitchen", email="kitchen@test.com", password="Password123!", role=User.KITCHEN, is_active=True
        )
        self.cashier = User.objects.create_user(
            username="test_cashier", email="cashier@test.com", password="Password123!", role=User.CASHIER, is_active=True
        )
        self.inventory_user = User.objects.create_user(
            username="test_inventory", email="inventory@test.com", password="Password123!", role=User.INVENTORY, is_active=True
        )
        self.finance_user = User.objects.create_user(
            username="test_finance", email="finance@test.com", password="Password123!", role=User.FINANCE, is_active=True
        )

        # Base room
        self.room = Room.objects.create(
            room_number="101", room_type="Standard", base_price=Decimal("100.00"), status="Available"
        )

        # Base restaurant table and category
        self.table = RestaurantTable.objects.create(table_code="T-01", capacity=4)
        self.category = Category.objects.create(name="Hot Meals", station="Kitchen")
        self.menu_item = MenuItem.objects.create(
            name="Club Sandwich", category=self.category, price=Decimal("150.00")
        )

    def test_workflow_1_to_3_front_desk_reservation_checkin_folio_checkout(self):
        """Workflow: Walk-in Reservation -> Check-in -> Folio Charge -> Enhanced Checkout -> Auto Housekeeping"""
        self.client.force_authenticate(user=self.reception)

        today = timezone.now().date()
        tomorrow = today + datetime.timedelta(days=1)

        # 1. Walk-in Reservation
        reserve_url = f"/api/users/rooms/{self.room.id}/reserve-now/"
        payload = {
            "guest_name": "Alice Guest",
            "guest_email": "alice@example.com",
            "guest_phone": "0911000000",
            "check_in_date": today.isoformat(),
            "check_out_date": tomorrow.isoformat(),
            "adults": 1,
            "children": 0,
        }
        res = self.client.post(reserve_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        reservation_id = res.data["reservation"]["id"]

        # Check-in via front desk status action
        checkin_url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        res_in = self.client.patch(checkin_url, {
            "action": "checkin",
            "reservation_id": reservation_id,
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_in.status_code, status.HTTP_200_OK)

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Occupied")

        # 2. Add Folio Charge (Room Service)
        folio_url = f"/api/users/reservations/{reservation_id}/folio/"
        res_folio = self.client.post(folio_url, {
            "charge_type": "room_service",
            "amount": "50.00",
            "description": "Late snack",
        }, format="json")
        self.assertEqual(res_folio.status_code, status.HTTP_201_CREATED)

        # 3. Enhanced Checkout
        checkout_url = f"/api/users/reservations/{reservation_id}/enhanced-checkout/"
        res_checkout = self.client.post(checkout_url, {
            "payment_status": "paid",
            "payment_method": "Cash",
            "payment_reference": "CASH-REC-101",
        }, format="json")
        self.assertEqual(res_checkout.status_code, status.HTTP_200_OK)

        # Assert room transitioned to Cleaning
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Cleaning")

        # Assert automated housekeeping task created
        hk_task = HousekeepingTask.objects.filter(room=self.room).first()
        self.assertIsNotNone(hk_task)
        self.assertEqual(hk_task.priority, "high")
        self.assertEqual(hk_task.task_type, "checkout_cleaning")

    def test_workflow_4_to_6_waiter_order_kds_cashier_settlement(self):
        """Workflow: Waiter POS Order -> Kitchen KDS progress -> Cashier Cash Settlement"""
        # 1. Waiter Order
        self.client.force_authenticate(user=self.waiter)
        order_payload = {
            "table_id": self.table.id,
            "items": [
                {"id": self.menu_item.id, "quantity": 2, "special_notes": "Extra mayo"}
            ],
        }
        res_order = self.client.post(
            "/api/users/orders/create/",
            order_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="order-wf-456",
        )
        self.assertEqual(res_order.status_code, status.HTTP_201_CREATED)
        order_id = res_order.data["order_id"]

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.sub_total, Decimal("300.00"))
        # 300 sub_total + 15% VAT + 10% Service Charge = 375.00
        self.assertEqual(order.total_amount, Decimal("375.00"))

        # 2. Kitchen KDS
        self.client.force_authenticate(user=self.kitchen)
        res_kds1 = self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "preparing"}, format="json")
        self.assertEqual(res_kds1.status_code, status.HTTP_200_OK)

        res_kds2 = self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "ready"}, format="json")
        self.assertEqual(res_kds2.status_code, status.HTTP_200_OK)

        # Waiter marks served
        self.client.force_authenticate(user=self.waiter)
        res_served = self.client.post(f"/api/users/orders/{order_id}/mark-served/", {}, format="json")
        self.assertEqual(res_served.status_code, status.HTTP_200_OK)

        # 3. Cashier Settlement
        self.client.force_authenticate(user=self.cashier)
        res_settle = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
            "payment_reference": "POS-CASH-789",
        }, format="json")
        self.assertEqual(res_settle.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.payment_status, "paid")

    def test_workflow_7_inventory_bom_deduction_and_reversal(self):
        """Workflow: Inventory stock recording, recipe BOM auto-deduction, and non-destructive reversal"""
        # Create raw inventory ingredient
        inv_cat = InventoryCategory.objects.create(name="Provisions", category_type="f_and_b")
        ingredient = InventoryItem.objects.create(
            item_code="BEEF-01",
            name="Ground Beef",
            category=inv_cat,
            unit="kg",
            current_stock=Decimal("10.000"),
            unit_cost=Decimal("200.00"),
        )

        # Link recipe BOM: 0.25 kg beef per sandwich
        RecipeBOM.objects.create(
            menu_item=self.menu_item,
            ingredient=ingredient,
            quantity_required=Decimal("0.250"),
        )

        # Waiter orders 2 sandwiches
        self.client.force_authenticate(user=self.waiter)
        res_order = self.client.post(
            "/api/users/orders/create/",
            {
                "table_id": self.table.id,
                "items": [{"id": self.menu_item.id, "quantity": 2}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="bom-order-test-1",
        )
        self.assertEqual(res_order.status_code, status.HTTP_201_CREATED)
        order_id = res_order.data["order_id"]

        # Cashier finalizes order
        self.client.force_authenticate(user=self.cashier)
        res_finalize = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_finalize.status_code, status.HTTP_200_OK)

        # Verify stock auto-deducted: 10.000 - (2 * 0.250) = 9.500
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.current_stock, Decimal("9.500"))

        # Reversal test via authorized stock service
        tx = StockTransaction.objects.filter(item=ingredient, transaction_type="sale_deduction").first()
        self.assertIsNotNone(tx)

        reversal_tx, created = reverse_stock_transaction(
            transaction_id=tx.id,
            reason="Order cancellation refund",
            logged_by_username=self.inventory_user.username,
        )
        self.assertTrue(created)
        ingredient.refresh_from_db()
        # Balance restored to 10.000
        self.assertEqual(ingredient.current_stock, Decimal("10.000"))

    def test_workflow_8_general_ledger_and_remediated_endpoints_integrity(self):
        """Workflow: Financial GL balance invariant & verification of remediated endpoints (ERP-001, 002, 004)"""
        # Ensure double entry balance invariant across all posted journals
        entries = JournalEntry.objects.all()
        for entry in entries:
            self.assertEqual(entry.total_debit, entry.total_credit, f"Unbalanced entry: {entry.entry_number}")

        # ERP-002: Inventory Report Route
        self.client.force_authenticate(user=self.inventory_user)
        res_inv = self.client.get("/api/users/inventory-items/")
        self.assertEqual(res_inv.status_code, status.HTTP_200_OK)

        # ERP-001: Public Site Endpoint
        with override_settings(FRONTEND_BASE_URL="http://localhost:3000"):
            res_pub = self.client.get("/api/users/public-site/")
            self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
            self.assertEqual(res_pub.data, {"public_site_url": "http://localhost:3000"})

        # ERP-004: Dual Admin Routing
        res_admin1 = self.client.get("/admin/")
        self.assertIn(res_admin1.status_code, [200, 302])

        res_admin2 = self.client.get("/api/admin/")
        self.assertIn(res_admin2.status_code, [200, 302])
