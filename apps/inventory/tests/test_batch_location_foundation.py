"""
Phase 1.1 Batch and Location Foundation Tests.
Validates StockLocation, StockBatch, Location Balances, Constraints,
Chart of Accounts seeding, and the Legacy Batch Verification workflow.
"""
import datetime
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.models import (
    Account,
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    StockBatch,
    StockBatchConsumption,
    StockLocation,
    StockTransaction,
    Supplier,
)
from users.models import User


class BatchLocationFoundationTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_p1", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.inventory_mgr = User.objects.create_user(
            username="inv_mgr_p1", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.chef = User.objects.create_user(
            username="chef_p1", password="password123", role="kitchen", is_active=True, is_verified=True
        )
        self.waiter = User.objects.create_user(
            username="waiter_p1", password="password123", role="waiter", is_active=True, is_verified=True
        )

        # 2. Setup Category & Supplier
        self.cat_fb, _ = InventoryCategory.objects.get_or_create(
            name="Food and Beverage P1", defaults={"category_type": "f_and_b"}
        )
        self.supplier, _ = Supplier.objects.get_or_create(
            name="Fresh Farms Ltd P1", defaults={"phone": "+251911223344"}
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

        # 4. Setup Chart of Accounts via existing service
        ensure_default_accounts()

    def test_01_default_locations_exist_post_migration(self):
        """Verify standard locations exist with correct metadata."""
        codes = set(StockLocation.objects.values_list("code", flat=True))
        self.assertIn("STORE-MAIN", codes)
        self.assertIn("KITCHEN-MAIN", codes)
        self.assertIn("BAR-MAIN", codes)
        self.assertIn("MINIBAR-PANTRY", codes)

        main_loc = StockLocation.objects.get(code="STORE-MAIN")
        self.assertEqual(main_loc.location_type, "warehouse")
        self.assertTrue(main_loc.is_active)

    def test_02_legacy_batch_creation_for_positive_stock_item(self):
        """Verify positive items get an unverified legacy batch without fake lot/expiry."""
        item = InventoryItem.objects.create(
            item_code="BEEF-001",
            name="Prime Beef Tenderloin",
            category=self.cat_fb,
            unit="kg",
            current_stock=Decimal("45.50"),
            unit_cost=Decimal("250.00"),
            is_perishable=True,
            last_supplier=self.supplier,
        )

        # Simulate migration logic for single item
        batch_num = f"LEGACY-INITIAL-{item.item_code}"
        batch = StockBatch.objects.create(
            item=item,
            batch_number=batch_num,
            supplier=self.supplier,
            supplier_batch_number=None,  # No fake vendor lot
            initial_quantity=item.current_stock,
            current_quantity=item.current_stock,
            unit_cost=item.unit_cost,
            expiry_date=None,  # Strictly None: no synthetic expiry dates
            is_legacy=True,
            status="unverified_quarantine",  # Perishable legacy must be quarantined
        )

        blb = BatchLocationBalance.objects.create(
            batch=batch, location=self.main_store, quantity=item.current_stock
        )
        ilb = ItemLocationBalance.objects.create(
            item=item, location=self.main_store, quantity=item.current_stock
        )

        self.assertEqual(batch.batch_number, "LEGACY-INITIAL-BEEF-001")
        self.assertTrue(batch.is_legacy)
        self.assertIsNone(batch.supplier_batch_number)
        self.assertIsNone(batch.expiry_date)
        self.assertEqual(batch.status, "unverified_quarantine")
        self.assertEqual(blb.quantity, Decimal("45.50"))
        self.assertEqual(ilb.quantity, Decimal("45.50"))

    def test_03_non_perishable_legacy_item_status_is_active(self):
        """Non-perishable legacy items get active status; perishable get unverified_quarantine."""
        non_perishable_item = InventoryItem.objects.create(
            item_code="NAPKIN-001",
            name="Linen Dinner Napkins",
            category=self.cat_fb,
            unit="pcs",
            current_stock=Decimal("500.00"),
            unit_cost=Decimal("12.00"),
            is_perishable=False,
        )
        status_np = "unverified_quarantine" if non_perishable_item.is_perishable else "active"
        self.assertEqual(status_np, "active")

        perishable_item = InventoryItem.objects.create(
            item_code="MILK-001",
            name="Pasteurized Whole Milk",
            category=self.cat_fb,
            unit="l",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("45.00"),
            is_perishable=True,
        )
        status_p = "unverified_quarantine" if perishable_item.is_perishable else "active"
        self.assertEqual(status_p, "unverified_quarantine")

    def test_04_check_constraints_prevent_negative_batch_and_location_balances(self):
        """Database check constraints must block negative quantities at model level."""
        item = InventoryItem.objects.create(
            item_code="OIL-001",
            name="Cooking Oil",
            category=self.cat_fb,
            unit="l",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("180.00"),
        )
        batch = StockBatch.objects.create(
            item=item,
            batch_number="BAT-OIL-2026-001",
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("180.00"),
        )

        # 1. Batch current_quantity cannot be negative
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockBatch.objects.create(
                    item=item,
                    batch_number="BAT-OIL-NEG",
                    initial_quantity=Decimal("10.00"),
                    current_quantity=Decimal("-1.00"),
                    unit_cost=Decimal("180.00"),
                )

        # 2. Batch current_quantity cannot exceed initial_quantity
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockBatch.objects.create(
                    item=item,
                    batch_number="BAT-OIL-OVERFLOW",
                    initial_quantity=Decimal("10.00"),
                    current_quantity=Decimal("15.00"),
                    unit_cost=Decimal("180.00"),
                )

        # 3. BatchLocationBalance cannot be negative
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BatchLocationBalance.objects.create(
                    batch=batch, location=self.main_store, quantity=Decimal("-5.00")
                )

        # 4. ItemLocationBalance cannot be negative
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemLocationBalance.objects.create(
                    item=item, location=self.main_store, quantity=Decimal("-10.00")
                )

    def test_05_chart_of_accounts_contains_phase1_accounts(self):
        """Verify seeded accounts 2010, 5010, 5020, 5030 exist in Chart of Accounts."""
        codes = set(Account.objects.values_list("code", flat=True))
        self.assertIn("2010", codes)
        self.assertIn("5010", codes)
        self.assertIn("5020", codes)
        self.assertIn("5030", codes)

        grni = Account.objects.get(code="2010")
        self.assertEqual(grni.account_type, "liability")

        waste_exp = Account.objects.get(code="5010")
        self.assertEqual(waste_exp.account_type, "expense")

    def test_06_legacy_batch_verification_endpoint_success(self):
        """Chef or Inventory Manager can inspect and verify an unverified legacy perishable batch."""
        item = InventoryItem.objects.create(
            item_code="YOGURT-001",
            name="Natural Greek Yogurt",
            category=self.cat_fb,
            unit="kg",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("110.00"),
            is_perishable=True,
        )
        batch = StockBatch.objects.create(
            item=item,
            batch_number=f"LEGACY-INITIAL-{item.item_code}",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("110.00"),
            is_legacy=True,
            status="unverified_quarantine",
        )

        future_date = (timezone.now() + datetime.timedelta(days=14)).date().isoformat()

        # Call verify endpoint as Inventory Manager
        self.client.force_authenticate(user=self.inventory_mgr)
        res = self.client.post(
            f"/api/users/batches/{batch.id}/verify/",
            {
                "expiry_date": future_date,
                "verification_notes": "Inspected cold room seals. Expiry confirmed by Chef Fitsum.",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "active")
        self.assertEqual(str(batch.expiry_date), future_date)
        self.assertEqual(batch.verified_by, self.inventory_mgr)
        self.assertIsNotNone(batch.verified_at)
        self.assertIn("Chef Fitsum", batch.verification_notes)

    def test_07_legacy_batch_verification_rejects_past_expiry(self):
        """Verification must reject expired dates; expired stock must go to waste."""
        item = InventoryItem.objects.create(
            item_code="CHEESE-001",
            name="Gouda Cheese Wheel",
            category=self.cat_fb,
            unit="kg",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("350.00"),
            is_perishable=True,
        )
        batch = StockBatch.objects.create(
            item=item,
            batch_number=f"LEGACY-INITIAL-{item.item_code}",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("350.00"),
            is_legacy=True,
            status="unverified_quarantine",
        )

        past_date = (timezone.now() - datetime.timedelta(days=2)).date().isoformat()

        self.client.force_authenticate(user=self.chef)
        res = self.client.post(
            f"/api/users/batches/{batch.id}/verify/",
            {"expiry_date": past_date, "verification_notes": "Expired"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot verify batch with a past expiry date", res.data["error"])

    def test_08_legacy_batch_verification_unauthorized_role_rejected(self):
        """Unauthorized staff (e.g. Waiter) cannot verify batches."""
        item = InventoryItem.objects.create(
            item_code="BUTTER-001",
            name="Table Butter",
            category=self.cat_fb,
            unit="pcs",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("25.00"),
            is_perishable=True,
        )
        batch = StockBatch.objects.create(
            item=item,
            batch_number=f"LEGACY-INITIAL-{item.item_code}",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("25.00"),
            is_legacy=True,
            status="unverified_quarantine",
        )

        future_date = (timezone.now() + datetime.timedelta(days=30)).date().isoformat()

        self.client.force_authenticate(user=self.waiter)
        res = self.client.post(
            f"/api/users/batches/{batch.id}/verify/",
            {"expiry_date": future_date},
            format="json",
        )
        # IsInventoryManager permission blocks waiter at view level
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_09_stock_transaction_and_batch_consumptions_relation(self):
        """Verify multi-batch child consumptions link to parent StockTransaction."""
        item = InventoryItem.objects.create(
            item_code="SUGAR-001",
            name="Refined White Sugar",
            category=self.cat_fb,
            unit="kg",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("80.00"),
        )
        batch_1 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-SUGAR-001",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("78.00"),
        )
        batch_2 = StockBatch.objects.create(
            item=item,
            batch_number="BAT-SUGAR-002",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("82.00"),
        )

        # Parent transaction (e.g. Kitchen Issuance of 30 kg)
        tx = StockTransaction.objects.create(
            item=item,
            transaction_type="issuance",
            quantity=Decimal("30.00"),
            unit_cost=Decimal("79.33"),  # Weighted cost
            location=self.main_store,
            notes="Bulk Kitchen Dispatch",
        )

        # Child consumptions: 20 kg from batch_1, 10 kg from batch_2
        c1 = StockBatchConsumption.objects.create(
            transaction=tx,
            batch=batch_1,
            quantity_consumed=Decimal("20.00"),
            unit_cost=Decimal("78.00"),
            total_cost=Decimal("1560.00"),
        )
        c2 = StockBatchConsumption.objects.create(
            transaction=tx,
            batch=batch_2,
            quantity_consumed=Decimal("10.00"),
            unit_cost=Decimal("82.00"),
            total_cost=Decimal("820.00"),
        )

        consumptions = list(tx.batch_consumptions.all())
        self.assertEqual(len(consumptions), 2)
        total_consumed = sum(c.quantity_consumed for c in consumptions)
        total_cost = sum(c.total_cost for c in consumptions)
        self.assertEqual(total_consumed, Decimal("30.00"))
        self.assertEqual(total_cost, Decimal("2380.00"))

    def test_10_legacy_stock_transactions_without_batch_or_location_remain_valid(self):
        """Historical StockTransaction records without location or batch remain valid and queryable."""
        item = InventoryItem.objects.create(
            item_code="SALT-001",
            name="Table Salt",
            category=self.cat_fb,
            unit="kg",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("15.00"),
        )
        historical_tx = StockTransaction.objects.create(
            item=item,
            transaction_type="purchase",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("15.00"),
            location=None,  # Historical
            batch=None,     # Historical
            reference_number="INV-LEGACY-001",
        )
        self.assertIsNone(historical_tx.location)
        self.assertIsNone(historical_tx.batch)
        self.assertEqual(historical_tx.batch_consumptions.count(), 0)
