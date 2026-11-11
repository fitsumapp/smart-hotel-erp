"""
Dedicated Procurement RBAC & Authorization Boundary Regression Test Suite.

Target Location: apps/inventory/tests/test_procurement_rbac.py
Isolated Test Runner: manage.py test apps.inventory.tests.test_procurement_rbac --keepdb

Systematically validates:
1. Departmental Role Gating & Separation:
   - Unprivileged roles (waiter, cashier, reception, customer) are strictly denied
     access across all 7 procurement endpoints.
   - General procurement desks (Orders, RFQs, Quotations, GRNs, Invoices, Policies)
     strictly forbid all departmental staff (kitchen, bar, waiter, cashier, reception, housekeeping, customer).
2. Purchase Requisition Scoping & Safeguards:
   - Departmental staff (kitchen, bar, housekeeping) can only create requisitions for their own department.
   - Row-scoping restricts departmental staff to viewing only their own department's requisitions.
   - Conversion of requisitions to Purchase Orders is restricted strictly to Procurement Operators (admin, hotel_manager, inventory).
3. Authorized Operations:
   - inventory: Full procurement operations (view all desks, create PR, convert to PO, receive GRN, Tier 1 approvals).
   - hotel_manager: Full operational visibility and supervisory oversight across all 7 endpoints.
   - finance: Orders & invoices access, 3-way matching, invoice settlement approval, Tier 2 approvals.
   - admin: Property-wide superuser access across all endpoints, Tier 3 approvals, and policy management.
4. Separation of Duties (SoD) & Fraud Prevention:
   - Requisition requester cannot self-approve requisition (requester != approver).
   - Inventory / dock receiver cannot approve supplier invoices for payment (storekeeper != invoice approver).
   - Supplier invoice price variance overrides strictly require hotel administrator authority.
5. Multi-Tier Approval Threshold Boundaries:
   - Tier 1 (<= $10,000): inventory / kitchen / f_and_b / hotel_manager / admin authorized.
   - Tier 2 ($10,000.01 - $50,000): inventory denied; finance / admin authorized.
   - Tier 3 (> $50,000): inventory denied; finance denied; admin authorized.
"""

import datetime
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.models import (
    InventoryCategory,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    RequestForQuotation,
    RequestForQuotationItem,
    StockLocation,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierQuotation,
    SupplierQuotationItem,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
)
from hotel.procurement import (
    ensure_default_procurement_policy,
    request_purchase_requisition,
    approve_purchase_requisition,
    reject_purchase_requisition,
    convert_requisition_to_purchase_order,
    receive_goods_receipt_note,
    match_and_record_supplier_invoice,
    approve_supplier_invoice,
)
from users.models import User


