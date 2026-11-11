"""
Phase 1.2 Authoritative Batch Allocation Engine Tests.
Validates FEFO/FIFO allocation, multi-batch consumption layers,
weighted-average costing, strict expiry & quarantine lockouts,
atomic multi-balance synchronization, GL matching, and reversals.
"""
import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.integrity import record_stock_change, reverse_stock_transaction
from hotel.models import (
    Account,
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    JournalEntry,
    StockBatch,
    StockBatchConsumption,
    StockLocation,
    StockTransaction,
    Supplier,
)
from users.models import User


class BatchAllocationEngineTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_alloc", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.inv_mgr = User.objects.create_user(
            username="inv_alloc", password="password123", role="inventory", is_active=True, is_verified=True
        )

        # 2. Setup Category & Supplier
        self.category, _ = InventoryCategory.objects.get_or_create(
            name="Allocation Test Cat", defaults={"category_type": "f_and_b"}
        )
        self.supplier, _ = Supplier.objects.get_or_create(
            name="Allocation Test Supplier", defaults={"phone": "+251911998877"}
        )

        # 3. Setup Default Locations
        self.main_store, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN",
            defaults={"name": "Main Central Store", "location_type": "warehouse", "is_active": True},
        )
        self.kitchen_store, _ = StockLocation.objects.get_or_create(
            code="KITCHEN-MAIN",
            defaults={"name": "Main Kitchen Pantry", "location_type": "kitchen", "is_active": True},
        )
        self.bar_store, _ = StockLocation.objects.get_or_create(
            code="BAR-MAIN",
            defaults={"name": "Main Bar Station", "location_type": "bar", "is_active": True},
        )
        self.minibar_pantry, _ = StockLocation.objects.get_or_create(
            code="MINIBAR-PANTRY",
            defaults={"name": "Housekeeping Minibar Pantry", "location_type": "minibar", "is_active": True},
        )

        # 4. Setup Chart of Accounts
        ensure_default_accounts()

        self.today = timezone.now().date()

    def test_01_fefo_allocation_for_perishable_stock(self):
        """Perishable items must allocate via FEFO: earliest expiry consumed first."""
        item = InventoryItem.objects.create(
            item_code="PERISH-MILK-01",
            name="Pasteurized Whole Milk",
            category=self.category,
            unit="l",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("40.00"),
            is_perishable=True,
            last_supplier=self.supplier,
        )

        # Batch 1: Received 10 days ago, expires in 15 days
        batch_later = StockBatch.objects.create(
            item=item,
            batch_number="BAT-MILK-LATER",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("40.00"),
            received_date=self.today - datetime.timedelta(days=10),
            expiry_date=self.today + datetime.timedelta(days=15),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_later, location=self.main_store, quantity=Decimal("50.00"))

        # Batch 2: Received 2 days ago, expires in 4 days (earlier expiry!)
        batch_earlier = StockBatch.objects.create(
            item=item,
            batch_number="BAT-MILK-EARLIER",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("42.00"),
            received_date=self.today - datetime.timedelta(days=2),
            expiry_date=self.today + datetime.timedelta(days=4),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_earlier, location=self.main_store, quantity=Decimal("50.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        # Consume 30 litres: FEFO must consume from batch_earlier (expires in 4 days)
        updated_item, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="issuance",
            quantity=Decimal("30.00"),
            unit_cost=Decimal("42.00"),
            destination_dept="Kitchen",
        )

        batch_earlier.refresh_from_db()
        batch_later.refresh_from_db()

        self.assertEqual(batch_earlier.current_quantity, Decimal("20.00"))  # 50 - 30
        self.assertEqual(batch_later.current_quantity, Decimal("50.00"))   # Untouched
        self.assertEqual(tx.batch, batch_earlier)
        self.assertEqual(tx.unit_cost, Decimal("42.00"))

    def test_02_fifo_allocation_for_non_perishable_stock(self):
        """Non-perishable items must allocate via FIFO: earliest received date consumed first."""
        item = InventoryItem.objects.create(
            item_code="DRY-RICE-01",
            name="Basmati White Rice",
            category=self.category,
            unit="kg",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("80.00"),
            is_perishable=False,
            last_supplier=self.supplier,
        )

        # Batch 1: Received 10 days ago (older)
        batch_older = StockBatch.objects.create(
            item=item,
            batch_number="BAT-RICE-OLDER",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("78.00"),
            received_date=self.today - datetime.timedelta(days=10),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_older, location=self.main_store, quantity=Decimal("50.00"))

        # Batch 2: Received 2 days ago (newer)
        batch_newer = StockBatch.objects.create(
            item=item,
            batch_number="BAT-RICE-NEWER",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("82.00"),
            received_date=self.today - datetime.timedelta(days=2),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_newer, location=self.main_store, quantity=Decimal("50.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        # Consume 30 kg: FIFO must consume from batch_older
        updated_item, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="issuance",
            quantity=Decimal("30.00"),
            unit_cost=Decimal("78.00"),
            destination_dept="Kitchen",
        )

        batch_older.refresh_from_db()
        batch_newer.refresh_from_db()

        self.assertEqual(batch_older.current_quantity, Decimal("20.00"))  # 50 - 30
        self.assertEqual(batch_newer.current_quantity, Decimal("50.00"))  # Untouched
        self.assertEqual(tx.batch, batch_older)

    def test_03_multi_batch_consumption_layers_and_weighted_cost(self):
        """Consuming across multiple layers creates StockBatchConsumption records and weighted unit cost."""
        item = InventoryItem.objects.create(
            item_code="OIL-PALM-01",
            name="Pure Cooking Oil",
            category=self.category,
            unit="l",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("200.00"),
            is_perishable=False,
        )

        # Layer 1: 10 l @ ETB 200.00 (older)
        b1 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-OIL-L1",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("200.00"),
            received_date=self.today - datetime.timedelta(days=5),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b1, location=self.main_store, quantity=Decimal("10.00"))

        # Layer 2: 20 l @ ETB 220.00 (newer)
        b2 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-OIL-L2",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("220.00"),
            received_date=self.today - datetime.timedelta(days=1),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b2, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("30.00"))

        # Consume 15 litres: 10 from b1, 5 from b2
        # Total cost: (10 * 200) + (5 * 220) = 2000 + 1100 = 3100.00
        # Weighted cost: 3100 / 15 = 206.67
        updated_item, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="issuance",
            quantity=Decimal("15.00"),
            unit_cost=Decimal("200.00"),
            destination_dept="Kitchen",
        )

        b1.refresh_from_db()
        b2.refresh_from_db()

        self.assertEqual(b1.current_quantity, Decimal("0.00"))
        self.assertEqual(b1.status, "depleted")
        self.assertEqual(b2.current_quantity, Decimal("15.00"))
        self.assertEqual(b2.status, "active")

        # Parent transaction
        self.assertEqual(tx.quantity, Decimal("15.00"))
        self.assertEqual(tx.unit_cost, Decimal("206.67"))

        # Child consumptions
        consumptions = list(tx.batch_consumptions.order_by("id"))
        self.assertEqual(len(consumptions), 2)
        self.assertEqual(consumptions[0].batch, b1)
        self.assertEqual(consumptions[0].quantity_consumed, Decimal("10.00"))
        self.assertEqual(consumptions[0].unit_cost, Decimal("200.00"))
        self.assertEqual(consumptions[0].total_cost, Decimal("2000.00"))

        self.assertEqual(consumptions[1].batch, b2)
        self.assertEqual(consumptions[1].quantity_consumed, Decimal("5.00"))
        self.assertEqual(consumptions[1].unit_cost, Decimal("220.00"))
        self.assertEqual(consumptions[1].total_cost, Decimal("1100.00"))

        self.assertEqual(sum(c.total_cost for c in consumptions), Decimal("3100.00"))

    def test_04_expired_batch_strict_lockout(self):
        """Expired batches must be strictly excluded from allocation and block issuance."""
        item = InventoryItem.objects.create(
            item_code="YOGURT-EXP-01",
            name="Greek Yogurt 500g",
            category=self.category,
            unit="pcs",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("80.00"),
            is_perishable=True,
        )
        expired_batch = StockBatch.objects.create(
            item=item,
            batch_number="BAT-YOGURT-EXPIRED",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("80.00"),
            received_date=self.today - datetime.timedelta(days=20),
            expiry_date=self.today - datetime.timedelta(days=1),  # Expired yesterday!
            status="active",
        )
        BatchLocationBalance.objects.create(batch=expired_batch, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("20.00"))

        # Issuing expired stock must fail with ValidationError
        with self.assertRaises(ValidationError) as cm:
            record_stock_change(
                item_id=item.pk,
                transaction_type="issuance",
                quantity=Decimal("5.00"),
                unit_cost=Decimal("80.00"),
                destination_dept="Restaurant",
            )
        self.assertIn("Insufficient valid stock", str(cm.exception))

        # Balances untouched
        item.refresh_from_db()
        expired_batch.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("20.00"))
        self.assertEqual(expired_batch.current_quantity, Decimal("20.00"))

    def test_05_unverified_legacy_quarantine_lockout(self):
        """Perishable legacy items in unverified_quarantine cannot be issued to guest services."""
        item = InventoryItem.objects.create(
            item_code="CHEESE-UNV-01",
            name="Cheddar Cheese Block",
            category=self.category,
            unit="kg",
            current_stock=Decimal("15.00"),
            unit_cost=Decimal("300.00"),
            is_perishable=True,
        )
        quarantine_batch = StockBatch.objects.create(
            item=item,
            batch_number="LEGACY-INITIAL-CHEESE-UNV-01",
            initial_quantity=Decimal("15.00"),
            current_quantity=Decimal("15.00"),
            unit_cost=Decimal("300.00"),
            is_legacy=True,
            status="unverified_quarantine",
        )
        BatchLocationBalance.objects.create(batch=quarantine_batch, location=self.main_store, quantity=Decimal("15.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("15.00"))

        # Issuance must fail
        with self.assertRaises(ValidationError) as cm:
            record_stock_change(
                item_id=item.pk,
                transaction_type="issuance",
                quantity=Decimal("5.00"),
                unit_cost=Decimal("300.00"),
                destination_dept="Kitchen",
            )
        self.assertIn("Insufficient valid stock", str(cm.exception))

    def test_06_insufficient_valid_stock_rejection(self):
        """If aggregate stock is 50, but 30 is expired and 20 is valid, requesting 25 fails atomically."""
        item = InventoryItem.objects.create(
            item_code="CREAM-01",
            name="Heavy Cream 1L",
            category=self.category,
            unit="l",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("120.00"),
            is_perishable=True,
        )
        b_expired = StockBatch.objects.create(
            item=item,
            batch_number="BAT-CREAM-EXP",
            initial_quantity=Decimal("30.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("120.00"),
            expiry_date=self.today - datetime.timedelta(days=2),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b_expired, location=self.main_store, quantity=Decimal("30.00"))

        b_valid = StockBatch.objects.create(
            item=item,
            batch_number="BAT-CREAM-VAL",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("120.00"),
            expiry_date=self.today + datetime.timedelta(days=10),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b_valid, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("50.00"))

        # Request 25 litres (more than the 20 unexpired litres available)
        with self.assertRaises(ValidationError) as cm:
            record_stock_change(
                item_id=item.pk,
                transaction_type="issuance",
                quantity=Decimal("25.00"),
                unit_cost=Decimal("120.00"),
                destination_dept="Kitchen",
            )
        self.assertIn("Insufficient valid stock", str(cm.exception))
        self.assertIn("Available (Unexpired & Verified): 20.00", str(cm.exception))

        # Check that no partial deduction occurred
        b_valid.refresh_from_db()
        b_expired.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(b_valid.current_quantity, Decimal("20.00"))
        self.assertEqual(b_expired.current_quantity, Decimal("30.00"))
        self.assertEqual(item.current_stock, Decimal("50.00"))

    def test_07_atomic_multi_balance_synchronization(self):
        """Batch, BLB, ILB, and aggregate stock all stay in 100% exact numerical sync."""
        item = InventoryItem.objects.create(
            item_code="BUTTER-02",
            name="Unsalted Butter 250g",
            category=self.category,
            unit="pcs",
            current_stock=Decimal("40.00"),
            unit_cost=Decimal("90.00"),
            is_perishable=True,
        )
        batch = StockBatch.objects.create(
            item=item,
            batch_number="BAT-BUTTER-02",
            initial_quantity=Decimal("40.00"),
            current_quantity=Decimal("40.00"),
            unit_cost=Decimal("90.00"),
            expiry_date=self.today + datetime.timedelta(days=30),
            status="active",
        )
        blb = BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("40.00"))
        ilb = ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("40.00"))

        record_stock_change(
            item_id=item.pk,
            transaction_type="issuance",
            quantity=Decimal("15.00"),
            unit_cost=Decimal("90.00"),
            destination_dept="Pastry",
        )

        item.refresh_from_db()
        batch.refresh_from_db()
        blb.refresh_from_db()
        ilb.refresh_from_db()

        self.assertEqual(item.current_stock, Decimal("25.00"))
        self.assertEqual(batch.current_quantity, Decimal("25.00"))
        self.assertEqual(blb.quantity, Decimal("25.00"))
        self.assertEqual(ilb.quantity, Decimal("25.00"))

    def test_08_reversal_restores_batch_layers_and_balances(self):
        """Reversing a multi-batch transaction restores all consumed batch layers, status, and balances."""
        item = InventoryItem.objects.create(
            item_code="SUGAR-REV-01",
            name="Caster Sugar",
            category=self.category,
            unit="kg",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("70.00"),
            is_perishable=False,
        )
        b1 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-SUGAR-L1",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("65.00"),
            received_date=self.today - datetime.timedelta(days=5),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b1, location=self.main_store, quantity=Decimal("10.00"))

        b2 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-SUGAR-L2",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("75.00"),
            received_date=self.today - datetime.timedelta(days=1),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b2, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("30.00"))

        # Issue 15 kg (depletes b1 completely, consumes 5 from b2)
        _, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="issuance",
            quantity=Decimal("15.00"),
            unit_cost=Decimal("70.00"),
            destination_dept="Kitchen",
        )

        b1.refresh_from_db()
        self.assertEqual(b1.status, "depleted")
        self.assertEqual(b1.current_quantity, Decimal("0.00"))

        # Reverse the transaction
        reversal, created = reverse_stock_transaction(
            transaction_id=tx.pk,
            reason="Kitchen order cancelled before prep",
            logged_by_username="inv_alloc",
        )
        self.assertTrue(created)

        # Confirm exact restorations
        b1.refresh_from_db()
        b2.refresh_from_db()
        item.refresh_from_db()
        blb1 = BatchLocationBalance.objects.get(batch=b1, location=self.main_store)
        blb2 = BatchLocationBalance.objects.get(batch=b2, location=self.main_store)
        ilb = ItemLocationBalance.objects.get(item=item, location=self.main_store)

        self.assertEqual(b1.current_quantity, Decimal("10.00"))
        self.assertEqual(b1.status, "active")  # Depleted status restored to active!
        self.assertEqual(b2.current_quantity, Decimal("20.00"))
        self.assertEqual(blb1.quantity, Decimal("10.00"))
        self.assertEqual(blb2.quantity, Decimal("20.00"))
        self.assertEqual(ilb.quantity, Decimal("30.00"))
        self.assertEqual(item.current_stock, Decimal("30.00"))

    def test_09_general_ledger_exact_sum_matching(self):
        """General Ledger posting uses the exact sum of batch consumption costs."""
        self.client.force_authenticate(user=self.inv_mgr)

        item = InventoryItem.objects.create(
            item_code="TEA-GL-01",
            name="Earl Grey Tea Leaves",
            category=self.category,
            unit="kg",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("150.00"),
            is_perishable=False,
        )
        b1 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-TEA-L1",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("140.00"),
            received_date=self.today - datetime.timedelta(days=5),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b1, location=self.main_store, quantity=Decimal("10.00"))

        b2 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-TEA-L2",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("160.00"),
            received_date=self.today - datetime.timedelta(days=1),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=b2, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("30.00"))

        # Issue 15 kg via DRF ViewSet: 10 * 140 + 5 * 160 = 1400 + 800 = 2200.00
        res = self.client.post(
            reverse("stocktransaction-list"),
            data={
                "item": item.pk,
                "transaction_type": "issuance",
                "quantity": "15.00",
                "unit_cost": "150.00",
                "destination_dept": "Lobby Lounge",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Inspect latest JournalEntry
        jv = JournalEntry.objects.filter(description__contains="Earl Grey Tea Leaves").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in jv.items.all()}

        # Dr 5000 (COGS) 2200.00, Cr 1300 (Asset) 2200.00
        self.assertEqual(items["5000"], (Decimal("2200.00"), Decimal("0.00")))
        self.assertEqual(items["1300"], (Decimal("0.00"), Decimal("2200.00")))

    def test_10_incoming_purchase_creates_batch_and_location_balance(self):
        """Direct purchase adds stock, creates a new batch, and increments location balances."""
        item = InventoryItem.objects.create(
            item_code="COFFEE-PUR-01",
            name="Yirgacheffe Coffee Beans",
            category=self.category,
            unit="kg",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("250.00"),
            is_perishable=True,
            shelf_life_days=180,
            last_supplier=self.supplier,
        )

        future_exp = (self.today + datetime.timedelta(days=180)).isoformat()
        _, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="purchase",
            quantity=Decimal("50.00"),
            unit_cost=Decimal("260.00"),
            supplier=self.supplier,
            expiry_date=future_exp,
            reference_number="PO-COFFEE-001",
        )

        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("50.00"))
        self.assertEqual(item.unit_cost, Decimal("260.00"))

        batch = tx.batch
        self.assertIsNotNone(batch)
        self.assertEqual(batch.current_quantity, Decimal("50.00"))
        self.assertEqual(batch.unit_cost, Decimal("260.00"))
        self.assertEqual(str(batch.expiry_date), future_exp)

        blb = BatchLocationBalance.objects.get(batch=batch, location=self.main_store)
        ilb = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(blb.quantity, Decimal("50.00"))
        self.assertEqual(ilb.quantity, Decimal("50.00"))

    def test_11_waste_disposal_of_expired_stock_allowed(self):
        """Disposing of an expired batch via loss/waste transaction is permitted."""
        item = InventoryItem.objects.create(
            item_code="MILK-SPOIL-01",
            name="Spoiled Cow Milk",
            category=self.category,
            unit="l",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("40.00"),
            is_perishable=True,
        )
        expired_batch = StockBatch.objects.create(
            item=item,
            batch_number="BAT-MILK-SPOILED",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("40.00"),
            expiry_date=self.today - datetime.timedelta(days=3),
            status="quarantined_expired",
        )
        BatchLocationBalance.objects.create(batch=expired_batch, location=self.main_store, quantity=Decimal("10.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("10.00"))

        # Waste write-off specifically passing the expired batch
        updated_item, tx = record_stock_change(
            item_id=item.pk,
            transaction_type="loss",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("40.00"),
            batch=expired_batch,
            notes="Expired batch disposal",
        )

        expired_batch.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(expired_batch.current_quantity, Decimal("0.00"))
        self.assertEqual(expired_batch.status, "depleted")
        self.assertEqual(item.current_stock, Decimal("0.00"))

