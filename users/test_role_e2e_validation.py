"""
users/test_role_e2e_validation.py
Comprehensive End-to-End Role-Based Validation and Edge-Case Test Suite.
Verifies all configured hotel roles, permissions, allowed & prohibited actions,
cross-module data consistency, financial invariants, and failure handling.
"""
import datetime
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from hotel.models import (
    Room, Reservation, FolioCharge, HousekeepingTask,
    RestaurantTable, Category, MenuItem,
    InventoryCategory, InventoryItem, RecipeBOM, StockTransaction,
    Order, OrderItem, Account, JournalEntry, JournalEntryItem, SystemSettings
)
from apps.finance.services import ensure_default_accounts
from apps.orders.services import sync_order_financials
from hotel.accounting import post_entry


class RoleBasedEndToEndValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. System Settings
        self.settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
        self.settings_obj.vat_enabled = True
        self.settings_obj.vat_percentage = Decimal("15.00")
        self.settings_obj.service_charge_enabled = True
        self.settings_obj.service_charge_percentage = Decimal("10.00")
        self.settings_obj.save()

        # 2. General Ledger Accounts
        ensure_default_accounts()

        # 3. Staff Accounts for All Configured Roles
        self.admin_user = User.objects.create_superuser(
            username="test_admin", email="admin@test.local", password="Password123!",
            role=User.ADMIN, is_active=True
        )
        self.reception_user = User.objects.create_user(
            username="test_reception", email="reception@test.local", password="Password123!",
            role=User.RECEPTION, is_active=True
        )
        self.waiter_user = User.objects.create_user(
            username="test_waiter", email="waiter@test.local", password="Password123!",
            role=User.WAITER, is_active=True
        )
        self.cashier_user = User.objects.create_user(
            username="test_cashier", email="cashier@test.local", password="Password123!",
            role=User.CASHIER, is_active=True
        )
        self.kitchen_user = User.objects.create_user(
            username="test_kitchen", email="kitchen@test.local", password="Password123!",
            role=User.KITCHEN, is_active=True
        )
        self.bar_user = User.objects.create_user(
            username="test_bar", email="bar@test.local", password="Password123!",
            role=User.BAR, is_active=True
        )
        self.inventory_user = User.objects.create_user(
            username="test_inventory", email="inventory@test.local", password="Password123!",
            role=User.INVENTORY, is_active=True
        )
        self.finance_user = User.objects.create_user(
            username="test_finance", email="finance@test.local", password="Password123!",
            role=User.FINANCE, is_active=True
        )
        self.customer_user = User.objects.create_user(
            username="test_customer", email="customer@test.local", password="Password123!",
            role=User.CUSTOMER, is_active=True
        )
        self.delivery_user = User.objects.create_user(
            username="test_delivery", email="delivery@test.local", password="Password123!",
            role=User.DELIVERY, is_active=True
        )

        # 4. Rooms across statuses
        self.room_101 = Room.objects.create(
            room_number="101", name="Deluxe 101", room_type="Deluxe",
            floor_number=1, base_price=Decimal("3000.00"), status="Available",
            max_adults=2, max_children=1
        )
        self.room_102 = Room.objects.create(
            room_number="102", name="Suite 102", room_type="Suite",
            floor_number=1, base_price=Decimal("5000.00"), status="Occupied",
            max_adults=3, max_children=2
        )
        self.room_103 = Room.objects.create(
            room_number="103", name="Twin 103", room_type="Standard",
            floor_number=1, base_price=Decimal("2000.00"), status="dirty",
            max_adults=2, max_children=1
        )

        # 5. Restaurant Tables, Menus & BOM
        self.table_t1 = RestaurantTable.objects.create(table_code="T1", label_name="Table 1", capacity=4, status="available")
        self.table_t2 = RestaurantTable.objects.create(table_code="T2", label_name="Table 2", capacity=2, status="available")

        self.cat_kitchen = Category.objects.create(name="Hot Kitchen", station="Kitchen")
        self.cat_bar = Category.objects.create(name="Bar", station="Bar")

        self.burger = MenuItem.objects.create(name="Steak Burger", price=Decimal("400.00"), category=self.cat_kitchen, is_available=True)
        self.cocktail = MenuItem.objects.create(name="Mojito Mocktail", price=Decimal("150.00"), category=self.cat_bar, is_available=True)

        # 6. Inventory & Recipe
        self.inv_cat = InventoryCategory.objects.create(name="Provisions", category_type="f_and_b")
        self.meat_item = InventoryItem.objects.create(
            item_code="BEEF-STEAK", name="Raw Beef Patty", category=self.inv_cat,
            unit="kg", current_stock=Decimal("20.000"), opening_stock=Decimal("20.000"),
            unit_cost=Decimal("250.00"), min_reorder_level=Decimal("5.000")
        )
        RecipeBOM.objects.create(menu_item=self.burger, ingredient=self.meat_item, quantity_required=Decimal("0.200"))

        # 7. Initial Balanced Opening Ledger
        post_entry(
            description="Initial Capital Test",
            lines=[
                {"account_code": "1000", "debit": Decimal("50000.00"), "credit": Decimal("0.00")},
                {"account_code": "3000", "debit": Decimal("0.00"), "credit": Decimal("50000.00")},
            ]
        )

    # ─────────────────────────────────────────────────────────────────────────────
    # A. FRONT DESK ROLE WORKFLOW & RBAC
    # ─────────────────────────────────────────────────────────────────────────────
    def test_front_desk_lifecycle_and_rbac(self):
        """Front desk: Reservation -> Check-in -> Folio Charge -> Enhanced Checkout -> Auto Housekeeping"""
        self.client.force_authenticate(user=self.reception_user)

        # 1. Create walk-in reservation
        today = timezone.now().date()
        tomorrow = today + datetime.timedelta(days=2)
        res = self.client.post(f"/api/users/rooms/{self.room_101.id}/reserve-now/", {
            "guest_name": "VIP Walk-In Guest",
            "guest_email": "vip.guest@example.com",
            "guest_phone": "+251911998877",
            "check_in_date": today.isoformat(),
            "check_out_date": tomorrow.isoformat(),
            "adults": 2,
            "children": 0,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        reservation_id = res.data["reservation"]["id"]

        # 2. Check in guest
        res_ci = self.client.patch(f"/api/users/rooms/{self.room_101.id}/front-desk-status/", {
            "action": "checkin",
            "reservation_id": reservation_id,
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_ci.status_code, status.HTTP_200_OK)

        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, "Occupied")

        # 3. Add Folio Charge (e.g. VIP Airport Limousine)
        res_folio = self.client.post(f"/api/users/reservations/{reservation_id}/folio/", {
            "description": "Airport Limousine Transfer",
            "amount": "750.00",
        }, format="json")
        self.assertEqual(res_folio.status_code, status.HTTP_201_CREATED)

        # 4. Enhanced Checkout
        res_co = self.client.post(f"/api/users/reservations/{reservation_id}/enhanced-checkout/", {
            "payment_method": "Cash",
            "payment_reference": "FD-CASH-REC-101",
        }, format="json")
        self.assertEqual(res_co.status_code, status.HTTP_200_OK)

        self.room_101.refresh_from_db()
        # Room must be marked dirty
        self.assertIn(self.room_101.status.lower(), ["dirty", "cleaning"])

        # Auto Housekeeping Task generated
        hk_task = HousekeepingTask.objects.filter(room=self.room_101, task_type="checkout_cleaning").first()
        self.assertIsNotNone(hk_task)
        self.assertEqual(hk_task.priority, "high")

        # 5. Prohibited Action: Reception cannot access General Ledger Accounts
        res_prohibited = self.client.get("/api/users/finance/accounts/")
        self.assertEqual(res_prohibited.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────────
    # B. HOUSEKEEPING ROLE WORKFLOW
    # ─────────────────────────────────────────────────────────────────────────────
    def test_housekeeping_task_lifecycle_to_available(self):
        """Housekeeping: Retrieve task -> in_progress -> cleaned -> inspected -> room available"""
        task = HousekeepingTask.objects.create(
            room=self.room_103,
            task_type="checkout_cleaning",
            priority="high",
            status="pending",
        )
        self.assertEqual(self.room_103.status, "dirty")

        self.client.force_authenticate(user=self.reception_user)

        # 1. Update task to in_progress
        res_prog = self.client.patch(f"/api/users/housekeeping/tasks/{task.id}/", {
            "status": "in_progress"
        }, format="json")
        self.assertEqual(res_prog.status_code, status.HTTP_200_OK)

        # 2. Update task to cleaned
        res_clean = self.client.patch(f"/api/users/housekeeping/tasks/{task.id}/", {
            "status": "cleaned"
        }, format="json")
        self.assertEqual(res_clean.status_code, status.HTTP_200_OK)

        # 3. Supervised Inspection
        res_insp = self.client.post(f"/api/users/housekeeping/tasks/{task.id}/inspect/", {
            "approved": True,
            "notes": "Linen pristine, room sanitized and inspection passed."
        }, format="json")
        self.assertEqual(res_insp.status_code, status.HTTP_200_OK)

        # Room becomes Available!
        self.room_103.refresh_from_db()
        self.assertEqual(self.room_103.status, "Available")

    # ─────────────────────────────────────────────────────────────────────────────
    # C. WAITER, KITCHEN & CASHIER F&B WORKFLOW & RBAC
    # ─────────────────────────────────────────────────────────────────────────────
    def test_fnb_order_kitchen_cashier_pipeline_and_rbac(self):
        """Waiter orders -> Kitchen KDS prepares -> Waiter serves -> Cashier settles"""
        # 1. Waiter creates POS Order
        self.client.force_authenticate(user=self.waiter_user)
        res_order = self.client.post("/api/users/orders/create/", {
            "table_id": self.table_t1.id,
            "items": [{"id": self.burger.id, "quantity": 2}],
        }, format="json", HTTP_IDEMPOTENCY_KEY="fnb-test-key-01")
        self.assertEqual(res_order.status_code, status.HTTP_201_CREATED)
        order_id = res_order.data["order_id"]

        order = Order.objects.get(id=order_id)
        # Subtotal: 800, SC 10%: 80, VAT 15%: 120 -> Total: 1000.00
        self.assertEqual(order.sub_total, Decimal("800.00"))
        self.assertEqual(order.total_amount, Decimal("1000.00"))

        # Waiter prohibited from processing cashier payment
        res_waiter_forbidden = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_waiter_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Kitchen KDS progresses order
        self.client.force_authenticate(user=self.kitchen_user)
        res_prep = self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "preparing"}, format="json")
        self.assertEqual(res_prep.status_code, status.HTTP_200_OK)

        res_ready = self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "ready"}, format="json")
        self.assertEqual(res_ready.status_code, status.HTTP_200_OK)

        # Kitchen prohibited from accessing Front Desk reservations
        res_kitchen_forbidden = self.client.get("/api/users/reservations/")
        self.assertEqual(res_kitchen_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Waiter marks served
        self.client.force_authenticate(user=self.waiter_user)
        res_served = self.client.post(f"/api/users/orders/{order_id}/mark-served/", {}, format="json")
        self.assertEqual(res_served.status_code, status.HTTP_200_OK)

        # 4. Cashier settles order with Cash
        self.client.force_authenticate(user=self.cashier_user)
        res_settle = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
            "payment_reference": "POS-CASH-V99",
        }, format="json")
        self.assertEqual(res_settle.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.payment_status, "paid")

        # 5. Inventory Recipe BOM Auto-Deduction Check: 20.000 - (2 * 0.200) = 19.600 kg
        self.meat_item.refresh_from_db()
        self.assertEqual(self.meat_item.current_stock, Decimal("19.600"))

        # Cashier receipt retrieval
        res_receipt = self.client.get(f"/api/users/cashier/receipt/{order_id}/")
        self.assertEqual(res_receipt.status_code, status.HTTP_200_OK)
        self.assertEqual(res_receipt.data["grand_total"], 1000.0)

    # ─────────────────────────────────────────────────────────────────────────────
    # D. INVENTORY ROLE WORKFLOW & RBAC
    # ─────────────────────────────────────────────────────────────────────────────
    def test_inventory_role_stock_transaction_and_rbac(self):
        """Inventory manager records stock batch purchase and audit trail"""
        self.client.force_authenticate(user=self.inventory_user)

        # Record stock purchase of 10 kg beef
        res_stock = self.client.post("/api/users/stock-transactions/", {
            "item": self.meat_item.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "250.00",
            "reference_number": "PO-TEST-BATCH-77",
            "destination_dept": "Kitchen",
            "notes": "Verified fresh batch delivery",
        }, format="json")
        self.assertEqual(res_stock.status_code, status.HTTP_201_CREATED)

        self.meat_item.refresh_from_db()
        # 20.000 + 10.000 = 30.000 kg
        self.assertEqual(self.meat_item.current_stock, Decimal("30.000"))

        # Inventory prohibited from creating reservations or booking rooms
        res_inv_forbidden = self.client.post(f"/api/users/rooms/{self.room_101.id}/reserve-now/", {
            "guest_name": "Unauthorized Booking Attempt",
        }, format="json")
        self.assertEqual(res_inv_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────────
    # E. FINANCE ROLE WORKFLOW & GENERAL LEDGER INVARIANT
    # ─────────────────────────────────────────────────────────────────────────────
    def test_finance_role_reports_and_general_ledger_balance(self):
        """Finance accesses chart of accounts, statements, and asserts double-entry GL balance"""
        self.client.force_authenticate(user=self.finance_user)

        res_accounts = self.client.get("/api/users/finance/accounts/")
        self.assertEqual(res_accounts.status_code, status.HTTP_200_OK)

        res_statements = self.client.get("/api/users/finance/statements/")
        self.assertEqual(res_statements.status_code, status.HTTP_200_OK)

        res_tax = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_tax.status_code, status.HTTP_200_OK)

        # Enforce mathematical double-entry balance invariant across all posted journal entries
        for entry in JournalEntry.objects.prefetch_related("items").all():
            debits = sum(i.amount_debit for i in entry.items.all())
            credits = sum(i.amount_credit for i in entry.items.all())
            self.assertEqual(
                debits, credits,
                f"Double-entry ledger out of balance for journal #{entry.id} ({entry.entry_number})"
            )

        # Finance prohibited from modifying kitchen orders
        res_fin_forbidden = self.client.post("/api/users/orders/create/", {
            "table_id": self.table_t1.id,
            "items": [{"id": self.burger.id, "quantity": 1}],
        }, format="json")
        self.assertEqual(res_fin_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    # ─────────────────────────────────────────────────────────────────────────────
    # F. ADMINISTRATOR & SECURITY GUARDS
    # ─────────────────────────────────────────────────────────────────────────────
    def test_administrator_access_and_unauthenticated_guards(self):
        """Administrator has access across system settings & user registry; unauthenticated calls rejected"""
        # Admin authentication
        self.client.force_authenticate(user=self.admin_user)

        res_users = self.client.get("/api/users/users/")
        self.assertEqual(res_users.status_code, status.HTTP_200_OK)

        res_settings = self.client.get("/api/users/settings/")
        self.assertEqual(res_settings.status_code, status.HTTP_200_OK)

        # Unauthenticated request to protected endpoints must return 401 Unauthorized
        client_anon = APIClient()
        res_anon = client_anon.get("/api/users/dashboard-stats/")
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

    # ─────────────────────────────────────────────────────────────────────────────
    # G. FAILURE MODES & EDGE CASES
    # ─────────────────────────────────────────────────────────────────────────────
    def test_failure_modes_and_edge_cases(self):
        """Idempotency re-submission, double payment prevention, and invalid state transitions"""
        self.client.force_authenticate(user=self.waiter_user)

        # 1. Missing required fields in order creation
        res_missing = self.client.post("/api/users/orders/create/", {
            "table_id": self.table_t2.id,
            # items missing
        }, format="json")
        self.assertEqual(res_missing.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Idempotency Key replay returns identical cached order
        idempotency_key = "idemp-edge-case-001"
        res_order1 = self.client.post("/api/users/orders/create/", {
            "table_id": self.table_t2.id,
            "items": [{"id": self.burger.id, "quantity": 1}],
        }, format="json", HTTP_IDEMPOTENCY_KEY=idempotency_key)
        self.assertEqual(res_order1.status_code, status.HTTP_201_CREATED)
        order_id = res_order1.data["order_id"]

        # Resubmit with identical key returns cached 200 OK
        res_order2 = self.client.post("/api/users/orders/create/", {
            "table_id": self.table_t2.id,
            "items": [{"id": self.burger.id, "quantity": 1}],
        }, format="json", HTTP_IDEMPOTENCY_KEY=idempotency_key)
        self.assertEqual(res_order2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_order2.data["order_id"], order_id)

        # 3. Invalid order transition (e.g. attempting to skip straight to invalid status)
        self.client.force_authenticate(user=self.kitchen_user)
        res_invalid_trans = self.client.post(f"/api/users/orders/{order_id}/update-status/", {
            "status": "archived"  # unsupported status
        }, format="json")
        self.assertEqual(res_invalid_trans.status_code, status.HTTP_400_BAD_REQUEST)

        # Progress to paid
        self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "preparing"}, format="json")
        self.client.post(f"/api/users/orders/{order_id}/update-status/", {"status": "ready"}, format="json")
        self.client.force_authenticate(user=self.waiter_user)
        self.client.post(f"/api/users/orders/{order_id}/mark-served/", {}, format="json")

        self.client.force_authenticate(user=self.cashier_user)
        res_settle1 = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_settle1.status_code, status.HTTP_200_OK)

        # 4. Double payment attempt on already paid order
        res_settle2 = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Cash",
        }, format="json")
        self.assertEqual(res_settle2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already marked as paid", res_settle2.data.get("error", ""))

        # 5. Room Charge attempt for a room without active checked-in guest
        res_rc_unoccupied = self.client.post(f"/api/users/cashier/process/{order_id}/", {
            "payment_method": "Room Charge",
            "room_number": "103", # Room 103 has no active checked in guest
        }, format="json")
        self.assertEqual(res_rc_unoccupied.status_code, status.HTTP_400_BAD_REQUEST)