class ProcurementRBACRegressionTestCase(APITestCase):
    """
    Exhaustive regression test suite verifying role-based access control (RBAC),
    Separation of Duties (SoD), and approval tier threshold boundaries across
    all 7 procurement endpoints in Acrma Hotel ERP.
    """

    @classmethod
    def setUpTestData(cls):
        # 1. Authorized Procurement Roles
        cls.admin_user = User.objects.create_user(
            username="rbac_admin", password="password123", role="admin", is_active=True, is_verified=True
        )
        cls.hotel_manager_user = User.objects.create_user(
            username="rbac_hm", password="password123", role="hotel_manager", is_active=True, is_verified=True
        )
        cls.inventory_user = User.objects.create_user(
            username="rbac_inventory", password="password123", role="inventory", is_active=True, is_verified=True
        )
        cls.inventory_user_2 = User.objects.create_user(
            username="rbac_inventory2", password="password123", role="inventory", is_active=True, is_verified=True
        )
        cls.finance_user = User.objects.create_user(
            username="rbac_finance", password="password123", role="finance", is_active=True, is_verified=True
        )

        # 2. Departmental / Operational Staff
        cls.kitchen_user = User.objects.create_user(
            username="rbac_kitchen", password="password123", role="kitchen", is_active=True, is_verified=True
        )
        cls.bar_user = User.objects.create_user(
            username="rbac_bar", password="password123", role="bar", is_active=True, is_verified=True
        )
        cls.housekeeping_user = User.objects.create_user(
            username="rbac_housekeeping", password="password123", role="housekeeping", is_active=True, is_verified=True
        )

        # 3. Line / External Roles (Strictly unprivileged on procurement)
        cls.waiter_user = User.objects.create_user(
            username="rbac_waiter", password="password123", role="waiter", is_active=True, is_verified=True
        )
        cls.cashier_user = User.objects.create_user(
            username="rbac_cashier", password="password123", role="cashier", is_active=True, is_verified=True
        )
        cls.reception_user = User.objects.create_user(
            username="rbac_reception", password="password123", role="reception", is_active=True, is_verified=True
        )
        cls.customer_user = User.objects.create_user(
            username="rbac_customer", password="password123", role="customer", is_active=True, is_verified=True
        )

        # Aggregated groups
        cls.DEPARTMENTAL_USERS = [
            cls.kitchen_user,
            cls.bar_user,
            cls.waiter_user,
            cls.cashier_user,
            cls.reception_user,
            cls.housekeeping_user,
            cls.customer_user,
        ]

        cls.UNPRIVILEGED_USERS = [
            cls.waiter_user,
            cls.cashier_user,
            cls.reception_user,
            cls.customer_user,
        ]

        cls.DEPARTMENTAL_REQUISITION_STAFF = [
            cls.kitchen_user,
            cls.bar_user,
            cls.housekeeping_user,
        ]

        # 4. Foundation Master Data
        ensure_default_accounts()
        cls.policy = ensure_default_procurement_policy()

        cls.category = InventoryCategory.objects.create(
            name="Procurement Test Category", category_type="f_and_b"
        )
        cls.main_store = StockLocation.objects.create(
            code="STORE-RBAC-01", name="Main Warehouse", location_type="warehouse", is_active=True
        )
        cls.supplier = Supplier.objects.create(
            name="Apex Foodservice Ltd", phone="+251911998877", email="orders@apexfood.com"
        )
        cls.item_small = InventoryItem.objects.create(
            item_code="RBAC-ITM-01",
            name="Table Salt 1kg",
            category=cls.category,
            unit="kg",
            current_stock=Decimal("10.00"),
            unit_cost=Decimal("50.00"),
        )
        cls.item_medium = InventoryItem.objects.create(
            item_code="RBAC-ITM-02",
            name="Cooking Oil 20L",
            category=cls.category,
            unit="tins",
            current_stock=Decimal("5.00"),
            unit_cost=Decimal("2500.00"),
        )
        cls.item_large = InventoryItem.objects.create(
            item_code="RBAC-ITM-03",
            name="Commercial Coffee Machine",
            category=cls.category,
            unit="units",
            current_stock=Decimal("1.00"),
            unit_cost=Decimal("60000.00"),
        )

        # 5. Standard Requisition Fixture (Department: inventory)
        cls.std_req = request_purchase_requisition(
            requester=cls.inventory_user,
            department="inventory",
            delivery_location=cls.main_store,
            items=[{"item_id": cls.item_small.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
            notes="Standard PR for RBAC checks",
        )

        # 6. Approved Requisition & Purchase Order Fixture
        req_for_po = request_purchase_requisition(
            requester=cls.inventory_user,
            department="inventory",
            delivery_location=cls.main_store,
            items=[{"item_id": cls.item_small.id, "quantity_requested": 20, "estimated_unit_cost": Decimal("50.00")}],
        )
        req_for_po.status = "approved"
        req_for_po.approved_by = cls.admin_user
        req_for_po.approved_at = timezone.now()
        req_for_po.save()

        cls.std_po = convert_requisition_to_purchase_order(
            requisition_id=req_for_po.id,
            issuer=cls.admin_user,
            supplier_id=cls.supplier.id,
            delivery_location_id=cls.main_store.id,
            notes="Standard PO for RBAC checks",
        )

        # 7. Goods Receipt Note Fixture
        po_item = cls.std_po.items.first()
        cls.std_grn = receive_goods_receipt_note(
            purchase_order_id=cls.std_po.id,
            receiver=cls.inventory_user,
            delivery_note_number="DN-RBAC-01",
            location_id=cls.main_store.id,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": 10}],
            notes="Standard GRN for RBAC checks",
        )

        # 8. Request For Quotation Fixture
        cls.std_rfq = RequestForQuotation.objects.create(
            rfq_number="RFQ-RBAC-01",
            title="Produce Procurement RFQ",
            created_by=cls.inventory_user,
            delivery_location=cls.main_store,
            submission_deadline=timezone.now() + datetime.timedelta(days=7),
            status="draft",
        )

        # 9. Supplier Quotation Fixture
        cls.std_quote = SupplierQuotation.objects.create(
            quotation_number="SQ-RBAC-01",
            supplier=cls.supplier,
            rfq=cls.std_rfq,
            created_by=cls.inventory_user,
            valid_until=timezone.now().date() + datetime.timedelta(days=30),
            delivery_lead_time_days=5,
            subtotal=Decimal("500.00"),
            total_quoted_amount=Decimal("500.00"),
            total_landed_cost_etb=Decimal("500.00"),
            status="submitted",
        )

        # 10. Supplier Invoice Fixture
        cls.std_invoice = match_and_record_supplier_invoice(
            purchase_order_id=cls.std_po.id,
            vendor_invoice_number="INV-RBAC-01",
            invoice_date=str(timezone.now().date()),
            due_date=str(timezone.now().date() + datetime.timedelta(days=30)),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": 10, "billed_unit_price": "50.00"}],
            matched_by=cls.finance_user,
        )

    # -------------------------------------------------------------------------
    # 1. Systematic Departmental Denials Across General Procurement Endpoints
    # -------------------------------------------------------------------------

    def test_departmental_roles_forbidden_on_procurement_orders(self):
        """Departmental staff receive HTTP 403 on PO list, retrieve, create, and receive-grn."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("purchaseorder-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PO list.")

            # Retrieve
            res = self.client.get(reverse("purchaseorder-detail", args=[self.std_po.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PO retrieve.")

            # Create
            res = self.client.post(
                reverse("purchaseorder-list"),
                {"supplier": self.supplier.id, "delivery_location": self.main_store.id},
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PO create.")

            # Receive GRN action
            res = self.client.post(
                reverse("purchaseorder-receive-grn", args=[self.std_po.id]),
                {"delivery_note_number": "DN-ATTEMPT", "items": []},
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on receive-grn.")

    def test_unprivileged_roles_forbidden_on_procurement_requisitions(self):
        """Unprivileged roles (waiter, cashier, reception, customer) receive HTTP 403 on all PR actions."""
        for user in self.UNPRIVILEGED_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("purchaserequisition-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PR list.")

            # Retrieve
            res = self.client.get(reverse("purchaserequisition-detail", args=[self.std_req.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PR retrieve.")

            # Create
            res = self.client.post(
                reverse("purchaserequisition-list"),
                {
                    "department": "kitchen",
                    "delivery_location": self.main_store.id,
                    "items": [{"item_id": self.item_small.id, "quantity_requested": 5}],
                },
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PR create.")

            # Convert to PO
            res = self.client.post(
                reverse("purchaserequisition-convert-to-po", args=[self.std_req.id]),
                {"supplier": self.supplier.id},
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on PR convert-to-po.")

    def test_departmental_requisition_scoping_and_action_guards(self):
        """Departmental staff (kitchen, bar, housekeeping) can create/view scoped PRs, but cannot convert to PO."""
        # 1. Kitchen staff can create PR for their own department -> 201 Created
        self.client.force_authenticate(user=self.kitchen_user)
        res_create = self.client.post(
            reverse("purchaserequisition-list"),
            {
                "department": "kitchen",
                "delivery_location": self.main_store.id,
                "notes": "Kitchen scoped requisition",
                "items": [{"item_id": self.item_small.id, "quantity_requested": 5, "estimated_unit_cost": "50.00"}],
            },
            format="json",
        )
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        kitchen_pr_id = res_create.data["id"]

        # 2. Kitchen staff CANNOT create PR for another department (e.g. bar) -> 403 Forbidden
        res_cross = self.client.post(
            reverse("purchaserequisition-list"),
            {
                "department": "bar",
                "delivery_location": self.main_store.id,
                "items": [{"item_id": self.item_small.id, "quantity_requested": 5}],
            },
            format="json",
        )
        self.assertEqual(res_cross.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Kitchen staff CANNOT convert requisition to PO -> 403 Forbidden (restricted to IsProcurementOperator)
        res_conv = self.client.post(
            reverse("purchaserequisition-convert-to-po", args=[kitchen_pr_id]),
            {"supplier": self.supplier.id},
            format="json",
        )
        self.assertEqual(res_conv.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Bar staff cannot see or retrieve Kitchen's requisition (row-scoping) -> 404 Not Found
        self.client.force_authenticate(user=self.bar_user)
        res_get_cross = self.client.get(reverse("purchaserequisition-detail", args=[kitchen_pr_id]))
        self.assertEqual(res_get_cross.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Bar staff CAN see their own scoped list (only bar PRs)
        res_bar_list = self.client.get(reverse("purchaserequisition-list"))
        self.assertEqual(res_bar_list.status_code, status.HTTP_200_OK)
        results = res_bar_list.data.get("results") if isinstance(res_bar_list.data, dict) else res_bar_list.data
        returned_ids = [r["id"] for r in results]
        self.assertNotIn(kitchen_pr_id, returned_ids)

        # 6. Bar staff CANNOT reject Kitchen's requisition -> 404 Not Found (row-scoping enforced via get_object)
        res_cross_rej = self.client.post(
            reverse("purchaserequisition-reject", args=[kitchen_pr_id]),
            {"reason": "Unauthorized cross-department rejection attempt"},
            format="json",
        )
        self.assertEqual(res_cross_rej.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_department_rejection_blocked(self):
        """Asserts HTTP 404 NOT FOUND when kitchen staff attempts to call POST /users/procurement/requisitions/<bar_id>/reject/."""
        pr_bar = request_purchase_requisition(
            requester=self.bar_user,
            department="bar",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_small.id, "quantity_requested": 5, "estimated_unit_cost": "20.00"}],
            notes="Bar spirits requisition for cross-department rejection test",
        )
        self.assertEqual(pr_bar.status, "pending_approval")

        # Kitchen user attempts to reject Bar's requisition -> HTTP 404 NOT FOUND via row-scoping
        self.client.force_authenticate(user=self.kitchen_user)
        res = self.client.post(
            reverse("purchaserequisition-reject", args=[pr_bar.id]),
            {"reason": "Cross-department sabotage attempt"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Confirm Bar PR remains untouched
        pr_bar.refresh_from_db()
        self.assertEqual(pr_bar.status, "pending_approval")
        self.assertEqual(pr_bar.rejection_reason, "")

    def test_unauthorized_cross_department_rejection_blocked(self):
        """Proves unauthorized cross-department users cannot reject requisitions via API or service layer."""
        pr_bar = request_purchase_requisition(
            requester=self.bar_user,
            department="bar",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_small.id, "quantity_requested": 10, "estimated_unit_cost": "25.00"}],
            notes="Bar requisitions for spirits",
        )
        self.assertEqual(pr_bar.status, "pending_approval")

        # 1. Kitchen user cannot reject Bar PR via API -> 404 Not Found
        self.client.force_authenticate(user=self.kitchen_user)
        res_api_rej = self.client.post(
            reverse("purchaserequisition-reject", args=[pr_bar.id]),
            {"reason": "Kitchen sabotage attempt"},
            format="json",
        )
        self.assertEqual(res_api_rej.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Housekeeping user cannot reject Bar PR via API -> 404 Not Found
        self.client.force_authenticate(user=self.housekeeping_user)
        res_hk_rej = self.client.post(
            reverse("purchaserequisition-reject", args=[pr_bar.id]),
            {"reason": "Housekeeping sabotage attempt"},
            format="json",
        )
        self.assertEqual(res_hk_rej.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Direct service call with cross-department rejecter raises PermissionDenied
        with self.assertRaises(PermissionDenied):
            reject_purchase_requisition(
                requisition_id=pr_bar.id,
                rejecter=self.kitchen_user,
                reason="Direct service sabotage attempt",
            )

        # 4. Confirm Bar PR status is completely untouched
        pr_bar.refresh_from_db()
        self.assertEqual(pr_bar.status, "pending_approval")
        self.assertEqual(pr_bar.rejection_reason, "")

        # 5. Privileged user (hotel_manager) CAN reject with documented reason -> 200 OK
        self.client.force_authenticate(user=self.hotel_manager_user)
        res_hm_rej = self.client.post(
            reverse("purchaserequisition-reject", args=[pr_bar.id]),
            {"reason": "Over budget for this period"},
            format="json",
        )
        self.assertEqual(res_hm_rej.status_code, status.HTTP_200_OK)
        pr_bar.refresh_from_db()
        self.assertEqual(pr_bar.status, "rejected")
        self.assertEqual(pr_bar.rejection_reason, "Over budget for this period")

    def test_departmental_roles_forbidden_on_procurement_rfqs(self):
        """Departmental staff receive HTTP 403 on RFQ list, retrieve, create, publish, and close."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("rfq-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on RFQ list.")

            # Retrieve
            res = self.client.get(reverse("rfq-detail", args=[self.std_rfq.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on RFQ retrieve.")

            # Create
            res = self.client.post(
                reverse("rfq-list"),
                {
                    "title": "Unauthorized RFQ",
                    "delivery_location": self.main_store.id,
                    "submission_deadline": "2026-12-31T23:59:59Z",
                },
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on RFQ create.")

            # Publish
            res = self.client.post(reverse("rfq-publish", args=[self.std_rfq.id]), format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on RFQ publish.")

            # Close
            res = self.client.post(reverse("rfq-close-rfq", args=[self.std_rfq.id]), format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on RFQ close.")

    def test_departmental_roles_forbidden_on_procurement_quotations(self):
        """Departmental staff receive HTTP 403 on Quotation list, retrieve, create, evaluate, award, convert."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("supplierquotation-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation list.")

            # Retrieve
            res = self.client.get(reverse("supplierquotation-detail", args=[self.std_quote.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation retrieve.")

            # Create
            res = self.client.post(
                reverse("supplierquotation-list"),
                {"supplier": self.supplier.id, "valid_until": "2026-12-31", "items": []},
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation create.")

            # Evaluate
            res = self.client.post(reverse("supplierquotation-evaluate", args=[self.std_quote.id]), format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation evaluate.")

            # Award
            res = self.client.post(reverse("supplierquotation-award-quotations"), {"awards_data": []}, format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation award.")

            # Convert to PO
            res = self.client.post(reverse("supplierquotation-convert-to-po"), {"quotation_ids": [self.std_quote.id]}, format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Quotation convert-to-po.")

    def test_departmental_roles_forbidden_on_procurement_grns(self):
        """Departmental staff receive HTTP 403 on GRN list, retrieve, and create."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("goodsreceiptnote-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on GRN list.")

            # Retrieve
            res = self.client.get(reverse("goodsreceiptnote-detail", args=[self.std_grn.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on GRN retrieve.")

            # Create
            res = self.client.post(
                reverse("goodsreceiptnote-list"),
                {"purchase_order": self.std_po.id, "items": []},
                format="json",
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on GRN create.")

    def test_departmental_roles_forbidden_on_procurement_invoices(self):
        """Departmental staff receive HTTP 403 on Invoice list, retrieve, create, match-and-record, approve."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("supplierinvoice-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Invoice list.")

            # Retrieve
            res = self.client.get(reverse("supplierinvoice-detail", args=[self.std_invoice.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Invoice retrieve.")

            # Create / Match-and-record
            res = self.client.post(reverse("supplierinvoice-match-and-record"), {"purchase_order": self.std_po.id}, format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Invoice match-and-record.")

            # Approve
            res = self.client.post(reverse("supplierinvoice-approve", args=[self.std_invoice.id]), format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Invoice approve.")

    def test_departmental_roles_forbidden_on_procurement_policies(self):
        """Departmental staff receive HTTP 403 on Policy list, retrieve, and create."""
        for user in self.DEPARTMENTAL_USERS:
            self.client.force_authenticate(user=user)

            # List
            res = self.client.get(reverse("procurementpolicy-list"))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Policy list.")

            # Retrieve
            res = self.client.get(reverse("procurementpolicy-detail", args=[self.policy.id]))
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Policy retrieve.")

            # Create
            res = self.client.post(reverse("procurementpolicy-list"), {"name": "Unauthorized Policy"}, format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role '{user.role}' was not forbidden on Policy create.")

    # -------------------------------------------------------------------------
    # 2. Authorized Operations for Permitted Roles
    # -------------------------------------------------------------------------

    def test_inventory_role_authorized_procurement_access(self):
        """Inventory staff has full operational procurement capabilities (list, retrieve, create, convert, receive)."""
        self.client.force_authenticate(user=self.inventory_user)

        # 1. View lists
        self.assertEqual(self.client.get(reverse("purchaseorder-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("purchaserequisition-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("rfq-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierquotation-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("goodsreceiptnote-list")).status_code, status.HTTP_200_OK)

        # 2. Create Requisition
        req_res = self.client.post(
            reverse("purchaserequisition-list"),
            {
                "department": "kitchen",
                "delivery_location": self.main_store.id,
                "notes": "Inventory user PR creation test",
                "items": [{"item_id": self.item_small.id, "quantity_requested": 5, "estimated_unit_cost": "50.00"}],
            },
            format="json",
        )
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        new_req_id = req_res.data["id"]

        # 3. Managerial approval by peer inventory user
        self.client.force_authenticate(user=self.inventory_user_2)
        app_res = self.client.post(reverse("purchaserequisition-approve", args=[new_req_id]), format="json")
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)

        # 4. Convert Requisition to PO
        po_res = self.client.post(
            reverse("purchaserequisition-convert-to-po", args=[new_req_id]),
            {"supplier": self.supplier.id, "delivery_location": self.main_store.id},
            format="json",
        )
        self.assertEqual(po_res.status_code, status.HTTP_201_CREATED)
        po_id = po_res.data["id"]
        po_item_id = po_res.data["items"][0]["id"]

        # 5. Receive GRN
        grn_res = self.client.post(
            reverse("purchaseorder-receive-grn", args=[po_id]),
            {
                "delivery_note_number": "DN-INV-001",
                "location": self.main_store.id,
                "items": [{"po_item_id": po_item_id, "quantity_received": 5}],
            },
            format="json",
        )
        self.assertEqual(grn_res.status_code, status.HTTP_201_CREATED)

    def test_hotel_manager_role_authorized_procurement_access(self):
        """Hotel Manager has operational visibility across all 7 procurement endpoints."""
        self.client.force_authenticate(user=self.hotel_manager_user)

        self.assertEqual(self.client.get(reverse("purchaserequisition-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("purchaseorder-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("rfq-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierquotation-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("goodsreceiptnote-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierinvoice-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("procurementpolicy-list")).status_code, status.HTTP_200_OK)

    def test_finance_role_procurement_access_and_matching(self):
        """Finance staff has access to orders/invoices, performs 3-way matching and invoice approval."""
        self.client.force_authenticate(user=self.finance_user)

        # Access orders and invoices
        self.assertEqual(self.client.get(reverse("purchaseorder-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierinvoice-list")).status_code, status.HTTP_200_OK)

        # Approve invoice
        app_res = self.client.post(reverse("supplierinvoice-approve", args=[self.std_invoice.id]), format="json")
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)
        self.assertEqual(app_res.data["match_status"], "approved")

    def test_finance_cannot_receive_grn_or_create_po(self):
        """Finance staff cannot create purchase orders or receive goods at the dock (SoD)."""
        self.client.force_authenticate(user=self.finance_user)

        # PO Create denied
        res_po = self.client.post(
            reverse("purchaseorder-list"),
            {"supplier": self.supplier.id, "delivery_location": self.main_store.id},
            format="json",
        )
        self.assertEqual(res_po.status_code, status.HTTP_403_FORBIDDEN)

        # Receive GRN action denied
        res_grn = self.client.post(
            reverse("purchaseorder-receive-grn", args=[self.std_po.id]),
            {"delivery_note_number": "DN-FINANCE", "items": [{"po_item_id": self.std_po.items.first().id, "quantity_received": 1}]},
            format="json",
        )
        self.assertEqual(res_grn.status_code, status.HTTP_403_FORBIDDEN)

    def test_inventory_cannot_approve_invoice_sod(self):
        """Inventory staff cannot approve supplier invoices for financial settlement (SoD)."""
        self.client.force_authenticate(user=self.inventory_user)
        res = self.client.post(reverse("supplierinvoice-approve", args=[self.std_invoice.id]), format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_dock_receiver_cannot_approve_invoice_sod(self):
        """Dock receiver who received goods cannot approve supplier invoice payment (anti-embezzlement SoD)."""
        # If a finance user was somehow recorded as dock receiver, they cannot approve payment
        finance_receiver = User.objects.create_user(
            username="rbac_fin_receiver", password="password123", role="finance", is_active=True, is_verified=True
        )

        # Create PO & GRN received by finance_receiver
        po_item = self.std_po.items.first()
        grn = GoodsReceiptNote.objects.create(
            grn_number="GRN-SOD-CHECK",
            purchase_order=self.std_po,
            supplier=self.supplier,
            location=self.main_store,
            delivery_note_number="DN-SOD-01",
            status="draft",
            received_by=finance_receiver,
            received_at=timezone.now(),
        )

        invoice = match_and_record_supplier_invoice(
            purchase_order_id=self.std_po.id,
            vendor_invoice_number="INV-SOD-TEST",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": 5, "billed_unit_price": "50.00"}],
            matched_by=self.finance_user,
        )

        # finance_receiver attempts to approve invoice
        self.client.force_authenticate(user=finance_receiver)
        res = self.client.post(reverse("supplierinvoice-approve", args=[invoice.id]), format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Dock receiver cannot approve invoice payment", str(res.data.get("error", "")))

    def test_admin_role_full_property_wide_access(self):
        """Admin has full property-wide access across all 7 endpoints and can modify policies."""
        self.client.force_authenticate(user=self.admin_user)

        self.assertEqual(self.client.get(reverse("procurementpolicy-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("purchaserequisition-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("purchaseorder-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("goodsreceiptnote-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierinvoice-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("rfq-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("supplierquotation-list")).status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 3. Separation of Duties (SoD) Testing
    # -------------------------------------------------------------------------

    def test_separation_of_duties_requester_cannot_approve_own_requisition(self):
        """Requester cannot self-approve their own requisition even if they hold the approval role."""
        # Inventory User 1 creates requisition
        req = request_purchase_requisition(
            requester=self.inventory_user,
            department="inventory",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_small.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
        )

        # Inventory User 1 attempts to approve own requisition
        self.client.force_authenticate(user=self.inventory_user)
        res = self.client.post(reverse("purchaserequisition-approve", args=[req.id]), format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Separation of duties violation", str(res.data.get("error", "")))

        # Peer Inventory User 2 approves -> Success
        self.client.force_authenticate(user=self.inventory_user_2)
        res_peer = self.client.post(reverse("purchaserequisition-approve", args=[req.id]), format="json")
        self.assertEqual(res_peer.status_code, status.HTTP_200_OK)
        self.assertEqual(res_peer.data["status"], "approved")

    # -------------------------------------------------------------------------
    # 4. Multi-Tier Approval Threshold Boundary Testing
    # -------------------------------------------------------------------------

    def test_tier_threshold_boundary_enforcement(self):
        """Validates role-based threshold authority across Tier 1 (<=10k), Tier 2 (<=50k), Tier 3 (>50k)."""

        # Tier 1 Requisition (Total = $5,000 <= $10,000)
        req_t1 = request_purchase_requisition(
            requester=self.inventory_user,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_medium.id, "quantity_requested": 2, "estimated_unit_cost": Decimal("2500.00")}],
        )
        self.assertEqual(req_t1.approval_tier.tier_level, 1)

        # Inventory User 2 approves Tier 1 -> Allowed
        self.client.force_authenticate(user=self.inventory_user_2)
        res_t1 = self.client.post(reverse("purchaserequisition-approve", args=[req_t1.id]), format="json")
        self.assertEqual(res_t1.status_code, status.HTTP_200_OK)

        # Tier 2 Requisition (Total = $25,000: $10,000.01 - $50,000)
        req_t2 = request_purchase_requisition(
            requester=self.inventory_user,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_medium.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("2500.00")}],
        )
        self.assertEqual(req_t2.approval_tier.tier_level, 2)

        # Inventory User 2 attempts Tier 2 -> Denied with HTTP 403 Forbidden
        self.client.force_authenticate(user=self.inventory_user_2)
        res_t2_inv = self.client.post(reverse("purchaserequisition-approve", args=[req_t2.id]), format="json")
        self.assertEqual(res_t2_inv.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("not authorized to approve", str(res_t2_inv.data.get("error", "")))

        # Finance User approves Tier 2 -> Allowed
        self.client.force_authenticate(user=self.finance_user)
        res_t2_fin = self.client.post(reverse("purchaserequisition-approve", args=[req_t2.id]), format="json")
        self.assertEqual(res_t2_fin.status_code, status.HTTP_200_OK)

        # Tier 3 Requisition (Total = $60,000 > $50,000)
        req_t3 = request_purchase_requisition(
            requester=self.inventory_user,
            department="kitchen",
            delivery_location=self.main_store,
            items=[{"item_id": self.item_large.id, "quantity_requested": 1, "estimated_unit_cost": Decimal("60000.00")}],
        )
        self.assertEqual(req_t3.approval_tier.tier_level, 3)

        # Inventory User attempts Tier 3 -> Denied
        self.client.force_authenticate(user=self.inventory_user_2)
        res_t3_inv = self.client.post(reverse("purchaserequisition-approve", args=[req_t3.id]), format="json")
        self.assertEqual(res_t3_inv.status_code, status.HTTP_403_FORBIDDEN)

        # Finance User attempts Tier 3 -> Denied
        self.client.force_authenticate(user=self.finance_user)
        res_t3_fin = self.client.post(reverse("purchaserequisition-approve", args=[req_t3.id]), format="json")
        self.assertEqual(res_t3_fin.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("not authorized to approve", str(res_t3_fin.data.get("error", "")))

        # Admin User approves Tier 3 -> Allowed
        self.client.force_authenticate(user=self.admin_user)
        res_t3_adm = self.client.post(reverse("purchaserequisition-approve", args=[req_t3.id]), format="json")
        self.assertEqual(res_t3_adm.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 5. Price Variance Override Authority Testing
    # -------------------------------------------------------------------------

    def test_price_variance_override_requires_admin(self):
        """Flagged price variance can only be overridden by hotel administrators."""
        po_item = self.std_po.items.first()
        # Bill 100 per unit instead of 50 -> 100% variance (flagged)
        invoice = match_and_record_supplier_invoice(
            purchase_order_id=self.std_po.id,
            vendor_invoice_number="INV-FLAGGED-01",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": 5, "billed_unit_price": "100.00"}],
            matched_by=self.finance_user,
        )
        self.assertEqual(invoice.match_status, "variance_flagged")

        # Finance user attempts override -> 403 Forbidden
        self.client.force_authenticate(user=self.finance_user)
        res_fin = self.client.post(
            reverse("supplierinvoice-approve", args=[invoice.id]),
            {"override_variance": True, "variance_justification": "Finance override attempt"},
            format="json",
        )
        self.assertEqual(res_fin.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Only hotel administrators can authorize supplier invoice price variance overrides", str(res_fin.data.get("error", "")))

        # Admin user overrides -> 200 OK
        self.client.force_authenticate(user=self.admin_user)
        res_adm = self.client.post(
            reverse("supplierinvoice-approve", args=[invoice.id]),
            {"override_variance": True, "variance_justification": "Admin approved surge cost"},
            format="json",
        )
        self.assertEqual(res_adm.status_code, status.HTTP_200_OK)
        self.assertEqual(res_adm.data["match_status"], "approved")
