"""
Phase 2 Location and Stock Transfer Management Tests.
Validates:
1. StockLocation CRUD, custodian assignment, safe deactivation protection when balances exist.
2. Location-level inventory dashboard endpoint (items, valuation, batches).
3. Full Requisition -> Dispatch -> Receipt -> Breakage API workflow.
4. Separation of duties: Dispatcher cannot self-confirm receipt.
"""
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.models import (
    BatchLocationBalance,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    StockBatch,
    StockLocation,
    StockTransfer,
    Supplier,
)
from users.models import User


class LocationAndTransfersPhase2TestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="p2_admin", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.storekeeper = User.objects.create_user(
            username="p2_storekeeper", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.bar_custodian = User.objects.create_user(
            username="p2_bar_custodian", password="password123", role="kitchen", is_active=True, is_verified=True
        )

        ensure_default_accounts()

        self.category = InventoryCategory.objects.create(name="Phase 2 Beverages", category_type="f_and_b")
        self.supplier = Supplier.objects.create(name="Phase 2 Supplier")

        self.wh_location = StockLocation.objects.create(
            code="WH-CENTRAL-P2",
            name="Central Warehouse Phase 2",
            location_type="warehouse",
            custodian=self.storekeeper,
            is_active=True,
        )
        self.bar_location = StockLocation.objects.create(
            code="BAR-LOUNGE-P2",
            name="Lounge Bar Phase 2",
            location_type="bar",
            custodian=self.bar_custodian,
            is_active=True,
        )

        self.item = InventoryItem.objects.create(
            item_code="GIN-P2-01",
            name="Premium Dry Gin 750ml",
            category=self.category,
            unit="bottles",
            current_stock=Decimal("50.00"),
            opening_stock=Decimal("50.00"),
            unit_cost=Decimal("600.00"),
        )

        self.batch = StockBatch.objects.create(
            batch_number="BAT-GIN-001",
            item=self.item,
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("600.00"),
            received_date=timezone.now().date(),
            status="active",
        )

        BatchLocationBalance.objects.create(
            batch=self.batch, location=self.wh_location, quantity=Decimal("50.00")
        )
        ItemLocationBalance.objects.create(
            item=self.item, location=self.wh_location, quantity=Decimal("50.00")
        )

    def test_01_stock_location_inventory_endpoint(self):
        """Location inventory endpoint returns live stock, valuation, and batches for a location."""
        self.client.force_authenticate(user=self.storekeeper)

        url = reverse("stocklocation-location-inventory", kwargs={"pk": self.wh_location.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertEqual(data["location_code"], "WH-CENTRAL-P2")
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(Decimal(data["total_valuation"]), Decimal("30000.00"))  # 50 * 600

        item_entry = data["items"][0]
        self.assertEqual(item_entry["item_name"], "Premium Dry Gin 750ml")
        self.assertEqual(Decimal(item_entry["quantity"]), Decimal("50.00"))
        self.assertEqual(len(item_entry["batches"]), 1)
        self.assertEqual(item_entry["batches"][0]["batch_number"], "BAT-GIN-001")

    def test_02_stock_location_safe_deactivation_protection(self):
        """Deleting a location that has active balances soft-deactivates it safely instead of breaking FKs."""
        self.client.force_authenticate(user=self.admin)

        delete_url = reverse("stocklocation-detail", kwargs={"pk": self.wh_location.pk})
        res = self.client.delete(delete_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.wh_location.refresh_from_db()
        self.assertFalse(self.wh_location.is_active)  # Soft deactivated
        self.assertTrue(StockLocation.objects.filter(pk=self.wh_location.pk).exists())  # Record preserved

    def test_03_full_api_transfer_lifecycle_and_damage_reconciliation(self):
        """Requisition, dispatch, and receiving with breakage reconciliation via API endpoints."""
        # 1. Requisition: Bar custodian requests 10 bottles
        self.client.force_authenticate(user=self.bar_custodian)
        req_res = self.client.post(
            reverse("stocktransfer-list"),
            data={
                "source_location": self.wh_location.pk,
                "destination_location": self.bar_location.pk,
                "items": [{"item_id": self.item.pk, "quantity_requested": 10}],
                "notes": "Bar restock for Friday night",
            },
            format="json",
        )
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        transfer_id = req_res.data["id"]
        transfer_number = req_res.data["transfer_number"]
        self.assertEqual(req_res.data["status"], "requested")

        # 2. Dispatch: Storekeeper dispatches 10 bottles
        self.client.force_authenticate(user=self.storekeeper)
        dispatch_url = reverse("stocktransfer-dispatch-transfer", kwargs={"pk": transfer_id})
        disp_res = self.client.post(
            dispatch_url,
            data={"notes": "Dispatched via cargo trolley"},
            format="json",
        )
        self.assertEqual(disp_res.status_code, status.HTTP_200_OK)
        self.assertEqual(disp_res.data["status"], "in_transit")

        # 3. Separation of duties: Storekeeper cannot self-confirm receipt
        self.client.force_authenticate(user=self.storekeeper)
        recv_url = reverse("stocktransfer-receive-transfer", kwargs={"pk": transfer_id})
        bad_recv_res = self.client.post(
            recv_url,
            data={"items": [{"item_id": self.item.pk, "quantity_received": 10, "quantity_damaged": 0}]},
            format="json",
        )
        self.assertEqual(bad_recv_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Storekeeper who dispatched", str(bad_recv_res.data))

        # 4. Receiving: Bar custodian confirms receipt (9 intact, 1 broken)
        self.client.force_authenticate(user=self.bar_custodian)
        recv_res = self.client.post(
            recv_url,
            data={
                "notes": "1 bottle smashed during elevator transit",
                "items": [{"item_id": self.item.pk, "quantity_received": 9, "quantity_damaged": 1}],
            },
            format="json",
        )
        self.assertEqual(recv_res.status_code, status.HTTP_200_OK)
        self.assertEqual(recv_res.data["status"], "partially_received")

        # Verify balances
        wh_bal = ItemLocationBalance.objects.get(item=self.item, location=self.wh_location)
        self.assertEqual(wh_bal.quantity, Decimal("40.00"))  # 50 - 10

        bar_bal = ItemLocationBalance.objects.get(item=self.item, location=self.bar_location)
        self.assertEqual(bar_bal.quantity, Decimal("9.00"))  # 9 intact

        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("49.00"))  # 50 - 1 broken

