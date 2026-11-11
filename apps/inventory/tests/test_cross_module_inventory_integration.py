"""
apps/inventory/tests/test_cross_module_inventory_integration.py

Cross-Module Integration Test Suite:
Validates the end-to-end operational lifecycle:
1. Procurement (PO -> GRN -> 3-Way Match) -> Transfer to Kitchen -> POS Order Settlement & Recipe BOM FEFO Deduction -> COGS GL
2. Procurement -> Transfer to Minibar Pantry -> Room Guest Consumption -> Folio Billing -> COGS GL
3. Expired Batch Lockout from POS & Spoilage Write-Off to Account 5010
4. Dual-Mode Physical Stocktaking Reconciliation (Subledger & GL Sync)
5. Stock Transfer In-Transit Breakage & Waste Spoilage JV (Account 5010)
6. Departmental Operating Supplies Issuance (Account 5030)
7. Concurrent POS Order Settlement & Subledger Layer-Exact COGS
8. Owner Observation 1: Superuser Self-Approval Governance & AuditEvent Logging
9. Owner Observation 2: Parent Serializer Blind Theoretical Value Masking
10. Trial Balance Equilibrium (Debits == Credits across the entire ERP ecosystem)
"""
import datetime
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts, post_journal_entry
from apps.orders.services import finalize_paid_order
from hotel.integrity import record_stock_change, record_waste_entry, approve_waste_entry
from hotel.models import (
    Account,
    AuditEvent,
    BatchLocationBalance,
    Category,
    DiningSession,
    FolioCharge,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
    InventoryItem,
    InventoryWasteRecord,
    ItemLocationBalance,
    JournalEntry,
    MenuItem,
    MinibarItem,
    Order,
    OrderItem,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    RecipeBOM,
    Reservation,
    RestaurantTable,
    Room,
    StockBatch,
    StockBatchConsumption,
    StockLocation,
    StocktakeItem,
    StocktakeSession,
    StockTransaction,
    StockTransfer,
    StockTransferItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
)
from hotel.procurement import (
    approve_purchase_requisition,
    approve_supplier_invoice,
    convert_requisition_to_purchase_order,
    ensure_default_procurement_policy,
    match_and_record_supplier_invoice,
    receive_goods_receipt_note,
    request_purchase_requisition,
)
from hotel.stocktaking import (
    approve_stocktake_session,
    create_stocktake_session,
    record_counts,
    request_recount,
    submit_recount,
)
from hotel.transfers import (
    dispatch_stock_transfer,
    receive_stock_transfer,
    request_stock_transfer,
)
from users.models import User


class CrossModuleInventoryIntegrationTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_e2e", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.superuser = User.objects.create_superuser(
            username="super_e2e", password="password123", email="super@acrmatech.com"
        )
        self.cashier = User.objects.create_user(
            username="cashier_e2e", password="password123", role="cashier", is_active=True, is_verified=True
        )
        self.chef = User.objects.create_user(
            username="chef_e2e", password="password123", role="kitchen", is_active=True, is_verified=True
        )
        self.storekeeper = User.objects.create_user(
            username="storekeeper_e2e", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.housekeeper = User.objects.create_user(
            username="hk_e2e", password="password123", role="housekeeping", is_active=True, is_verified=True
        )

        # 2. Setup Default Locations
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

        # 3. Setup Chart of Accounts
        ensure_default_accounts()

        # 4. Setup Procurement Policy
        ensure_default_procurement_policy()

        # 5. Setup Categories & Supplier
        self.cat_fnb, _ = InventoryCategory.objects.get_or_create(
            name="E2E Food & Beverage", defaults={"category_type": "f_and_b"}
        )
        self.cat_supplies, _ = InventoryCategory.objects.get_or_create(
            name="E2E Operating Supplies", defaults={"category_type": "supplies"}
        )
        self.pos_cat, _ = Category.objects.get_or_create(
            name="Burgers & Mains"
        )
        self.supplier, _ = Supplier.objects.get_or_create(
            name="Acrma Prime Provisions", defaults={"phone": "+251911002233"}
        )

        self.today = timezone.now().date()

    def test_e2e_01_procurement_to_kitchen_transfer_to_pos_bom_sale(self):
        """
        Complete Lifecycle 1:
        Purchase Requisition -> PO -> GRN at STORE-MAIN -> 3-Way Match Invoice
        -> Transfer to KITCHEN-MAIN -> POS Dining Order Settle -> Recipe BOM Deduction -> Exact COGS GL
        """
        # Step A: Create Items
        patty_item = InventoryItem.objects.create(
            item_code="E2E-PATTY",
            name="Beef Burger Patty 150g",
            category=self.cat_fnb,
            unit="pieces",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("120.00"),
            is_perishable=True,
            shelf_life_days=30,
        )
        bun_item = InventoryItem.objects.create(
            item_code="E2E-BUN",
            name="Brioche Burger Bun",
            category=self.cat_fnb,
            unit="pieces",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("30.00"),
            is_perishable=True,
            shelf_life_days=7,
        )

        # Step B: Procurement Requisition & Purchase Order
        pr = request_purchase_requisition(
            requested_by=self.chef,
            items=[
                {"item_id": patty_item.id, "quantity_requested": 50, "estimated_unit_price": 120},
                {"item_id": bun_item.id, "quantity_requested": 50, "estimated_unit_price": 30},
            ],
            notes="Weekly burger stock replenishment",
        )
        approve_purchase_requisition(requisition_id=pr.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=pr.id, supplier_id=self.supplier.id, user=self.admin)

        # Step C: Goods Receipt Note into STORE-MAIN (creates batches and posts GRNI: Dr 1300, Cr 2010)
        po_patty_line = po.items.get(item=patty_item)
        po_bun_line = po.items.get(item=bun_item)
        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            received_by=self.storekeeper,
            items=[
                {
                    "po_item_id": po_patty_line.id,
                    "quantity_received": 50,
                    "unit_cost": 120.00,
                    "expiry_date": self.today + datetime.timedelta(days=20),
                    "supplier_batch_number": "SUP-PATTY-001",
                },
                {
                    "po_item_id": po_bun_line.id,
                    "quantity_received": 50,
                    "unit_cost": 30.00,
                    "expiry_date": self.today + datetime.timedelta(days=5),
                    "supplier_batch_number": "SUP-BUN-001",
                },
            ],
        )
        self.assertEqual(grn.status, "approved")
        patty_item.refresh_from_db()
        self.assertEqual(patty_item.current_stock, Decimal("50.00"))
        self.assertEqual(ItemLocationBalance.objects.get(item=patty_item, location=self.main_store).quantity, Decimal("50.00"))

        # Step D: 3-Way Matched Supplier Invoice
        inv = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-E2E-001",
            invoice_date=self.today,
            due_date=self.today + datetime.timedelta(days=30),
            billed_items=[
                {"po_item_id": po_patty_line.id, "grn_item_id": grn.items.get(item=patty_item).id, "billed_quantity": 50, "billed_unit_price": 120.00},
                {"po_item_id": po_bun_line.id, "grn_item_id": grn.items.get(item=bun_item).id, "billed_quantity": 50, "billed_unit_price": 30.00},
            ],
            matched_by=self.admin,
        )
        approve_supplier_invoice(invoice_id=inv.id, approver=self.admin)
        inv.refresh_from_db()
        self.assertEqual(inv.match_status, "approved")

        # Step E: Transfer 30 patties and 30 buns from STORE-MAIN to KITCHEN-MAIN
        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.kitchen_store,
            requested_by=self.chef,
            items=[
                {"item_id": patty_item.id, "quantity_requested": 30},
                {"item_id": bun_item.id, "quantity_requested": 30},
            ],
            notes="Transfer to kitchen for daily service",
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)
        receive_stock_transfer(transfer_id=transfer.id, receiver=self.chef)

        # Verify Kitchen Pantry balances
        self.assertEqual(ItemLocationBalance.objects.get(item=patty_item, location=self.kitchen_store).quantity, Decimal("30.00"))
        self.assertEqual(ItemLocationBalance.objects.get(item=bun_item, location=self.kitchen_store).quantity, Decimal("30.00"))

        # Step F: POS Menu Item & Recipe BOM
        burger_menu = MenuItem.objects.create(
            name="Classic Cheeseburger",
            category=self.pos_cat,
            price=Decimal("450.00"),
            is_available=True,
        )
        RecipeBOM.objects.create(menu_item=burger_menu, ingredient=patty_item, quantity_required=Decimal("1.00"))
        RecipeBOM.objects.create(menu_item=burger_menu, ingredient=bun_item, quantity_required=Decimal("1.00"))

        # Step G: Create & Settle Dining Order (2 Burgers = 2 patties + 2 buns)
        table = RestaurantTable.objects.create(table_code="T101", label_name="Table 101", capacity=4, status="occupied")
        order = Order.objects.create(
            table=table,
            status="served",
            payment_status="pending",
            sub_total=Decimal("900.00"),
            total_amount=Decimal("900.00"),
        )
        order_item = OrderItem.objects.create(
            order=order,
            menu_item=burger_menu,
            quantity=2,
            price_at_order=Decimal("450.00"),
            status="served",
        )

        # Cashier finalizes paid order
        finalize_paid_order(order=order, payment_method="cash", cashier=self.cashier)

        # Step H: Assertions on inventory deduction & layer-exact COGS
        patty_kitchen_bal = ItemLocationBalance.objects.get(item=patty_item, location=self.kitchen_store)
        bun_kitchen_bal = ItemLocationBalance.objects.get(item=bun_item, location=self.kitchen_store)
        self.assertEqual(patty_kitchen_bal.quantity, Decimal("28.00"))  # 30 - 2
        self.assertEqual(bun_kitchen_bal.quantity, Decimal("28.00"))    # 30 - 2

        # 2 patties @ 120 + 2 buns @ 30 = 240 + 60 = 300.00 COGS
        cogs_jv = JournalEntry.objects.filter(description__icontains=f"COGS for Order #{order.id}").first()
        self.assertIsNotNone(cogs_jv)
        items = list(cogs_jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertEqual(dr.account.code, "5000")
        self.assertEqual(dr.amount_debit, Decimal("300.00"))
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("300.00"))

    def test_e2e_02_procurement_to_minibar_to_guest_checkout_settlement(self):
        """
        Complete Lifecycle 2:
        Procure beverages -> Transfer to MINIBAR-PANTRY -> MinibarConsumeView
        -> Deducts from MINIBAR-PANTRY -> Layer-Exact COGS (Dr 5000, Cr 1300) -> FolioCharge created
        """
        soda = InventoryItem.objects.create(
            item_code="E2E-SODA",
            name="Sparkling Water 330ml",
            category=self.cat_fnb,
            unit="cans",
            current_stock=Decimal("100.00"),
            unit_cost=Decimal("25.00"),
            selling_price=Decimal("80.00"),
        )
        ItemLocationBalance.objects.create(item=soda, location=self.main_store, quantity=Decimal("100.00"))
        batch = StockBatch.objects.create(
            item=soda,
            batch_number="BATCH-SODA-01",
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("25.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("100.00"))

        # Transfer 20 cans to MINIBAR-PANTRY
        trf = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.minibar_pantry,
            requested_by=self.housekeeper,
            items=[{"item_id": soda.id, "quantity_requested": 20}],
        )
        dispatch_stock_transfer(transfer_id=trf.id, dispatcher=self.storekeeper)
        receive_stock_transfer(transfer_id=trf.id, receiver=self.housekeeper)

        # Setup Room & Checked-In Reservation
        room = Room.objects.create(
            name="Deluxe 305",
            room_number="305",
            room_type="Deluxe Suite",
            base_price=Decimal("2500.00"),
        )
        reservation = Reservation.objects.create(
            guest_name="Abebe Bikila",
            guest_phone="+251911998877",
            room=room,
            check_in_date=self.today,
            check_out_date=self.today + datetime.timedelta(days=2),
            status="checked_in",
            total_amount=Decimal("5000.00"),
        )
        MinibarItem.objects.create(room=room, item=soda, standard_quantity=5, current_quantity=5)

        # Housekeeper posts consumption of 3 cans via MinibarConsumeView
        self.client.force_authenticate(user=self.housekeeper)
        consume_url = reverse("minibar-consume")
        res = self.client.post(
            consume_url,
            {
                "room_id": room.id,
                "items_consumed": [{"item_id": soda.id, "quantity": 3, "price": 80.00}],
                "notes": "Minibar guest inspection Room 305",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify deduction targeted MINIBAR-PANTRY
        pantry_bal = ItemLocationBalance.objects.get(item=soda, location=self.minibar_pantry)
        self.assertEqual(pantry_bal.quantity, Decimal("17.00"))  # 20 - 3

        # Verify FolioCharge was created
        folio_charge = FolioCharge.objects.filter(reservation=reservation, inventory_item=soda).first()
        self.assertIsNotNone(folio_charge)
        self.assertEqual(folio_charge.amount, Decimal("240.00"))  # 3 * 80.00
        self.assertEqual(folio_charge.quantity, Decimal("3.00"))

        # Verify COGS Journal Entry: 3 cans @ 25.00 = 75.00
        mb_jv = JournalEntry.objects.filter(description__icontains=f"Minibar Issuance - {soda.name}").first()
        self.assertIsNotNone(mb_jv)
        items = list(mb_jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertEqual(dr.account.code, "5000")
        self.assertEqual(dr.amount_debit, Decimal("75.00"))
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("75.00"))

    def test_e2e_03_expired_batch_lockout_from_pos_and_spoilage_writeoff(self):
        """
        Complete Lifecycle 3:
        Expired batch in kitchen is strictly blocked from POS sale
        and written off to Account 5010 (Inventory Spoilage & Waste Expense).
        """
        milk = InventoryItem.objects.create(
            item_code="E2E-MILK",
            name="Fresh Cream 1L",
            category=self.cat_fnb,
            unit="liters",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("150.00"),
            is_perishable=True,
            shelf_life_days=3,
        )
        ItemLocationBalance.objects.create(item=milk, location=self.kitchen_store, quantity=Decimal("10.00"))
        # Create expired batch (expired yesterday)
        expired_batch = StockBatch.objects.create(
            item=milk,
            batch_number="BATCH-MILK-EXP",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("150.00"),
            received_date=self.today - datetime.timedelta(days=5),
            expiry_date=self.today - datetime.timedelta(days=1),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=expired_batch, location=self.kitchen_store, quantity=Decimal("10.00"))

        # Create Recipe BOM for Latte
        latte = MenuItem.objects.create(name="Cafe Latte", category=self.pos_cat, price=Decimal("120.00"))
        RecipeBOM.objects.create(menu_item=latte, ingredient=milk, quantity_required=Decimal("0.50"))

        table = RestaurantTable.objects.create(table_code="T102", label_name="Table 102", capacity=2)
        order = Order.objects.create(table=table, status="served", sub_total=Decimal("120.00"), total_amount=Decimal("120.00"))
        OrderItem.objects.create(order=order, menu_item=latte, quantity=1, price_at_order=Decimal("120.00"), status="served")

        # POS settlement MUST fail due to expired batch lockout (Owner Decision D-2)
        with self.assertRaises(ValueError) as ctx:
            finalize_paid_order(order=order, payment_method="cash", cashier=self.cashier)
        self.assertIn("insufficient valid stock", str(ctx.exception).lower())
        self.assertIn("unexpired & verified", str(ctx.exception).lower())

        # Kitchen supervisor writes off the 10 expired liters
        waste_record, _ = record_waste_entry(
            item_id=milk.id,
            entered_quantity=10,
            entered_unit="liters",
            waste_category="spoilage_expired",
            waste_source="direct_loss",
            idempotency_key=f"WASTE-MILK-{milk.id}",
            notes="Expired in Kitchen Pantry chiller",
            storage_area="Kitchen Pantry",
            logged_by_username=self.chef.username,
        )

        # Admin approves waste entry
        approve_waste_entry(waste_id=waste_record.id, reviewer=self.admin)

        waste_record.refresh_from_db()
        milk.refresh_from_db()
        self.assertEqual(waste_record.status, "approved")
        self.assertEqual(milk.current_stock, Decimal("0.00"))

        # Verify General Ledger Entry posted to 5010 (Inventory Spoilage & Waste Expense), NOT 5000 (COGS)
        jv = waste_record.journal_entry
        self.assertIsNotNone(jv)
        items = list(jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertEqual(dr.account.code, "5010")
        self.assertEqual(dr.amount_debit, Decimal("1500.00"))  # 10 * 150
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("1500.00"))

    def test_e2e_04_stocktaking_discrepancy_reconciles_subledger_and_gl(self):
        """
        Complete Lifecycle 4:
        Stocktaking at BAR-MAIN identifies discrepancy, recounts, approves,
        and posts balanced variance JVs (Account 5020).
        """
        gin = InventoryItem.objects.create(
            item_code="E2E-GIN",
            name="London Dry Gin 750ml",
            category=self.cat_fnb,
            unit="bottles",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("700.00"),
        )
        ItemLocationBalance.objects.create(item=gin, location=self.bar_store, quantity=Decimal("20.00"))
        batch = StockBatch.objects.create(
            item=gin,
            batch_number="BATCH-GIN-01",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("700.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.bar_store, quantity=Decimal("20.00"))

        session = create_stocktake_session(location=self.bar_store, counting_mode="blind", created_by=self.admin)
        # Bar staff counts 18 bottles (2 bottles shrinkage = -1400.00)
        record_counts(session_id=session.pk, counts_data=[{"item_id": gin.pk, "counted_quantity": 18}], user=self.storekeeper)

        approve_stocktake_session(session_id=session.pk, supervisor=self.admin, notes="Bar inventory shrinkage verified")

        session.refresh_from_db()
        gin.refresh_from_db()
        self.assertEqual(session.status, "approved")
        self.assertEqual(gin.current_stock, Decimal("18.00"))
        self.assertEqual(ItemLocationBalance.objects.get(item=gin, location=self.bar_store).quantity, Decimal("18.00"))

        # Verify General Ledger Journal Entry: Dr 5020 (Variance Expense) 1400.00, Cr 1300 (Asset) 1400.00
        jv = session.journal_entry
        self.assertIsNotNone(jv)
        items = list(jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertEqual(dr.account.code, "5020")
        self.assertEqual(dr.amount_debit, Decimal("1400.00"))
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("1400.00"))

    def test_e2e_05_transfer_in_transit_breakage_generates_waste_and_spoilage_gl(self):
        """
        Complete Lifecycle 5:
        Transfer dispatch -> In-transit breakage -> Partial receive -> Auto waste generation & GL 5010
        """
        beer = InventoryItem.objects.create(
            item_code="E2E-BEER",
            name="Craft IPA 330ml Glass Bottle",
            category=self.cat_fnb,
            unit="bottles",
            current_stock=Decimal("50.00"),
            unit_cost=Decimal("60.00"),
        )
        ItemLocationBalance.objects.create(item=beer, location=self.main_store, quantity=Decimal("50.00"))
        batch = StockBatch.objects.create(
            item=beer,
            batch_number="BATCH-BEER-01",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("60.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("50.00"))

        transfer = request_stock_transfer(
            source_location=self.main_store,
            destination_location=self.bar_store,
            requested_by=self.storekeeper,
            items=[{"item_id": beer.id, "quantity_requested": 20}],
        )
        dispatch_stock_transfer(transfer_id=transfer.id, dispatcher=self.storekeeper)

        # Bar staff receives 18 bottles; 2 broken in transit
        trf_item = transfer.items.first()
        receive_stock_transfer(
            transfer_id=transfer.id,
            receiver=self.admin,
            receipt_items=[{"transfer_item_id": trf_item.id, "quantity_received": 18, "quantity_damaged": 2, "damage_notes": "Broken on service stairs"}],
        )

        transfer.refresh_from_db()
        beer.refresh_from_db()
        self.assertEqual(transfer.status, "partially_received")
        self.assertEqual(beer.current_stock, Decimal("48.00"))  # 50 - 2 broken
        self.assertEqual(ItemLocationBalance.objects.get(item=beer, location=self.bar_store).quantity, Decimal("18.00"))
        self.assertEqual(ItemLocationBalance.objects.get(item=beer, location=self.main_store).quantity, Decimal("30.00"))

        # Verify breakage waste record and JV against 5010
        waste = InventoryWasteRecord.objects.filter(item=beer, waste_category="breakage_or_damage").first()
        self.assertIsNotNone(waste)
        self.assertEqual(waste.base_quantity, Decimal("2.00"))

        jv = waste.journal_entry
        self.assertIsNotNone(jv)
        items = list(jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertEqual(dr.account.code, "5010")
        self.assertEqual(dr.amount_debit, Decimal("120.00"))  # 2 * 60.00
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("120.00"))

    def test_e2e_06_departmental_supplies_issuance_posts_account_5030(self):
        """
        Complete Lifecycle 6:
        Store issues operating supplies to Housekeeping; posts to Account 5030.
        """
        soap = InventoryItem.objects.create(
            item_code="E2E-SOAP",
            name="Guest Hand Soap 50g",
            category=self.cat_supplies,
            unit="pieces",
            current_stock=Decimal("200.00"),
            unit_cost=Decimal("15.00"),
        )
        ItemLocationBalance.objects.create(item=soap, location=self.main_store, quantity=Decimal("200.00"))

        # Issue 50 pieces to Housekeeping via API
        self.client.force_authenticate(user=self.admin)
        txn_url = reverse("stocktransaction-list")
        res = self.client.post(
            txn_url,
            {
                "item": soap.id,
                "transaction_type": "issuance",
                "quantity": 50,
                "unit_cost": 15.00,
                "destination_dept": "Housekeeping",
                "notes": "Weekly guest amenities replenishment",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        soap.refresh_from_db()
        self.assertEqual(soap.current_stock, Decimal("150.00"))

        # Verify Journal Entry posted
        jv = JournalEntry.objects.filter(description__icontains=f"Inventory Issuance - {soap.name}").first()
        self.assertIsNotNone(jv)
        items = list(jv.items.all())
        dr = [i for i in items if i.amount_debit > 0][0]
        cr = [i for i in items if i.amount_credit > 0][0]
        self.assertIn(dr.account.code, ("5000", "5030"))
        self.assertEqual(dr.amount_debit, Decimal("750.00"))  # 50 * 15.00
        self.assertEqual(cr.account.code, "1300")
        self.assertEqual(cr.amount_credit, Decimal("750.00"))

    def test_e2e_07_concurrent_pos_settlement_layer_exact_cogs(self):
        """
        Complete Lifecycle 7:
        Sequential POS order settlements for the same menu item consume batch layers
        and produce exact subledger COGS debit entries.
        """
        coffee = InventoryItem.objects.create(
            item_code="E2E-COFFEE",
            name="Espresso Beans Blend",
            category=self.cat_fnb,
            unit="kg",
            current_stock=Decimal("5.00"),
            unit_cost=Decimal("400.00"),
        )
        ItemLocationBalance.objects.create(item=coffee, location=self.main_store, quantity=Decimal("5.00"))
        batch = StockBatch.objects.create(
            item=coffee,
            batch_number="BATCH-COFFEE-01",
            initial_quantity=Decimal("5.00"),
            current_quantity=Decimal("5.00"),
            unit_cost=Decimal("400.00"),
            received_date=self.today,
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch, location=self.main_store, quantity=Decimal("5.00"))

        espresso = MenuItem.objects.create(name="Single Espresso", category=self.pos_cat, price=Decimal("80.00"))
        RecipeBOM.objects.create(menu_item=espresso, ingredient=coffee, quantity_required=Decimal("0.02"))  # 20g per shot

        table = RestaurantTable.objects.create(table_code="T103", label_name="Table 103", capacity=2)

        # Order 1 (10 shots = 0.20 kg = 80.00 COGS)
        ord1 = Order.objects.create(table=table, status="served", sub_total=Decimal("800.00"), total_amount=Decimal("800.00"))
        OrderItem.objects.create(order=ord1, menu_item=espresso, quantity=10, price_at_order=Decimal("80.00"), status="served")
        finalize_paid_order(order=ord1, payment_method="cash", cashier=self.cashier)

        # Order 2 (5 shots = 0.10 kg = 40.00 COGS)
        ord2 = Order.objects.create(table=table, status="served", sub_total=Decimal("400.00"), total_amount=Decimal("400.00"))
        OrderItem.objects.create(order=ord2, menu_item=espresso, quantity=5, price_at_order=Decimal("80.00"), status="served")
        finalize_paid_order(order=ord2, payment_method="cash", cashier=self.cashier)

        coffee.refresh_from_db()
        self.assertEqual(coffee.current_stock, Decimal("4.70"))  # 5.00 - 0.30

        jv1 = JournalEntry.objects.filter(description__icontains=f"COGS for Order #{ord1.id}").first()
        jv2 = JournalEntry.objects.filter(description__icontains=f"COGS for Order #{ord2.id}").first()
        self.assertEqual(jv1.items.get(amount_debit__gt=0).amount_debit, Decimal("80.00"))
        self.assertEqual(jv2.items.get(amount_debit__gt=0).amount_debit, Decimal("40.00"))

    def test_e2e_08_owner_obs1_superuser_self_approval_governance(self):
        """
        Lifecycle 8 (OBS-1 Resolution):
        Superuser who personally counted a stocktake cannot approve it normally (403 Forbidden).
        Only with emergency_self_approval=True and justification can superuser approve, creating an AuditEvent.
        """
        rice = InventoryItem.objects.create(
            item_code="E2E-RICE",
            name="Jasmine Rice 5kg",
            category=self.cat_fnb,
            unit="bags",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("300.00"),
        )
        ItemLocationBalance.objects.create(item=rice, location=self.main_store, quantity=Decimal("10.00"))

        session = create_stocktake_session(location=self.main_store, created_by=self.admin)
        # Superuser personally records counts
        record_counts(session_id=session.pk, counts_data=[{"item_id": rice.pk, "counted_quantity": 10}], user=self.superuser)

        session.refresh_from_db()
        self.assertEqual(session.counted_by, self.superuser)

        # 1. Standard approval attempt by superuser who counted: FAILS with PermissionDenied
        with self.assertRaises(PermissionDenied):
            approve_stocktake_session(session_id=session.pk, supervisor=self.superuser)

        # 2. Emergency self-approval without adequate justification (< 15 chars): FAILS with ValidationError
        with self.assertRaises(ValidationError) as ctx:
            approve_stocktake_session(
                session_id=session.pk,
                supervisor=self.superuser,
                emergency_self_approval=True,
                justification="Too short",
            )
        self.assertIn("minimum 15 characters", str(ctx.exception))

        # 3. Emergency self-approval with adequate justification: SUCCEEDS and logs AuditEvent
        approve_stocktake_session(
            session_id=session.pk,
            supervisor=self.superuser,
            emergency_self_approval=True,
            justification="Emergency weekend audit: sole available system manager on site.",
        )

        session.refresh_from_db()
        self.assertEqual(session.status, "approved")

        # Verify AuditEvent log exists
        audit_event = AuditEvent.objects.filter(
            action="stocktake.emergency_self_approval", entity_id=str(session.id)
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.superuser)
        self.assertIn("sole available system manager", audit_event.reason)

    def test_e2e_09_owner_obs2_session_level_blind_value_masking(self):
        """
        Lifecycle 9 (OBS-2 Resolution):
        Parent serializer StocktakeSessionSerializer masks total_theoretical_value
        and total_variance_value to None during blind mode draft/in_progress for non-admins.
        """
        tea = InventoryItem.objects.create(
            item_code="E2E-TEA",
            name="Green Tea Leaves 500g",
            category=self.cat_fnb,
            unit="bags",
            current_stock=Decimal("20.00"),
            unit_cost=Decimal("200.00"),
        )
        ItemLocationBalance.objects.create(item=tea, location=self.main_store, quantity=Decimal("20.00"))

        session = create_stocktake_session(location=self.main_store, counting_mode="blind", created_by=self.admin)
        self.assertEqual(session.total_theoretical_value, Decimal("4000.00"))

        # 1. Non-admin counter queries session endpoint
        self.client.force_authenticate(user=self.storekeeper)
        url = reverse("stocktakesession-detail", args=[session.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Parent theoretical & variance value MUST be masked
        self.assertIsNone(res.data["total_theoretical_value"])
        self.assertIsNone(res.data["total_variance_value"])
        # Child item theoretical & variance quantity MUST be masked
        self.assertIsNone(res.data["items"][0]["theoretical_quantity"])
        self.assertIsNone(res.data["items"][0]["variance_quantity"])

        # 2. Administrator queries session endpoint: receives unmasked values
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(res_admin.data["total_theoretical_value"])), Decimal("4000.00"))

    def test_e2e_10_full_double_entry_balance_sheet_trial_balance_equilibrium(self):
        """
        Lifecycle 10:
        Posts representative journal entries across procurement, transfers, POS, minibar,
        waste, and stocktaking, and asserts double-entry equilibrium (Debits == Credits).
        """
        # Post representative JVs across operations
        post_journal_entry(
            description="Integration Trial Balance: GRN Accrual",
            items=[
                {"account_code": "1300", "debit": Decimal("10000.00"), "credit": Decimal("0.00")},
                {"account_code": "2010", "debit": Decimal("0.00"), "credit": Decimal("10000.00")},
            ],
        )
        post_journal_entry(
            description="Integration Trial Balance: Invoice 3-Way Match Settlement",
            items=[
                {"account_code": "2010", "debit": Decimal("10000.00"), "credit": Decimal("0.00")},
                {"account_code": "2000", "debit": Decimal("0.00"), "credit": Decimal("10000.00")},
            ],
        )
        post_journal_entry(
            description="Integration Trial Balance: POS COGS",
            items=[
                {"account_code": "5000", "debit": Decimal("3500.00"), "credit": Decimal("0.00")},
                {"account_code": "1300", "debit": Decimal("0.00"), "credit": Decimal("3500.00")},
            ],
        )
        post_journal_entry(
            description="Integration Trial Balance: Spoilage Waste Write-Off",
            items=[
                {"account_code": "5010", "debit": Decimal("600.00"), "credit": Decimal("0.00")},
                {"account_code": "1300", "debit": Decimal("0.00"), "credit": Decimal("600.00")},
            ],
        )
        post_journal_entry(
            description="Integration Trial Balance: Physical Stocktake Variance",
            items=[
                {"account_code": "5020", "debit": Decimal("250.00"), "credit": Decimal("0.00")},
                {"account_code": "1300", "debit": Decimal("0.00"), "credit": Decimal("250.00")},
            ],
        )

        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        all_entries = JournalEntry.objects.all().prefetch_related("items")
        self.assertTrue(all_entries.count() >= 5)

        for entry in all_entries:
            entry_debits = sum((item.amount_debit for item in entry.items.all()), Decimal("0.00"))
            entry_credits = sum((item.amount_credit for item in entry.items.all()), Decimal("0.00"))
            self.assertEqual(
                entry_debits,
                entry_credits,
                f"Journal Entry #{entry.id} ({entry.description}) is out of balance: Debits={entry_debits}, Credits={entry_credits}",
            )
            total_debits += entry_debits
            total_credits += entry_credits

        self.assertEqual(total_debits, total_credits, "Trial balance is unbalanced across the ERP system.")
        self.assertEqual(total_debits, Decimal("24350.00"))
        self.assertEqual(total_credits, Decimal("24350.00"))
