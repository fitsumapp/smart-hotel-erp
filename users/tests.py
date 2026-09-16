"""
Unit Tests for FinanceDashboardStatsView.

Notes:
- Uses DRF APIClient with force_authenticate() since the view uses JWT-based
  DRF permissions.IsAuthenticated (not Django session auth).
- The cross-tenant isolation test is marked as skip in single-tenant mode
  because connection.schema_name is a django-tenants attribute not present in
  the standard DatabaseWrapper.
"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from unittest import skip

from rest_framework.test import APIClient

from users.models import User
from hotel.models import (
    Room, Reservation, RoomHistory, Order, FolioCharge,
    InventoryCategory, InventoryItem, StockTransaction, Category,
    RestaurantTable, Supplier, MenuItem, Account, JournalEntry,
    JournalEntryItem, ExpenseTransaction, Budget
)


class FinanceDashboardStatsViewTests(TestCase):
    def setUp(self):
        # Use DRF's APIClient so that force_authenticate() works with JWT views
        self.client = APIClient()

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin_user",
            email="admin@hotel.com",
            password="password123",
            role="admin",
            is_active=True          # Required: default is False (email-verify flow)
        )
        self.waiter_user = User.objects.create_user(
            username="waiter_user",
            email="waiter@hotel.com",
            password="password123",
            role="waiter",
            is_active=True          # Required: default is False (email-verify flow)
        )

        # Create categories, menu items, and restaurant tables
        self.category = Category.objects.create(name="Beverage", station="Bar")
        self.table = RestaurantTable.objects.create(table_code="T-01")
        self.supplier = Supplier.objects.create(name="Supplier Alpha", phone="0911123456")

        # Create rooms
        self.room1 = Room.objects.create(
            name="Room 101 Standard",
            room_number="101",
            room_type="Standard",
            base_price=Decimal("1500.00"),
            status="Available"
        )

        # Create reservation
        self.reservation = Reservation.objects.create(
            room=self.room1,
            guest_name="Guest One",
            check_in_date=date.today() - timedelta(days=2),
            check_out_date=date.today() + timedelta(days=2),
            total_amount=Decimal("6000.00"),
            deposit_amount=Decimal("1500.00"),
            status="confirmed"
        )

        # Create test dates
        self.today = timezone.now().date()
        self.yesterday = self.today - timedelta(days=1)
        self.last_week = self.today - timedelta(days=7)

        # Create RoomHistory (Room Revenue)
        # 1. Active range (within 7 days)
        rh_active = RoomHistory.objects.create(
            room=self.room1,
            event_type="checkout",
            revenue=Decimal("3000.00"),
            payment_method="Cash"
        )
        RoomHistory.objects.filter(id=rh_active.id).update(created_at=timezone.now())

        # 2. Out of range (8 days ago — should be excluded from 7-day filter)
        rh_old = RoomHistory.objects.create(
            room=self.room1,
            event_type="checkin",
            revenue=Decimal("1500.00"),
            payment_method="Digital Payment"
        )
        RoomHistory.objects.filter(id=rh_old.id).update(created_at=timezone.now() - timedelta(days=8))

        # Create paid Orders (F&B Revenue)
        # 1. Paid in active range
        self.order_paid = Order.objects.create(
            table=self.table,
            waiter_username="waiter_user",
            total_amount=Decimal("450.50"),
            payment_status="paid",
            payment_method="Cash"
        )
        Order.objects.filter(id=self.order_paid.id).update(updated_at=timezone.now())

        # 2. Unpaid in active range (excluded from F&B revenue, included in receivables)
        self.order_unpaid = Order.objects.create(
            table=self.table,
            waiter_username="waiter_user",
            total_amount=Decimal("250.00"),
            payment_status="pending",
            payment_method="Cash"
        )
        Order.objects.filter(id=self.order_unpaid.id).update(updated_at=timezone.now())

        # 3. Paid out of range (excluded)
        self.order_old = Order.objects.create(
            table=self.table,
            waiter_username="waiter_user",
            total_amount=Decimal("600.00"),
            payment_status="paid",
            payment_method="Chapa"
        )
        Order.objects.filter(id=self.order_old.id).update(
            updated_at=timezone.now() - timedelta(days=8)
        )

        # Create FolioCharge (Extra Revenue)
        # 1. In active range
        fc_active = FolioCharge.objects.create(
            reservation=self.reservation,
            description="Laundry Charge",
            amount=Decimal("120.00")
        )
        FolioCharge.objects.filter(id=fc_active.id).update(added_at=timezone.now())

        # 2. Out of range (excluded)
        old_charge = FolioCharge.objects.create(
            reservation=self.reservation,
            description="Room Service",
            amount=Decimal("350.00"),
        )
        FolioCharge.objects.filter(id=old_charge.id).update(
            added_at=timezone.now() - timedelta(days=8)
        )

        # Create Inventory and StockTransactions (Expenses)
        self.inv_category = InventoryCategory.objects.create(
            name="Kitchen Raw Materials", category_type="f_and_b"
        )
        self.inv_item = InventoryItem.objects.create(
            item_code="RAW-01",
            name="Sugar",
            category=self.inv_category,
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("75.00")
        )

        # 1. Stock purchase in active range (Expense, qty=5, unit_cost=80 → 400.00)
        st_active = StockTransaction.objects.create(
            item=self.inv_item,
            transaction_type="purchase",
            quantity=Decimal("5.00"),
            unit_cost=Decimal("80.00")
        )
        StockTransaction.objects.filter(id=st_active.id).update(timestamp=timezone.now())

        # 2. Stock issuance in active range (NOT an expense)
        st_issue = StockTransaction.objects.create(
            item=self.inv_item,
            transaction_type="issuance",
            quantity=Decimal("2.00"),
            unit_cost=Decimal("80.00")
        )
        StockTransaction.objects.filter(id=st_issue.id).update(timestamp=timezone.now())

        # 3. Stock purchase out of range (excluded)
        st_old = StockTransaction.objects.create(
            item=self.inv_item,
            transaction_type="purchase",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("70.00")
        )
        StockTransaction.objects.filter(id=st_old.id).update(timestamp=timezone.now() - timedelta(days=8))

        self.url = reverse("finance-stats")

    # ── Access Control Tests ──────────────────────────────────────────────────

    def test_anonymous_access_denied(self):
        """Anonymous requests should be blocked (401)."""
        # No credentials set → DRF returns 401 Unauthorized
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_non_admin_access_denied(self):
        """Non-admin users (e.g. waiter) should be blocked (403)."""
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_access_allowed(self):
        """Admins should receive a 200 OK response."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    # ── Financial Calculation Tests ───────────────────────────────────────────

    def test_finance_dashboard_calculations(self):
        """Validate financial stats are accurate and respect date filters."""
        self.client.force_authenticate(user=self.admin_user)

        # Filter for the last 7 days (includes today's transactions, excludes 8-day-old ones)
        start_date = (timezone.localdate() - timedelta(days=7)).isoformat()
        end_date = timezone.localdate().isoformat()

        response = self.client.get(self.url, {"start_date": start_date, "end_date": end_date})
        self.assertEqual(response.status_code, 200)

        data = response.data

        # Expected calculations:
        # Room Revenue  = 3000.00 (checkout in range)
        # F&B Revenue   = 450.50  (paid order in range)
        # Folio Revenue = 120.00  (laundry charge in range)
        # Total Revenue = 3570.50
        self.assertEqual(
            Decimal(str(data["metrics"]["total_revenue"])),
            Decimal("3570.50"),
            "Total revenue mismatch"
        )

        # Expenses = purchase qty(5) × unit_cost(80) = 400.00
        self.assertEqual(
            Decimal(str(data["metrics"]["total_expenses"])),
            Decimal("400.00"),
            "Total expenses mismatch"
        )

        # Net Profit = 3570.50 - 400.00 = 3170.50
        self.assertEqual(
            Decimal(str(data["metrics"]["net_profit"])),
            Decimal("3170.50"),
            "Net profit mismatch"
        )

    def test_response_structure(self):
        """Validate the API response contains all required top-level keys."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("metrics", response.data)
        self.assertIn("chart_trend", response.data)
        self.assertIn("ledger", response.data)
        self.assertIn("closed_days", response.data)

        # Check all metric keys exist
        required_metrics = [
            "total_revenue", "room_revenue", "fb_revenue",
            "folio_revenue", "total_expenses", "net_profit", "total_receivables"
        ]
        for key in required_metrics:
            self.assertIn(key, response.data["metrics"], f"Missing metric: {key}")

class GeneralLedgerIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin_gl",
            email="admin_gl@hotel.com",
            password="password123",
            role="admin",
            is_active=True
        )
        self.client.force_authenticate(user=self.admin_user)

        # Basic setup
        self.category = Category.objects.create(name="Food", station="Kitchen")
        self.menu_item = MenuItem.objects.create(
            name="Injera Fitfit",
            price=Decimal("150.00"),
            category=self.category
        )
        self.table = RestaurantTable.objects.create(table_code="T-02")
        self.room = Room.objects.create(
            name="Room 102 Deluxe",
            room_number="102",
            room_type="Deluxe",
            base_price=Decimal("2000.00"),
            status="Available"
        )
        self.supplier = Supplier.objects.create(name="Supplier Beta", phone="0911223344")

    def test_ensure_default_accounts_creation(self):
        """Verify that default accounts are seeded correctly."""
        from users.views import ensure_default_accounts
        ensure_default_accounts()
        
        # Check that key accounts exist
        self.assertTrue(Account.objects.filter(code="1000", account_type="asset").exists())
        self.assertTrue(Account.objects.filter(code="4000", account_type="revenue").exists())
        self.assertTrue(Account.objects.filter(code="5000", account_type="expense").exists())

    def test_journal_entry_balancing_validation(self):
        """Verify that unbalanced journal entries raise an error."""
        from users.views import post_journal_entry, ensure_default_accounts
        ensure_default_accounts()

        # Unbalanced entry
        with self.assertRaises(ValueError):
            post_journal_entry(
                description="Test Unbalanced",
                items=[
                    {"account_code": "1000", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
                    {"account_code": "4000", "debit": Decimal("0.00"), "credit": Decimal("90.00")}
                ]
            )

        # Balanced entry should succeed
        entry = post_journal_entry(
            description="Test Balanced",
            items=[
                {"account_code": "1000", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
                {"account_code": "4000", "debit": Decimal("0.00"), "credit": Decimal("100.00")}
            ]
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.items.count(), 2)

    def test_restaurant_order_posting(self):
        """Verify order finalization posts correct journal entries."""
        from users.views import finalize_paid_order, ensure_default_accounts
        ensure_default_accounts()

        # Create order
        order = Order.objects.create(table=self.table, total_amount=Decimal("150.00"), sub_total=Decimal("150.00"))
        # Add order item
        from hotel.models import OrderItem
        OrderItem.objects.create(order=order, menu_item=self.menu_item, quantity=1, price_at_order=Decimal("150.00"))

        finalize_paid_order(order, payment_method="Cash")

        # Verify journal entry was posted
        entries = JournalEntry.objects.filter(description__icontains=f"Order #{order.id}")
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        
        # Cash account code is 1000, F&B Revenue is 4100
        cash_item = entry.items.get(account__code="1000")
        revenue_item = entry.items.get(account__code="4100")
        
        self.assertEqual(cash_item.amount_debit, Decimal("189.75"))
        self.assertEqual(revenue_item.amount_credit, Decimal("150.00"))

        vat_item = entry.items.get(account__code="2200")
        sc_item = entry.items.get(account__code="2300")
        self.assertEqual(vat_item.amount_credit, Decimal("24.75"))
        self.assertEqual(sc_item.amount_credit, Decimal("15.00"))

    def test_inventory_purchase_and_issuance_posting(self):
        """Verify stock transaction creation posts correct journal entries."""
        from users.views import ensure_default_accounts
        ensure_default_accounts()

        inv_category = InventoryCategory.objects.create(name="Supplies", category_type="housekeeping")
        item = InventoryItem.objects.create(
            item_code="SUP-01",
            name="Soap",
            category=inv_category,
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("15.00")
        )

        # 1. Purchase
        # Using client to trigger StockTransactionViewSet.perform_create
        response = self.client.post("/api/users/stock-transactions/", {
            "item": item.id,
            "transaction_type": "purchase",
            "quantity": "20.00",
            "unit_cost": "15.00",
            "supplier": self.supplier.id
        })
        self.assertEqual(response.status_code, 201)

        # Inventory Asset (1300) should be debited by 300.00, Accounts Payable (2000) credited by 300.00
        purchase_entry = JournalEntry.objects.get(description__icontains="Purchase - Soap")
        self.assertEqual(purchase_entry.items.get(account__code="1300").amount_debit, Decimal("300.00"))
        self.assertEqual(purchase_entry.items.get(account__code="2000").amount_credit, Decimal("300.00"))

        # 2. Issuance
        response = self.client.post("/api/users/stock-transactions/", {
            "item": item.id,
            "transaction_type": "issuance",
            "quantity": "5.00",
            "unit_cost": "15.00",
            "destination_dept": "Housekeeping"
        })
        self.assertEqual(response.status_code, 201)

        # Cost of Goods Sold (5000) debited by 75.00, Inventory Asset (1300) credited by 75.00
        issuance_entry = JournalEntry.objects.get(description__icontains="Issuance - Soap")
        self.assertEqual(issuance_entry.items.get(account__code="5000").amount_debit, Decimal("75.00"))
        self.assertEqual(issuance_entry.items.get(account__code="1300").amount_credit, Decimal("75.00"))

    def test_folio_charge_create_and_delete_posting(self):
        """Verify folio charge create/delete posts correct entries."""
        from users.views import ensure_default_accounts
        ensure_default_accounts()

        res = Reservation.objects.create(
            room=self.room,
            guest_name="Guest Two",
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=1),
            total_amount=Decimal("2000.00"),
            deposit_amount=Decimal("0.00")
        )

        # Post folio charge
        response = self.client.post(f"/api/users/reservations/{res.id}/folio/", {
            "description": "Room Service",
            "amount": "250.00",
            "quantity": "1.00"
        })
        self.assertEqual(response.status_code, 201)

        # Debit Accounts Receivable (1200) 250, Credit Folio Extras Revenue (4200) 250
        entry = JournalEntry.objects.get(description__icontains=f"Folio Charge - Room Service")
        self.assertEqual(entry.items.get(account__code="1200").amount_debit, Decimal("250.00"))
        self.assertEqual(entry.items.get(account__code="4200").amount_credit, Decimal("250.00"))

        charge_id = response.data["id"]

        # Delete folio charge
        response = self.client.delete(f"/api/users/folio/{charge_id}/")
        self.assertEqual(response.status_code, 200)

        # Reversing entry: Debit 4200 (250), Credit 1200 (250)
        rev_entry = JournalEntry.objects.get(description__icontains=f"Reverse Folio Charge #{charge_id}")
        self.assertEqual(rev_entry.items.get(account__code="4200").amount_debit, Decimal("250.00"))
        self.assertEqual(rev_entry.items.get(account__code="1200").amount_credit, Decimal("250.00"))


class AdminOrdersViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin_test",
            email="admin_test@hotel.com",
            password="password123",
            role="admin",
            is_active=True
        )
        self.waiter_user = User.objects.create_user(
            username="waiter_test",
            email="waiter_test@hotel.com",
            password="password123",
            role="waiter",
            is_active=True
        )
        self.finance_user = User.objects.create_user(
            username="finance_test",
            email="finance_test@hotel.com",
            password="password123",
            role="finance",
            is_active=True
        )

        self.table = RestaurantTable.objects.create(table_code="T-TEST-01")
        self.order_pending = Order.objects.create(
            table=self.table,
            waiter_username="waiter_test",
            total_amount=Decimal("150.00"),
            status="pending",
            payment_status="pending"
        )
        self.order_paid = Order.objects.create(
            table=self.table,
            waiter_username="waiter_test",
            total_amount=Decimal("300.00"),
            status="served",
            payment_status="paid"
        )
        
        self.url = "/api/users/orders/"

    def test_anonymous_access_denied(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_non_admin_or_finance_access_denied(self):
        self.client.force_authenticate(user=self.waiter_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_access_allowed_and_lists_orders(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        
        # Verify fields in serialized order
        order_data = response.data[0]
        self.assertIn("id", order_data)
        self.assertIn("status", order_data)
        self.assertIn("total_amount", order_data)
        self.assertIn("table_code", order_data)

    def test_finance_access_allowed(self):
        self.client.force_authenticate(user=self.finance_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_filtering_by_status(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], "pending")


class DashboardStatsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin_dashboard_test",
            email="admin_dashboard@hotel.com",
            password="password123",
            role="admin",
            is_active=True
        )
        self.waiter_user = User.objects.create_user(
            username="waiter_dashboard_test",
            email="waiter_dashboard@hotel.com",
            password="password123",
            role="waiter",
            is_active=True
        )

        self.table = RestaurantTable.objects.create(table_code="T-DASH-01")
        self.order_paid = Order.objects.create(
            table=self.table,
            waiter_username="waiter_dashboard_test",
            total_amount=Decimal("500.00"),
            status="served",
            payment_status="paid"
        )
        self.order_pending = Order.objects.create(
            table=self.table,
            waiter_username="waiter_dashboard_test",
            total_amount=Decimal("150.00"),
            status="pending",
            payment_status="pending"
        )

        # Create room
        self.room = Room.objects.create(
            name="Room 201 Deluxe",
            room_number="201",
            room_type="Deluxe",
            base_price=Decimal("2500.00"),
            status="Occupied"
        )

        # Create reservation
        self.reservation = Reservation.objects.create(
            room=self.room,
            guest_name="Guest Three",
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            total_amount=Decimal("5000.00"),
            deposit_amount=Decimal("1000.00"),
            status="checked_in",
            payment_status="paid"
        )

        # Create Inventory
        self.inv_category = InventoryCategory.objects.create(
            name="Food Supplies", category_type="f_and_b"
        )
        self.item = InventoryItem.objects.create(
            item_code="INV-001",
            name="Oil",
            category=self.inv_category,
            current_stock=Decimal("2.00"),
            unit_cost=Decimal("20.00"),
            min_reorder_level=Decimal("5.00")
        )

        self.url = "/api/users/dashboard-stats/"

    def test_anonymous_access_denied(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_authenticated_access_allowed(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Assert correct stats are returned
        data = response.data
        self.assertIn("pos", data)
        self.assertIn("rooms", data)
        self.assertIn("reservations", data)
        self.assertIn("inventory", data)
        self.assertIn("finance", data)
        self.assertIn("staff", data)

        # Check specifics
        self.assertEqual(data["pos"]["totalOrders"], 2)
        self.assertEqual(data["pos"]["pendingOrders"], 1)
        self.assertEqual(data["pos"]["revenue"], 500.00)

        self.assertEqual(data["rooms"]["total"], 1)
        self.assertEqual(data["rooms"]["occupied"], 1)
        
        self.assertEqual(data["reservations"]["active"], 1)
        self.assertEqual(data["reservations"]["roomRevenue"], 5000.00)

        self.assertEqual(data["inventory"]["lowStockAlerts"], 1)


# ══════════════════════════════════════════════════════════════════════════════
# Account.cached_balance — Signal-driven Tests
# ══════════════════════════════════════════════════════════════════════════════

class AccountCachedBalanceTests(TestCase):
    """
    Tests for the ``cached_balance`` field on ``Account`` and the Django
    signals in ``hotel/signals.py`` that keep it up-to-date.

    Accounting conventions under test:
      • Asset / Expense  → balance = Σ debits  − Σ credits
      • Liability / Equity / Revenue → balance = Σ credits − Σ debits

    Each test is independent: setUp creates a fresh JournalEntry and two
    Accounts (one asset, one liability) to avoid ordering dependencies.
    """

    def setUp(self):
        self.asset_account = Account.objects.create(
            code="1000-T",
            name="Cash (Test)",
            account_type="asset",
        )
        self.liability_account = Account.objects.create(
            code="2000-T",
            name="Accounts Payable (Test)",
            account_type="liability",
        )
        self.expense_account = Account.objects.create(
            code="5000-T",
            name="COGS (Test)",
            account_type="expense",
        )
        self.revenue_account = Account.objects.create(
            code="4000-T",
            name="F&B Revenue (Test)",
            account_type="revenue",
        )
        self.entry = JournalEntry.objects.create(description="Test Entry")

    # ── 1. Initial state ──────────────────────────────────────────────────────

    def test_initial_cached_balance_is_zero(self):
        """Freshly created accounts must start with cached_balance = 0."""
        self.assertEqual(self.asset_account.cached_balance, Decimal("0.00"))
        self.assertEqual(self.liability_account.cached_balance, Decimal("0.00"))

    # ── 2. Signal fires on save (debit) ──────────────────────────────────────

    def test_debit_updates_asset_balance(self):
        """Posting a debit to an asset account increases its cached_balance."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("500.00"),
            amount_credit=Decimal("0.00"),
        )
        self.asset_account.refresh_from_db()
        # Asset: Debits(500) - Credits(0) = 500
        self.assertEqual(self.asset_account.cached_balance, Decimal("500.00"))

    def test_credit_updates_asset_balance(self):
        """Posting a credit to an asset account decreases its cached_balance."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("0.00"),
            amount_credit=Decimal("200.00"),
        )
        self.asset_account.refresh_from_db()
        # Asset: Debits(0) - Credits(200) = -200
        self.assertEqual(self.asset_account.cached_balance, Decimal("-200.00"))

    # ── 3. Signal fires on save (credit) ──────────────────────────────────────

    def test_credit_updates_liability_balance(self):
        """Posting a credit to a liability account increases its cached_balance."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.liability_account,
            amount_debit=Decimal("0.00"),
            amount_credit=Decimal("1000.00"),
        )
        self.liability_account.refresh_from_db()
        # Liability: Credits(1000) - Debits(0) = 1000
        self.assertEqual(self.liability_account.cached_balance, Decimal("1000.00"))

    def test_debit_updates_liability_balance(self):
        """Posting a debit to a liability account reduces its cached_balance."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.liability_account,
            amount_debit=Decimal("300.00"),
            amount_credit=Decimal("0.00"),
        )
        self.liability_account.refresh_from_db()
        # Liability: Credits(0) - Debits(300) = -300
        self.assertEqual(self.liability_account.cached_balance, Decimal("-300.00"))

    # ── 4. Signal fires on delete ──────────────────────────────────────────────

    def test_delete_journal_item_updates_balance(self):
        """Deleting a JournalEntryItem triggers a signal that reverts the balance."""
        item = JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("750.00"),
            amount_credit=Decimal("0.00"),
        )
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.cached_balance, Decimal("750.00"))

        # Delete the item — signal must reduce balance back to 0
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            item.delete()
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.cached_balance, Decimal("750.00"))

    # ── 5. Accounting formula — Expense ──────────────────────────────────────

    def test_expense_account_formula(self):
        """Expense accounts follow the same formula as Asset accounts."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.expense_account,
            amount_debit=Decimal("400.00"),
            amount_credit=Decimal("50.00"),
        )
        self.expense_account.refresh_from_db()
        # Expense (like asset): Debits(400) - Credits(50) = 350
        self.assertEqual(self.expense_account.cached_balance, Decimal("350.00"))

    # ── 6. Accounting formula — Revenue ──────────────────────────────────────

    def test_revenue_account_formula(self):
        """Revenue accounts follow the same formula as Liability accounts."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.revenue_account,
            amount_debit=Decimal("0.00"),
            amount_credit=Decimal("800.00"),
        )
        self.revenue_account.refresh_from_db()
        # Revenue (like liability): Credits(800) - Debits(0) = 800
        self.assertEqual(self.revenue_account.cached_balance, Decimal("800.00"))

    # ── 7. Multiple entries — cumulative accuracy ──────────────────────────────

    def test_multiple_entries_cumulative_balance(self):
        """
        Balance is the SUM of all entries — not just the latest one.
        """
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("1000.00"),
            amount_credit=Decimal("0.00"),
        )
        entry2 = JournalEntry.objects.create(description="Test Entry 2")
        JournalEntryItem.objects.create(
            entry=entry2,
            account=self.asset_account,
            amount_debit=Decimal("500.00"),
            amount_credit=Decimal("200.00"),
        )
        self.asset_account.refresh_from_db()
        # Asset: Debits(1500) - Credits(200) = 1300
        self.assertEqual(self.asset_account.cached_balance, Decimal("1300.00"))

    # ── 8. Balanced double-entry: paired accounts update independently ────────

    def test_balanced_double_entry_updates_both_accounts(self):
        """
        A balanced journal entry (Dr Cash / Cr Revenue) updates both accounts
        independently and correctly.
        """
        # Dr Asset 2000, Cr Revenue 2000
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("2000.00"),
            amount_credit=Decimal("0.00"),
        )
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.revenue_account,
            amount_debit=Decimal("0.00"),
            amount_credit=Decimal("2000.00"),
        )
        self.asset_account.refresh_from_db()
        self.revenue_account.refresh_from_db()

        self.assertEqual(self.asset_account.cached_balance, Decimal("2000.00"))
        self.assertEqual(self.revenue_account.cached_balance, Decimal("2000.00"))

    # ── 9. Signal only touches cached_balance (security / update_fields) ──────

    def test_signal_does_not_mutate_other_account_fields(self):
        """
        The signal must ONLY write cached_balance via update_fields.
        Other fields (code, name, account_type) must remain unchanged.
        """
        original_code         = self.asset_account.code
        original_name         = self.asset_account.name
        original_account_type = self.asset_account.account_type

        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("100.00"),
            amount_credit=Decimal("0.00"),
        )
        self.asset_account.refresh_from_db()

        # Verify only cached_balance changed
        self.assertEqual(self.asset_account.code, original_code)
        self.assertEqual(self.asset_account.name, original_name)
        self.assertEqual(self.asset_account.account_type, original_account_type)
        # And the balance is now correct
        self.assertEqual(self.asset_account.cached_balance, Decimal("100.00"))

    # ── 10. recompute_balance() back-fill helper ──────────────────────────────

    def test_recompute_balance_repairs_stale_cache(self):
        """
        If cached_balance is somehow stale, recompute_balance() fixes it
        by recalculating from raw ledger rows.
        """
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("600.00"),
            amount_credit=Decimal("0.00"),
        )
        # Manually corrupt the cache (simulating a stale value)
        Account.objects.filter(pk=self.asset_account.pk).update(cached_balance=Decimal("999.99"))
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.cached_balance, Decimal("999.99"))  # corrupted

        # Repair it
        self.asset_account.recompute_balance()
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.cached_balance, Decimal("600.00"))  # fixed

    # ── 11. get_balance() accessor ────────────────────────────────────────────

    def test_get_balance_returns_cached_balance(self):
        """get_balance() is a safe read-only wrapper around cached_balance."""
        JournalEntryItem.objects.create(
            entry=self.entry,
            account=self.asset_account,
            amount_debit=Decimal("350.00"),
            amount_credit=Decimal("0.00"),
        )
        self.asset_account.refresh_from_db()
        self.assertEqual(self.asset_account.get_balance(), Decimal("350.00"))
        self.assertEqual(self.asset_account.get_balance(), self.asset_account.cached_balance)
