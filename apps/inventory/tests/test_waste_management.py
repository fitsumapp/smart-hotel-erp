from decimal import Decimal
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import (
    Account,
    AuditEvent,
    InventoryCategory,
    InventoryItem,
    InventoryWasteRecord,
    JournalEntry,
    StockTransaction,
    Supplier,
    SystemSettings,
)
from users.models import User
from hotel.integrity import record_stock_change


class InventoryWasteManagementTestCase(APITestCase):
    def setUp(self):
        # Settings
        self.settings_obj, _ = SystemSettings.objects.get_or_create(
            id=1,
            defaults={"waste_approval_threshold": Decimal("1000.00")}
        )
        self.settings_obj.waste_approval_threshold = Decimal("1000.00")
        self.settings_obj.module_pos = True
        self.settings_obj.save()

        # Users
        self.admin = User.objects.create_user(
            username="admin-waste-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.second_admin = User.objects.create_user(
            username="second-admin-waste-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.superuser = User.objects.create_superuser(
            username="superuser-waste-test",
            password="test-password",
            email="super@example.com",
            role=User.ADMIN,
            is_active=True,
        )
        self.inventory_mgr = User.objects.create_user(
            username="inventory-waste-test",
            password="test-password",
            role=User.INVENTORY,
            is_active=True,
        )
        self.waiter = User.objects.create_user(
            username="waiter-waste-test",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )

        # Inventory Category & Supplier
        self.category = InventoryCategory.objects.create(
            name="Raw Food & Vegetables",
            category_type="food",
        )
        self.beverage_category = InventoryCategory.objects.create(
            name="Beverages",
            category_type="beverage",
        )
        self.supplier = Supplier.objects.create(name="Fresh Farms Ltd")

        # Items
        # 1. Tomato (kg)
        self.tomato = InventoryItem.objects.create(
            item_code="ING-TOMATO",
            name="Fresh Tomatoes",
            category=self.category,
            unit="kg",
            current_stock=Decimal("50.00"),
            min_reorder_level=Decimal("10.00"),
            unit_cost=Decimal("30.00"),
            last_supplier=self.supplier,
            units_per_pack=Decimal("1.00"),
        )
        # 2. Milk (l)
        self.milk = InventoryItem.objects.create(
            item_code="ING-MILK",
            name="Fresh Whole Milk",
            category=self.category,
            unit="l",
            current_stock=Decimal("20.00"),
            min_reorder_level=Decimal("5.00"),
            unit_cost=Decimal("50.00"),
            last_supplier=self.supplier,
            units_per_pack=Decimal("1.00"),
        )
        # 3. Beer Bottles (bottle, 24 per pack)
        self.beer = InventoryItem.objects.create(
            item_code="BEV-BEER",
            name="Premium Beer",
            category=self.beverage_category,
            unit="bottle",
            current_stock=Decimal("120.00"),
            min_reorder_level=Decimal("24.00"),
            unit_cost=Decimal("45.00"),
            last_supplier=self.supplier,
            units_per_pack=Decimal("24.00"),
        )

    def test_direct_loss_stock_deduction_and_ledger(self):
        """Direct stock loss immediately deducts current_stock and posts transaction & GL entry."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        payload = {
            "item": self.tomato.id,
            "entered_quantity": "5.00",
            "entered_unit": "kg",
            "waste_category": "food_spoilage_or_expiry",
            "waste_source": "direct_loss",
            "storage_area": "Cold Room A",
            "notes": "Rotten tomatoes identified during morning audit",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "KEY-DIRECT-001"}

        response = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.data
        self.assertEqual(data["stock_deducted"], True)
        self.assertEqual(Decimal(str(data["base_quantity"])), Decimal("5.00"))
        self.assertEqual(Decimal(str(data["total_cost_loss"])), Decimal("150.00"))  # 5 * 30.00

        # Stock deduction verification
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("45.00"))

        # StockTransaction verification
        stx_id = data["stock_transaction"]
        stx = StockTransaction.objects.get(id=stx_id)
        self.assertEqual(stx.transaction_type, "loss")
        self.assertEqual(stx.quantity, Decimal("5.00"))
        self.assertEqual(stx.destination_dept, "Cold Room A")

        # Journal Entry verification (Debit 5000, Credit 1300)
        self.assertIsNotNone(data["journal_entry"])
        je = JournalEntry.objects.get(id=data["journal_entry"])
        items = list(je.items.all())
        self.assertEqual(len(items), 2)
        debit_item = next(it for it in items if it.account.code == "5000")
        credit_item = next(it for it in items if it.account.code == "1300")
        self.assertEqual(debit_item.amount_debit, Decimal("150.00"))
        self.assertEqual(credit_item.amount_credit, Decimal("150.00"))

    def test_direct_loss_insufficient_stock(self):
        """Direct stock loss fails atomically if entered quantity exceeds current_stock."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        payload = {
            "item": self.tomato.id,
            "entered_quantity": "55.00",  # Available is 50.00
            "entered_unit": "kg",
            "waste_category": "spillage",
            "waste_source": "direct_loss",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "KEY-INSUFFICIENT-001"}

        response = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Insufficient stock", response.data["error"])

        # Verify no stock was deducted
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("50.00"))
        self.assertFalse(InventoryWasteRecord.objects.filter(idempotency_key="KEY-INSUFFICIENT-001").exists())

    def test_kitchen_preparation_waste_no_store_deduction(self):
        """Kitchen preparation waste records against an issuance without deducting warehouse stock."""
        # 1. Issue 10 kg of tomatoes to Kitchen
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("10.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
            logged_by_username=self.inventory_mgr.username,
        )
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("40.00"))

        # 2. Record prep waste against this issuance
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        payload = {
            "item": self.tomato.id,
            "entered_quantity": "1.50",
            "entered_unit": "kg",
            "waste_category": "unissued_prep_loss",
            "waste_source": "kitchen_prep_waste",
            "source_dispatch": issuance_stx.id,
            "notes": "Tomato peeling and bad seed trimming",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "KEY-PREP-001"}

        response = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["stock_deducted"], False)
        self.assertIsNone(data["stock_transaction"])
        self.assertIsNone(data["journal_entry"])  # Kitchen issuance already expensed

        # Verify warehouse stock remains 40.00 kg (no secondary deduction)
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("40.00"))

    def test_kitchen_prep_waste_ceiling_enforcement(self):
        """Cumulative prep waste cannot exceed the parent issuance quantity."""
        # Issue 5 kg
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("5.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
            logged_by_username=self.inventory_mgr.username,
        )

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # First waste: 3 kg (succeeds)
        resp1 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "3.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-CEIL-001",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Second waste: 2.50 kg (fails, remaining is 2.00 kg)
        resp2 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "2.50",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-CEIL-002",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds issued quantity", resp2.data["error"])

        # Third waste: 2.00 kg (succeeds, reaches exactly 5.00 kg)
        resp3 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "2.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-CEIL-003",
        )
        self.assertEqual(resp3.status_code, status.HTTP_201_CREATED)

        # Fourth waste: 0.10 kg (fails, ceiling reached)
        resp4 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "0.10",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-CEIL-004",
        )
        self.assertEqual(resp4.status_code, status.HTTP_400_BAD_REQUEST)

    def test_uom_mass_and_volume_conversions(self):
        """Test unit conversions: g -> kg and ml -> l."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 1. Tomato: 500 grams -> 0.50 kg
        resp1 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "500",
                "entered_unit": "g",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-UOM-G",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp1.data["base_quantity"])), Decimal("0.50"))
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("49.50"))

        # 2. Milk: 250 ml -> 0.25 L
        resp2 = self.client.post(
            url,
            data={
                "item": self.milk.id,
                "entered_quantity": "250",
                "entered_unit": "ml",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-UOM-ML",
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp2.data["base_quantity"])), Decimal("0.25"))
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.current_stock, Decimal("19.75"))

    def test_uom_pack_multiplier_conversion(self):
        """Test pack to bottle conversion using item.units_per_pack."""
        self.beer.unit_cost = Decimal("15.00")
        self.beer.save()
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # Beer: 2 packs = 48 bottles (since units_per_pack = 24), cost = 48 * 15 = 720 ETB (< 1000 ETB)
        resp = self.client.post(
            url,
            data={
                "item": self.beer.id,
                "entered_quantity": "2",
                "entered_unit": "pack",
                "waste_category": "breakage_or_damage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-UOM-PACK",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp.data["base_quantity"])), Decimal("48.00"))
        self.beer.refresh_from_db()
        self.assertEqual(self.beer.current_stock, Decimal("72.00"))  # 120 - 48

    def test_incompatible_uom_conversion_rejected(self):
        """Attempting to convert mass to volume (kg to ml) or undefined pack raises HTTP 400."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # Tomato (unit='kg') with entered_unit='ml'
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "100",
                "entered_unit": "ml",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-INCOMPAT-001",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Incompatible unit", resp.data["error"])

    def test_idempotency_exact_replay_vs_payload_conflict(self):
        """Exact replay returns HTTP 200 with existing record; altered payload returns HTTP 409."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        payload1 = {
            "item": self.tomato.id,
            "entered_quantity": "2.00",
            "entered_unit": "kg",
            "waste_category": "spillage",
            "waste_source": "direct_loss",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "KEY-IDEMP-TEST-99"}

        # First request: 201 Created
        resp1 = self.client.post(url, data=payload1, format="json", **headers)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        created_id = resp1.data["id"]

        # Replay identical request: 200 OK with same record
        resp2 = self.client.post(url, data=payload1, format="json", **headers)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["id"], created_id)

        # Verify stock was only deducted once (50 - 2 = 48)
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("48.00"))

        # Altered payload with same idempotency key: 409 Conflict
        payload_conflict = {
            "item": self.tomato.id,
            "entered_quantity": "4.00",  # Changed quantity
            "entered_unit": "kg",
            "waste_category": "spillage",
            "waste_source": "direct_loss",
        }
        resp3 = self.client.post(url, data=payload_conflict, format="json", **headers)
        self.assertEqual(resp3.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already used for a different waste payload", resp3.data["error"])

    def test_direct_loss_reversal_workflow(self):
        """Reversing a direct loss restores current_stock and posts reversing journal entry."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 1. Create direct loss of 5 kg
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "5.00",
                "entered_unit": "kg",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-REV-FLOW-01",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        waste_id = resp.data["id"]

        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("45.00"))

        # 2. Reverse the waste entry
        rev_url = reverse("wasterecord-reverse", kwargs={"pk": waste_id})
        rev_resp = self.client.post(rev_url, data={"reason": "Incorrect item was selected by auditor"}, format="json")
        self.assertEqual(rev_resp.status_code, status.HTTP_201_CREATED)

        # Verify original record is marked reversed
        orig_record = InventoryWasteRecord.objects.get(id=waste_id)
        self.assertTrue(orig_record.is_reversed)
        self.assertEqual(orig_record.reversal_reason, "Incorrect item was selected by auditor")
        self.assertIsNotNone(orig_record.reversed_at)

        # Verify stock was restored to 50.00 kg
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("50.00"))

        # Verify reversal record was created
        rev_data = rev_resp.data
        self.assertEqual(rev_data["reversal_of"], waste_id)
        self.assertTrue(rev_data["is_reversed"])

        # Verify reversing Journal Entry exists (Debit 1300, Credit 5000)
        self.assertIsNotNone(rev_data["journal_entry"])
        rev_je = JournalEntry.objects.get(id=rev_data["journal_entry"])
        self.assertEqual(rev_je.reversal_of_id, orig_record.journal_entry_id)
        debit_line = rev_je.items.get(account__code="1300")
        credit_line = rev_je.items.get(account__code="5000")
        self.assertEqual(debit_line.amount_debit, Decimal("150.00"))
        self.assertEqual(credit_line.amount_credit, Decimal("150.00"))

        # 3. Duplicate reversal attempt must be rejected
        dup_resp = self.client.post(rev_url, data={"reason": "Trying duplicate reversal"}, format="json")
        self.assertEqual(dup_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been reversed", dup_resp.data["error"])

    def test_kitchen_prep_waste_reversal_frees_ceiling(self):
        """Reversing kitchen prep waste frees the ceiling on the parent issuance."""
        # 1. Issue 4 kg
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("4.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
            logged_by_username=self.inventory_mgr.username,
        )

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 2. Record 4 kg prep waste (consumes full ceiling)
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "4.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-REV-01",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        waste_id = resp.data["id"]

        # Any further waste fails
        resp_fail = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "1.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-REV-FAIL",
        )
        self.assertEqual(resp_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Reverse the 4 kg prep waste
        rev_url = reverse("wasterecord-reverse", kwargs={"pk": waste_id})
        rev_resp = self.client.post(rev_url, data={"reason": "Entered under wrong recipe"}, format="json")
        self.assertEqual(rev_resp.status_code, status.HTTP_201_CREATED)

        # 4. Now a new prep waste of 2.50 kg succeeds because ceiling is freed
        resp_retry = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "2.50",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-REV-RETRY",
        )
        self.assertEqual(resp_retry.status_code, status.HTTP_201_CREATED)

    def test_permission_enforcement(self):
        """Unauthorized roles cannot record or reverse waste."""
        # Waiter attempting to record waste
        self.client.force_authenticate(user=self.waiter)
        url = reverse("wasterecord-list")
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "1.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PERM-01",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Phase 2: Threshold and Valuation Tests ───────────────────────────────

    def test_loss_below_threshold_auto_approved(self):
        """Loss below ETB 1,000 is auto-approved with immediate stock and accounting mutation."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 10 kg @ 30.00 ETB = 300.00 ETB (< 1000.00)
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "10.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-BELOW-1000",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "approved")
        self.assertEqual(resp.data["stock_deducted"], True)
        self.assertIsNotNone(resp.data["stock_transaction"])
        self.assertIsNotNone(resp.data["journal_entry"])
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("40.00"))

    def test_loss_at_exact_threshold_auto_approved(self):
        """Loss of exactly ETB 1,000.00 is auto-approved (strictly greater required for review)."""
        # Set tomato stock to 100 kg, unit cost to 25.00 ETB: 40 kg * 25.00 = 1000.00 ETB
        self.tomato.current_stock = Decimal("100.00")
        self.tomato.unit_cost = Decimal("25.00")
        self.tomato.save()

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",
                "entered_unit": "kg",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-EXACT-1000",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "approved")
        self.assertEqual(resp.data["stock_deducted"], True)
        self.assertEqual(Decimal(str(resp.data["total_cost_loss"])), Decimal("1000.00"))
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("60.00"))

    def test_loss_above_threshold_pending_review(self):
        """Loss strictly greater than ETB 1,000 is held as pending_review without stock or GL mutation."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 40 kg @ 30.00 ETB = 1,200.00 ETB (> 1000.00)
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",
                "entered_unit": "kg",
                "waste_category": "breakage_or_damage",
                "waste_source": "direct_loss",
                "notes": "Large batch spoiled in cold room compressor failure",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-ABOVE-1000",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending_review")
        self.assertEqual(resp.data["stock_deducted"], False)
        self.assertIsNone(resp.data["stock_transaction"])
        self.assertIsNone(resp.data["journal_entry"])

        # Warehouse stock MUST remain unchanged
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("50.00"))

    def test_zero_cost_item_pending_review_without_fabricated_entries(self):
        """Positive-quantity waste for items with zero unit cost requires review regardless of threshold."""
        salt = InventoryItem.objects.create(
            item_code="ING-SALT",
            name="Table Salt",
            category=self.category,
            unit="kg",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("0.00"),
            last_supplier=self.supplier,
        )

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        resp = self.client.post(
            url,
            data={
                "item": salt.id,
                "entered_quantity": "10.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-ZERO-COST-01",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending_review")
        self.assertEqual(resp.data["stock_deducted"], False)
        self.assertIsNone(resp.data["stock_transaction"])
        self.assertIsNone(resp.data["journal_entry"])
        salt.refresh_from_db()
        self.assertEqual(salt.current_stock, Decimal("100.00"))

    def test_cannot_approve_zero_cost_without_valid_cost(self):
        """Approving a zero-cost waste record is stopped until a valid unit cost is provided."""
        salt = InventoryItem.objects.create(
            item_code="ING-SALT-2",
            name="Cooking Salt",
            category=self.category,
            unit="kg",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("0.00"),
            last_supplier=self.supplier,
        )
        self.client.force_authenticate(user=self.inventory_mgr)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": salt.id,
                "entered_quantity": "5.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-ZERO-COST-APPR",
        )
        waste_id = create_resp.data["id"]

        # Admin attempts to approve while unit cost is still 0
        self.client.force_authenticate(user=self.second_admin)
        appr_resp = self.client.post(reverse("wasterecord-approve", kwargs={"pk": waste_id}), format="json")
        self.assertEqual(appr_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("has no valid unit cost", appr_resp.data["error"])

        # Update item unit cost in inventory
        salt.unit_cost = Decimal("15.00")
        salt.save()

        # Now approval succeeds and applies real accounting
        appr_resp2 = self.client.post(reverse("wasterecord-approve", kwargs={"pk": waste_id}), format="json")
        self.assertEqual(appr_resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(appr_resp2.data["status"], "approved")
        self.assertEqual(Decimal(str(appr_resp2.data["total_cost_loss"])), Decimal("75.00"))  # 5 * 15
        salt.refresh_from_db()
        self.assertEqual(salt.current_stock, Decimal("95.00"))

    def test_configured_threshold_change(self):
        """Configuring SystemSettings waste_approval_threshold adjusts the approval threshold dynamically."""
        self.settings_obj.waste_approval_threshold = Decimal("2000.00")
        self.settings_obj.save()

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 50 kg @ 30 = 1500 ETB. Below 2000 -> auto-approved!
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "50.00",
                "entered_unit": "kg",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-THRESH-CHANGE",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "approved")
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("0.00"))

    # ── Phase 2: Approval and Rejection Lifecycle Tests ───────────────────────

    def test_authorized_approval_processes_stock_and_accounting_once(self):
        """Authorized approval executes stock deduction and accounting exactly once."""
        self.client.force_authenticate(user=self.inventory_mgr)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",  # 40 * 30 = 1200 ETB (> 1000)
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-APPR-ONCE",
        )
        waste_id = create_resp.data["id"]
        self.assertEqual(create_resp.data["status"], "pending_review")

        # Approve by second admin
        self.client.force_authenticate(user=self.second_admin)
        appr_url = reverse("wasterecord-approve", kwargs={"pk": waste_id})
        appr_resp = self.client.post(appr_url, format="json")
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(appr_resp.data["status"], "approved")
        self.assertEqual(appr_resp.data["reviewed_by_username"], self.second_admin.username)
        self.assertIsNotNone(appr_resp.data["reviewed_at"])

        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("10.00"))  # 50 - 40

        # Repeated approval attempt fails
        repeat_resp = self.client.post(appr_url, format="json")
        self.assertEqual(repeat_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already 'approved'", repeat_resp.data["error"])
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("10.00"))

    def test_rejection_leaves_stock_and_accounting_unchanged(self):
        """Rejection records reason and leaves stock balances and GL entries untouched."""
        self.client.force_authenticate(user=self.inventory_mgr)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-REJECT-TEST",
        )
        waste_id = create_resp.data["id"]

        self.client.force_authenticate(user=self.second_admin)
        reject_url = reverse("wasterecord-reject", kwargs={"pk": waste_id})

        # Missing rejection reason fails
        empty_reason_resp = self.client.post(reject_url, data={"reason": ""}, format="json")
        self.assertEqual(empty_reason_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rejection reason is required", empty_reason_resp.data["error"])

        # Rejection with valid reason succeeds
        reject_resp = self.client.post(
            reject_url,
            data={"reason": "Physical inspection confirmed tomatoes are clean and usable"},
            format="json"
        )
        self.assertEqual(reject_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_resp.data["status"], "rejected")
        self.assertEqual(reject_resp.data["rejection_reason"], "Physical inspection confirmed tomatoes are clean and usable")
        self.assertEqual(reject_resp.data["reviewed_by_username"], self.second_admin.username)

        # Stock is completely intact
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("50.00"))

        # Repeated rejection attempt fails
        repeat_resp = self.client.post(reject_url, data={"reason": "Repeat"}, format="json")
        self.assertEqual(repeat_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already 'rejected'", repeat_resp.data["error"])

    def test_self_approval_and_rejection_prohibited_for_ordinary_admin(self):
        """An ordinary administrator cannot approve or reject their own waste submission."""
        self.client.force_authenticate(user=self.admin)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "45.00",
                "entered_unit": "kg",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-SELF-PROHIBIT",
        )
        waste_id = create_resp.data["id"]

        # Self-approval attempt
        self.client.force_authenticate(user=self.admin)
        appr_resp = self.client.post(reverse("wasterecord-approve", kwargs={"pk": waste_id}), format="json")
        self.assertEqual(appr_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("independent administrator review is required", appr_resp.data["error"])

        # Self-rejection attempt
        rej_resp = self.client.post(
            reverse("wasterecord-reject", kwargs={"pk": waste_id}),
            data={"reason": "Self reject attempt"},
            format="json"
        )
        self.assertEqual(rej_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("independent administrator review is required", rej_resp.data["error"])

    def test_superuser_self_approval_exception_with_audit_trail(self):
        """Superuser may self-approve under explicit auditable exception."""
        self.client.force_authenticate(user=self.superuser)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "45.00",
                "entered_unit": "kg",
                "waste_category": "food_spoilage_or_expiry",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-SUPER-SELF",
        )
        waste_id = create_resp.data["id"]

        # Superuser self-approves with justification
        appr_resp = self.client.post(
            reverse("wasterecord-approve", kwargs={"pk": waste_id}),
            data={"justification": "Night audit emergency reconciliation"},
            format="json"
        )
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(appr_resp.data["status"], "approved")
        self.assertEqual(appr_resp.data["is_self_reviewed"], True)
        self.assertEqual(appr_resp.data["self_review_justification"], "Night audit emergency reconciliation")

        # Verify persistent AuditEvent entry
        audit_event = AuditEvent.objects.filter(
            entity_type="InventoryWasteRecord",
            entity_id=str(waste_id),
            action="inventory_waste.self_review_exception"
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.superuser)
        self.assertEqual(audit_event.client_metadata.get("self_approval_exception"), True)
        self.assertEqual(audit_event.client_metadata.get("decision"), "approved")

    def test_superuser_self_rejection_exception_with_audit_trail(self):
        """Superuser may self-reject under explicit auditable exception."""
        self.client.force_authenticate(user=self.superuser)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "45.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-SUPER-REJ",
        )
        waste_id = create_resp.data["id"]

        rej_resp = self.client.post(
            reverse("wasterecord-reject", kwargs={"pk": waste_id}),
            data={
                "reason": "Mistaken submission during training session",
                "justification": "Superuser correction of own training test entry"
            },
            format="json"
        )
        self.assertEqual(rej_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(rej_resp.data["status"], "rejected")
        self.assertEqual(rej_resp.data["is_self_reviewed"], True)

        # AuditEvent verified
        audit_event = AuditEvent.objects.filter(
            entity_type="InventoryWasteRecord",
            entity_id=str(waste_id),
            action="inventory_waste.self_review_exception"
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.client_metadata.get("self_rejection_exception"), True)

    def test_approval_failure_due_to_interim_stock_consumption_rolls_back(self):
        """If stock is consumed between submission and approval, approval fails and rolls back."""
        self.client.force_authenticate(user=self.inventory_mgr)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-INTERIM-FAIL",
        )
        waste_id = create_resp.data["id"]

        # Consume 30 kg in the interim (leaving only 20 kg available)
        record_stock_change(
            item_id=self.tomato.id,
            transaction_type="loss",
            quantity=Decimal("30.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Other Department",
        )
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("20.00"))

        # Admin tries to approve the 40 kg waste
        self.client.force_authenticate(user=self.second_admin)
        appr_resp = self.client.post(reverse("wasterecord-approve", kwargs={"pk": waste_id}), format="json")
        self.assertEqual(appr_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Insufficient stock", appr_resp.data["error"])

        # Record remains pending_review, stock remains 20.00 kg
        waste_rec = InventoryWasteRecord.objects.get(id=waste_id)
        self.assertEqual(waste_rec.status, "pending_review")
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("20.00"))

    def test_cannot_reverse_pending_or_rejected_waste(self):
        """Pending and rejected waste records cannot be reversed."""
        self.client.force_authenticate(user=self.inventory_mgr)
        create_resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "40.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-REV-GUARD",
        )
        waste_id = create_resp.data["id"]

        # Attempt to reverse pending record
        self.client.force_authenticate(user=self.admin)
        rev_url = reverse("wasterecord-reverse", kwargs={"pk": waste_id})
        rev_resp = self.client.post(rev_url, data={"reason": "premature reversal"}, format="json")
        self.assertEqual(rev_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only approved records can be reversed", rev_resp.data["error"])

        # Reject it
        self.client.force_authenticate(user=self.second_admin)
        self.client.post(reverse("wasterecord-reject", kwargs={"pk": waste_id}), data={"reason": "Rejected"}, format="json")

        # Attempt to reverse rejected record
        rev_resp2 = self.client.post(rev_url, data={"reason": "reversing rejected"}, format="json")
        self.assertEqual(rev_resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only approved records can be reversed", rev_resp2.data["error"])

    # ── Phase 2: Kitchen Preparation Waste Reservation Tests ──────────────────

    def test_pending_kitchen_waste_reserves_issuance_quantity(self):
        """Pending kitchen preparation waste reserves issuance quantity against concurrent submissions."""
        # 1. Issue 10 kg of tomatoes to Kitchen
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("10.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
        )

        # 2. Submit 7 kg prep waste (> 1000 ETB, so pending_review)
        # 7 kg * 30 = 210.00 ETB (wait, 7 * 30 = 210, let's make unit cost 200 ETB so 7 * 200 = 1400 ETB)
        self.tomato.unit_cost = Decimal("200.00")
        self.tomato.save()

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")
        resp1 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "7.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-RES-01",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp1.data["status"], "pending_review")

        # 3. Competing submission for 4 kg prep waste against same issuance (7 + 4 = 11 > 10)
        resp2 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "4.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-RES-02",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds issued quantity", resp2.data["error"])

    def test_rejected_kitchen_waste_releases_reservation(self):
        """Rejecting a pending kitchen waste record releases its reservation on the issuance."""
        self.tomato.unit_cost = Decimal("200.00")
        self.tomato.save()
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("10.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
        )

        self.client.force_authenticate(user=self.inventory_mgr)
        resp1 = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "7.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-REJ-REL",
        )
        waste_id = resp1.data["id"]

        # Reject the 7 kg reservation
        self.client.force_authenticate(user=self.second_admin)
        self.client.post(
            reverse("wasterecord-reject", kwargs={"pk": waste_id}),
            data={"reason": "Excessive trim reported, rejected"},
            format="json"
        )

        # Now 4 kg submission succeeds because reservation was released!
        self.client.force_authenticate(user=self.inventory_mgr)
        resp2 = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "4.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-AFTER-REJ",
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

    def test_kitchen_prep_waste_never_deducts_warehouse_stock_or_duplicates_gl(self):
        """Even upon approval of kitchen preparation waste, warehouse stock is never deducted."""
        self.tomato.unit_cost = Decimal("200.00")
        self.tomato.save()
        # Initial stock: 50. Issue 10 -> warehouse stock is 40.
        _, issuance_stx = record_stock_change(
            item_id=self.tomato.id,
            transaction_type="issuance",
            quantity=Decimal("10.00"),
            unit_cost=self.tomato.unit_cost,
            destination_dept="Main Kitchen",
        )
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("40.00"))

        # Submit 6 kg prep waste
        self.client.force_authenticate(user=self.inventory_mgr)
        resp = self.client.post(
            reverse("wasterecord-list"),
            data={
                "item": self.tomato.id,
                "entered_quantity": "6.00",
                "entered_unit": "kg",
                "waste_category": "unissued_prep_loss",
                "waste_source": "kitchen_prep_waste",
                "source_dispatch": issuance_stx.id,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREP-NO-STORE",
        )
        waste_id = resp.data["id"]

        # Approve by second admin
        self.client.force_authenticate(user=self.second_admin)
        appr_resp = self.client.post(reverse("wasterecord-approve", kwargs={"pk": waste_id}), format="json")
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(appr_resp.data["status"], "approved")
        self.assertEqual(appr_resp.data["stock_deducted"], False)
        self.assertIsNone(appr_resp.data["stock_transaction"])
        self.assertIsNone(appr_resp.data["journal_entry"])

        # Warehouse stock remains 40.00 kg! No double deduction.
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("40.00"))

    # ── Phase 2: Quantity Precision Tests ────────────────────────────────────

    def test_precision_reject_excess_decimals(self):
        """Quantities with precision exceeding supported 0.01 resolution (e.g. 0.333 kg) are rejected."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "0.333",  # 3 decimal places
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREC-0333",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds supported precision of 2 decimal places", resp.data["error"])
        self.tomato.refresh_from_db()
        self.assertEqual(self.tomato.current_stock, Decimal("50.00"))

    def test_precision_reject_unrepresentable_gram_conversion(self):
        """Grams that do not convert cleanly to 0.01 kg (e.g. 333 g = 0.333 kg) are rejected."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "333",  # 333 / 1000 = 0.333 kg
                "entered_unit": "g",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREC-333G",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("results in fractional precision beyond supported 0.01 kg", resp.data["error"])

    def test_precision_accept_valid_precision(self):
        """Valid quantities adhering to 0.01 kg resolution (0.25 kg and 250 g) are accepted."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 0.25 kg
        resp1 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "0.25",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREC-025",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp1.data["base_quantity"])), Decimal("0.25"))

        # 250 g (= 0.25 kg)
        resp2 = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "250",
                "entered_unit": "g",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PREC-250G",
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp2.data["base_quantity"])), Decimal("0.25"))

    def test_precision_reject_fractional_discrete_units(self):
        """Discrete units (pcs, bottle) reject non-integer quantities."""
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 1.5 bottle
        resp = self.client.post(
            url,
            data={
                "item": self.beer.id,
                "entered_quantity": "1.5",
                "entered_unit": "bottle",
                "waste_category": "breakage_or_damage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-FRAC-BOTTLE",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be a whole number", resp.data["error"])

    def test_precision_pack_discrete_conversion(self):
        """Packs for discrete items must yield whole item quantities."""
        self.beer.unit_cost = Decimal("10.00")
        self.beer.save()
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # 0.5 pack of 24 bottles = 12 bottles -> whole number -> accepted!
        resp1 = self.client.post(
            url,
            data={
                "item": self.beer.id,
                "entered_quantity": "0.5",
                "entered_unit": "pack",
                "waste_category": "breakage_or_damage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PACK-HALF",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(resp1.data["base_quantity"])), Decimal("12.00"))

        # 0.33 pack of 24 bottles = 7.92 bottles -> non-integer -> rejected!
        resp2 = self.client.post(
            url,
            data={
                "item": self.beer.id,
                "entered_quantity": "0.33",
                "entered_unit": "pack",
                "waste_category": "breakage_or_damage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-PACK-FRAC",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not result in a whole number of items", resp2.data["error"])

    # ── Phase 2: Product Configurations ──────────────────────────────────────

    def test_inventory_only_mode_with_pos_disabled(self):
        """In inventory-only mode (module_pos=False), waste operations work without POS dependencies."""
        self.settings_obj.module_pos = False
        self.settings_obj.save()

        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("wasterecord-list")

        # Recording waste operates completely independently of POS
        resp = self.client.post(
            url,
            data={
                "item": self.tomato.id,
                "entered_quantity": "5.00",
                "entered_unit": "kg",
                "waste_category": "spillage",
                "waste_source": "direct_loss",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="KEY-INV-ONLY-01",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "approved")

        # Listing waste records
        list_resp = self.client.get(url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(list_resp.data) >= 1)

    def test_waste_record_model_default_status_pending_review_prevents_bypass(self):
        """
        Regression Test for DEFECT: InventoryWasteRecord.status default must be 'pending_review'.
        Direct model instantiation without explicit status must fail-safe to 'pending_review'
        so that records cannot bypass manager review.
        """
        from uuid import uuid4
        rec = InventoryWasteRecord.objects.create(
            idempotency_key=f"DEFECT-REGRESSION-{uuid4().hex[:10]}",
            payload_hash="testhash",
            item=self.tomato,
            entered_quantity=Decimal("50.00"),
            entered_unit="kg",
            base_quantity=Decimal("50.00"),
            waste_category="spillage",
            waste_source="direct_loss",
            unit_cost_snapshot=Decimal("100.00"),
            total_cost_loss=Decimal("5000.00"),  # Above threshold of 1000 ETB
            reported_by_username="test_waiter",
        )
        # Must fail-safe to pending_review, NOT approved
        self.assertEqual(rec.status, "pending_review")
        self.assertFalse(rec.stock_deducted)
        self.assertIsNone(rec.reviewed_by)
        self.assertIsNone(rec.reviewed_at)
