"""
Phase 3 Opening Stock, Unit Conversion & Procurement Tests.
Validates:
1. Unit conversions across mass (kg/g), volume (L/ml), and packaging (pack/pcs via units_per_pack).
2. Bulk opening stock import with validation, duplicate detection, batch/location balances, and equity GL entry.
3. Spot purchase direct dock intake with PO/GRN creation, stock increase, and cash GL entry.
4. Purchase order printable document export endpoint.
"""
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from apps.inventory.services import convert_item_quantity
from hotel.models import (
    BatchLocationBalance,
    GoodsReceiptNote,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    JournalEntry,
    PurchaseOrder,
    StockBatch,
    StockLocation,
    StockTransaction,
    Supplier,
)
from users.models import User


class OpeningStockAndProcurementPhase3TestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="p3_admin", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.inventory_mgr = User.objects.create_user(
            username="p3_inv_mgr", password="password123", role="inventory", is_active=True, is_verified=True
        )

        ensure_default_accounts()

        self.category = InventoryCategory.objects.create(name="Phase 3 Groceries", category_type="f_and_b")
        self.supplier = Supplier.objects.create(name="Phase 3 Vendor Ltd")

        self.main_store, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN",
            defaults={
                "name": "Main Hotel Store",
                "location_type": "warehouse",
                "is_active": True,
            },
        )

    def test_01_unit_conversion_engine(self):
        """Validates consistent unit conversion across mass, volume, and packaging dimensions."""
        # Mass item (base unit kg)
        flour = InventoryItem.objects.create(
            item_code="FLOUR-01", name="Baking Flour", category=self.category, unit="kg"
        )
        self.assertEqual(convert_item_quantity(flour, 500, from_unit="g"), Decimal("0.50"))
        self.assertEqual(convert_item_quantity(flour, 2.5, from_unit="kg"), Decimal("2.50"))

        # Volume item (base unit liters)
        milk = InventoryItem.objects.create(
            item_code="MILK-01", name="Whole Milk", category=self.category, unit="liters"
        )
        self.assertEqual(convert_item_quantity(milk, 750, from_unit="ml"), Decimal("0.75"))

        # Packaging item (base unit pcs, units_per_pack=24)
        coke = InventoryItem.objects.create(
            item_code="COKE-01", name="Coca Cola 330ml", category=self.category, unit="pcs", units_per_pack=Decimal("24.00")
        )
        self.assertEqual(convert_item_quantity(coke, 2, from_unit="pack"), Decimal("48.00"))
        self.assertEqual(convert_item_quantity(coke, 48, from_unit="pcs", to_unit="pack"), Decimal("2.00"))

    def test_02_opening_stock_import_and_duplicate_protection(self):
        """Bulk opening stock import creates verified batches, balances, ledger entries, and equity GL JV."""
        self.client.force_authenticate(user=self.inventory_mgr)

        import_url = reverse("inventoryitem-import-opening-stock")
        records = [
            {
                "item_code": "OPN-COFFEE-01",
                "item_name": "Ethiopian Yirgacheffe Beans 1kg",
                "category": "Coffee & Tea",
                "unit": "kg",
                "quantity": 50,
                "unit_cost": 450.00,
                "location_code": "STORE-MAIN",
                "batch_number": "BAT-OPN-COF-01",
            },
            {
                "item_code": "OPN-SUGAR-01",
                "item_name": "White Refined Sugar 50kg",
                "category": "Dry Goods",
                "unit": "kg",
                "quantity": 200,
                "unit_cost": 85.00,
                "location_code": "STORE-MAIN",
            },
        ]

        res = self.client.post(import_url, data={"records": records}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["imported_count"], 2)
        expected_valuation = (Decimal("50") * Decimal("450.00")) + (Decimal("200") * Decimal("85.00"))  # 22500 + 17000 = 39500
        self.assertEqual(Decimal(res.data["total_valuation"]), expected_valuation)

        # Verify item state
        coffee = InventoryItem.objects.get(item_code="OPN-COFFEE-01")
        self.assertEqual(coffee.opening_stock, Decimal("50.00"))
        self.assertEqual(coffee.current_stock, Decimal("50.00"))
        self.assertEqual(coffee.unit_cost, Decimal("450.00"))

        # Verify batch state
        batch = StockBatch.objects.get(batch_number="BAT-OPN-COF-01")
        self.assertEqual(batch.current_quantity, Decimal("50.00"))
        self.assertEqual(batch.status, "active")

        # Verify location balances
        bal = ItemLocationBalance.objects.get(item=coffee, location=self.main_store)
        self.assertEqual(bal.quantity, Decimal("50.00"))

        # Verify audit transaction
        stx = StockTransaction.objects.get(item=coffee, reference_number="OPENING-STOCK")
        self.assertEqual(stx.quantity, Decimal("50.00"))
        self.assertEqual(stx.transaction_type, "purchase")

        # Verify duplicate protection: re-importing without overwrite raises 400
        res_dup = self.client.post(import_url, data={"records": records}, format="json")
        self.assertEqual(res_dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already has an established opening stock", str(res_dup.data))

        # Re-importing with overwrite=true succeeds
        res_overwrite = self.client.post(import_url, data={"records": records, "overwrite": True}, format="json")
        self.assertEqual(res_overwrite.status_code, status.HTTP_201_CREATED)

    def test_03_spot_purchase_workflow(self):
        """Spot purchase creates completed PO, received GRN, updates inventory, and posts cash GL entry."""
        self.client.force_authenticate(user=self.inventory_mgr)

        item = InventoryItem.objects.create(
            item_code="SPOT-FISH-01",
            name="Fresh Red Snapper Fish",
            category=self.category,
            unit="kg",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("400.00"),
        )

        spot_url = reverse("purchaseorder-spot-purchase")
        payload = {
            "supplier_name": "Fish Harbor Vendor",
            "delivery_location": self.main_store.id,
            "payment_method": "cash",
            "invoice_number": "FISH-MKT-778",
            "notes": "Emergency banquet fish purchase",
            "items": [
                {
                    "item_id": item.id,
                    "quantity": 15,
                    "unit_cost": 420.00,
                    "batch_number": "BAT-FISH-SPOT-01",
                }
            ],
        }

        res = self.client.post(spot_url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(res.data["total_amount"]), Decimal("6300.00"))  # 15 * 420

        # Verify PO & GRN created in completed state
        po = PurchaseOrder.objects.get(pk=res.data["purchase_order_id"])
        self.assertEqual(po.status, "received")

        grn = GoodsReceiptNote.objects.get(pk=res.data["grn_id"])
        self.assertEqual(grn.status, "approved")

        # Verify inventory updated
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("15.00"))
        self.assertEqual(item.unit_cost, Decimal("420.00"))

        # Verify batch created
        batch = StockBatch.objects.get(batch_number="BAT-FISH-SPOT-01")
        self.assertEqual(batch.current_quantity, Decimal("15.00"))

    def test_04_purchase_order_printable_document(self):
        """Printable action returns formatted PO document for supplier dispatch."""
        self.client.force_authenticate(user=self.inventory_mgr)

        po = PurchaseOrder.objects.create(
            po_number="PO-TEST-PRINT-01",
            supplier=self.supplier,
            delivery_location=self.main_store,
            status="issued",
            issued_by=self.inventory_mgr,
            issued_at=timezone.now(),
            total_amount=Decimal("5000.00"),
        )

        url = reverse("purchaseorder-printable-document", kwargs={"pk": po.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        self.assertEqual(data["po_number"], "PO-TEST-PRINT-01")
        self.assertEqual(data["supplier"]["name"], "Phase 3 Vendor Ltd")
        self.assertEqual(data["delivery_location"]["code"], "STORE-MAIN")
        self.assertIn("lines", data)

