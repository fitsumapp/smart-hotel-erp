"""
Phase 1.4 Configurable Procurement Management & 3-Way Match GRNI Tests.
Validates:
1. Dynamic tier creation & threshold evaluation (Owner Decision 3).
2. Requisition creation & separation-of-duties self-approval rejection.
3. Managerial approval and conversion of PR to PO.
4. PO issuance and supplier contract price locking.
5. GRN physical receipt into STORE-MAIN with StockBatch creation.
6. Mandatory perishable expiry date enforcement on GRN.
7. GRNI accrual accounting entry auto-posting (Dr 1300, Cr 2010).
8. Partial GRN receipt updating PO quantities and statuses.
9. 3-Way Match exact match approval and GRNI clearing (Dr 2010, Cr 2000).
10. 3-Way Match price variance flagged when exceeding tolerance.
11. 3-Way Match approved price variance posting to PPV (Dr 5040).
12. Over-billing quantity rejection and API endpoints.
"""
import datetime
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.models import (
    Account,
    BatchLocationBalance,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    InventoryCategory,
    InventoryItem,
    ItemLocationBalance,
    JournalEntry,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    StockBatch,
    StockLocation,
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
    reject_purchase_requisition,
    request_purchase_requisition,
    resolve_approval_tier,
)
from users.models import User


