import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    Account, InventoryCategory, InventoryItem, JournalEntry,
    StockBatch, StockLocation, StockTransaction
)
from apps.finance.services import ensure_default_accounts, post_journal_entry

User = get_user_model()


class ReportingAndGLReconciliationPhase5TestCase(TestCase):
    """
    Validates Phase 5 requirements:
    1. Monthly Stock Movement Report API:
       Opening + Purchases + Transfers In - Transfers Out - Issuances - Waste +/- Adjustments = Closing Stock.
    2. Server-side valuations and aggregate summary totals.
    3. Location and category scoped reporting.
    4. Inventory Sub-ledger to General Ledger (Account 1300) Reconciliation API.
    """

    def setUp(self):
        self.client = APIClient()
        ensure_default_accounts()

        self.finance_user = User.objects.create_user(
            username="finance_officer",
            password="password123",
            role="finance",
            is_active=True,
        )
        self.inventory_mgr = User.objects.create_user(
            username="inv_controller",
            password="password123",
            role="inventory",
            is_active=True,
        )

        self.loc_main, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN", defaults={"name": "Main Central Store", "is_active": True}
        )
        self.loc_kitchen, _ = StockLocation.objects.get_or_create(
            code="KIT-MAIN", defaults={"name": "Main Kitchen", "is_active": True}
        )

        self.cat_fnb = InventoryCategory.objects.create(name="Food & Beverage", category_type="f_and_b")

        self.coffee = InventoryItem.objects.create(
            name="Yirgacheffe Coffee Beans 1kg",
            item_code="RAW-COF-01",
            category=self.cat_fnb,
            unit="kg",
            unit_cost=Decimal("350.00"),
            selling_price=Decimal("600.00"),
            opening_stock=Decimal("20.00"),
            current_stock=Decimal("20.00"),
        )

    def test_01_stock_movement_report_formula_reconciliation(self):
        """Validates that Opening + Inflows - Outflows +/- Adjustments == Closing Stock exactly."""
        today = datetime.date.today()
        first_of_month = today.replace(day=1)

        # Baseline: 20 opening stock at 350 = 7000 ETB
        # Add period transactions:
        # 1. Purchase +30 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="purchase",
            quantity=Decimal("30.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_main,
            reference_number="PO-TEST-01",
            logged_by_username="inv_controller",
        )
        # 2. Transfer In to Kitchen +10 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="transfer_in",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_kitchen,
            reference_number="TRF-01",
            logged_by_username="inv_controller",
        )
        # 3. Transfer Out from Main -10 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="transfer_out",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_main,
            reference_number="TRF-01",
            logged_by_username="inv_controller",
        )
        # 4. Issuance / Kitchen prep -12 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="issuance",
            quantity=Decimal("12.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_kitchen,
            reference_number="ISS-01",
            logged_by_username="inv_controller",
        )
        # 5. Waste / Spillage -2 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="loss",
            quantity=Decimal("2.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_kitchen,
            reference_number="WST-01",
            logged_by_username="inv_controller",
        )
        # 6. Audit adjustment +1 kg
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="adjustment",
            quantity=Decimal("1.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_main,
            reference_number="ADJ-01",
            adjustment_direction="increase",
            logged_by_username="inv_controller",
        )

        self.client.force_authenticate(user=self.finance_user)
        url = reverse("inventory-report-stock-movement")
        res = self.client.get(url, {"start_date": str(first_of_month), "end_date": str(today)})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        item_row = next(r for r in data["items"] if r["item_id"] == self.coffee.id)

        # Expected:
        # Opening: 20
        # Purchases: 30
        # Transfers In: 10
        # Transfers Out: 10
        # Issuances: 12
        # Waste: 2
        # Adjustments: +1
        # Closing: 20 + 30 + 10 - 10 - 12 - 2 + 1 = 37.00
        self.assertEqual(Decimal(item_row["opening_stock"]), Decimal("20.00"))
        self.assertEqual(Decimal(item_row["purchases"]), Decimal("30.00"))
        self.assertEqual(Decimal(item_row["transfers_in"]), Decimal("10.00"))
        self.assertEqual(Decimal(item_row["transfers_out"]), Decimal("10.00"))
        self.assertEqual(Decimal(item_row["issuances"]), Decimal("12.00"))
        self.assertEqual(Decimal(item_row["waste"]), Decimal("2.00"))
        self.assertEqual(Decimal(item_row["adjustments"]), Decimal("1.00"))
        self.assertEqual(Decimal(item_row["closing_stock"]), Decimal("37.00"))

        # Valuation check: 37 * 350 = 12950.00
        self.assertEqual(Decimal(item_row["closing_valuation"]), Decimal("12950.00"))

    def test_02_gl_reconciliation_perfect_equilibrium(self):
        """Reconciliation report returns reconciled when GL Account 1300 equals Sub-ledger Batch Valuation."""
        today = datetime.date.today()

        # Batch 1: 50 kg at 350 = 17500.00
        StockBatch.objects.create(
            batch_number="BAT-REC-01",
            item=self.coffee,
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("350.00"),
            received_date=today,
            status="active",
        )
        self.coffee.current_stock = Decimal("50.00")
        self.coffee.save(update_fields=["current_stock"])

        # Post matching GL entry: Dr 1300 / Cr 1000 for 17500.00
        post_journal_entry(
            description="Stock intake batch BAT-REC-01",
            items=[
                {"account_code": "1300", "debit": Decimal("17500.00"), "credit": Decimal("0.00")},
                {"account_code": "1000", "debit": Decimal("0.00"), "credit": Decimal("17500.00")},
            ],
        )

        self.client.force_authenticate(user=self.finance_user)
        url = reverse("inventory-report-gl-reconciliation")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertTrue(data["is_reconciled"])
        self.assertEqual(data["status"], "reconciled")
        self.assertEqual(Decimal(data["subledger_batch_valuation"]), Decimal("17500.00"))
        self.assertEqual(Decimal(data["item_master_valuation"]), Decimal("17500.00"))
        self.assertEqual(Decimal(data["general_ledger_1300_balance"]), Decimal("17500.00"))
        self.assertEqual(Decimal(data["gl_vs_subledger_variance"]), Decimal("0.00"))

    def test_03_gl_reconciliation_detects_discrepancy(self):
        """Reconciliation report correctly detects discrepancy when GL and Sub-ledger differ."""
        today = datetime.date.today()

        # Batch 1: 20 kg at 350 = 7000.00
        StockBatch.objects.create(
            batch_number="BAT-REC-DISC",
            item=self.coffee,
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("350.00"),
            received_date=today,
            status="active",
        )
        self.coffee.current_stock = Decimal("20.00")
        self.coffee.save(update_fields=["current_stock"])

        # Post mismatched GL entry: Dr 1300 for 8500.00 (1500 discrepancy)
        post_journal_entry(
            description="Mismatched inventory entry",
            items=[
                {"account_code": "1300", "debit": Decimal("8500.00"), "credit": Decimal("0.00")},
                {"account_code": "2000", "debit": Decimal("0.00"), "credit": Decimal("8500.00")},
            ],
        )

        self.client.force_authenticate(user=self.finance_user)
        url = reverse("inventory-report-gl-reconciliation")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertFalse(data["is_reconciled"])
        self.assertEqual(data["status"], "discrepancy_detected")
        self.assertEqual(Decimal(data["gl_vs_subledger_variance"]), Decimal("1500.00"))
        self.assertEqual(len(data["recent_journal_entries"]), 1)

    def test_04_movement_report_location_filtering(self):
        """Validates that movement report can be scoped specifically to a single stock location."""
        today = datetime.date.today()

        # Transaction at Main Store
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="purchase",
            quantity=Decimal("50.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_main,
            reference_number="PO-LOC-01",
            logged_by_username="inv_controller",
        )
        # Transaction at Kitchen
        StockTransaction.objects.create(
            item=self.coffee,
            transaction_type="issuance",
            quantity=Decimal("5.00"),
            unit_cost=Decimal("350.00"),
            location=self.loc_kitchen,
            reference_number="ISS-LOC-01",
            logged_by_username="inv_controller",
        )

        self.client.force_authenticate(user=self.finance_user)
        url = reverse("inventory-report-stock-movement")

        # Query only Kitchen location
        res = self.client.get(url, {"location_id": self.loc_kitchen.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data["location"]["code"], "KIT-MAIN")
        item_row = next(r for r in data["items"] if r["item_id"] == self.coffee.id)
        # In Kitchen, purchase is 0, issuance is 5
        self.assertEqual(Decimal(item_row["purchases"]), Decimal("0.00"))
        self.assertEqual(Decimal(item_row["issuances"]), Decimal("5.00"))

