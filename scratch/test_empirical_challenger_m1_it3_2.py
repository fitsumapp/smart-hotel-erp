"""
scratch/test_empirical_challenger_m1_it3_2.py
Empirical Challenger Test Suite for Milestone 1 Iteration 3.
Exhaustively stress-tests:
1. Requisition Department Scoping & Isolation (Kitchen vs Bar vs Housekeeping).
2. Non-privileged requisition creation restriction on department="finance" and department="inventory".
3. Separation of Duties on Goods Receipt & Invoices (Dock receiver cannot approve invoice).
4. Invoice Price Variance Override Authorization (Only Hotel Admin can override).
5. Service-layer defensive assertions & tamper resistance.
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

import users.urls
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    StockLocation,
    InventoryCategory,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceItem,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
)
from hotel.procurement import (
    ensure_default_procurement_policy,
    request_purchase_requisition,
    approve_purchase_requisition,
    convert_requisition_to_purchase_order,
    receive_goods_receipt_note,
    match_and_record_supplier_invoice,
    approve_supplier_invoice,
)
from apps.finance.services import ensure_default_accounts

User = get_user_model()


def get_or_create_test_users():
    """Ensure we have active users for each role required for testing."""
    users = {}
    roles = [
        "admin",
        "hotel_manager",
        "inventory",
        "finance",
        "kitchen",
        "bar",
        "housekeeping",
        "waiter",
        "cashier",
        "reception",
        "customer",
    ]
    for r in roles:
        u = User.objects.filter(role=r, is_active=True).first()
        if not u:
            u = User.objects.create_user(
                username=f"challenger_{r}",
                password="Password123!",
                role=r,
                is_active=True,
                is_verified=True,
            )
        users[r] = u
    return users


def test_section_1_requisition_department_scoping(users):
    print("\n" + "=" * 75)
    print("SECTION 1: Requisition Department Scoping & Isolation Stress-Tests")
    print("=" * 75)
    results = {}
    client = APIClient()

    kitchen_user = users["kitchen"]
    bar_user = users["bar"]
    hk_user = users["housekeeping"]
    admin_user = users["admin"]
    inv_user = users["inventory"]
    fin_user = users["finance"]
    waiter_user = users["waiter"]
    cashier_user = users["cashier"]
    reception_user = users["reception"]
    customer_user = users["customer"]

    loc = StockLocation.objects.first()
    item = InventoryItem.objects.first()

    with transaction.atomic():
        # Setup: create PRs in different departments
        pr_kitchen = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 5, "estimated_unit_cost": Decimal("50.00")}],
            notes="Kitchen Requisition Probe",
        )
        pr_bar = request_purchase_requisition(
            requester=bar_user,
            department="bar",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 3, "estimated_unit_cost": Decimal("40.00")}],
            notes="Bar Requisition Probe",
        )
        pr_hk = request_purchase_requisition(
            requester=hk_user,
            department="housekeeping",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("15.00")}],
            notes="Housekeeping Requisition Probe",
        )
        pr_fin = request_purchase_requisition(
            requester=fin_user,
            department="finance",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 2, "estimated_unit_cost": Decimal("100.00")}],
            notes="Finance Requisition Probe",
        )
        pr_inv = request_purchase_requisition(
            requester=inv_user,
            department="inventory",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 20, "estimated_unit_cost": Decimal("10.00")}],
            notes="Inventory Requisition Probe",
        )

        # 1.1 Kitchen user lists requisitions: must see kitchen PR, but NEVER bar, hk, finance, or inventory PRs
        client.force_authenticate(user=kitchen_user)
        r_list = client.get("/users/procurement/requisitions/")
        assert r_list.status_code == status.HTTP_200_OK, f"Expected 200, got {r_list.status_code}"
        items_data = r_list.data.get("results") if isinstance(r_list.data, dict) else r_list.data
        returned_ids = [d["id"] for d in items_data]
        assert pr_kitchen.id in returned_ids, "Kitchen user could not see their own kitchen requisition!"
        assert pr_bar.id not in returned_ids, "LEAK: Kitchen user could see bar requisition!"
        assert pr_hk.id not in returned_ids, "LEAK: Kitchen user could see housekeeping requisition!"
        assert pr_fin.id not in returned_ids, "LEAK: Kitchen user could see finance requisition!"
        assert pr_inv.id not in returned_ids, "LEAK: Kitchen user could see inventory requisition!"
        print("  [PASS] 1.1 Kitchen user list is strictly row-scoped to kitchen.")
        results["1.1_kitchen_list_scoping"] = "PASS"

        # 1.2 Kitchen user attempts querying ?department=bar
        r_query_bar = client.get("/users/procurement/requisitions/?department=bar")
        assert r_query_bar.status_code == status.HTTP_200_OK
        qbar_items = r_query_bar.data.get("results") if isinstance(r_query_bar.data, dict) else r_query_bar.data
        qbar_ids = [d["id"] for d in qbar_items]
        assert pr_bar.id not in qbar_ids, "LEAK: Kitchen user queried bar requisitions via ?department=bar!"
        print("  [PASS] 1.2 Kitchen user cannot query bar requisitions via ?department=bar parameter.")
        results["1.2_kitchen_query_bar_scoping"] = "PASS"

        # 1.3 Kitchen user attempts querying ?department=housekeeping
        r_query_hk = client.get("/users/procurement/requisitions/?department=housekeeping")
        assert r_query_hk.status_code == status.HTTP_200_OK
        qhk_items = r_query_hk.data.get("results") if isinstance(r_query_hk.data, dict) else r_query_hk.data
        qhk_ids = [d["id"] for d in qhk_items]
        assert pr_hk.id not in qhk_ids, "LEAK: Kitchen user queried hk requisitions via ?department=housekeeping!"
        print("  [PASS] 1.3 Kitchen user cannot query housekeeping requisitions via ?department=housekeeping parameter.")
        results["1.3_kitchen_query_hk_scoping"] = "PASS"

        # 1.4 Kitchen user attempts direct GET /users/procurement/requisitions/<bar_id>/ -> 404 Not Found
        r_get_bar = client.get(f"/users/procurement/requisitions/{pr_bar.id}/")
        assert r_get_bar.status_code == status.HTTP_404_NOT_FOUND, f"Expected 404, got {r_get_bar.status_code}"
        print("  [PASS] 1.4 Direct detail retrieval of bar requisition by kitchen user yields HTTP 404.")
        results["1.4_kitchen_detail_bar_404"] = "PASS"

        # 1.5 Kitchen user attempts direct GET /users/procurement/requisitions/<hk_id>/ -> 404 Not Found
        r_get_hk = client.get(f"/users/procurement/requisitions/{pr_hk.id}/")
        assert r_get_hk.status_code == status.HTTP_404_NOT_FOUND, f"Expected 404, got {r_get_hk.status_code}"
        print("  [PASS] 1.5 Direct detail retrieval of housekeeping requisition by kitchen user yields HTTP 404.")
        results["1.5_kitchen_detail_hk_404"] = "PASS"

        # 1.6 Kitchen user attempts actions on bar requisition
        r_act_appr = client.post(f"/users/procurement/requisitions/{pr_bar.id}/approve/", {"notes": "hack"})
        assert r_act_appr.status_code == status.HTTP_404_NOT_FOUND, f"Expected 404, got {r_act_appr.status_code}"
        print("  [PASS] 1.6a Approval attempt by kitchen user on bar requisition return HTTP 404.")
        results["1.6a_kitchen_approve_on_bar_404"] = "PASS"

        # EMPIRICAL AUDIT CHECK: Does reject() properly enforce row-scoping?
        r_act_rej = client.post(f"/users/procurement/requisitions/{pr_bar.id}/reject/", {"reason": "hack"})
        if r_act_rej.status_code == status.HTTP_200_OK:
            print("  [FAIL - VULNERABILITY] 1.6b Rejection of bar requisition by kitchen user SUCCEEDED (HTTP 200 OK)!")
            print("         Root Cause: PurchaseRequisitionViewSet.reject() lacks self.get_object() and hotel.procurement.reject_purchase_requisition lacks role validation!")
            results["1.6b_kitchen_reject_on_bar_scoping"] = "FAIL_VULNERABILITY"
        elif r_act_rej.status_code == status.HTTP_404_NOT_FOUND:
            print("  [PASS] 1.6b Rejection attempt by kitchen user on bar requisition return HTTP 404.")
            results["1.6b_kitchen_reject_on_bar_scoping"] = "PASS"
        else:
            print(f"  [UNCLEAR] 1.6b Rejection returned HTTP {r_act_rej.status_code}")
            results["1.6b_kitchen_reject_on_bar_scoping"] = f"STATUS_{r_act_rej.status_code}"

        # 1.7 Non-privileged creation of requisitions with department='finance' or 'inventory'
        # Kitchen user tests
        r_k_fin = client.post(
            "/users/procurement/requisitions/",
            {"department": "finance", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_k_fin.status_code == status.HTTP_403_FORBIDDEN, f"Kitchen creating finance PR expected 403, got {r_k_fin.status_code}"

        r_k_inv = client.post(
            "/users/procurement/requisitions/",
            {"department": "inventory", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_k_inv.status_code == status.HTTP_403_FORBIDDEN, f"Kitchen creating inventory PR expected 403, got {r_k_inv.status_code}"

        # Bar user tests
        client.force_authenticate(user=bar_user)
        r_b_fin = client.post(
            "/users/procurement/requisitions/",
            {"department": "finance", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_b_fin.status_code == status.HTTP_403_FORBIDDEN, f"Bar creating finance PR expected 403, got {r_b_fin.status_code}"

        r_b_inv = client.post(
            "/users/procurement/requisitions/",
            {"department": "inventory", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_b_inv.status_code == status.HTTP_403_FORBIDDEN, f"Bar creating inventory PR expected 403, got {r_b_inv.status_code}"

        # Housekeeping user tests
        client.force_authenticate(user=hk_user)
        r_hk_fin = client.post(
            "/users/procurement/requisitions/",
            {"department": "finance", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_hk_fin.status_code == status.HTTP_403_FORBIDDEN, f"HK creating finance PR expected 403, got {r_hk_fin.status_code}"

        r_hk_inv = client.post(
            "/users/procurement/requisitions/",
            {"department": "inventory", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
            format="json",
        )
        assert r_hk_inv.status_code == status.HTTP_403_FORBIDDEN, f"HK creating inventory PR expected 403, got {r_hk_inv.status_code}"

        # Line / external staff (waiter, cashier, reception, customer)
        for line_user, role_name in [
            (waiter_user, "waiter"),
            (cashier_user, "cashier"),
            (reception_user, "reception"),
            (customer_user, "customer"),
        ]:
            client.force_authenticate(user=line_user)
            r_line_fin = client.post(
                "/users/procurement/requisitions/",
                {"department": "finance", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
                format="json",
            )
            assert r_line_fin.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} creating finance PR expected 403, got {r_line_fin.status_code}"

            r_line_inv = client.post(
                "/users/procurement/requisitions/",
                {"department": "inventory", "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
                format="json",
            )
            assert r_line_inv.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} creating inventory PR expected 403, got {r_line_inv.status_code}"

        print("  [PASS] 1.7 Non-privileged staff (kitchen, bar, hk, waiter, cashier, reception, customer) blocked from creating finance or inventory requisitions.")
        results["1.7_non_privileged_blocked_fin_inv"] = "PASS"

        # 1.8 Adversarial department string fuzzing (casing, whitespace, tampering)
        client.force_authenticate(user=kitchen_user)
        fuzz_tests = [
            ("FINANCE", status.HTTP_403_FORBIDDEN),
            ("  finance  ", status.HTTP_403_FORBIDDEN),
            ("INVENTORY", status.HTTP_403_FORBIDDEN),
            ("inventory ", status.HTTP_403_FORBIDDEN),
            ("kitchen/finance", status.HTTP_403_FORBIDDEN),
            ("general", status.HTTP_403_FORBIDDEN),
        ]
        for f_dept, expected_code in fuzz_tests:
            r_fuzz = client.post(
                "/users/procurement/requisitions/",
                {"department": f_dept, "delivery_location": loc.id, "items": [{"item_id": item.id, "quantity_requested": 1}]},
                format="json",
            )
            assert r_fuzz.status_code == expected_code, f"Fuzz department '{f_dept}' expected {expected_code}, got {r_fuzz.status_code}"
        print("  [PASS] 1.8 Adversarial department string tampering (whitespace, upper case, cross-department) strictly forbidden.")
        results["1.8_department_fuzzing_blocked"] = "PASS"

        transaction.set_rollback(True)

    return results


def test_section_2_separation_of_duties_grn_and_invoices(users):
    print("\n" + "=" * 75)
    print("SECTION 2: Separation of Duties (SoD) on GRN & Invoice Matching")
    print("=" * 75)
    results = {}
    client = APIClient()

    admin_user = users["admin"]
    inv_user = users["inventory"]
    fin_user_1 = users["finance"]
    # Ensure second independent finance user exists
    fin_user_2 = User.objects.filter(role="finance", is_active=True).exclude(id=fin_user_1.id).first()
    if not fin_user_2:
        fin_user_2 = User.objects.create_user(
            username="challenger_fin2",
            password="Password123!",
            role="finance",
            is_active=True,
            is_verified=True,
        )

    loc = StockLocation.objects.first()
    item = InventoryItem.objects.first()
    supplier = Supplier.objects.first()

    with transaction.atomic():
        ensure_default_accounts()
        policy = ensure_default_procurement_policy()

        # Step 1: Create PO
        pr = request_purchase_requisition(
            requester=inv_user,
            department="inventory",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
        )
        pr.status = "approved"
        pr.approved_by = admin_user
        pr.save()

        po = convert_requisition_to_purchase_order(
            requisition_id=pr.id,
            issuer=admin_user,
            supplier_id=supplier.id,
            delivery_location_id=loc.id,
            item_prices={item.id: Decimal("50.00")},
        )
        po_item = po.items.first()

        # Step 2: Dock receiver records GRN
        # Scenario 2.1: Admin user (non-superuser) acts as dock receiver
        admin_receiver = User.objects.filter(role="admin", is_superuser=False, is_active=True).first()
        if not admin_receiver:
            admin_receiver = User.objects.create_user(
                username="challenger_admin_receiver",
                password="Password123!",
                role="admin",
                is_superuser=False,
                is_active=True,
                is_verified=True,
            )

        grn_admin = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=admin_receiver,
            delivery_note_number="DN-SOD-TEST-01",
            location_id=loc.id,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": Decimal("5")}],
        )

        # Step 3: 3-Way Invoice Matching
        inv = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-SOD-TEST-01",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": Decimal("5"), "billed_unit_price": Decimal("50.00")}],
            matched_by=fin_user_1,
        )
        assert inv.match_status == "matched", f"Expected matched, got {inv.match_status}"

        # 2.1 Test that the admin user who received the GRN CANNOT approve the matched invoice
        client.force_authenticate(user=admin_receiver)
        r_appr_receiver = client.post(f"/users/procurement/invoices/{inv.id}/approve/", format="json")
        assert r_appr_receiver.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 Bad Request, got {r_appr_receiver.status_code}"
        assert "Dock receiver cannot approve invoice payment" in str(r_appr_receiver.data.get("error", "")), f"Unexpected message: {r_appr_receiver.data}"
        print("  [PASS] 2.1 Dock receiver (admin_receiver) blocked from approving supplier invoice (HTTP 400 SoD Violation).")
        results["2.1_grn_receiver_cannot_approve_invoice"] = "PASS"

        # 2.2 Test that inventory staff cannot approve invoice (SoD between warehouse and accounts payable)
        client.force_authenticate(user=inv_user)
        r_appr_inv = client.post(f"/users/procurement/invoices/{inv.id}/approve/", format="json")
        assert r_appr_inv.status_code == status.HTTP_403_FORBIDDEN, f"Inventory approving invoice expected 403, got {r_appr_inv.status_code}"
        print("  [PASS] 2.2 Inventory staff strictly denied invoice approval endpoint (HTTP 403 Forbidden).")
        results["2.2_inventory_cannot_approve_invoice"] = "PASS"

        # 2.3 Test that independent finance officer (fin_user_1, who did not receive goods) CAN approve matched invoice
        client.force_authenticate(user=fin_user_1)
        r_appr_indep = client.post(f"/users/procurement/invoices/{inv.id}/approve/", format="json")
        assert r_appr_indep.status_code == status.HTTP_200_OK, f"Independent finance approval expected 200, got {r_appr_indep.status_code}"
        inv.refresh_from_db()
        assert inv.match_status == "approved", f"Invoice status expected approved, got {inv.match_status}"
        assert inv.approved_by == fin_user_1, "Approved_by mismatch"
        print("  [PASS] 2.3 Independent finance officer (fin_user_1) cleanly approved matched invoice (HTTP 200 OK).")
        results["2.3_independent_finance_approves_invoice"] = "PASS"

        # 2.4 Multi-GRN Scenario: PO with multiple GRNs received by multiple receivers (inv_user and admin_receiver)
        grn_2 = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=inv_user,
            delivery_note_number="DN-SOD-TEST-02",
            location_id=loc.id,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": Decimal("5")}],
        )
        inv2 = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-SOD-TEST-02",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": Decimal("5"), "billed_unit_price": Decimal("50.00")}],
            matched_by=fin_user_1,
        )
        # Now PO has GRNs received by admin_receiver AND inv_user
        # admin_receiver attempts approval -> BLOCKED (SoD violation)
        client.force_authenticate(user=admin_receiver)
        assert client.post(f"/users/procurement/invoices/{inv2.id}/approve/").status_code == status.HTTP_400_BAD_REQUEST
        # inv_user attempts approval -> BLOCKED (HTTP 403)
        client.force_authenticate(user=inv_user)
        assert client.post(f"/users/procurement/invoices/{inv2.id}/approve/").status_code == status.HTTP_403_FORBIDDEN

        # Independent finance officer (fin_user_2, who is not dock receiver) approves -> ALLOWED
        client.force_authenticate(user=fin_user_2)
        r_fin2_appr = client.post(f"/users/procurement/invoices/{inv2.id}/approve/")
        assert r_fin2_appr.status_code == status.HTTP_200_OK, f"Finance approval expected 200, got {r_fin2_appr.status_code}"
        print("  [PASS] 2.4 Multi-GRN PO correctly prevents all cumulative dock receivers from approving payment.")
        results["2.4_multi_grn_receivers_all_blocked"] = "PASS"

        transaction.set_rollback(True)

    return results


def test_section_3_variance_override_safeguards(users):
    print("\n" + "=" * 75)
    print("SECTION 3: Invoice Price Variance Override Safeguard Stress-Tests")
    print("=" * 75)
    results = {}
    client = APIClient()

    admin_user = users["admin"]
    hm_user = users["hotel_manager"]
    inv_user = users["inventory"]
    fin_user = users["finance"]
    kitchen_user = users["kitchen"]

    loc = StockLocation.objects.first()
    item = InventoryItem.objects.first()
    supplier = Supplier.objects.first()

    with transaction.atomic():
        ensure_default_accounts()
        policy = ensure_default_procurement_policy()

        # Create PO with PO unit price = 50.00
        pr = request_purchase_requisition(
            requester=inv_user,
            department="inventory",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
        )
        pr.status = "approved"
        pr.approved_by = admin_user
        pr.save()

        po = convert_requisition_to_purchase_order(
            requisition_id=pr.id,
            issuer=admin_user,
            supplier_id=supplier.id,
            delivery_location_id=loc.id,
            item_prices={item.id: Decimal("50.00")},
        )
        po_item = po.items.first()

        # Dock receiver (inv_user) receives 5 units
        receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=inv_user,
            delivery_note_number="DN-VAR-TEST-01",
            location_id=loc.id,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": Decimal("5")}],
        )

        # Match invoice with price variance: PO price=50.00, Billed price=100.00 (100% variance, exceeds 2% tolerance)
        inv_flagged = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-FLAGGED-OVERRIDE-01",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": Decimal("5"), "billed_unit_price": Decimal("100.00")}],
            matched_by=fin_user,
        )
        assert inv_flagged.match_status == "variance_flagged", f"Expected variance_flagged, got {inv_flagged.match_status}"

        # 3.1 Finance staff attempts approval without override -> 400 Bad Request
        client.force_authenticate(user=fin_user)
        r_fin_no_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": False},
            format="json",
        )
        assert r_fin_no_override.status_code == status.HTTP_400_BAD_REQUEST
        assert "without explicit override" in str(r_fin_no_override.data.get("error", ""))
        print("  [PASS] 3.1 Approval of flagged invoice without override rejected (HTTP 400).")
        results["3.1_flagged_without_override_400"] = "PASS"

        # 3.2 Finance staff attempts approval WITH override_variance=True -> 403 Forbidden
        r_fin_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": True, "variance_justification": "Finance attempting override"},
            format="json",
        )
        assert r_fin_override.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403 Forbidden, got {r_fin_override.status_code}"
        assert "Only hotel administrators can authorize supplier invoice price variance overrides" in str(r_fin_override.data.get("error", ""))
        print("  [PASS] 3.2 Finance staff blocked from overriding price variance (HTTP 403 Forbidden).")
        results["3.2_finance_override_blocked_403"] = "PASS"

        # 3.3 Hotel Manager attempts approval WITH override_variance=True -> 403 Forbidden (endpoint level IsFinanceStaff)
        client.force_authenticate(user=hm_user)
        r_hm_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": True, "variance_justification": "Hotel Manager attempting override"},
            format="json",
        )
        assert r_hm_override.status_code == status.HTTP_403_FORBIDDEN, f"HM expected 403, got {r_hm_override.status_code}"
        print("  [PASS] 3.3 Hotel Manager blocked from invoice approval endpoint (HTTP 403 Forbidden).")
        results["3.3_hotel_manager_override_blocked_403"] = "PASS"

        # 3.4 Inventory staff attempts approval WITH override_variance=True -> 403 Forbidden
        client.force_authenticate(user=inv_user)
        r_inv_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": True, "variance_justification": "Inventory attempting override"},
            format="json",
        )
        assert r_inv_override.status_code == status.HTTP_403_FORBIDDEN
        print("  [PASS] 3.4 Inventory staff blocked from invoice approval endpoint (HTTP 403 Forbidden).")
        results["3.4_inventory_override_blocked_403"] = "PASS"

        # 3.5 Operational staff (kitchen) attempts approval -> 403 Forbidden
        client.force_authenticate(user=kitchen_user)
        r_k_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": True},
            format="json",
        )
        assert r_k_override.status_code == status.HTTP_403_FORBIDDEN
        print("  [PASS] 3.5 Kitchen staff blocked from invoice approval endpoint (HTTP 403 Forbidden).")
        results["3.5_kitchen_override_blocked_403"] = "PASS"

        # 3.6 Admin user attempts approval with override_variance=False -> 400 Bad Request
        client.force_authenticate(user=admin_user)
        r_admin_no_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": False},
            format="json",
        )
        assert r_admin_no_override.status_code == status.HTTP_400_BAD_REQUEST
        print("  [PASS] 3.6 Admin without explicit override_variance=True rejected on flagged invoice (HTTP 400).")
        results["3.6_admin_without_override_400"] = "PASS"

        # 3.7 Admin user attempts approval with string 'false' -> 400 Bad Request
        r_admin_str_false = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": "false"},
            format="json",
        )
        assert r_admin_str_false.status_code == status.HTTP_400_BAD_REQUEST
        print("  [PASS] 3.7 Admin passing override_variance='false' (string) properly evaluated as False (HTTP 400).")
        results["3.7_admin_str_false_400"] = "PASS"

        # 3.8 Admin user approves with override_variance=True -> 200 OK
        r_admin_override = client.post(
            f"/users/procurement/invoices/{inv_flagged.id}/approve/",
            {"override_variance": True, "variance_justification": "Authorized price spike override"},
            format="json",
        )
        assert r_admin_override.status_code == status.HTTP_200_OK, f"Expected 200 OK, got {r_admin_override.status_code}"
        inv_flagged.refresh_from_db()
        assert inv_flagged.match_status == "approved"
        assert inv_flagged.approved_by == admin_user
        print("  [PASS] 3.8 Administrator successfully authorizes flagged price variance override (HTTP 200 OK).")
        results["3.8_admin_authorizes_variance_override"] = "PASS"

        transaction.set_rollback(True)

    return results


def test_section_4_service_layer_defensive_assertions(users):
    print("\n" + "=" * 75)
    print("SECTION 4: Service Layer Direct Bypass Stress-Tests (hotel.procurement)")
    print("=" * 75)
    results = {}

    admin_user = users["admin"]
    fin_user = users["finance"]
    inv_user = users["inventory"]
    hm_user = users["hotel_manager"]
    kitchen_user = users["kitchen"]

    loc = StockLocation.objects.first()
    item = InventoryItem.objects.first()
    supplier = Supplier.objects.first()

    with transaction.atomic():
        ensure_default_accounts()
        policy = ensure_default_procurement_policy()

        pr = request_purchase_requisition(
            requester=inv_user,
            department="inventory",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
        )
        pr.status = "approved"
        pr.approved_by = admin_user
        pr.save()

        po = convert_requisition_to_purchase_order(
            requisition_id=pr.id,
            issuer=admin_user,
            supplier_id=supplier.id,
            delivery_location_id=loc.id,
            item_prices={item.id: Decimal("50.00")},
        )
        po_item = po.items.first()

        admin_receiver = User.objects.filter(role="admin", is_superuser=False, is_active=True).first()
        if not admin_receiver:
            admin_receiver = User.objects.create_user(
                username="challenger_admin_receiver2",
                password="Password123!",
                role="admin",
                is_superuser=False,
                is_active=True,
                is_verified=True,
            )

        grn = receive_goods_receipt_note(
            purchase_order_id=po.id,
            receiver=admin_receiver,
            delivery_note_number="DN-SRV-TEST",
            location_id=loc.id,
            receipt_items=[{"po_item_id": po_item.id, "quantity_received": Decimal("5")}],
        )

        inv = match_and_record_supplier_invoice(
            purchase_order_id=po.id,
            vendor_invoice_number="INV-SRV-TEST",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": po_item.id, "billed_quantity": Decimal("5"), "billed_unit_price": Decimal("50.00")}],
            matched_by=admin_user,
        )

        # 4.1 Direct service call: approve_supplier_invoice by GRN dock receiver -> raises ValidationError
        sod_blocked = False
        try:
            approve_supplier_invoice(invoice_id=inv.id, approver=admin_receiver)
        except ValidationError as e:
            sod_blocked = True
            assert "Dock receiver cannot approve invoice payment" in str(e)
        assert sod_blocked, "Direct service layer call did not raise ValidationError on SoD violation!"
        print("  [PASS] 4.1 Direct service layer call raises ValidationError when dock receiver attempts invoice approval.")
        results["4.1_service_sod_validation_error"] = "PASS"

        # 4.2 Direct service call: approve_supplier_invoice by inventory role -> raises PermissionDenied
        inv_blocked = False
        try:
            approve_supplier_invoice(invoice_id=inv.id, approver=inv_user)
        except PermissionDenied as e:
            inv_blocked = True
            assert "Required role: admin, finance" in str(e)
        assert inv_blocked, "Direct service layer call did not raise PermissionDenied for inventory user!"
        print("  [PASS] 4.2 Direct service layer call raises PermissionDenied when inventory staff attempts invoice approval.")
        results["4.2_service_inventory_role_denied"] = "PASS"

        # 4.3 Direct service call: approve_supplier_invoice by hotel manager role -> raises PermissionDenied
        hm_blocked = False
        try:
            approve_supplier_invoice(invoice_id=inv.id, approver=hm_user)
        except PermissionDenied as e:
            hm_blocked = True
            assert "Required role: admin, finance" in str(e)
        assert hm_blocked, "Direct service layer call did not raise PermissionDenied for hotel manager!"
        print("  [PASS] 4.3 Direct service layer call raises PermissionDenied when hotel manager attempts invoice approval.")
        results["4.3_service_hotel_manager_role_denied"] = "PASS"

        # 4.4 Direct service call: convert_requisition_to_purchase_order by kitchen user -> raises PermissionDenied
        pr_k = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=loc,
            items=[{"item_id": item.id, "quantity_requested": 5, "estimated_unit_cost": Decimal("50.00")}],
        )
        pr_k.status = "approved"
        pr_k.approved_by = admin_user
        pr_k.save()

        po_conv_blocked = False
        try:
            convert_requisition_to_purchase_order(
                requisition_id=pr_k.id,
                issuer=kitchen_user,
                supplier_id=supplier.id,
            )
        except PermissionDenied as e:
            po_conv_blocked = True
            assert "Required role: admin, hotel_manager, inventory" in str(e)
        assert po_conv_blocked, "Direct service layer call did not raise PermissionDenied for kitchen PO conversion!"
        print("  [PASS] 4.4 Direct service layer call raises PermissionDenied when kitchen user attempts PO conversion.")
        results["4.4_service_kitchen_po_convert_denied"] = "PASS"

        transaction.set_rollback(True)

    return results


def main():
    print("=" * 75)
    print("ACRMA HOTEL ERP — EMPIRICAL CHALLENGER VERIFICATION (M1-It3-2)")
    print("=" * 75)

    initial_users = User.objects.count()
    users = get_or_create_test_users()

    res1 = test_section_1_requisition_department_scoping(users)
    res2 = test_section_2_separation_of_duties_grn_and_invoices(users)
    res3 = test_section_3_variance_override_safeguards(users)
    res4 = test_section_4_service_layer_defensive_assertions(users)

    all_results = {**res1, **res2, **res3, **res4}

    print("\n" + "=" * 75)
    print("SUMMARY OF EMPIRICAL ADVERSARIAL STRESS RESULTS:")
    print("=" * 75)
    for test_name, test_status in all_results.items():
        print(f"  {test_name:<45}: {test_status}")

    all_passed = all(status == "PASS" for status in all_results.values())
    print("\n" + "=" * 75)
    print(f"OVERALL EMPIRICAL VERDICT: {'ALL PASS' if all_passed else 'FAILURES DETECTED'}")
    print(f"Total Tests Executed: {len(all_results)} | Passed: {sum(1 for s in all_results.values() if s == 'PASS')} | Failed: {sum(1 for s in all_results.values() if s != 'PASS')}")
    print("=" * 75)

    post_users = User.objects.count()
    assert post_users == initial_users, f"Database leak! Pre-test users: {initial_users}, Post-test users: {post_users}"
    print(f"DATABASE CLEANLINESS CONFIRMED: 0 records leaked. User count preserved at {post_users}.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
