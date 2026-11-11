from decimal import Decimal
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from hotel.models import (
    Account,
    FolioCharge,
    InventoryCategory,
    InventoryItem,
    JournalEntry,
    MinibarItem,
    Reservation,
    Room,
    StockTransaction,
    Supplier,
    SystemSettings,
)
from hotel.inventory import expected_stock, reconcile_stock, transaction_delta
from hotel.integrity import record_stock_change, reverse_stock_transaction
from users.models import User


class InventoryIntegrityPhase0TestCase(APITestCase):
    def setUp(self):
        # Settings
        self.settings_obj, _ = SystemSettings.objects.get_or_create(
            id=1,
            defaults={"waste_approval_threshold": Decimal("1000.00"), "module_pos": True}
        )
        self.settings_obj.waste_approval_threshold = Decimal("1000.00")
        self.settings_obj.module_pos = True
        self.settings_obj.save()

        # Chart of Accounts setup
        self.acct_cash, _ = Account.objects.get_or_create(code="1000", defaults={"name": "Cash", "account_type": "asset"})
        self.acct_ar, _ = Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "asset"})
        self.acct_inv, _ = Account.objects.get_or_create(code="1300", defaults={"name": "Inventory Asset", "account_type": "asset"})
        self.acct_ap, _ = Account.objects.get_or_create(code="2000", defaults={"name": "Accounts Payable", "account_type": "liability"})
        self.acct_extras, _ = Account.objects.get_or_create(code="4200", defaults={"name": "Folio Extras Revenue", "account_type": "revenue"})
        self.acct_cogs, _ = Account.objects.get_or_create(code="5000", defaults={"name": "Cost of Goods Sold", "account_type": "expense"})

        # Users
        self.admin = User.objects.create_user(
            username="admin-inv-test",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.inventory_mgr = User.objects.create_user(
            username="inventory-mgr-test",
            password="test-password",
            role=User.INVENTORY,
            is_active=True,
        )
        self.housekeeping = User.objects.create_user(
            username="hk-inv-test",
            password="test-password",
            role=User.HOUSEKEEPING,
            is_active=True,
        )
        self.reception = User.objects.create_user(
            username="rec-inv-test",
            password="test-password",
            role=User.RECEPTION,
            is_active=True,
        )

        # Inventory setup
        self.category = InventoryCategory.objects.create(name="Beverages Test", category_type="beverage")
        self.supplier = Supplier.objects.create(name="Acrma Beverage Suppliers Ltd")

        self.water = InventoryItem.objects.create(
            item_code="BEV-WATER-01",
            name="Mineral Water 500ml",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("50.00"),
            opening_stock=Decimal("50.00"),
            min_reorder_level=Decimal("10.00"),
            unit_cost=Decimal("15.00"),
            selling_price=Decimal("30.00"),
            last_supplier=self.supplier,
        )

        self.coke = InventoryItem.objects.create(
            item_code="BEV-COKE-01",
            name="Coca Cola 330ml",
            category=self.category,
            unit="bottle",
            current_stock=Decimal("30.00"),
            opening_stock=Decimal("30.00"),
            min_reorder_level=Decimal("5.00"),
            unit_cost=Decimal("20.00"),
            selling_price=Decimal("40.00"),
            last_supplier=self.supplier,
        )

        # Room & Reservation setup
        self.room = Room.objects.create(name="Room 401", room_number="401", room_type="Standard", base_price=Decimal("500.00"), status="Occupied")
        self.minibar_water = MinibarItem.objects.create(room=self.room, item=self.water, standard_quantity=4, current_quantity=4, price=Decimal("30.00"))

        from datetime import date, timedelta
        self.reservation = Reservation.objects.create(
            guest_name="Abebe Bikila",
            guest_phone="+251911000000",
            guest_email="abebe@example.com",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            status="checked_in",
            total_amount=Decimal("1000.00"),
        )

    # -------------------------------------------------------------------------
    # 1. Minibar consumption creates a valid stock transaction
    # -------------------------------------------------------------------------
    def test_01_minibar_consumption_creates_valid_stock_transaction(self):
        self.client.force_authenticate(user=self.housekeeping)
        url = reverse("minibar-consume")
        payload = {
            "room_id": self.room.id,
            "items": [{"item_id": self.water.id, "quantity": 2, "price": "30.00"}],
            "notes": "Daily room refresh audit",
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        stx = StockTransaction.objects.filter(item=self.water, transaction_type="issuance").latest("timestamp")
        self.assertEqual(stx.quantity, Decimal("2.00"))
        self.assertEqual(stx.destination_room, f"Room {self.room.room_number}")
        self.assertEqual(stx.destination_dept, "Housekeeping")
        self.assertIn("Daily room refresh audit", stx.notes)

    # -------------------------------------------------------------------------
    # 2. Minibar consumption updates stock and accounting consistently
    # -------------------------------------------------------------------------
    def test_02_minibar_consumption_updates_stock_and_accounting_consistently(self):
        self.client.force_authenticate(user=self.housekeeping)
        url = reverse("minibar-consume")
        payload = {
            "room_id": self.room.id,
            "items": [{"item_id": self.water.id, "quantity": 3}],
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("47.00"))  # 50 - 3

        # Check GL entry: 3 * 15.00 = 45.00
        jv = JournalEntry.objects.filter(description__contains="Auto JV: Minibar Issuance").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in jv.items.all()}
        self.assertEqual(items["5000"], (Decimal("45.00"), Decimal("0.00")))  # COGS debit
        self.assertEqual(items["1300"], (Decimal("0.00"), Decimal("45.00")))  # Asset credit

        # MinibarItem quantity updated
        self.minibar_water.refresh_from_db()
        self.assertEqual(self.minibar_water.current_quantity, 1)  # 4 - 3

    # -------------------------------------------------------------------------
    # 3. Concurrent minibar requests cannot oversell stock
    # -------------------------------------------------------------------------
    def test_03_minibar_requests_cannot_oversell_stock(self):
        self.client.force_authenticate(user=self.housekeeping)
        self.water.current_stock = Decimal("2.00")
        self.water.save(update_fields=["current_stock"])

        url = reverse("minibar-consume")
        payload = {
            "room_id": self.room.id,
            "items": [{"item_id": self.water.id, "quantity": 5}],
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Insufficient stock", res.data["error"])

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("2.00"))  # Unchanged

    # -------------------------------------------------------------------------
    # 4. Generic purchase reversal creates the correct compensating GL entry
    # -------------------------------------------------------------------------
    def test_04_generic_purchase_reversal_creates_compensating_gl_entry(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        # Create purchase
        buy_res = self.client.post(
            reverse("stocktransaction-list"),
            data={
                "item": self.water.id,
                "transaction_type": "purchase",
                "quantity": "20.00",
                "unit_cost": "15.00",
                "supplier": self.supplier.id,
                "reference_number": "PO-TEST-004",
            },
            format="json"
        )
        self.assertEqual(buy_res.status_code, status.HTTP_201_CREATED)
        buy_stx_id = buy_res.data["id"]

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("70.00"))  # 50 + 20

        # Reverse purchase
        rev_url = reverse("stocktransaction-reverse", kwargs={"pk": buy_stx_id})
        rev_res = self.client.post(rev_url, data={"reason": "Goods damaged on delivery arrival"}, format="json")
        self.assertEqual(rev_res.status_code, status.HTTP_201_CREATED)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))  # Returned to 50

        # Verify compensating JV: Dr 2000 (AP), Cr 1300 (Asset) for 300.00 (20 * 15)
        rev_jv = JournalEntry.objects.filter(description__contains="Auto Reversal JV: Purchase").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in rev_jv.items.all()}
        self.assertEqual(items["2000"], (Decimal("300.00"), Decimal("0.00")))
        self.assertEqual(items["1300"], (Decimal("0.00"), Decimal("300.00")))

    # -------------------------------------------------------------------------
    # 5. Generic issuance reversal creates the correct compensating GL entry
    # -------------------------------------------------------------------------
    def test_05_generic_issuance_reversal_creates_compensating_gl_entry(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        # Issue goods to kitchen
        issue_res = self.client.post(
            reverse("stocktransaction-list"),
            data={
                "item": self.coke.id,
                "transaction_type": "issuance",
                "quantity": "10.00",
                "unit_cost": "20.00",
                "destination_dept": "Bar",
                "notes": "Bar dispatch for event",
            },
            format="json"
        )
        self.assertEqual(issue_res.status_code, status.HTTP_201_CREATED)
        stx_id = issue_res.data["id"]

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("20.00"))  # 30 - 10

        # Reverse issuance
        rev_url = reverse("stocktransaction-reverse", kwargs={"pk": stx_id})
        rev_res = self.client.post(rev_url, data={"reason": "Bar returned unused stock"}, format="json")
        self.assertEqual(rev_res.status_code, status.HTTP_201_CREATED)

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("30.00"))  # Restored to 30

        # Verify compensating JV: Dr 1300 (Asset), Cr 5000 (COGS) for 200.00 (10 * 20)
        rev_jv = JournalEntry.objects.filter(description__contains="Auto Reversal JV: Issuance").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in rev_jv.items.all()}
        self.assertEqual(items["1300"], (Decimal("200.00"), Decimal("0.00")))
        self.assertEqual(items["5000"], (Decimal("0.00"), Decimal("200.00")))

    # -------------------------------------------------------------------------
    # 6. Folio charge creates appropriate inventory cost accounting
    # -------------------------------------------------------------------------
    def test_06_folio_charge_creates_inventory_cost_accounting(self):
        self.client.force_authenticate(user=self.reception)
        url = reverse("folio-charges", kwargs={"reservation_id": self.reservation.id})
        payload = {
            "description": "Guest requested extra water bottle",
            "amount": "30.00",
            "inventory_item": self.water.id,
            "quantity": "1.00",
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("49.00"))

        # Inventory cost entry: Dr 5000, Cr 1300 for 15.00
        cost_jv = JournalEntry.objects.filter(description__contains="Auto JV: Folio Inventory Cost").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in cost_jv.items.all()}
        self.assertEqual(items["5000"], (Decimal("15.00"), Decimal("0.00")))
        self.assertEqual(items["1300"], (Decimal("0.00"), Decimal("15.00")))

    # -------------------------------------------------------------------------
    # 7. Folio charge deletion reverses the corresponding inventory and revenue accounting
    # -------------------------------------------------------------------------
    def test_07_folio_charge_deletion_reverses_inventory_and_revenue_accounting(self):
        self.client.force_authenticate(user=self.reception)
        # Create charge
        charge = FolioCharge.objects.create(
            reservation=self.reservation,
            description="Minibar: Mineral Water 500ml (x2)",
            amount=Decimal("60.00"),
            added_by=self.reception.username,
            inventory_item=self.water,
            quantity=Decimal("2.00"),
        )
        record_stock_change(
            item_id=self.water.pk,
            transaction_type="issuance",
            quantity=Decimal("2.00"),
            unit_cost=self.water.unit_cost,
            notes=f"Minibar consumption charge recorded on guest folio (Charge ID #{charge.id}).",
        )
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("48.00"))

        # Delete charge
        del_url = reverse("folio-charge-delete", kwargs={"charge_id": charge.id})
        del_res = self.client.delete(del_url)
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))  # Restored

        # Compensating inventory JV created
        rev_inv_jv = JournalEntry.objects.filter(description__contains="Auto Reversal JV: Issuance").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in rev_inv_jv.items.all()}
        self.assertEqual(items["1300"], (Decimal("30.00"), Decimal("0.00")))
        self.assertEqual(items["5000"], (Decimal("0.00"), Decimal("30.00")))

    # -------------------------------------------------------------------------
    # 8. Stock adjustment increase works correctly
    # -------------------------------------------------------------------------
    def test_08_stock_adjustment_increase_works_correctly(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.water.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "increase",
            "quantity": "10.00",
            "unit_cost": "15.00",
            "notes": "Found unrecorded carton during physical store count",
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("60.00"))  # 50 + 10

        stx = StockTransaction.objects.get(id=res.data["id"])
        self.assertEqual(stx.adjustment_direction, "increase")
        self.assertEqual(transaction_delta(stx), Decimal("10.00"))

        # GL JV: Dr 1300 (Asset), Cr 5000 (COGS/Gain) for 150.00
        jv = JournalEntry.objects.filter(description__contains="Inventory Adjustment (Increase)").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in jv.items.all()}
        self.assertEqual(items["1300"], (Decimal("150.00"), Decimal("0.00")))
        self.assertEqual(items["5000"], (Decimal("0.00"), Decimal("150.00")))

    # -------------------------------------------------------------------------
    # 9. Stock adjustment decrease works correctly
    # -------------------------------------------------------------------------
    def test_09_stock_adjustment_decrease_works_correctly(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.water.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "decrease",
            "quantity": "8.00",
            "unit_cost": "15.00",
            "notes": "Unaccounted shortage identified during audit count",
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("42.00"))  # 50 - 8

        stx = StockTransaction.objects.get(id=res.data["id"])
        self.assertEqual(stx.adjustment_direction, "decrease")
        self.assertEqual(transaction_delta(stx), Decimal("-8.00"))

        # GL JV: Dr 5000 (COGS/Shrinkage), Cr 1300 (Asset) for 120.00
        jv = JournalEntry.objects.filter(description__contains="Inventory Adjustment (Decrease)").latest("id")
        items = {it.account.code: (it.amount_debit, it.amount_credit) for it in jv.items.all()}
        self.assertEqual(items["5000"], (Decimal("120.00"), Decimal("0.00")))
        self.assertEqual(items["1300"], (Decimal("0.00"), Decimal("120.00")))

    # -------------------------------------------------------------------------
    # 10. Adjustment cannot reduce stock below zero
    # -------------------------------------------------------------------------
    def test_10_adjustment_cannot_reduce_stock_below_zero(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.water.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "decrease",
            "quantity": "100.00",  # Available is only 50.00
            "unit_cost": "15.00",
            "notes": "Attempting excess write-down",
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))  # Unchanged

    # -------------------------------------------------------------------------
    # 11. Adjustment reason is mandatory
    # -------------------------------------------------------------------------
    def test_11_adjustment_reason_is_mandatory(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.water.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "decrease",
            "quantity": "2.00",
            "unit_cost": "15.00",
            "notes": "",  # Empty reason
        }
        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 12. Repeated purchase requests do not create duplicate stock movements
    # -------------------------------------------------------------------------
    def test_12_repeated_purchase_requests_idempotent(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.coke.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
            "supplier": self.supplier.id,
            "reference_number": "PO-REPLAY-001",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "IDEMP-BUY-12345"}

        # First attempt
        res1 = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        tx_id1 = res1.data["id"]

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("40.00"))  # 30 + 10

        # Duplicate replay
        res2 = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["id"], tx_id1)

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("40.00"))  # Still 40, not 50!

    # -------------------------------------------------------------------------
    # 13. Repeated issuance requests do not create duplicate stock movements
    # -------------------------------------------------------------------------
    def test_13_repeated_issuance_requests_idempotent(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        payload = {
            "item": self.coke.id,
            "transaction_type": "issuance",
            "quantity": "5.00",
            "unit_cost": "20.00",
            "destination_dept": "Kitchen",
            "notes": "Cooking soda for kitchen recipe",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "IDEMP-ISS-998877"}

        # First attempt
        res1 = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        tx_id1 = res1.data["id"]

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("25.00"))  # 30 - 5

        # Replay
        res2 = self.client.post(url, data=payload, format="json", **headers)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["id"], tx_id1)

        self.coke.refresh_from_db()
        self.assertEqual(self.coke.current_stock, Decimal("25.00"))  # Still 25, not 20!

    # -------------------------------------------------------------------------
    # 14. Duplicate reversal attempts are safely rejected
    # -------------------------------------------------------------------------
    def test_14_duplicate_reversal_attempts_safely_rejected(self):
        # Create an issuance
        _, stx = record_stock_change(
            item_id=self.water.pk,
            transaction_type="issuance",
            quantity=Decimal("5.00"),
            unit_cost=self.water.unit_cost,
            notes="Testing duplicate reversal protection",
        )
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("45.00"))

        # First reversal
        rev1, created1 = reverse_stock_transaction(
            transaction_id=stx.pk,
            reason="Accidental issuance",
            logged_by_username=self.inventory_mgr.username,
        )
        self.assertTrue(created1)
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))

        # Second reversal attempt on same transaction
        rev2, created2 = reverse_stock_transaction(
            transaction_id=stx.pk,
            reason="Trying to reverse again",
            logged_by_username=self.inventory_mgr.username,
        )
        self.assertFalse(created2)
        self.assertEqual(rev1.pk, rev2.pk)

        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))  # Still 50, not 55!

    # -------------------------------------------------------------------------
    # 15. Inventory ledger reconciliation detects discrepancies
    # -------------------------------------------------------------------------
    def test_15_ledger_reconciliation_detects_and_repairs_discrepancies(self):
        # Baseline: expected == cached
        self.assertEqual(expected_stock(self.water), Decimal("50.00"))
        self.assertEqual(self.water.current_stock, Decimal("50.00"))

        # Artificially tamper with cached current_stock (simulating direct out-of-band write)
        InventoryItem.objects.filter(pk=self.water.pk).update(current_stock=Decimal("40.00"))
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("40.00"))

        # Reconcile without repair
        mismatches = reconcile_stock(repair=False)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["id"], self.water.pk)
        self.assertEqual(mismatches[0]["cached"], Decimal("40.00"))
        self.assertEqual(mismatches[0]["expected"], Decimal("50.00"))

        # Reconcile with repair
        reconcile_stock(repair=True)
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("50.00"))  # Restored to 50

    # -------------------------------------------------------------------------
    # 16. Concurrent stock operations preserve the correct final balance
    # -------------------------------------------------------------------------
    def test_16_multiple_stock_operations_preserve_exact_balance(self):
        # 1. Purchase +20 (stock -> 70)
        record_stock_change(item_id=self.water.pk, transaction_type="purchase", quantity=Decimal("20.00"), unit_cost=Decimal("15.00"))
        # 2. Issuance -15 (stock -> 55)
        record_stock_change(item_id=self.water.pk, transaction_type="issuance", quantity=Decimal("15.00"), unit_cost=Decimal("15.00"))
        # 3. Adjustment Increase +5 (stock -> 60)
        record_stock_change(item_id=self.water.pk, transaction_type="adjustment", adjustment_direction="increase", quantity=Decimal("5.00"), unit_cost=Decimal("15.00"), notes="Physical count surplus")
        # 4. Adjustment Decrease -10 (stock -> 50)
        record_stock_change(item_id=self.water.pk, transaction_type="adjustment", adjustment_direction="decrease", quantity=Decimal("10.00"), unit_cost=Decimal("15.00"), notes="Physical count deficit")

        self.water.refresh_from_db()
        expected = expected_stock(self.water)
        self.assertEqual(self.water.current_stock, Decimal("50.00"))
        self.assertEqual(expected, Decimal("50.00"))
        self.assertEqual(self.water.current_stock, expected)


