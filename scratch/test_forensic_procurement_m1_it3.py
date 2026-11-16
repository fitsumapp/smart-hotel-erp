"""
scratch/test_forensic_procurement_m1_it3.py
Authoritative Forensic Integrity Verification Harness for Milestone 1 Iteration 3.
Inspects DRF procurement endpoints and service layer role boundaries.
All mutation tests run inside atomic rollbacks.
"""
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

import users.urls  # Register all URLs and viewsets
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    StockLocation,
    InventoryItem,
    InventoryCategory,
    PurchaseRequisition,
    PurchaseOrder,
    GoodsReceiptNote,
    SupplierInvoice,
    RequestForQuotation,
    SupplierQuotation,
    ProcurementApprovalPolicy,
    Supplier,
)
from hotel.procurement import (
    _validate_procurement_role,
    approve_purchase_requisition,
    convert_requisition_to_purchase_order,
    receive_goods_receipt_note,
    approve_supplier_invoice,
)

User = get_user_model()


def run_forensic_audit():
    print("=" * 75)
    print("M1-IT3 FORENSIC AUDIT: PROCUREMENT RBAC & SERVICE LAYER VALIDATION")
    print("=" * 75)

    client = APIClient()

    # Find users for each role from staging database
    roles = [
        "admin", "hotel_manager", "inventory", "finance",
        "kitchen", "bar", "waiter", "cashier", "reception", "housekeeping", "customer"
    ]
    users_by_role = {}
    for r in roles:
        u = User.objects.filter(role=r, is_active=True).first()
        if not u:
            # Try any user with this role
            u = User.objects.filter(role=r).first()
        users_by_role[r] = u
        print(f"Role '{r}': User ID {getattr(u, 'id', None)} ({getattr(u, 'username', 'N/A')})")

    # -------------------------------------------------------------------------
    # PART 1: HTTP GET Access Across All 7 Procurement Endpoints
    # -------------------------------------------------------------------------
    print("\n" + "-" * 75)
    print("PART 1: HTTP GET ENDPOINT RBAC PROBING")
    print("-" * 75)

    endpoints = [
        ("orders", "/users/procurement/orders/"),
        ("grns", "/users/procurement/grns/"),
        ("invoices", "/users/procurement/invoices/"),
        ("rfqs", "/users/procurement/rfqs/"),
        ("quotations", "/users/procurement/quotations/"),
        ("policies", "/users/procurement/policies/"),
        ("requisitions", "/users/procurement/requisitions/"),
    ]

    # Departmental roles that MUST receive 403 on general procurement endpoints
    forbidden_departmental_roles = ["kitchen", "bar", "waiter", "cashier", "customer"]

    for desk_name, endpoint in endpoints:
        print(f"\n[Desk: {desk_name.upper()}] URL: {endpoint}")
        for r in roles:
            u = users_by_role[r]
            if not u:
                continue
            client.force_authenticate(user=u)
            res = client.get(endpoint)
            status_code = res.status_code

            if desk_name == "requisitions":
                # Kitchen, bar, housekeeping, inventory, finance, hotel_manager, admin -> 200 OK
                # Waiter, cashier, reception, customer -> 403 Forbidden
                if r in ["waiter", "cashier", "reception", "customer"]:
                    assert status_code == status.HTTP_403_FORBIDDEN, (
                        f"SECURITY VIOLATION: Role '{r}' received {status_code} on {endpoint}, expected 403!"
                    )
                    print(f"  {r:15} -> {status_code} Forbidden (EXPECTED RESTRICTION)")
                else:
                    assert status_code == status.HTTP_200_OK, (
                        f"UNEXPECTED DENIAL: Role '{r}' received {status_code} on {endpoint}, expected 200!"
                    )
                    print(f"  {r:15} -> {status_code} OK (AUTHORIZED)")
            elif desk_name == "policies":
                # Gated with IsInventoryManager: admin, hotel_manager, inventory -> 200
                # finance, kitchen, bar, waiter, cashier, customer, etc. -> 403
                if r in ["admin", "hotel_manager", "inventory"]:
                    assert status_code == status.HTTP_200_OK, (
                        f"UNEXPECTED DENIAL: Role '{r}' received {status_code} on {endpoint}, expected 200!"
                    )
                    print(f"  {r:15} -> {status_code} OK (AUTHORIZED)")
                else:
                    assert status_code == status.HTTP_403_FORBIDDEN, (
                        f"SECURITY VIOLATION: Role '{r}' received {status_code} on {endpoint}, expected 403!"
                    )
                    print(f"  {r:15} -> {status_code} Forbidden (EXPECTED RESTRICTION)")
            else:
                # General procurement viewsets (orders, grns, invoices, rfqs, quotations):
                # IsProcurementOrFinanceOperator: admin, hotel_manager, inventory, finance -> 200
                # All departmental line roles (kitchen, bar, waiter, cashier, reception, housekeeping, customer) -> 403
                if r in ["admin", "hotel_manager", "inventory", "finance"]:
                    assert status_code == status.HTTP_200_OK, (
                        f"UNEXPECTED DENIAL: Role '{r}' received {status_code} on {endpoint}, expected 200!"
                    )
                    print(f"  {r:15} -> {status_code} OK (AUTHORIZED)")
                else:
                    assert status_code == status.HTTP_403_FORBIDDEN, (
                        f"SECURITY VIOLATION: Role '{r}' received {status_code} on {endpoint}, expected 403!"
                    )
                    print(f"  {r:15} -> {status_code} Forbidden (EXPECTED RESTRICTION)")

    # -------------------------------------------------------------------------
    # PART 2: MUTATION & ACTION PERMISSION GUARDS
    # -------------------------------------------------------------------------
    print("\n" + "-" * 75)
    print("PART 2: MUTATION & ACTION PERMISSION GUARDS (ATOMIC ROLLBACK)")
    print("-" * 75)

    with transaction.atomic():
        try:
            # 2.1 PO Creation by Waiter -> 403
            client.force_authenticate(user=users_by_role["waiter"])
            r_po = client.post("/users/procurement/orders/", {"supplier": 1, "delivery_location": 1}, format="json")
            assert r_po.status_code == status.HTTP_403_FORBIDDEN, f"Waiter PO create expected 403, got {r_po.status_code}"
            print("  2.1 Waiter POST /users/procurement/orders/ -> 403 Forbidden (PASS)")

            # 2.2 PO Creation by Finance -> 403 (Only admin, hotel_manager, inventory can create POs)
            client.force_authenticate(user=users_by_role["finance"])
            r_po_fin = client.post("/users/procurement/orders/", {"supplier": 1, "delivery_location": 1}, format="json")
            assert r_po_fin.status_code == status.HTTP_403_FORBIDDEN, f"Finance PO create expected 403, got {r_po_fin.status_code}"
            print("  2.2 Finance POST /users/procurement/orders/ -> 403 Forbidden (PASS)")

            # 2.3 PR Creation by Waiter -> 403
            client.force_authenticate(user=users_by_role["waiter"])
            r_pr_w = client.post("/users/procurement/requisitions/", {"department": "kitchen", "items": []}, format="json")
            assert r_pr_w.status_code == status.HTTP_403_FORBIDDEN, f"Waiter PR create expected 403, got {r_pr_w.status_code}"
            print("  2.3 Waiter POST /users/procurement/requisitions/ -> 403 Forbidden (PASS)")

            # 2.4 PR Creation by Customer -> 403
            client.force_authenticate(user=users_by_role["customer"])
            r_pr_c = client.post("/users/procurement/requisitions/", {"department": "kitchen", "items": []}, format="json")
            assert r_pr_c.status_code == status.HTTP_403_FORBIDDEN, f"Customer PR create expected 403, got {r_pr_c.status_code}"
            print("  2.4 Customer POST /users/procurement/requisitions/ -> 403 Forbidden (PASS)")

            # 2.5 Kitchen cannot submit PR for bar department -> 403
            client.force_authenticate(user=users_by_role["kitchen"])
            r_pr_cross = client.post("/users/procurement/requisitions/", {"department": "bar", "items": []}, format="json")
            assert r_pr_cross.status_code == status.HTTP_403_FORBIDDEN, f"Cross-dept PR create expected 403, got {r_pr_cross.status_code}"
            print("  2.5 Kitchen cross-department PR submit -> 403 Forbidden (PASS)")

            # 2.6 Kitchen cannot convert PR to PO -> 403
            client.force_authenticate(user=users_by_role["kitchen"])
            r_conv = client.post("/users/procurement/requisitions/1/convert-to-po/", {"supplier": 1}, format="json")
            assert r_conv.status_code == status.HTTP_403_FORBIDDEN, f"Kitchen convert-to-po expected 403, got {r_conv.status_code}"
            print("  2.6 Kitchen POST /convert-to-po/ -> 403 Forbidden (PASS)")

            # 2.7 Inventory staff cannot approve supplier invoice payment -> 403
            client.force_authenticate(user=users_by_role["inventory"])
            r_inv_app = client.post("/users/procurement/invoices/1/approve/", {}, format="json")
            assert r_inv_app.status_code == status.HTTP_403_FORBIDDEN, f"Inventory invoice approve expected 403, got {r_inv_app.status_code}"
            print("  2.7 Inventory POST /users/procurement/invoices/1/approve/ -> 403 Forbidden (PASS)")

        finally:
            transaction.set_rollback(True)

    # -------------------------------------------------------------------------
    # PART 3: SERVICE LAYER AUTHORIZATION & SOD CHECKS
    # -------------------------------------------------------------------------
    print("\n" + "-" * 75)
    print("PART 3: SERVICE LAYER AUTHORIZATION & SOD CHECKS (ATOMIC ROLLBACK)")
    print("-" * 75)

    with transaction.atomic():
        try:
            # 3.1 _validate_procurement_role helper directly
            u_waiter = users_by_role["waiter"]
            try:
                _validate_procurement_role(u_waiter, {"admin", "hotel_manager", "inventory"}, "convert PO")
                assert False, "Should have raised PermissionDenied"
            except PermissionDenied:
                print("  3.1 _validate_procurement_role blocks waiter -> PermissionDenied (PASS)")

            # 3.2 Tier 1 Requisition Approval by Hotel Manager
            u_hm = users_by_role["hotel_manager"]
            u_inv = users_by_role["inventory"]
            loc = StockLocation.objects.first()
            itm = InventoryItem.objects.first()

            # Create a PR
            pr = PurchaseRequisition.objects.create(
                requisition_number="PR-TEST-AUDIT-01",
                department="kitchen",
                status="pending_approval",
                requested_by=u_inv,
                total_estimated_amount=Decimal("5000.00"),
            )
            tier1 = ProcurementApprovalPolicy.objects.first().tiers.order_by("tier_level").first()
            pr.approval_tier = tier1
            pr.save()

            # Approve by Hotel Manager
            approved_pr = approve_purchase_requisition(requisition_id=pr.id, approver=u_hm)
            assert approved_pr.status == "approved"
            assert approved_pr.approved_by == u_hm
            print(f"  3.2 Tier 1 PR Approved by Hotel Manager (ID {u_hm.id}) -> Status: {approved_pr.status} (PASS)")

            # 3.3 Separation of Duties: Requester self-approval blocked
            pr_sod = PurchaseRequisition.objects.create(
                requisition_number="PR-TEST-AUDIT-SOD",
                department="inventory",
                status="pending_approval",
                requested_by=u_hm,
                total_estimated_amount=Decimal("2000.00"),
                approval_tier=tier1,
            )
            try:
                approve_purchase_requisition(requisition_id=pr_sod.id, approver=u_hm)
                assert False, "Should have blocked self-approval"
            except ValidationError as ve:
                assert "Separation of duties violation" in str(ve)
                print("  3.3 Requester self-approval blocked -> ValidationError (PASS)")

            # 3.4 Service-layer role block on convert_requisition_to_purchase_order
            try:
                convert_requisition_to_purchase_order(
                    requisition_id=pr.id,
                    user=users_by_role["kitchen"],
                    supplier_id=1,
                )
                assert False, "Should have blocked kitchen from issuing PO"
            except PermissionDenied:
                print("  3.4 Kitchen convert_requisition_to_purchase_order blocked -> PermissionDenied (PASS)")

            # 3.5 Service-layer role block on receive_goods_receipt_note
            try:
                receive_goods_receipt_note(
                    purchase_order_id=1,
                    receiver=users_by_role["waiter"],
                    items=[],
                )
                assert False, "Should have blocked waiter from receiving GRN"
            except PermissionDenied:
                print("  3.5 Waiter receive_goods_receipt_note blocked -> PermissionDenied (PASS)")

        finally:
            transaction.set_rollback(True)

    print("\n" + "=" * 75)
    print("ALL EMPIRICAL FORENSIC VERIFICATIONS PASSED CLEANLY (100% COMPLIANT)")
    print("=" * 75)


if __name__ == "__main__":
    run_forensic_audit()
