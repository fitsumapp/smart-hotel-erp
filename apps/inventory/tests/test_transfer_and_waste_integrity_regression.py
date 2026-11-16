"""
apps/inventory/tests/test_transfer_and_waste_integrity_regression.py

Targeted regression tests for Phase A (Stock Transfer Integrity),
Phase B (Waste and Stock Adjustment Integrity), and
Phase C (Inventory Integrity Architecture & Invariants).
"""
import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from apps.inventory.services import (
    calculate_authoritative_item_quantities,
    generate_gl_reconciliation_report,
)
from hotel.integrity import (
    approve_waste_entry,
    record_stock_change,
    record_waste_entry,
)
from hotel.models import (
    Account,
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    JournalEntry,
    StockBatch,
    StockLocation,
    StockTransaction,
    StockTransfer,
    Supplier,
)
from hotel.transfers import (
    cancel_stock_transfer,
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.models import User


class TransferAndWasteIntegrityRegressionTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="reg_admin", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.storekeeper = User.objects.create_user(
            username="reg_storekeeper", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.bar_manager = User.objects.create_user(
            username="reg_bar_mgr", password="password123", role="kitchen", is_active=True, is_verified=True
        )

        ensure_default_accounts()

        self.category = InventoryCategory.objects.create(name="Regression Beverages", category_type="f_and_b")
        self.supplier = Supplier.objects.create(name="Regression Supplier")

        self.loc_main = StockLocation.objects.create(
            code="REG-STORE-MAIN",
            name="Main Warehouse Regression",
            location_type="warehouse",
            custodian=self.storekeeper,
            is_active=True,
        )
        self.loc_bar = StockLocation.objects.create(
            code="REG-BAR-MAIN",
            name="Main Bar Regression",
            location_type="bar",
            custodian=self.bar_manager,
            is_active=True,
        )

        self.today = timezone.now().date()

    def test_01_transfer_dispatch_and_intact_receipt_balances(self):
        """Phase A: Dispatch strictly decrements source location, receipt increments destination."""
        item = InventoryItem.objects.create(
            item_code="REG-JUICE-01",
            name="Orange Juice 1L",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("60.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-REG-JUICE-01",
            item=item,
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("60.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.loc_main, quantity=Decimal("100.00"))
        ItemLocationBalance.objects.create(item=item, location=self.loc_main, quantity=Decimal("100.00"))

        # Requisition
        transfer = request_stock_transfer(
            source_location=self.loc_main,
            destination_location=self.loc_bar,
            requested_by=self.bar_manager,
            items=[{"item_id": item.id, "quantity_requested": Decimal("25.00")}],
        )
        self.assertEqual(transfer.status, "requested")

        # Dispatch
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, "in_transit")

        # Source balances decremented to 75.00
        blb_main = BatchLocationBalance.objects.get(batch=batch, location=self.loc_main)
        self.assertEqual(blb_main.quantity, Decimal("75.00"))
        ilb_main = ItemLocationBalance.objects.get(item=item, location=self.loc_main)
        self.assertEqual(ilb_main.quantity, Decimal("75.00"))

        # In-transit: company master stock and batch remain 100.00
        item.refresh_from_db()
        batch.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("100.00"))
        self.assertEqual(batch.current_quantity, Decimal("100.00"))

        # Authoritative invariant check in-transit
        qty_info = calculate_authoritative_item_quantities(item)
        self.assertEqual(Decimal(qty_info["in_transit_stock"]), Decimal("25.00"))
        self.assertEqual(Decimal(qty_info["location_stock_sum"]), Decimal("75.00"))
        self.assertEqual(Decimal(qty_info["on_hand_physical_stock"]), Decimal("100.00"))
        self.assertTrue(qty_info["is_consistent"])

        # Intact Receipt
        receive_stock_transfer(transfer_id=transfer.id, receiver=self.bar_manager)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, "completed")

        # Destination balances incremented to 25.00
        blb_bar = BatchLocationBalance.objects.get(batch=batch, location=self.loc_bar)
        self.assertEqual(blb_bar.quantity, Decimal("25.00"))
        ilb_bar = ItemLocationBalance.objects.get(item=item, location=self.loc_bar)
        self.assertEqual(ilb_bar.quantity, Decimal("25.00"))

        # Invariant after receipt: in-transit is 0, locations sum to 100.00
        qty_info_after = calculate_authoritative_item_quantities(item)
        self.assertEqual(Decimal(qty_info_after["in_transit_stock"]), Decimal("0.00"))
        self.assertEqual(Decimal(qty_info_after["location_stock_sum"]), Decimal("100.00"))
        self.assertTrue(qty_info_after["is_consistent"])

    def test_02_transfer_partial_receipt_with_breakage_and_gl_clearing(self):
        """Phase A & B: Partial receipt with transit damage writes off batch, updates GL 5010/1300."""
        item = InventoryItem.objects.create(
            item_code="REG-CORDIAL-01",
            name="Lime Cordial 1L",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("40.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-REG-CORD-01",
            item=item,
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("40.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.loc_main, quantity=Decimal("50.00"))
        ItemLocationBalance.objects.create(item=item, location=self.loc_main, quantity=Decimal("50.00"))

        transfer = request_stock_transfer(
            source_location=self.loc_main,
            destination_location=self.loc_bar,
            requested_by=self.bar_manager,
            items=[{"item_id": item.id, "quantity_requested": Decimal("10.00")}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # 8 received intact, 2 damaged in transit
        receipt_items = [
            {
                "item_id": item.id,
                "quantity_received": Decimal("8.00"),
                "quantity_damaged": Decimal("2.00"),
            }
        ]
        receive_stock_transfer(
            transfer_id=transfer.id,
            receiver=self.bar_manager,
            receipt_items=receipt_items,
            notes="2 bottles broken during trolley transit",
        )

        transfer.refresh_from_db()
        self.assertEqual(transfer.status, "partially_received")

        # Destination received exactly 8
        blb_bar = BatchLocationBalance.objects.get(batch=batch, location=self.loc_bar)
        self.assertEqual(blb_bar.quantity, Decimal("8.00"))
        ilb_bar = ItemLocationBalance.objects.get(item=item, location=self.loc_bar)
        self.assertEqual(ilb_bar.quantity, Decimal("8.00"))

        # Batch and Item reduced by 2 damaged units (from 50 to 48)
        batch.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(batch.current_quantity, Decimal("48.00"))
        self.assertEqual(item.current_stock, Decimal("48.00"))

        # GL Journal Entry posted: Dr 5010 (80.00), Cr 1300 (80.00)
        je = JournalEntry.objects.filter(description__icontains=transfer.transfer_number).first()
        self.assertIsNotNone(je)
        acc_5010 = Account.objects.get(code="5010")
        acc_1300 = Account.objects.get(code="1300")
        line_5010 = je.items.get(account=acc_5010)
        line_1300 = je.items.get(account=acc_1300)
        self.assertEqual(line_5010.amount_debit, Decimal("80.00"))
        self.assertEqual(line_1300.amount_credit, Decimal("80.00"))

        # Invariant check
        qty_info = calculate_authoritative_item_quantities(item)
        self.assertEqual(Decimal(qty_info["on_hand_physical_stock"]), Decimal("48.00"))
        self.assertEqual(Decimal(qty_info["location_stock_sum"]), Decimal("48.00"))
        self.assertTrue(qty_info["is_consistent"])

    def test_03_duplicate_dispatch_and_receive_prevention(self):
        """Phase A: State machine strictly blocks duplicate dispatch and receipt operations."""
        item = InventoryItem.objects.create(
            item_code="REG-SODA-01",
            name="Soda Can 330ml",
            category=self.category,
            unit="can",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("25.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-REG-SODA-01",
            item=item,
            initial_quantity=Decimal("30.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("25.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.loc_main, quantity=Decimal("30.00"))
        ItemLocationBalance.objects.create(item=item, location=self.loc_main, quantity=Decimal("30.00"))

        transfer = request_stock_transfer(
            source_location=self.loc_main,
            destination_location=self.loc_bar,
            requested_by=self.bar_manager,
            items=[{"item_id": item.id, "quantity_requested": Decimal("10.00")}],
        )

        # Dispatch 1
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Duplicate dispatch must fail
        with self.assertRaises(ValidationError) as ctx:
            dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        self.assertIn("expected 'requested'", str(ctx.exception))

        # Receipt 1
        receive_stock_transfer(transfer_id=transfer.id, receiver=self.bar_manager)

        # Duplicate receipt must fail
        with self.assertRaises(ValidationError) as ctx2:
            receive_stock_transfer(transfer_id=transfer.id, receiver=self.bar_manager)
        self.assertIn("expected 'in_transit'", str(ctx2.exception))

    def test_04_door_rejection_returns_stock_to_source(self):
        """Phase A: Door rejection of in-transit delivery returns stock to source balances."""
        item = InventoryItem.objects.create(
            item_code="REG-DAIRY-01",
            name="Fresh Cream 1L",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("150.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-REG-CREAM-01",
            item=item,
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("150.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.loc_main, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.loc_main, quantity=Decimal("20.00"))

        transfer = request_stock_transfer(
            source_location=self.loc_main,
            destination_location=self.loc_bar,
            requested_by=self.bar_manager,
            items=[{"item_id": item.id, "quantity_requested": Decimal("5.00")}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Door rejection
        rejected_trf = cancel_stock_transfer(
            transfer_id=transfer.id,
            user=self.bar_manager,
            reason="Door Rejection: Ambient temperature too warm",
        )
        self.assertEqual(rejected_trf.status, "rejected")

        # Source balances restored
        blb_main = BatchLocationBalance.objects.get(batch=batch, location=self.loc_main)
        ilb_main = ItemLocationBalance.objects.get(item=item, location=self.loc_main)
        self.assertEqual(blb_main.quantity, Decimal("20.00"))
        self.assertEqual(ilb_main.quantity, Decimal("20.00"))

        # Authoritative return transaction logged
        ret_tx = StockTransaction.objects.filter(
            item=item, reference_number=f"{transfer.transfer_number}-RETURN"
        ).first()
        self.assertIsNotNone(ret_tx)
        self.assertEqual(ret_tx.quantity, Decimal("5.00"))
        self.assertEqual(ret_tx.location, self.loc_main)

    def test_05_waste_recording_idempotency_and_atomic_deduction(self):
        """Phase B: Waste recording verifies idempotency, deducts stock atomically, and posts balanced GL entry."""
        item = InventoryItem.objects.create(
            item_code="REG-MILK-WASTE",
            name="Whole Milk 1L",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("50.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-REG-MILK-W1",
            item=item,
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("50.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.loc_main, quantity=Decimal("10.00"))
        ItemLocationBalance.objects.create(item=item, location=self.loc_main, quantity=Decimal("10.00"))

        # Immediate waste (cost = 100.00 < 1000.00 threshold)
        idemp_key = "REG-WASTE-KEY-001"
        rec1, created1 = record_waste_entry(
            item_id=item.id,
            entered_quantity=Decimal("2.00"),
            entered_unit="bottle",
            waste_category="food_spoilage_or_expiry",
            waste_source="direct_loss",
            idempotency_key=idemp_key,
            storage_area=self.loc_main.name,
            notes="Expired milk carton",
            logged_by_username="reg_admin",
        )
        self.assertTrue(created1)
        self.assertEqual(rec1.status, "approved")
        self.assertTrue(rec1.stock_deducted)

        # Balances decremented atomically
        item.refresh_from_db()
        batch.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("8.00"))
        self.assertEqual(batch.current_quantity, Decimal("8.00"))
        blb = BatchLocationBalance.objects.get(batch=batch, location=self.loc_main)
        ilb = ItemLocationBalance.objects.get(item=item, location=self.loc_main)
        self.assertEqual(blb.quantity, Decimal("8.00"))
        self.assertEqual(ilb.quantity, Decimal("8.00"))

        # GL entry posted
        self.assertIsNotNone(rec1.journal_entry)
        acc_5010 = Account.objects.get(code="5010")
        acc_1300 = Account.objects.get(code="1300")
        line_5010 = rec1.journal_entry.items.get(account=acc_5010)
        line_1300 = rec1.journal_entry.items.get(account=acc_1300)
        self.assertEqual(line_5010.amount_debit, Decimal("100.00"))
        self.assertEqual(line_1300.amount_credit, Decimal("100.00"))

        # Replay with same idempotency key returns existing record without duplicate stock deduction
        rec2, created2 = record_waste_entry(
            item_id=item.id,
            entered_quantity=Decimal("2.00"),
            entered_unit="bottle",
            waste_category="food_spoilage_or_expiry",
            waste_source="direct_loss",
            idempotency_key=idemp_key,
            storage_area=self.loc_main.name,
            notes="Expired milk carton",
            logged_by_username="reg_admin",
        )
        self.assertFalse(created2)
        self.assertEqual(rec1.id, rec2.id)

        # Stock must NOT be deducted again
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("8.00"))

        # Replay with different payload must fail with ValidationError
        with self.assertRaises(ValidationError) as ctx:
            record_waste_entry(
                item_id=item.id,
                entered_quantity=Decimal("5.00"),  # Changed qty
                entered_unit="bottle",
                waste_category="food_spoilage_or_expiry",
                waste_source="direct_loss",
                idempotency_key=idemp_key,
                storage_area=self.loc_main.name,
                notes="Different payload",
            )
        self.assertIn("already used for a different waste payload", str(ctx.exception))

    def test_06_gl_reconciliation_report_status_breakdown(self):
        """Phase C: GL reconciliation report segregates active, quarantined, and expired batches."""
        item = InventoryItem.objects.create(
            item_code="REG-GL-REPORT-01",
            name="Testing Item",
            category=self.category,
            unit="pcs",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("100.00"),
        )
        # Active batch
        StockBatch.objects.create(
            batch_number="BAT-GL-ACT",
            item=item,
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("100.00"),
            received_date=self.today,
            status="active",
        )
        # Quarantined batch
        StockBatch.objects.create(
            batch_number="BAT-GL-QUAR",
            item=item,
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("100.00"),
            received_date=self.today,
            status="quarantined",
        )

        rep = generate_gl_reconciliation_report()
        self.assertIn("active_batch_valuation", rep)
        self.assertIn("quarantined_batch_valuation", rep)
        self.assertIn("expired_batch_valuation", rep)
        self.assertIn("gl_vs_active_batch_variance", rep)
        self.assertGreater(Decimal(rep["active_batch_valuation"]), Decimal("0.00"))
        self.assertGreater(Decimal(rep["quarantined_batch_valuation"]), Decimal("0.00"))