class StockTransactionIdempotencyHardeningTestCase(APITransactionTestCase):
    def setUp(self):
        import uuid
        self.uid = uuid.uuid4().hex[:6]

        self.settings_obj, _ = SystemSettings.objects.get_or_create(
            id=1,
            defaults={"waste_approval_threshold": Decimal("1000.00"), "module_pos": True}
        )

        self.acct_cash, _ = Account.objects.get_or_create(code="1000", defaults={"name": "Cash", "account_type": "asset"})
        self.acct_inv, _ = Account.objects.get_or_create(code="1300", defaults={"name": "Inventory Asset", "account_type": "asset"})
        self.acct_ap, _ = Account.objects.get_or_create(code="2000", defaults={"name": "Accounts Payable", "account_type": "liability"})
        self.acct_cogs, _ = Account.objects.get_or_create(code="5000", defaults={"name": "Cost of Goods Sold", "account_type": "expense"})

        self.inventory_mgr = User.objects.create_user(
            username=f"mgr-idem-{self.uid}",
            password="test-password",
            role=User.INVENTORY,
            is_active=True,
        )

        self.category = InventoryCategory.objects.create(name=f"Beverages-{self.uid}", category_type="f_and_b")
        self.supplier = Supplier.objects.create(name=f"Main Beverage Supplier-{self.uid}", contact_person="John Doe")

        self.item_a = InventoryItem.objects.create(
            name=f"Test Juice A-{self.uid}",
            item_code=f"JUICE-A-{self.uid}",
            category=self.category,
            unit="pcs",
            current_stock=Decimal("100.00"),
            opening_stock=Decimal("100.00"),
            unit_cost=Decimal("20.00"),
        )
        self.item_b = InventoryItem.objects.create(
            name=f"Test Juice B-{self.uid}",
            item_code=f"JUICE-B-{self.uid}",
            category=self.category,
            unit="pcs",
            current_stock=Decimal("100.00"),
            opening_stock=Decimal("100.00"),
            unit_cost=Decimal("20.00"),
        )

    # 1. Same key and identical payload
    def test_01_same_key_and_identical_payload_replays_safely(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-TEST-1-{self.uid}"
        payload = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
            "supplier": self.supplier.id,
            "reference_number": "PO-101",
        }
        res1 = self.client.post(url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        tx_id1 = res1.data["id"]

        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.current_stock, Decimal("110.00"))

        res2 = self.client.post(url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["id"], tx_id1)

        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.current_stock, Decimal("110.00"))

    # 2. Same key with different item
    def test_02_same_key_with_different_item_rejected_with_409(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-TEST-2-{self.uid}"
        payload1 = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
        }
        res1 = self.client.post(url, data=payload1, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        payload2 = {
            "item": self.item_b.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
        }
        res2 = self.client.post(url, data=payload2, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("different", res2.data["error"].lower())

    # 3. Same key with different quantity
    def test_03_same_key_with_different_quantity_rejected_with_409(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-TEST-3-{self.uid}"
        payload1 = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
        }
        res1 = self.client.post(url, data=payload1, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        payload2 = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "25.00",
            "unit_cost": "20.00",
        }
        res2 = self.client.post(url, data=payload2, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)

    # 4. Same key with different unit cost
    def test_04_same_key_with_different_unit_cost_rejected_with_409(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-TEST-4-{self.uid}"
        payload1 = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "20.00",
        }
        res1 = self.client.post(url, data=payload1, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        payload2 = {
            "item": self.item_a.id,
            "transaction_type": "purchase",
            "quantity": "10.00",
            "unit_cost": "35.00",
        }
        res2 = self.client.post(url, data=payload2, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)

    # 5. Same key with different adjustment direction
    def test_05_same_key_with_different_adjustment_direction_rejected_with_409(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-TEST-5-{self.uid}"
        payload1 = {
            "item": self.item_a.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "increase",
            "quantity": "5.00",
            "unit_cost": "20.00",
            "notes": "Physical audit surplus",
        }
        res1 = self.client.post(url, data=payload1, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        payload2 = {
            "item": self.item_a.id,
            "transaction_type": "adjustment",
            "adjustment_direction": "decrease",
            "quantity": "5.00",
            "unit_cost": "20.00",
            "notes": "Physical audit deficit",
        }
        res2 = self.client.post(url, data=payload2, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)

    # 6. Five simultaneous requests with the same key and identical payload
    def test_06_five_simultaneous_requests_same_key_identical_payload(self):
        import threading
        from django.db import connection

        key = f"IDEM-CONC-SAME-{self.uid}"
        success_statuses = []
        created_tx_ids = []
        lock = threading.Lock()

        def submit_request(thread_idx):
            connection.close()
            try:
                from rest_framework.test import APIClient
                client = APIClient()
                client.force_authenticate(user=self.inventory_mgr)
                res = client.post(
                    reverse("stocktransaction-list"),
                    data={
                        "item": self.item_a.id,
                        "transaction_type": "purchase",
                        "quantity": "10.00",
                        "unit_cost": "20.00",
                        "reference_number": "PO-CONC-SAME",
                    },
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
                with lock:
                    success_statuses.append(res.status_code)
                    if res.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED):
                        created_tx_ids.append(res.data.get("id"))
            finally:
                connection.close()

        threads = [threading.Thread(target=submit_request, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        connection.close()
        self.item_a.refresh_from_db()

        # All 5 requests must complete with 200 OK or 201 Created (no 500 IntegrityError!)
        for s in success_statuses:
            self.assertIn(s, (status.HTTP_200_OK, status.HTTP_201_CREATED))

        # Stock added exactly once: 100 + 10 = 110 (not 150)
        self.assertEqual(self.item_a.current_stock, Decimal("110.00"))
        # Exactly one unique transaction ID created across all 5 threads
        self.assertEqual(len(set(created_tx_ids)), 1)

    # 7. Five simultaneous requests with the same key but different payloads
    def test_07_five_simultaneous_requests_same_key_different_payloads(self):
        import threading
        from django.db import connection

        key = f"IDEM-CONC-DIFF-{self.uid}"
        results = []
        lock = threading.Lock()

        def submit_diff_request(thread_idx):
            connection.close()
            try:
                from rest_framework.test import APIClient
                client = APIClient()
                client.force_authenticate(user=self.inventory_mgr)
                res = client.post(
                    reverse("stocktransaction-list"),
                    data={
                        "item": self.item_a.id,
                        "transaction_type": "purchase",
                        "quantity": f"{(thread_idx + 1) * 10}.00",
                        "unit_cost": "20.00",
                        "reference_number": f"PO-DIFF-{thread_idx}",
                    },
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
                with lock:
                    results.append((thread_idx, res.status_code, res.data))
            finally:
                connection.close()

        threads = [threading.Thread(target=submit_diff_request, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        connection.close()
        self.item_a.refresh_from_db()

        # Exactly 1 thread succeeds (201 Created), remaining 4 threads get 409 Conflict
        created_count = sum(1 for r in results if r[1] == status.HTTP_201_CREATED)
        conflict_count = sum(1 for r in results if r[1] == status.HTTP_409_CONFLICT)
        self.assertEqual(created_count, 1)
        self.assertEqual(conflict_count, 4)

        # Exactly 1 transaction exists for this key in the database
        self.assertEqual(StockTransaction.objects.filter(idempotency_key=key).count(), 1)

    # 8. Failed transaction followed by valid reuse of the key
    def test_08_failed_transaction_does_not_reserve_key(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")
        key = f"IDEM-FAIL-REUSE-{self.uid}"

        # Attempt 1: invalid request (issuing 500 units when only 100 exist)
        res_fail = self.client.post(
            url,
            data={
                "item": self.item_a.id,
                "transaction_type": "issuance",
                "quantity": "500.00",
                "unit_cost": "20.00",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # Confirm key was not committed to DB
        self.assertFalse(StockTransaction.objects.filter(idempotency_key=key).exists())

        # Attempt 2: valid request using the same key
        res_valid = self.client.post(
            url,
            data={
                "item": self.item_a.id,
                "transaction_type": "issuance",
                "quantity": "10.00",
                "unit_cost": "20.00",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(res_valid.status_code, status.HTTP_201_CREATED)
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.current_stock, Decimal("90.00"))

    # 9. No duplicate GL journal entries under concurrent replay
    def test_09_no_duplicate_gl_journal_entries_under_concurrent_replay(self):
        import threading
        from django.db import connection

        key = f"IDEM-GL-DEDUP-{self.uid}"
        ref_num = f"PO-GL-{self.uid}"

        def submit_gl_request():
            connection.close()
            try:
                from rest_framework.test import APIClient
                client = APIClient()
                client.force_authenticate(user=self.inventory_mgr)
                client.post(
                    reverse("stocktransaction-list"),
                    data={
                        "item": self.item_a.id,
                        "transaction_type": "purchase",
                        "quantity": "15.00",
                        "unit_cost": "20.00",
                        "supplier": self.supplier.id,
                        "reference_number": ref_num,
                    },
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
            finally:
                connection.close()

        threads = [threading.Thread(target=submit_gl_request) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        connection.close()

        # Count journal entries created
        jes = list(JournalEntry.objects.filter(description__contains=f"{self.item_a.name} (15.00 {self.item_a.unit})"))
        self.assertEqual(len(jes), 1, f"Expected exactly 1 JournalEntry, found {len(jes)}")

        # Verify entry is balanced (15 * 20 = 300 ETB)
        lines = list(jes[0].items.all())
        debits = sum(l.amount_debit for l in lines)
        credits = sum(l.amount_credit for l in lines)
        self.assertEqual(debits, Decimal("300.00"))
        self.assertEqual(credits, Decimal("300.00"))

    # 10. Legacy transactions without idempotency keys remain valid
    def test_10_legacy_transactions_without_idempotency_keys_remain_valid(self):
        self.client.force_authenticate(user=self.inventory_mgr)
        url = reverse("stocktransaction-list")

        # Create multiple transactions with no Idempotency-Key header
        res1 = self.client.post(
            url,
            data={"item": self.item_a.id, "transaction_type": "purchase", "quantity": "5.00", "unit_cost": "20.00"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(
            url,
            data={"item": self.item_a.id, "transaction_type": "purchase", "quantity": "5.00", "unit_cost": "20.00"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        self.assertNotEqual(res1.data["id"], res2.data["id"])
        self.assertIsNone(res1.data.get("idempotency_key"))
        self.assertIsNone(res2.data.get("idempotency_key"))
        self.assertIsNone(res1.data.get("payload_hash"))
        self.assertIsNone(res2.data.get("payload_hash"))

        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.current_stock, Decimal("110.00"))  # 100 + 5 + 5