class ProcurementManagementTestCase(APITestCase):
    def setUp(self):
        # 1. Setup Users
        self.admin = User.objects.create_user(
            username="admin_proc", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.storekeeper = User.objects.create_user(
            username="storekeeper_proc", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.chef = User.objects.create_user(
            username="chef_proc", password="password123", role="kitchen", is_active=True, is_verified=True
        )
        self.finance_user = User.objects.create_user(
            username="finance_proc", password="password123", role="finance", is_active=True, is_verified=True
        )

        # 2. Setup Category & Supplier
        self.category, _ = InventoryCategory.objects.get_or_create(
            name="Procurement Test Category", defaults={"category_type": "f_and_b"}
        )
        self.supplier, _ = Supplier.objects.get_or_create(
            name="Alpha Supplies Ltd",
            defaults={"phone": "+251911002233", "email": "alpha@supplies.com"},
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

        # 4. Setup Chart of Accounts (includes 1300, 2000, 2010 GRNI, 5040 PPV)
        ensure_default_accounts()

        # 5. Setup Default Procurement Approval Policy
        self.policy = ensure_default_procurement_policy()

        self.today = timezone.now().date()

    def test_01_dynamic_tier_creation_and_threshold_evaluation(self):
        """Owner Decision 3: Approval thresholds are dynamic and configurable per department/tier."""
        # Check default policy tiers exist
        tiers = self.policy.tiers.all().order_by("tier_level")
        self.assertTrue(tiers.count() >= 3)
        tier_supervisor = tiers[0]
        tier_manager = tiers[1]
        tier_exec = tiers[2]

        # Amount within supervisor limit
        t1 = resolve_approval_tier(Decimal("3000.00"), department="kitchen")
        self.assertEqual(t1.required_role, tier_supervisor.required_role)

        # Amount requiring manager
        t2 = resolve_approval_tier(Decimal("15000.00"), department="kitchen")
        self.assertEqual(t2.required_role, tier_manager.required_role)

        # Amount requiring executive
        t3 = resolve_approval_tier(Decimal("75000.00"), department="kitchen")
        self.assertEqual(t3.required_role, tier_exec.required_role)

        # Verify dynamic update: Change supervisor threshold to 10,000
        tier_supervisor.max_amount = Decimal("10000.00")
        tier_supervisor.save()
        tier_manager.min_amount = Decimal("10000.01")
        tier_manager.save()

        # Now 8,000 should resolve to supervisor
        t_updated = resolve_approval_tier(Decimal("8000.00"), department="kitchen")
        self.assertEqual(t_updated.required_role, tier_supervisor.required_role)

    def test_02_requisition_creation_and_self_approval_prevention(self):
        """Requisition created by department head; self-approval is rejected by separation of duties."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-01",
            name="Organic Flour 25kg",
            category=self.category,
            unit="bags",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("1500.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("1500.00")}],
            notes="Restock for bakery section",
        )

        self.assertEqual(req.status, "pending_approval")
        self.assertEqual(req.total_estimated_amount, Decimal("15000.00"))
        self.assertEqual(req.items.count(), 1)

        # Chef attempts to approve own requisition -> ValidationError
        with self.assertRaises(ValidationError) as ctx:
            approve_purchase_requisition(requisition_id=req.id, approver=self.chef)
        self.assertIn("Separation of duties violation", str(ctx.exception))

    def test_03_managerial_approval_and_conversion_to_po(self):
        """Managerial approval of requisition allows conversion to Purchase Order."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-02",
            name="Basmati Rice 20kg",
            category=self.category,
            unit="bags",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("1200.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": item.id, "quantity_requested": 5, "estimated_unit_cost": Decimal("1200.00")}],
        )

        # Inventory manager approves
        approved_req = approve_purchase_requisition(
            requisition_id=req.id, approver=self.storekeeper, notes="Approved for kitchen"
        )
        self.assertEqual(approved_req.status, "approved")
        self.assertEqual(approved_req.approved_by, self.storekeeper)

        # Convert to Purchase Order
        po = convert_requisition_to_purchase_order(
            requisition_id=approved_req.id,
            issuer=self.storekeeper,
            supplier_id=self.supplier.id,
            delivery_due_date=self.today + datetime.timedelta(days=7),
            payment_terms="Net 30 Days",
        )

        self.assertEqual(po.status, "issued")
        self.assertEqual(po.supplier, self.supplier)
        self.assertEqual(po.requisition, approved_req)
        self.assertTrue(po.po_number.startswith("PO-"))
        self.assertEqual(po.items.count(), 1)
        self.assertEqual(po.subtotal, Decimal("6000.00"))
        self.assertEqual(po.total_amount, Decimal("6000.00"))

    def test_04_po_issuance_and_supplier_contract_pricing(self):
        """PO issuance locks supplier contract price overriding requisition estimates if specified."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-03",
            name="Olive Oil Extra Virgin 5L",
            category=self.category,
            unit="tins",
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("800.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": item.id, "quantity_requested": 4, "estimated_unit_cost": Decimal("800.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)

        # Contract price is 850.00 instead of estimated 800.00
        po = convert_requisition_to_purchase_order(
            requisition_id=req.id,
            issuer=self.admin,
            supplier_id=self.supplier.id,
            item_prices={item.id: Decimal("850.00")},
        )

        po_item = po.items.first()
        self.assertEqual(po_item.unit_price, Decimal("850.00"))
        self.assertEqual(po_item.line_total, Decimal("3400.00"))
        self.assertEqual(po.total_amount, Decimal("3400.00"))

    def test_05_grn_physical_receipt_and_stock_batch_creation(self):
        """GRN receipt creates verified StockBatch, updates location balances and aggregate item stock."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-04",
            name="Granulated Sugar 50kg",
            category=self.category,
            unit="bags",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("2000.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("2000.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        # Receive 10 bags via GRN
        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            delivery_note_number="DN-SUGAR-99",
            receipt_items=[
                {
                    "po_item_id": po.items.first().id,
                    "quantity_received": 10,
                    "supplier_batch_number": "SUP-BAT-901",
                }
            ],
            notes="All bags intact and clean",
        )

        self.assertEqual(grn.status, "approved")
        self.assertEqual(grn.total_received_cost, Decimal("20000.00"))

        # Verify StockBatch created
        grn_item = grn.items.first()
        batch = grn_item.batch
        self.assertIsNotNone(batch)
        self.assertEqual(batch.status, "active")
        self.assertEqual(batch.current_quantity, Decimal("10.00"))
        self.assertEqual(batch.unit_cost, Decimal("2000.00"))
        self.assertEqual(batch.supplier, self.supplier)

        # Verify Location Balance at STORE-MAIN
        loc_bal = ItemLocationBalance.objects.get(item=item, location=self.main_store)
        self.assertEqual(loc_bal.quantity, Decimal("10.00"))

        batch_loc_bal = BatchLocationBalance.objects.get(batch=batch, location=self.main_store)
        self.assertEqual(batch_loc_bal.quantity, Decimal("10.00"))

        # Verify aggregate stock
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("10.00"))

    def test_06_mandatory_perishable_expiry_enforcement_on_grn(self):
        """Perishable item received without expiry date or with past expiry date must be strictly rejected."""
        item = InventoryItem.objects.create(
            item_code="PROC-PERISH-01",
            name="Fresh Pasteurized Milk 1L",
            category=self.category,
            unit="bottles",
            is_perishable=True,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("60.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 20, "estimated_unit_cost": Decimal("60.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        # Missing expiry date on perishable item
        with self.assertRaises(ValidationError) as ctx:
            receive_goods_receipt_note(
                purchase_order_id=po.id,
                receiver=self.storekeeper,
                receipt_items=[
                    {
                        "po_item_id": po.items.first().id,
                        "quantity_received": 20,
                    }
                ],
            )
        self.assertIn("Mandatory expiry date is required for perishable item", str(ctx.exception))

        # Past expiry date on perishable item
        with self.assertRaises(ValidationError) as ctx_past:
            receive_goods_receipt_note(
                purchase_order_id=po.id,
                receiver=self.storekeeper,
                receipt_items=[
                    {
                        "po_item_id": po.items.first().id,
                        "quantity_received": 20,
                        "expiry_date": self.today - datetime.timedelta(days=1),
                    }
                ],
            )
        self.assertIn("Cannot receive batch with a past expiry date", str(ctx_past.exception))

    def test_07_grni_accrual_accounting_entry_autoposting(self):
        """GRN receipt generates balanced GL Journal Entry: Dr 1300 Inventory Asset, Cr 2010 GRNI Accrual."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-05",
            name="Canned Tomatoes 800g",
            category=self.category,
            unit="cans",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("75.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 100, "estimated_unit_cost": Decimal("75.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po.items.first().id, "quantity_received": 100}],
        )

        self.assertIsNotNone(grn.journal_entry)
        jv = grn.journal_entry
        self.assertIsNotNone(jv.entry_number)

        jv_items = list(jv.items.all())
        self.assertEqual(len(jv_items), 2)

        # Check Dr 1300 and Cr 2010
        dr_item = [i for i in jv_items if i.amount_debit > 0][0]
        cr_item = [i for i in jv_items if i.amount_credit > 0][0]

        self.assertEqual(dr_item.account.code, "1300")  # Inventory Asset
        self.assertEqual(dr_item.amount_debit, Decimal("7500.00"))

        self.assertEqual(cr_item.account.code, "2010")  # GRNI Accrual
        self.assertEqual(cr_item.amount_credit, Decimal("7500.00"))

        # Exact debits == credits
        total_debits = sum(i.amount_debit for i in jv_items)
        total_credits = sum(i.amount_credit for i in jv_items)
        self.assertEqual(total_debits, total_credits)

    def test_08_partial_grn_receipt_and_po_status(self):
        """Partial GRN receipt transitions PO to partially_received; final receipt completes it."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-06",
            name="Mineral Water 500ml",
            category=self.category,
            unit="bottles",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("20.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="bar",
            items=[{"item_id": item.id, "quantity_requested": 50, "estimated_unit_cost": Decimal("20.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        po_item = po.items.first()

        # Partial receipt 1: 20 bottles
        grn1 = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": 20}],
        )
        po.refresh_from_db()
        po_item.refresh_from_db()
        self.assertEqual(po.status, "partially_received")
        self.assertEqual(po_item.quantity_received, Decimal("20.00"))

        # Partial receipt 2: remaining 30 bottles
        grn2 = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": 30}],
        )
        po.refresh_from_db()
        po_item.refresh_from_db()
        self.assertEqual(po.status, "received")
        self.assertEqual(po_item.quantity_received, Decimal("50.00"))

    def test_09_three_way_match_exact_and_grni_clearing(self):
        """3-Way Match exact match: Supplier invoice matches PO and GRN; clears GRNI to AP."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-07",
            name="Ground Coffee 1kg",
            category=self.category,
            unit="packs",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("350.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("350.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po.items.first().id, "quantity_received": 10}],
        )

        # Record and match invoice with exact quantities and prices
        invoice = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-COFFEE-001",
            invoice_date=self.today,
            billed_items=[{"po_item_id": po.items.first().id, "billed_quantity": 10, "billed_unit_price": Decimal("350.00")}],
            matched_by=self.finance_user,
        )

        self.assertEqual(invoice.match_status, "matched")
        self.assertEqual(invoice.total_amount, Decimal("3500.00"))

        # Finance user approves invoice for payment
        approved_inv = approve_supplier_invoice(invoice_id=invoice.id, approver=self.finance_user)
        self.assertIsNotNone(approved_inv.approved_at)
        self.assertIsNotNone(approved_inv.journal_entry)

        jv = approved_inv.journal_entry
        jv_items = list(jv.items.all())
        self.assertEqual(len(jv_items), 2)

        dr_grni = [i for i in jv_items if i.account.code == "2010"][0]
        cr_ap = [i for i in jv_items if i.account.code == "2000"][0]

        self.assertEqual(dr_grni.amount_debit, Decimal("3500.00"))
        self.assertEqual(cr_ap.amount_credit, Decimal("3500.00"))

    def test_10_three_way_match_price_variance_tolerance(self):
        """Price variance exceeding policy tolerance (e.g. 5%) is flagged and blocks unauthorized approval."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-08",
            name="Butter Salted 500g",
            category=self.category,
            unit="blocks",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("100.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("100.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po.items.first().id, "quantity_received": 10}],
        )

        # Supplier bills 110.00 per unit (10% higher, exceeding 2% tolerance)
        invoice = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-BUTTER-999",
            invoice_date=self.today,
            billed_items=[{"po_item_id": po.items.first().id, "billed_quantity": 10, "billed_unit_price": Decimal("110.00")}],
            matched_by=self.finance_user,
        )

        self.assertEqual(invoice.match_status, "variance_flagged")
        self.assertTrue(invoice.items.first().price_variance > 0)

        # Standard approval without override fails
        with self.assertRaises(ValidationError) as ctx:
            approve_supplier_invoice(invoice_id=invoice.id, approver=self.finance_user, override_variance=False)
        self.assertIn("cannot be approved due to price variance", str(ctx.exception))

    def test_11_three_way_match_approved_variance_posts_to_ppv(self):
        """Approved price variance posts delta to Account 5040 (Purchase Price Variance)."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-09",
            name="Imported Cheese 1kg",
            category=self.category,
            unit="blocks",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("500.00"),
        )

        req = request_purchase_requisition(
            requester=self.chef,
            department="kitchen",
            items=[{"item_id": item.id, "quantity_requested": 4, "estimated_unit_cost": Decimal("500.00")}],
        )
        approve_purchase_requisition(requisition_id=req.id, approver=self.admin)
        po = convert_requisition_to_purchase_order(requisition_id=req.id, issuer=self.admin, supplier_id=self.supplier.id)

        # Received 4 units @ 500.00 = 2000.00 (posted to GRNI)
        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=self.storekeeper,
            receipt_items=[{"po_item_id": po.items.first().id, "quantity_received": 4}],
        )

        # Supplier bills 4 units @ 550.00 = 2200.00 (Variance = +200.00)
        invoice = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-CHEESE-VAR",
            invoice_date=self.today,
            billed_items=[{"po_item_id": po.items.first().id, "billed_quantity": 4, "billed_unit_price": Decimal("550.00")}],
            matched_by=self.finance_user,
        )

        # Admin overrides variance with justification
        approved_inv = approve_supplier_invoice(
            invoice_id=invoice.id,
            approver=self.admin,
            override_variance=True,
            variance_justification="Market price surge approved by GM",
        )

        self.assertEqual(approved_inv.match_status, "approved")
        self.assertIn("approved", approved_inv.variance_notes.lower())
        jv = approved_inv.journal_entry
        jv_items = list(jv.items.all())

        dr_grni = [i for i in jv_items if i.account.code == "2010"][0]
        dr_ppv = [i for i in jv_items if i.account.code == "5040"][0]
        cr_ap = [i for i in jv_items if i.account.code == "2000"][0]

        # Dr 2010 GRNI: 2000.00
        self.assertEqual(dr_grni.amount_debit, Decimal("2000.00"))
        # Dr 5040 PPV: 200.00
        self.assertEqual(dr_ppv.amount_debit, Decimal("200.00"))
        # Cr 2000 AP: 2200.00
        self.assertEqual(cr_ap.amount_credit, Decimal("2200.00"))

        # Equality of debits and credits
        total_debits = sum(i.amount_debit for i in jv_items)
        total_credits = sum(i.amount_credit for i in jv_items)
        self.assertEqual(total_debits, total_credits)

    def test_12_overbilling_quantity_rejection_and_api_endpoints(self):
        """Billed quantity exceeding received quantity is rejected; validates full DRF API lifecycle."""
        item = InventoryItem.objects.create(
            item_code="PROC-ITEM-10",
            name="Cooking Wine 750ml",
            category=self.category,
            unit="bottles",
            is_perishable=False,
            current_stock=Decimal("0.00"),
            unit_cost=Decimal("150.00"),
        )

        # 1. API: Requisition creation
        self.client.force_authenticate(user=self.chef)
        req_res = self.client.post(
            "/api/users/procurement/requisitions/",
            {
                "department": "kitchen",
                "delivery_location": self.main_store.id,
                "notes": "End-to-end API test",
                "items": [{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": "150.00"}],
            },
            format="json",
        )
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        req_id = req_res.data["id"]

        # 2. API: Manager approval
        self.client.force_authenticate(user=self.storekeeper)
        app_res = self.client.post(f"/api/users/procurement/requisitions/{req_id}/approve/", format="json")
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)

        # 3. API: Convert to PO
        po_res = self.client.post(
            f"/api/users/procurement/requisitions/{req_id}/convert-to-po/",
            {"supplier": self.supplier.id},
            format="json",
        )
        self.assertEqual(po_res.status_code, status.HTTP_201_CREATED)
        po_id = po_res.data["id"]
        po_item_id = po_res.data["items"][0]["id"]

        # 4. API: Receive GRN (8 units received)
        grn_res = self.client.post(
            f"/api/users/procurement/orders/{po_id}/receive-grn/",
            {
                "delivery_note_number": "DN-API-01",
                "items": [{"po_item_id": po_item_id, "quantity_received": 8}],
            },
            format="json",
        )
        self.assertEqual(grn_res.status_code, status.HTTP_201_CREATED)

        # 5. API: Over-billing attempt (bill for 12 units when only 8 received) -> 400 Bad Request
        self.client.force_authenticate(user=self.finance_user)
        overbill_res = self.client.post(
            "/api/users/procurement/invoices/match-and-record/",
            {
                "purchase_order": po_id,
                "vendor_invoice_number": "INV-OVERBILL-99",
                "invoice_date": str(self.today),
                "items": [{"po_item_id": po_item_id, "billed_quantity": 12, "billed_unit_price": "150.00"}],
            },
            format="json",
        )
        self.assertEqual(overbill_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds grn received quantity", str(overbill_res.data["error"]).lower())

        # 6. API: Valid billing for 8 units -> 201 Created
        inv_res = self.client.post(
            "/api/users/procurement/invoices/match-and-record/",
            {
                "purchase_order": po_id,
                "vendor_invoice_number": "INV-VALID-88",
                "invoice_date": str(self.today),
                "items": [{"po_item_id": po_item_id, "billed_quantity": 8, "billed_unit_price": "150.00"}],
            },
            format="json",
        )
        self.assertEqual(inv_res.status_code, status.HTTP_201_CREATED)
        inv_id = inv_res.data["id"]

        # 7. API: Approve invoice
        app_inv_res = self.client.post(f"/api/users/procurement/invoices/{inv_id}/approve/", format="json")
        self.assertEqual(app_inv_res.status_code, status.HTTP_200_OK)
        self.assertEqual(app_inv_res.data["match_status"], "approved")
