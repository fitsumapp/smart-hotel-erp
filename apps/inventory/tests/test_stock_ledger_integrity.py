"""
Phase 1 Stock Ledger & Direct Mutation Integrity Tests.
Validates:
1. Bounded server-side pagination on stock ledger.
2. Filtering by item, transaction_type, location, date range, and search.
3. Stable deterministic ordering (-timestamp, -id).
4. Server-side summary statistics (inflow, outflow, adjustments, net, valuation).
5. Transfer audit trail (transfer_out at source, transfer_in at destination, loss on damage).
6. Aggregate stock reconciliation: expected_stock() matches item.current_stock across transfers and damage.
7. Rejected transfer return audit trail.
"""
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.inventory import expected_stock, reconcile_stock
from hotel.models import (
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    StockBatch,
    StockLocation,
    StockTransaction,
    Supplier,
)
from hotel.transfers import (
    cancel_stock_transfer,
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.models import User


class StockLedgerIntegrityTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ledger_admin", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.inventory_mgr = User.objects.create_user(
            username="ledger_mgr", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.chef = User.objects.create_user(
            username="ledger_chef", password="password123", role="kitchen", is_active=True, is_verified=True
        )

        ensure_default_accounts()

        self.category = InventoryCategory.objects.create(name="Ledger Test Category", category_type="f_and_b")
        self.supplier = Supplier.objects.create(name="Ledger Test Supplier")

        self.main_store = StockLocation.objects.create(
            code="STORE-MAIN-TEST", name="Main Warehouse Test", location_type="warehouse", is_active=True
        )
        self.kitchen_store = StockLocation.objects.create(
            code="KITCHEN-MAIN-TEST", name="Kitchen Pantry Test", location_type="kitchen", is_active=True
        )

        self.item = InventoryItem.objects.create(
            item_code="LEDGER-OIL-01",
            name="Olive Oil Extra Virgin 5L",
            category=self.category,
            unit="liters",
            current_stock=Decimal("100.00"),
            opening_stock=Decimal("100.00"),
            unit_cost=Decimal("300.00"),
        )

        self.batch = StockBatch.objects.create(
            batch_number="BAT-OIL-001",
            item=self.item,
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("300.00"),
            received_date=timezone.now().date(),
            status="active",
        )

        BatchLocationBalance.objects.create(
            batch=self.batch, location=self.main_store, quantity=Decimal("100.00")
        )
        ItemLocationBalance.objects.create(
            item=self.item, location=self.main_store, quantity=Decimal("100.00")
        )

    def test_01_stock_ledger_pagination_and_deterministic_ordering(self):
        """Stock ledger endpoints enforce bounded pagination and -timestamp, -id ordering."""
        self.client.force_authenticate(user=self.inventory_mgr)

        # Create 55 transactions to exceed page_size (50)
        transactions = []
        for i in range(55):
            transactions.append(
                StockTransaction(
                    item=self.item,
                    transaction_type="adjustment",
                    quantity=Decimal("1.00"),
                    unit_cost=Decimal("300.00"),
                    adjustment_direction="increase",
                    location=self.main_store,
                    reference_number=f"ADJ-TEST-{i:03d}",
                    notes=f"Test transaction batch #{i}",
                    logged_by_username="ledger_mgr",
                )
            )
        StockTransaction.objects.bulk_create(transactions)

        url = reverse("stocktransaction-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertGreaterEqual(data["count"], 55)
        self.assertEqual(len(data["results"]), 50)  # Capped at page_size=50

        # Verify deterministic ordering: IDs strictly descending
        results = data["results"]
        ids = [tx["id"] for tx in results]
        self.assertEqual(ids, sorted(ids, reverse=True))

        # Test page 2
        res_p2 = self.client.get(f"{url}?page=2")
        self.assertEqual(res_p2.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_p2.data["results"]), 5)

        # Test unpaginated override param
        res_unpaginated = self.client.get(f"{url}?paginate=false")
        self.assertEqual(res_unpaginated.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_unpaginated.data, list)
        self.assertGreaterEqual(len(res_unpaginated.data), 55)

    def test_02_stock_ledger_query_filtering(self):
        """Stock ledger supports filtering by location, transaction_type, date range, and text search."""
        self.client.force_authenticate(user=self.inventory_mgr)

        # Transaction 1: Main store purchase
        stx1 = StockTransaction.objects.create(
            item=self.item,
            transaction_type="purchase",
            quantity=Decimal("20.00"),
            unit_cost=Decimal("300.00"),
            location=self.main_store,
            reference_number="INV-ALPHA-99",
            notes="Morning shipment from supplier",
            logged_by_username="ledger_mgr",
        )

        # Transaction 2: Kitchen store issuance
        stx2 = StockTransaction.objects.create(
            item=self.item,
            transaction_type="issuance",
            quantity=Decimal("5.00"),
            unit_cost=Decimal("300.00"),
            location=self.kitchen_store,
            reference_number="DISP-BETA-01",
            notes="Chef prep dispatch",
            logged_by_username="ledger_mgr",
        )

        url = reverse("stocktransaction-list")

        # Filter by location
        res_loc = self.client.get(f"{url}?location={self.kitchen_store.id}")
        self.assertEqual(res_loc.status_code, status.HTTP_200_OK)
        results = res_loc.data["results"]
        self.assertTrue(all(tx["location"] == self.kitchen_store.id for tx in results))
        self.assertTrue(any(tx["id"] == stx2.id for tx in results))
        self.assertFalse(any(tx["id"] == stx1.id for tx in results))

        # Filter by search string
        res_search = self.client.get(f"{url}?search=ALPHA")
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        results_s = res_search.data["results"]
        self.assertTrue(any(tx["id"] == stx1.id for tx in results_s))
        self.assertFalse(any(tx["id"] == stx2.id for tx in results_s))

        # Filter by transaction_type
        res_type = self.client.get(f"{url}?transaction_type=purchase")
        self.assertEqual(res_type.status_code, status.HTTP_200_OK)
        self.assertTrue(all(tx["transaction_type"] == "purchase" for tx in res_type.data["results"]))

    def test_03_stock_ledger_summary_action(self):
        """Summary action computes server-side totals for filtered transactions."""
        self.client.force_authenticate(user=self.inventory_mgr)

        StockTransaction.objects.create(
            item=self.item,
            transaction_type="purchase",
            quantity=Decimal("30.00"),
            unit_cost=Decimal("100.00"),
            location=self.main_store,
        )
        StockTransaction.objects.create(
            item=self.item,
            transaction_type="issuance",
            quantity=Decimal("10.00"),
            unit_cost=Decimal("100.00"),
            location=self.main_store,
        )

        summary_url = reverse("stocktransaction-summary")
        res = self.client.get(f"{summary_url}?item={self.item.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertEqual(data["total_count"], 2)
        self.assertEqual(Decimal(data["total_inflow_qty"]), Decimal("30.00"))
        self.assertEqual(Decimal(data["total_outflow_qty"]), Decimal("10.00"))
        self.assertEqual(Decimal(data["net_quantity_change"]), Decimal("20.00"))
        self.assertEqual(Decimal(data["total_valuation"]), Decimal("4000.00"))  # (30*100) + (10*100)

    def test_04_transfer_creates_audit_trail_and_reconciles_cleanly(self):
        """Stock transfer records transfer_out at source, transfer_in at dest, loss on breakage, and reconciles perfectly."""
        # 1. Requisition 20 liters from Main Store to Kitchen
        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.chef,
            items=[{"item_id": self.item.id, "quantity_requested": 20}],
            notes="Dinner service transfer",
        )

        # 2. Dispatch
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.inventory_mgr)

        # Verify transfer_out transaction was recorded
        stx_out = StockTransaction.objects.filter(
            transaction_type="transfer_out", reference_number=transfer.transfer_number
        ).first()
        self.assertIsNotNone(stx_out)
        self.assertEqual(stx_out.quantity, Decimal("20.00"))
        self.assertEqual(stx_out.location, self.main_store)
        self.assertEqual(stx_out.item, self.item)

        # 3. Receive with 2 units damaged, 18 received intact
        receive_stock_transfer(
            transfer_id=transfer.id,
            receiver=self.admin,
            receipt_items=[{"item_id": self.item.id, "quantity_received": 18, "quantity_damaged": 2}],
            notes="2 liters leaked in transit",
        )

        # Verify transfer_in transaction was recorded for dispatched arrival
        stx_in = StockTransaction.objects.filter(
            transaction_type="transfer_in", reference_number=transfer.transfer_number
        ).first()
        self.assertIsNotNone(stx_in)
        self.assertEqual(stx_in.quantity, Decimal("20.00"))
        self.assertEqual(stx_in.location, self.kitchen_store)

        # Verify loss transaction was recorded
        stx_loss = StockTransaction.objects.filter(
            transaction_type="loss", reference_number=f"{transfer.transfer_number}-DAMAGE"
        ).first()
        self.assertIsNotNone(stx_loss)
        self.assertEqual(stx_loss.quantity, Decimal("2.00"))
        self.assertEqual(stx_loss.location, self.kitchen_store)

        # Verify expected_stock() matches item.current_stock exactly!
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("98.00"))  # 100 - 2 damaged
        expected = expected_stock(self.item)
        self.assertEqual(expected, self.item.current_stock)

        # reconcile_stock returns 0 mismatches
        mismatches = reconcile_stock(repair=False)
        self.assertEqual(len(mismatches), 0)

    def test_05_cancelled_in_transit_transfer_returns_stock_with_audit(self):
        """Cancelling an in-transit transfer logs a transfer_in return transaction to source."""
        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.chef,
            items=[{"item_id": self.item.id, "quantity_requested": 15}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.inventory_mgr)

        cancel_stock_transfer(transfer_id=transfer.id, user=self.admin, reason="Delivery truck broke down")

        # Verify transfer_in return transaction
        stx_return = StockTransaction.objects.filter(
            transaction_type="transfer_in", reference_number=f"{transfer.transfer_number}-RETURN"
        ).first()
        self.assertIsNotNone(stx_return)
        self.assertEqual(stx_return.quantity, Decimal("15.00"))
        self.assertEqual(stx_return.location, self.main_store)

        # Balances at main store restored
        bal = ItemLocationBalance.objects.get(item=self.item, location=self.main_store)
        self.assertEqual(bal.quantity, Decimal("100.00"))

        # Aggregate stock reconciles cleanly
        self.item.refresh_from_db()
        self.assertEqual(expected_stock(self.item), self.item.current_stock)

