"""
Phase 1.5 Dual-Mode Physical Stocktaking (Blind & Visible) Test Suite.
Validates:
- Snapshotting theoretical inventory from location balances
- Category scoping
- Zero-leak blind mode masking for non-admin counters
- Visible mode expected quantity display
- Permanent mode locking upon count submission (Owner Decision D-4)
- Recount workflow and discrepancy resolution
- Separation of duties (counted_by != approved_by)
- Authoritative surplus adjustments and GL posting (Dr 1300, Cr 5020)
- Authoritative shrinkage adjustments and GL posting (Dr 5020, Cr 1300)
- Concurrent approval idempotency
- Session cancellation safety
- Role-based access control restrictions
"""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.integrity import record_stock_change
from hotel.models import (
    Account,
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    JournalEntry,
    StockBatch,
    StockLocation,
    StocktakeItem,
    StocktakeSession,
    StockTransaction,
    Supplier,
)
from hotel.stocktaking import (
    approve_stocktake_session,
    cancel_stocktake_session,
    create_stocktake_session,
    record_counts,
    request_recount,
    submit_recount,
)
from users.models import User


class StocktakingManagementTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_stk", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.supervisor = User.objects.create_user(
            username="supervisor_stk", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.counter_1 = User.objects.create_user(
            username="counter1_stk", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.counter_2 = User.objects.create_user(
            username="counter2_stk", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.waiter = User.objects.create_user(
            username="waiter_stk", password="password123", role="waiter", is_active=True, is_verified=True
        )

        # 2. Setup Categories
        self.cat_fnb, _ = InventoryCategory.objects.get_or_create(
            name="F&B Stocktake", defaults={"category_type": "f_and_b"}
        )
        self.cat_hsk, _ = InventoryCategory.objects.get_or_create(
            name="Housekeeping Stocktake", defaults={"category_type": "housekeeping"}
        )

        # 3. Setup Locations
        self.main_store, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN",
            defaults={"name": "Main Central Warehouse", "location_type": "warehouse", "is_active": True},
        )
        self.kitchen_store, _ = StockLocation.objects.get_or_create(
            code="KITCHEN-MAIN",
            defaults={"name": "Main Kitchen Store", "location_type": "kitchen", "is_active": True},
        )

        # 4. Setup Chart of Accounts
        ensure_default_accounts()
        self.account_1300 = Account.objects.get(code="1300")
        self.account_5020 = Account.objects.get(code="5020")

        self.today = timezone.now().date()

    def test_01_create_stocktake_session_snapshots_theoretical_stock(self):
        """Verifies theoretical stock and unit cost snapshots from location balances."""
        item_a = InventoryItem.objects.create(
            item_code="STK-ITM-01A",
            name="Basmati Rice 25kg",
            category=self.cat_fnb,
            unit="bags",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("1200.00"),
        )
        ItemLocationBalance.objects.create(item=item_a, location=self.main_store, quantity=Decimal("50.00"))

        item_b = InventoryItem.objects.create(
            item_code="STK-ITM-01B",
            name="Olive Oil 5L",
            category=self.cat_fnb,
            unit="cans",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("800.00"),
        )
        ItemLocationBalance.objects.create(item=item_b, location=self.main_store, quantity=Decimal("20.00"))

        session = create_stocktake_session(
            location=self.main_store,
            counting_mode="blind",
            title="End of Month Main Store Count",
            created_by=self.admin,
        )

        self.assertTrue(session.session_number.startswith("STK-"))
        self.assertEqual(session.counting_mode, "blind")
        self.assertFalse(session.is_mode_locked)
        self.assertEqual(session.status, "draft")
        self.assertEqual(session.created_by, self.admin)
        self.assertEqual(session.items.count(), 2)

        stk_a = session.items.get(item=item_a)
        self.assertEqual(stk_a.theoretical_quantity, Decimal("50.00"))
        self.assertEqual(stk_a.unit_cost_snapshot, Decimal("1200.00"))
        self.assertIsNone(stk_a.counted_quantity)
        self.assertIsNone(stk_a.final_quantity)

        stk_b = session.items.get(item=item_b)
        self.assertEqual(stk_b.theoretical_quantity, Decimal("20.00"))
        self.assertEqual(stk_b.unit_cost_snapshot, Decimal("800.00"))

        # Total theoretical = 50 * 1200 + 20 * 800 = 60,000 + 16,000 = 76,000.00
        self.assertEqual(session.total_theoretical_value, Decimal("76000.00"))

    def test_02_category_scoping_limits_snapshot_items(self):
        """Confirms sessions scoped to specific categories snapshot only relevant items."""
        item_food = InventoryItem.objects.create(
            item_code="STK-ITM-02A",
            name="Fresh Milk 1L",
            category=self.cat_fnb,
            unit="liters",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("70.00"),
        )
        ItemLocationBalance.objects.create(item=item_food, location=self.kitchen_store, quantity=Decimal("30.00"))

        item_linen = InventoryItem.objects.create(
            item_code="STK-ITM-02B",
            name="Bed Sheet White",
            category=self.cat_hsk,
            unit="pieces",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("450.00"),
        )
        ItemLocationBalance.objects.create(item=item_linen, location=self.kitchen_store, quantity=Decimal("100.00"))

        session = create_stocktake_session(
            location=self.kitchen_store,
            category=self.cat_fnb,
            counting_mode="visible",
            created_by=self.admin,
        )

        self.assertEqual(session.items.count(), 1)
        self.assertEqual(session.items.first().item, item_food)
        self.assertFalse(session.items.filter(item=item_linen).exists())
        self.assertEqual(session.total_theoretical_value, Decimal("2100.00"))

    def test_03_blind_mode_masks_theoretical_qty_from_counters(self):
        """Verifies that non-admin counters query returns None for theoretical quantities in blind mode."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-03",
            name="Coffee Beans 1kg",
            category=self.cat_fnb,
            unit="kg",
            current_stock=Decimal("40.00"),
            unit_cost=Decimal("500.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("40.00"))

        session = create_stocktake_session(
            location=self.main_store,
            counting_mode="blind",
            created_by=self.admin,
        )

        # 1. Counter (non-admin inventory role) requests session via API
        self.client.force_authenticate(user=self.counter_1)
        url = reverse("stocktakesession-detail", args=[session.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        items_data = res.data["items"]
        self.assertEqual(len(items_data), 1)
        # Theoretical stock and variance MUST be masked (None / null)
        self.assertIsNone(items_data[0]["theoretical_quantity"])
        self.assertIsNone(items_data[0]["variance_quantity"])
        self.assertIsNone(items_data[0]["variance_value"])

        # 2. Administrator requests session via API
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        admin_items = res_admin.data["items"]
        self.assertEqual(Decimal(str(admin_items[0]["theoretical_quantity"])), Decimal("40.00"))

    def test_04_visible_mode_displays_theoretical_qty(self):
        """Confirms theoretical quantities are returned to counters in visible mode."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-04",
            name="Sugar 50kg",
            category=self.cat_fnb,
            unit="bags",
            current_stock=Decimal("15.00"),
            unit_cost=Decimal("3000.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("15.00"))

        session = create_stocktake_session(
            location=self.main_store,
            counting_mode="visible",
            created_by=self.admin,
        )

        self.client.force_authenticate(user=self.counter_1)
        url = reverse("stocktakesession-detail", args=[session.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        items_data = res.data["items"]
        self.assertEqual(Decimal(str(items_data[0]["theoretical_quantity"])), Decimal("15.00"))

    def test_05_mode_locking_on_first_count_submission(self):
        """Verifies is_mode_locked is set to True upon count entry and prevents mode changes (D-4)."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-05",
            name="Flour 25kg",
            category=self.cat_fnb,
            unit="bags",
            current_stock=Decimal("25.00"),
            unit_cost=Decimal("1500.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("25.00"))

        session = create_stocktake_session(
            location=self.main_store,
            counting_mode="blind",
            created_by=self.admin,
        )
        self.assertFalse(session.is_mode_locked)

        # Counter submits physical count
        self.client.force_authenticate(user=self.counter_1)
        record_url = reverse("stocktakesession-record-counts", args=[session.id])
        res = self.client.post(record_url, {"counts": [{"item_id": item.id, "counted_quantity": 24.00}]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertTrue(session.is_mode_locked)
        self.assertEqual(session.status, "under_review")

        # Now attempt to alter counting_mode to visible via PATCH
        self.client.force_authenticate(user=self.admin)
        patch_url = reverse("stocktakesession-detail", args=[session.id])
        res_patch = self.client.patch(patch_url, {"counting_mode": "visible"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("locked", str(res_patch.data))

        session.refresh_from_db()
        self.assertEqual(session.counting_mode, "blind")

    def test_06_recount_workflow_flagging_and_resubmission(self):
        """Verifies supervisor flagging items for recount, counter resubmitting recount, and updating final quantities."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-06",
            name="Butter 1kg",
            category=self.cat_fnb,
            unit="blocks",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("400.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("50.00"))

        session = create_stocktake_session(location=self.main_store, counting_mode="blind", created_by=self.admin)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("30.00")}], user=self.counter_1)

        session.refresh_from_db()
        stk_item = session.items.get(item=item)
        self.assertEqual(stk_item.variance_quantity, Decimal("-20.00"))
        self.assertEqual(session.status, "under_review")

        # Supervisor flags recount via API
        self.client.force_authenticate(user=self.supervisor)
        recount_req_url = reverse("stocktakesession-request-recount", args=[session.id])
        res_req = self.client.post(
            recount_req_url,
            {"item_ids": [stk_item.id], "reason": "Discrepancy of 20 blocks exceeds tolerance"},
            format="json",
        )
        self.assertEqual(res_req.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        stk_item.refresh_from_db()
        self.assertEqual(session.status, "recount_required")
        self.assertTrue(stk_item.requires_recount)

        # Attempt to approve during pending recount fails
        with self.assertRaises(ValidationError) as ctx:
            approve_stocktake_session(session_id=session.pk, supervisor=self.supervisor)
        self.assertIn("pending recount", str(ctx.exception))

        # Counter performs physical recount and submits 49 blocks
        self.client.force_authenticate(user=self.counter_1)
        recount_sub_url = reverse("stocktakesession-submit-recount", args=[session.id])
        res_sub = self.client.post(
            recount_sub_url,
            {"recounts": [{"id": stk_item.id, "recounted_quantity": 49.00, "notes": "One block in back chiller"}],},
            format="json",
        )
        self.assertEqual(res_sub.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        stk_item.refresh_from_db()
        self.assertEqual(session.status, "under_review")
        self.assertFalse(stk_item.requires_recount)
        self.assertEqual(stk_item.recounted_quantity, Decimal("49.00"))
        self.assertEqual(stk_item.final_quantity, Decimal("49.00"))
        self.assertEqual(stk_item.variance_quantity, Decimal("-1.00"))
        self.assertEqual(stk_item.variance_value, Decimal("-400.00"))

    def test_07_separation_of_duties_prevents_self_approval(self):
        """Confirms count submitter cannot approve the session (403 Forbidden)."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-07",
            name="Eggs Carton 30s",
            category=self.cat_fnb,
            unit="cartons",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("350.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("10.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("10.00")}], user=self.counter_1)

        session.refresh_from_db()
        self.assertEqual(session.counted_by, self.counter_1)

        # Counter 1 attempts to approve their own count via service
        with self.assertRaises(PermissionDenied) as ctx:
            approve_stocktake_session(session_id=session.pk, supervisor=self.counter_1)
        self.assertIn("Separation of duties violation", str(ctx.exception))

        # Counter 1 attempts to approve via API
        self.client.force_authenticate(user=self.counter_1)
        approve_url = reverse("stocktakesession-approve", args=[session.id])
        res = self.client.post(approve_url, {"notes": "Attempting self approval"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Separation of duties violation", str(res.data))

        # Independent supervisor approves successfully
        self.client.force_authenticate(user=self.supervisor)
        res_ok = self.client.post(approve_url, {"notes": "Approved by independent supervisor"})
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertEqual(session.status, "approved")
        self.assertEqual(session.reviewed_by, self.supervisor)

    def test_08_approval_surplus_variance_creates_stock_increase_and_gl(self):
        """Verifies surplus count increments item stock via record_stock_change and posts Dr 1300, Cr 5020."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-08",
            name="Canned Tomatoes 800g",
            category=self.cat_fnb,
            unit="cans",
            current_stock=Decimal("40.00"),
            unit_cost=Decimal("150.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("40.00"))
        batch = StockBatch.objects.create(
            item=item,
            batch_number="BATCH-STK-08",
            initial_quantity=Decimal("40.00"),
            current_quantity=Decimal("40.00"),
            unit_cost=Decimal("150.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("40.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        # Surplus count: 45 cans found (variance = +5 cans, value = +$750.00)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("45.00")}], user=self.counter_1)

        approve_stocktake_session(session_id=session.pk, supervisor=self.supervisor, notes="Surplus verified physically")

        session.refresh_from_db()
        item.refresh_from_db()
        ilb = ItemLocationBalance.objects.get(item=item, location=self.main_store)

        self.assertEqual(session.status, "approved")
        self.assertEqual(item.current_stock, Decimal("45.00"))
        self.assertEqual(ilb.quantity, Decimal("45.00"))

        # Verify StockTransaction
        txn = StockTransaction.objects.filter(item=item, transaction_type="adjustment", adjustment_direction="increase").latest("timestamp")
        self.assertEqual(txn.quantity, Decimal("5.00"))
        self.assertEqual(txn.location, self.main_store)

        # Verify General Ledger Journal Entry: Dr 1300 (Asset) 750.00, Cr 5020 (Expense recovery) 750.00
        self.assertIsNotNone(session.journal_entry)
        entry = session.journal_entry
        items = list(entry.items.all())
        self.assertEqual(len(items), 2)

        dr_item = [i for i in items if i.amount_debit > 0][0]
        cr_item = [i for i in items if i.amount_credit > 0][0]

        self.assertEqual(dr_item.account.code, "1300")
        self.assertEqual(dr_item.amount_debit, Decimal("750.00"))
        self.assertEqual(cr_item.account.code, "5020")
        self.assertEqual(cr_item.amount_credit, Decimal("750.00"))

    def test_09_approval_deficit_variance_creates_stock_reduction_and_gl(self):
        """Verifies shrinkage count deducts item stock via FEFO layers and posts Dr 5020, Cr 1300."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-09",
            name="Premium Vodka 750ml",
            category=self.cat_fnb,
            unit="bottles",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("600.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("50.00"))
        batch = StockBatch.objects.create(
            item=item,
            batch_number="BATCH-STK-09",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("600.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("50.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        # Deficit count: 42 bottles counted (shrinkage = -8 bottles, value = -$4800.00)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("42.00")}], user=self.counter_1)

        approve_stocktake_session(session_id=session.pk, supervisor=self.supervisor, notes="Shrinkage written off")

        session.refresh_from_db()
        item.refresh_from_db()
        batch.refresh_from_db()
        ilb = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        blb = BatchLocationBalance.objects.get(batch=batch, location=self.main_store)

        self.assertEqual(session.status, "approved")
        self.assertEqual(item.current_stock, Decimal("42.00"))
        self.assertEqual(ilb.quantity, Decimal("42.00"))
        self.assertEqual(batch.current_quantity, Decimal("42.00"))
        self.assertEqual(blb.quantity, Decimal("42.00"))

        # Verify StockTransaction
        txn = StockTransaction.objects.filter(item=item, transaction_type="adjustment", adjustment_direction="decrease").latest("timestamp")
        self.assertEqual(txn.quantity, Decimal("8.00"))
        self.assertEqual(txn.location, self.main_store)

        # Verify General Ledger Journal Entry: Dr 5020 (Variance Expense) 4800.00, Cr 1300 (Asset) 4800.00
        self.assertIsNotNone(session.journal_entry)
        entry = session.journal_entry
        items = list(entry.items.all())
        self.assertEqual(len(items), 2)

        dr_item = [i for i in items if i.amount_debit > 0][0]
        cr_item = [i for i in items if i.amount_credit > 0][0]

        self.assertEqual(dr_item.account.code, "5020")
        self.assertEqual(dr_item.amount_debit, Decimal("4800.00"))
        self.assertEqual(cr_item.account.code, "1300")
        self.assertEqual(cr_item.amount_credit, Decimal("4800.00"))

    def test_10_concurrent_approval_idempotency(self):
        """Confirms duplicate or concurrent approval requests do not double-adjust stock or duplicate GL entries."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-10",
            name="Mineral Water 1.5L",
            category=self.cat_fnb,
            unit="bottles",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("30.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("95.00")}], user=self.counter_1)

        # First approval
        s1 = approve_stocktake_session(session_id=session.pk, supervisor=self.supervisor)
        self.assertEqual(s1.status, "approved")
        je_id = s1.journal_entry.pk

        # Second approval call (idempotent replay)
        s2 = approve_stocktake_session(session_id=session.pk, supervisor=self.supervisor)
        self.assertEqual(s2.status, "approved")
        self.assertEqual(s2.journal_entry.pk, je_id)

        # Verify stock was only deducted once: 100 - 5 = 95 (not 90)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("95.00"))
        # Verify only one adjustment transaction was posted
        self.assertEqual(StockTransaction.objects.filter(item=item, transaction_type="adjustment").count(), 1)

    def test_11_session_cancellation_leaves_balances_intact(self):
        """Confirms cancelling a session releases the session and makes no stock or accounting changes."""
        item = InventoryItem.objects.create(
            item_code="STK-ITM-11",
            name="Orange Juice 1L",
            category=self.cat_fnb,
            unit="bottles",
            current_stock=Decimal("60.00"),
            unit_cost=Decimal("120.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("60.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("40.00")}], user=self.counter_1)

        # Cancel the session via API
        self.client.force_authenticate(user=self.admin)
        cancel_url = reverse("stocktakesession-cancel", args=[session.id])
        res = self.client.post(cancel_url, {"reason": "Count aborted due to flood in warehouse"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        item.refresh_from_db()
        ilb = ItemLocationBalance.objects.get(item=item, location=self.main_store)

        self.assertEqual(session.status, "cancelled")
        self.assertIn("flood in warehouse", session.variance_approval_notes)
        self.assertEqual(item.current_stock, Decimal("60.00"))
        self.assertEqual(ilb.quantity, Decimal("60.00"))
        self.assertIsNone(session.journal_entry)

        # Attempt to cancel an approved session raises error
        session.status = "approved"
        session.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            cancel_stocktake_session(session_id=session.pk, user=self.admin)

    def test_12_non_manager_cannot_create_or_approve_sessions(self):
        """Verifies role-based access restrictions for unprivileged users."""
        self.client.force_authenticate(user=self.waiter)

        # Waiter tries to create stocktake session
        create_url = reverse("stocktakesession-list")
        res_create = self.client.post(create_url, {"location": self.main_store.id, "counting_mode": "blind"})
        self.assertEqual(res_create.status_code, status.HTTP_403_FORBIDDEN)

        # Admin creates session
        session = create_stocktake_session(location=self.main_store, created_by=self.admin)

        # Waiter tries to approve session
        approve_url = reverse("stocktakesession-approve", args=[session.id])
        res_approve = self.client.post(approve_url, {"notes": "Waiter approval"})
        self.assertEqual(res_approve.status_code, status.HTTP_403_FORBIDDEN)

