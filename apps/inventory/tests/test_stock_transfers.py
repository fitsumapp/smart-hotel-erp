"""
Phase 1.3 Stock Transfer Management & In-Transit Custody Tests.
Validates requisition, dispatch with FEFO/FIFO source balance lock,
destination receipt, breakage/damage write-off with GL JV posting,
separation of duties, door rejections, and API endpoints.
"""
import datetime
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
    InventoryWasteRecord,
    ItemLocationBalance,
    JournalEntry,
    StockBatch,
    StockLocation,
    StockTransfer,
    StockTransferItem,
    Supplier,
)
from hotel.transfers import (
    cancel_stock_transfer,
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.models import User


class StockTransferTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_trf", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.storekeeper = User.objects.create_user(
            username="storekeeper_trf", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.kitchen_chef = User.objects.create_user(
            username="chef_trf", password="password123", role="kitchen", is_active=True, is_verified=True
        )

        # 2. Setup Category & Supplier
        self.category, _ = InventoryCategory.objects.get_or_create(
            name="Transfer Test Cat", defaults={"category_type": "f_and_b"}
        )
        self.supplier, _ = Supplier.objects.get_or_create(
            name="Transfer Test Supplier", defaults={"phone": "+251911334455"}
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

    def test_01_request_stock_transfer(self):
        """Requisition creates transfer in 'requested' state without touching balances."""
        item = InventoryItem.objects.create(
            item_code="TRF-ITEM-01",
            name="Cooking Oil 5L",
            category=self.category,
            unit="liters",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("250.00"),
        )
        # Seed balance at source store
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 15}],
            notes="Urgent requisition for lunch service",
        )

        self.assertEqual(transfer.status, "requested")
        self.assertEqual(transfer.requested_by, self.kitchen_chef)
        self.assertEqual(transfer.items.count(), 1)
        trf_item = transfer.items.first()
        self.assertEqual(trf_item.quantity_requested, Decimal("15.00"))
        self.assertEqual(trf_item.quantity_dispatched, Decimal("0.00"))

        # Balances untouched
        source_bal = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(source_bal.quantity, Decimal("100.00"))
        dest_bal = ItemLocationBalance.objects.filter(item=item, location=self.kitchen_store).first()
        self.assertIsNone(dest_bal)

    def test_02_dispatch_stock_transfer_fefo_source_deduction(self):
        """Dispatch selects batch via FEFO, decrements source location balance, and sets status to in_transit."""
        item = InventoryItem.objects.create(
            item_code="TRF-PERISH-01",
            name="Fresh Cream",
            category=self.category,
            unit="liters",
            is_perishable=True,
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("120.00"),
        )

        # Create two batches at STORE-MAIN: Batch A expires sooner, Batch B expires later
        batch_a = StockBatch.objects.create(
            batch_number="BAT-CREAM-EARLY",
            item=item,
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("110.00"),
            received_date=self.today - datetime.timedelta(days=3),
            expiry_date=self.today + datetime.timedelta(days=5),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_a, location=self.main_store, quantity=Decimal("20.00"))

        batch_b = StockBatch.objects.create(
            batch_number="BAT-CREAM-LATE",
            item=item,
            initial_quantity=Decimal("30.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("125.00"),
            received_date=self.today - datetime.timedelta(days=1),
            expiry_date=self.today + datetime.timedelta(days=15),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_b, location=self.main_store, quantity=Decimal("30.00"))

        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("50.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 12}],
        )

        # Dispatch by storekeeper
        dispatched_trf = dispatch_stock_transfer(
            transfer_id=transfer.id,
            dispatcher=self.storekeeper,
            notes="Dispatched 12L via runner",
        )

        self.assertEqual(dispatched_trf.status, "in_transit")
        self.assertEqual(dispatched_trf.dispatched_by, self.storekeeper)
        self.assertIsNotNone(dispatched_trf.dispatched_at)

        trf_item = dispatched_trf.items.first()
        self.assertEqual(trf_item.quantity_dispatched, Decimal("12.00"))
        # FEFO selected Batch A (earliest expiry)
        self.assertEqual(trf_item.batch, batch_a)
        self.assertEqual(trf_item.unit_cost, Decimal("110.00"))

        # Source balances decremented
        blb_a = BatchLocationBalance.objects.get(batch=batch_a, location=self.main_store)
        self.assertEqual(blb_a.quantity, Decimal("8.00"))  # 20 - 12
        ilb_source = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(ilb_source.quantity, Decimal("38.00"))  # 50 - 12

        # Aggregate item stock is NOT decremented yet (in transit within the hotel)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("50.00"))

    def test_03_receive_stock_transfer_intact(self):
        """Receipt at destination increments destination balances with exact batch layers."""
        item = InventoryItem.objects.create(
            item_code="TRF-RICE-01",
            name="Basmati Rice 25kg",
            category=self.category,
            unit="kilograms",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("150.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-RICE-01",
            item=item,
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("150.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("100.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 25}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Separation of duties: Storekeeper cannot confirm receipt
        with self.assertRaises(ValidationError) as ctx:
            receive_stock_transfer(
                transfer_id=transfer.id,
                receiver=self.storekeeper,
            )
        self.assertIn("cannot confirm receipt", str(ctx.exception))

        # Destination custodian confirms receipt
        received_trf = receive_stock_transfer(
            transfer_id=transfer.id,
            receiver=self.kitchen_chef,
            notes="Received intact at kitchen receiving bay",
        )

        self.assertEqual(received_trf.status, "completed")
        self.assertEqual(received_trf.received_by, self.kitchen_chef)

        # Destination balances incremented
        blb_dest = BatchLocationBalance.objects.get(batch=batch, location=self.kitchen_store)
        self.assertEqual(blb_dest.quantity, Decimal("25.00"))

        ilb_dest = ItemLocationBalance.objects.get(item=item, location=self.kitchen_store)
        self.assertEqual(ilb_dest.quantity, Decimal("25.00"))

        # Aggregate stock remains 100.00
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("100.00"))

    def test_04_receive_stock_transfer_partial_with_breakage_waste_and_gl(self):
        """Partial receipt with breakage auto-creates waste record and posts GL journal entry."""
        item = InventoryItem.objects.create(
            item_code="TRF-WINE-01",
            name="Cabernet Sauvignon 750ml",
            category=self.category,
            unit="bottles",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("800.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-WINE-01",
            item=item,
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("800.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("20.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("20.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.bar_store,
            requested_by=self.admin,
            items=[{"item_id": item.id, "quantity_requested": 10}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Receiver notes: 8 received intact, 2 broken in transit
        receipt_items = [
            {
                "item_id": item.id,
                "quantity_received": 8,
                "quantity_damaged": 2,
            }
        ]

        received_trf = receive_stock_transfer(
            transfer_id=transfer.id,
            receiver=self.admin,
            receipt_items=receipt_items,
            notes="2 bottles broken during trolley transit",
        )

        self.assertEqual(received_trf.status, "partially_received")

        # Destination balance: exactly 8 bottles
        blb_dest = BatchLocationBalance.objects.get(batch=batch, location=self.bar_store)
        self.assertEqual(blb_dest.quantity, Decimal("8.00"))

        # Aggregate stock and batch current_quantity reduced by 2 bottles
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("18.00"))  # 20 - 2

        batch.refresh_from_db()
        self.assertEqual(batch.current_quantity, Decimal("18.00"))

        # Waste record created
        trf_item = received_trf.items.first()
        self.assertIsNotNone(trf_item.waste_record)
        waste = trf_item.waste_record
        self.assertEqual(waste.base_quantity, Decimal("2.00"))
        self.assertEqual(waste.unit_cost_snapshot, Decimal("800.00"))
        self.assertEqual(waste.total_cost_loss, Decimal("1600.00"))
        self.assertEqual(waste.waste_category, "breakage_or_damage")
        self.assertTrue(waste.stock_deducted)

        # GL Journal Entry posted: Dr 5010 (1600.00), Cr 1300 (1600.00)
        spoilage_acct = Account.objects.get(code="5010")
        inventory_acct = Account.objects.get(code="1300")
        je = JournalEntry.objects.filter(description__icontains=transfer.transfer_number).first()
        self.assertIsNotNone(je)
        debit_line = je.items.filter(account=spoilage_acct).first()
        credit_line = je.items.filter(account=inventory_acct).first()
        self.assertIsNotNone(debit_line)
        self.assertIsNotNone(credit_line)
        self.assertEqual(debit_line.amount_debit, Decimal("1600.00"))
        self.assertEqual(credit_line.amount_credit, Decimal("1600.00"))

    def test_05_reconciliation_mismatch_validation(self):
        """Received + Damaged must strictly equal Dispatched quantity, else fail atomically."""
        item = InventoryItem.objects.create(
            item_code="TRF-ITEM-MISMATCH",
            name="Salt 1kg",
            category=self.category,
            unit="packs",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("20.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-SALT-01",
            item=item,
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("20.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("50.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("50.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 10}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Dispatched was 10. Received 7 + Damaged 1 = 8 != 10
        with self.assertRaises(ValidationError) as ctx:
            receive_stock_transfer(
                transfer_id=transfer.id,
                receiver=self.kitchen_chef,
                receipt_items=[{"item_id": item.id, "quantity_received": 7, "quantity_damaged": 1}],
            )
        self.assertIn("Quantity reconciliation mismatch", str(ctx.exception))

        # Status remains in_transit
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, "in_transit")

    def test_06_cancel_requested_transfer(self):
        """Cancelling a requested transfer changes status to cancelled with zero balance impact."""
        item = InventoryItem.objects.create(
            item_code="TRF-CANCEL-01",
            name="Paper Towels",
            category=self.category,
            unit="packs",
            current_stock=Decimal("30.00"),
            unit_cost=Decimal("50.00"),
        )
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("30.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 5}],
        )

        cancelled_trf = cancel_stock_transfer(
            transfer_id=transfer.id,
            user=self.kitchen_chef,
            reason="Ordered by mistake",
        )

        self.assertEqual(cancelled_trf.status, "cancelled")
        self.assertEqual(cancelled_trf.rejection_reason, "Ordered by mistake")
        source_bal = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(source_bal.quantity, Decimal("30.00"))

    def test_07_door_rejection_in_transit_returns_stock_to_source(self):
        """Rejecting an in-transit delivery returns stock back to source store balances."""
        item = InventoryItem.objects.create(
            item_code="TRF-REJECT-01",
            name="Fresh Fish Fillet",
            category=self.category,
            unit="kilograms",
            is_perishable=True,
            current_stock=Decimal("40.00"),
            unit_cost=Decimal("350.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-FISH-01",
            item=item,
            initial_quantity=Decimal("40.00"),
            current_quantity=Decimal("40.00"),
            unit_cost=Decimal("350.00"),
            received_date=self.today,
            expiry_date=self.today + datetime.timedelta(days=3),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("40.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("40.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 15}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Source balances were decremented to 25
        blb_source = BatchLocationBalance.objects.get(batch=batch, location=self.main_store)
        self.assertEqual(blb_source.quantity, Decimal("25.00"))

        # Receiving kitchen rejects delivery at door (e.g. wrong temperature)
        rejected_trf = cancel_stock_transfer(
            transfer_id=transfer.id,
            user=self.kitchen_chef,
            reason="Rejected: Temperature breach during transport",
        )

        self.assertEqual(rejected_trf.status, "rejected")
        self.assertEqual(rejected_trf.rejection_reason, "Rejected: Temperature breach during transport")

        # Source balances restored back to 40
        blb_source.refresh_from_db()
        self.assertEqual(blb_source.quantity, Decimal("40.00"))
        ilb_source = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(ilb_source.quantity, Decimal("40.00"))

    def test_08_insufficient_source_stock_prevent_dispatch(self):
        """Dispatching more stock than available at source must fail with ValidationError."""
        item = InventoryItem.objects.create(
            item_code="TRF-LOW-01",
            name="Vanilla Extract",
            category=self.category,
            unit="liters",
            current_stock=Decimal("2.00"),
            unit_cost=Decimal("500.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-VANILLA-01",
            item=item,
            initial_quantity=Decimal("2.00"),
            current_quantity=Decimal("2.00"),
            unit_cost=Decimal("500.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("2.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("2.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 5}],
        )

        with self.assertRaises(ValidationError) as ctx:
            dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        self.assertIn("Insufficient stock", str(ctx.exception))

    def test_09_expired_or_quarantined_batches_blocked_from_dispatch(self):
        """Expired or quarantined batches at source location cannot be allocated for dispatch."""
        item = InventoryItem.objects.create(
            item_code="TRF-EXPIRED-01",
            name="Yogurt 1L",
            category=self.category,
            unit="liters",
            is_perishable=True,
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("80.00"),
        )
        # Expired batch
        batch_exp = StockBatch.objects.create(
            batch_number="BAT-YOG-EXP",
            item=item,
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("80.00"),
            received_date=self.today - datetime.timedelta(days=10),
            expiry_date=self.today - datetime.timedelta(days=1),  # Expired yesterday
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch_exp, location=self.main_store, quantity=Decimal("10.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("10.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.kitchen_chef,
            items=[{"item_id": item.id, "quantity_requested": 5}],
        )

        with self.assertRaises(ValidationError) as ctx:
            dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        self.assertIn("Insufficient valid, unexpired stock", str(ctx.exception))

    def test_10_api_transfer_lifecycle_endpoints(self):
        """Test DRF REST API transfer request, dispatch, and receive actions."""
        item = InventoryItem.objects.create(
            item_code="TRF-API-01",
            name="Granulated Sugar 50kg",
            category=self.category,
            unit="kilograms",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("90.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-SUGAR-01",
            item=item,
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("90.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("100.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("100.00"))

        # 1. API Request
        self.client.force_authenticate(user=self.kitchen_chef)
        req_res = self.client.post(
            "/api/users/transfers/",
            {
                "source_location": self.main_store.id,
                "destination_location": self.kitchen_store.id,
                "notes": "API test transfer",
                "items": [{"item_id": item.id, "quantity_requested": 20}],
            },
            format="json",
        )
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        trf_id = req_res.data["id"]
        self.assertEqual(req_res.data["status"], "requested")
        self.assertEqual(req_res.data["requested_by_username"], self.kitchen_chef.username)

        # 2. API Dispatch by Storekeeper
        self.client.force_authenticate(user=self.storekeeper)
        disp_res = self.client.post(
            f"/api/users/transfers/{trf_id}/dispatch/",
            {"notes": "Dispatched via API"},
            format="json",
        )
        self.assertEqual(disp_res.status_code, status.HTTP_200_OK)
        self.assertEqual(disp_res.data["status"], "in_transit")
        self.assertEqual(disp_res.data["dispatched_by_username"], self.storekeeper.username)

        # 3. API Receive by Kitchen Chef
        self.client.force_authenticate(user=self.kitchen_chef)
        recv_res = self.client.post(
            f"/api/users/transfers/{trf_id}/receive/",
            {"notes": "Received via API"},
            format="json",
        )
        self.assertEqual(recv_res.status_code, status.HTTP_200_OK)
        self.assertEqual(recv_res.data["status"], "completed")
        self.assertEqual(recv_res.data["received_by_username"], self.kitchen_chef.username)

    def test_11_immutable_stock_transfer_prevention(self):
        """Modifying completed transfer or deleting any transfer is strictly forbidden."""
        item = InventoryItem.objects.create(
            item_code="TRF-IMMUTABLE-01",
            name="Ground Coffee 1kg",
            category=self.category,
            unit="packs",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("300.00"),
        )
        batch = StockBatch.objects.create(
            batch_number="BAT-COFFEE-01",
            item=item,
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("300.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("10.00"))
        ItemLocationBalance.objects.create(item=item, location=self.main_store, quantity=Decimal("10.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.bar_store,
            requested_by=self.admin,
            items=[{"item_id": item.id, "quantity_requested": 5}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        receive_stock_transfer(transfer_id=transfer.id, receiver=self.admin)

        self.client.force_authenticate(user=self.admin)

        # Attempt to delete transfer -> 405 Method Not Allowed
        del_res = self.client.delete(f"/api/users/transfers/{transfer.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Attempt to PUT modify completed transfer -> 400 Bad Request
        put_res = self.client.put(
            f"/api/users/transfers/{transfer.id}/",
            {"notes": "Trying to modify after completion"},
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_400_BAD_REQUEST)
