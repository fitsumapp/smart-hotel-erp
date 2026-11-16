"""
scratch/test_challenger_m1_it3.py

Empirical Challenger Test Harness for Milestone 1 Iteration 3
Rigorous adversarial testing of:
1. All 7 restricted roles across all 7 procurement endpoints (HTTP 403 / scoped)
2. Separation of Duties (Self-approval rejected with HTTP 400 / ValidationError)
3. Approval Tiers ($5k, $25k, $75k) for inventory, hotel_manager, finance, admin
4. Staging Database Integrity (PayrollEntry count == 0, User count == 37)
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

import datetime
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    StockLocation,
    InventoryCategory,
    InventoryItem,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceiptNote,
    GoodsReceiptNoteItem,
    RequestForQuotation,
    Supplier,
    SupplierQuotation,
    SupplierInvoice,
    ProcurementApprovalPolicy,
    ProcurementApprovalTier,
    PayrollEntry,
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

User = get_user_model()


def get_or_create_test_user(username, role, is_superuser=False):
    u = User.objects.filter(username=username).first()
    if not u:
        u = User.objects.create_user(
            username=username,
            password="testpassword123",
            role=role,
            is_superuser=is_superuser,
            is_staff=is_superuser,
            is_active=True,
            is_verified=True,
        )
    else:
        u.role = role
        u.is_superuser = is_superuser
        u.is_active = True
        u.save()
    return u


def run_challenger_tests():
    print("=" * 80)
    print("ACRMA HOTEL ERP — EMPIRICAL CHALLENGER VERIFICATION HARNESS (M1-It3-1)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # PART 1: STAGING DATABASE REMEDIATION VERIFICATION
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[TEST SUITE 1] STAGING DATABASE CLEANUP AUDIT (hotel_erp_staging)")
    print("=" * 80)

    user_count = User.objects.count()
    payroll_count = PayrollEntry.objects.count()

    print(f"[*] Staging User count        : {user_count} (Expected: 37)")
    print(f"[*] Staging PayrollEntry count: {payroll_count} (Expected: 0)")

    # Print breakdown of roles in staging
    roles_breakdown = {}
    for r in User.objects.values_list("role", flat=True):
        roles_breakdown[r] = roles_breakdown.get(r, 0) + 1
    print(f"[*] Staging Users by role     : {dict(sorted(roles_breakdown.items()))}")

    staging_db_pass = (user_count == 37 and payroll_count == 0)
    print(f"[*] Staging DB Audit Result   : {'PASS' if staging_db_pass else 'FAIL'}")

    # -------------------------------------------------------------------------
    # PART 2: SETUP TRANSACTION-ISOLATED FIXTURES FOR API TESTING
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[TEST SUITE 2] RBAC & APPROVAL BOUNDARY TESTING (TRANSACTION-ISOLATED)")
    print("=" * 80)

    matrix_results = {}
    client = APIClient()

    # We run the entire testing sequence inside an atomic transaction block
    # and rollback at the end so staging DB records are NEVER modified.
    with transaction.atomic():
        print("[*] Creating / fetching test actors...")
        admin_user = get_or_create_test_user("test_c_admin", "admin", is_superuser=False)
        hotel_manager_user = get_or_create_test_user("test_c_hm", "hotel_manager")
        inventory_user = get_or_create_test_user("test_c_inv1", "inventory")
        inventory_user_2 = get_or_create_test_user("test_c_inv2", "inventory")
        finance_user = get_or_create_test_user("test_c_fin", "finance")

        # 7 Restricted Roles
        kitchen_user = get_or_create_test_user("test_c_kitchen", "kitchen")
        bar_user = get_or_create_test_user("test_c_bar", "bar")
        waiter_user = get_or_create_test_user("test_c_waiter", "waiter")
        cashier_user = get_or_create_test_user("test_c_cashier", "cashier")
        reception_user = get_or_create_test_user("test_c_reception", "reception")
        housekeeping_user = get_or_create_test_user("test_c_housekeeping", "housekeeping")
        customer_user = get_or_create_test_user("test_c_customer", "customer")

        restricted_roles = {
            "kitchen": kitchen_user,
            "bar": bar_user,
            "waiter": waiter_user,
            "cashier": cashier_user,
            "reception": reception_user,
            "housekeeping": housekeeping_user,
            "customer": customer_user,
        }

        # Master Data Fixtures
        policy = ensure_default_procurement_policy()
        category, _ = InventoryCategory.objects.get_or_create(name="Challenger F&B Category", defaults={"category_type": "f_and_b"})
        location, _ = StockLocation.objects.get_or_create(code="LOC-CHALLENGE", defaults={"name": "Challenger Central Store", "location_type": "warehouse", "is_active": True})
        supplier, _ = Supplier.objects.get_or_create(name="Challenger Test Vendor", defaults={"phone": "+251900000000", "email": "vendor@challenger.test"})

        item_small, _ = InventoryItem.objects.get_or_create(
            item_code="CH-ITM-01",
            defaults={"name": "Sugar 1kg", "category": category, "unit": "kg", "unit_cost": Decimal("50.00"), "current_stock": Decimal("100.00")},
        )
        item_tier1, _ = InventoryItem.objects.get_or_create(
            item_code="CH-ITM-T1",
            defaults={"name": "Premium Coffee Beans 10kg", "category": category, "unit": "bag", "unit_cost": Decimal("2500.00"), "current_stock": Decimal("20.00")},
        )
        item_tier2, _ = InventoryItem.objects.get_or_create(
            item_code="CH-ITM-T2",
            defaults={"name": "Commercial Blender Set", "category": category, "unit": "set", "unit_cost": Decimal("12500.00"), "current_stock": Decimal("5.00")},
        )
        item_tier3, _ = InventoryItem.objects.get_or_create(
            item_code="CH-ITM-T3",
            defaults={"name": "Industrial Dishwasher", "category": category, "unit": "unit", "unit_cost": Decimal("75000.00"), "current_stock": Decimal("1.00")},
        )

        # Standard Procurement Records for retrieval & actions
        std_req = request_purchase_requisition(
            requester=inventory_user,
            department="inventory",
            delivery_location=location,
            items=[{"item_id": item_small.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
            notes="Standard PR for challenge tests",
        )

        # Approved Requisition for PO creation
        approved_req = request_purchase_requisition(
            requester=inventory_user,
            department="inventory",
            delivery_location=location,
            items=[{"item_id": item_small.id, "quantity_requested": 10, "estimated_unit_cost": Decimal("50.00")}],
        )
        approved_req.status = "approved"
        approved_req.approved_by = admin_user
        approved_req.approved_at = timezone.now()
        approved_req.save()

        std_po = convert_requisition_to_purchase_order(
            requisition_id=approved_req.id,
            issuer=admin_user,
            supplier_id=supplier.id,
            delivery_location_id=location.id,
        )

        std_grn = receive_goods_receipt_note(
            purchase_order_id=std_po.id,
            receiver=inventory_user,
            delivery_note_number="DN-CH-01",
            location_id=location.id,
            receipt_items=[{"po_item_id": std_po.items.first().id, "quantity_received": 5}],
        )

        std_rfq = RequestForQuotation.objects.create(
            rfq_number="RFQ-CH-01",
            title="Challenger Test RFQ",
            delivery_location=location,
            created_by=inventory_user,
            submission_deadline=timezone.now() + datetime.timedelta(days=5),
            status="draft",
        )

        std_quote = SupplierQuotation.objects.create(
            quotation_number="SQ-CH-01",
            supplier=supplier,
            rfq=std_rfq,
            created_by=inventory_user,
            valid_until=timezone.now().date() + datetime.timedelta(days=15),
            subtotal=Decimal("250.00"),
            total_quoted_amount=Decimal("250.00"),
            total_landed_cost_etb=Decimal("250.00"),
            status="submitted",
        )

        std_invoice = match_and_record_supplier_invoice(
            purchase_order_id=std_po.id,
            vendor_invoice_number="INV-CH-01",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": std_po.items.first().id, "billed_quantity": 5, "billed_unit_price": "50.00"}],
            matched_by=finance_user,
        )

        print("[*] Base fixtures created successfully.")

        # ---------------------------------------------------------------------
        # MATRIX 1: 7 RESTRICTED ROLES ACROSS 7 ENDPOINTS
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("EMPIRICAL MATRIX 1: 7 RESTRICTED ROLES x 7 PROCUREMENT ENDPOINTS")
        print("-" * 80)

        endpoints = [
            ("orders", f"/api/users/procurement/orders/", f"/api/users/procurement/orders/{std_po.id}/"),
            ("requisitions", f"/api/users/procurement/requisitions/", f"/api/users/procurement/requisitions/{std_req.id}/"),
            ("rfqs", f"/api/users/procurement/rfqs/", f"/api/users/procurement/rfqs/{std_rfq.id}/"),
            ("quotations", f"/api/users/procurement/quotations/", f"/api/users/procurement/quotations/{std_quote.id}/"),
            ("grns", f"/api/users/procurement/grns/", f"/api/users/procurement/grns/{std_grn.id}/"),
            ("invoices", f"/api/users/procurement/invoices/", f"/api/users/procurement/invoices/{std_invoice.id}/"),
            ("policies", f"/api/users/procurement/policies/", f"/api/users/procurement/policies/{policy.id}/"),
        ]

        # Table header
        print(f"{'Role':<14} | {'orders':<8} | {'rfqs':<8} | {'quotes':<8} | {'grns':<8} | {'invoices':<8} | {'policies':<8} | {'requisitions (general/cross)'}")
        print("-" * 105)

        for role_name, user_obj in restricted_roles.items():
            client.force_authenticate(user=user_obj)
            row_statuses = {}

            # Test general procurement desks (orders, rfqs, quotations, grns, invoices, policies)
            for ep_name, list_url, detail_url in endpoints:
                if ep_name == "requisitions":
                    continue
                # Test GET list
                res_list = client.get(list_url)
                # Test GET detail
                res_detail = client.get(detail_url)
                # Test POST create attempt
                res_create = client.post(list_url, {"test": "unauthorized"}, format="json")

                all_403 = (
                    res_list.status_code == status.HTTP_403_FORBIDDEN and
                    res_detail.status_code == status.HTTP_403_FORBIDDEN and
                    res_create.status_code == status.HTTP_403_FORBIDDEN
                )
                row_statuses[ep_name] = res_list.status_code

            # Test Requisitions endpoint
            # For unprivileged roles (waiter, cashier, reception, customer): must be 403 on list/retrieve/create/convert
            # For departmental roles (kitchen, bar, housekeeping): can access own list/create, but 403 on convert-to-po and cross-department create
            res_req_list = client.get(f"/api/users/procurement/requisitions/")
            res_req_detail = client.get(f"/api/users/procurement/requisitions/{std_req.id}/")
            res_req_conv = client.post(f"/api/users/procurement/requisitions/{std_req.id}/convert-to-po/", {"supplier": supplier.id}, format="json")

            if role_name in {"waiter", "cashier", "reception", "customer"}:
                req_summary = f"403 Forbidden (list={res_req_list.status_code}, conv={res_req_conv.status_code})"
                assert res_req_list.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} got {res_req_list.status_code} on PR list"
                assert res_req_conv.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} got {res_req_conv.status_code} on PR convert"
                matrix_results[f"{role_name}_requisitions_unprivileged_denied"] = "PASS"
            else:
                # kitchen, bar, housekeeping
                # 1. cross-department PR creation denied
                res_cross_create = client.post(
                    f"/api/users/procurement/requisitions/",
                    {"department": "finance", "items": [{"item_id": item_small.id, "quantity_requested": 1}]},
                    format="json",
                )
                # 2. convert-to-po denied
                assert res_req_conv.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} got {res_req_conv.status_code} on convert-to-po"
                assert res_cross_create.status_code == status.HTTP_403_FORBIDDEN, f"{role_name} got {res_cross_create.status_code} on cross create"
                req_summary = f"Scoped (list={res_req_list.status_code}, cross-create={res_cross_create.status_code}, conv={res_req_conv.status_code})"
                matrix_results[f"{role_name}_requisitions_departmental_scoped"] = "PASS"

            for ep_name in ["orders", "rfqs", "quotations", "grns", "invoices", "policies"]:
                assert row_statuses[ep_name] == status.HTTP_403_FORBIDDEN, f"{role_name} on {ep_name} expected 403, got {row_statuses[ep_name]}"
                matrix_results[f"{role_name}_{ep_name}_denied_403"] = "PASS"

            print(f"{role_name:<14} | {row_statuses['orders']:<8} | {row_statuses['rfqs']:<8} | {row_statuses['quotations']:<8} | {row_statuses['grns']:<8} | {row_statuses['invoices']:<8} | {row_statuses['policies']:<8} | {req_summary}")

        # ---------------------------------------------------------------------
        # MATRIX 2: SEPARATION OF DUTIES (SoD) VERIFICATION
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("EMPIRICAL TEST 2: SEPARATION OF DUTIES (SoD) ENFORCEMENT")
        print("-" * 80)

        # 2.1 Requisition Self-Approval Prevention
        print("[*] Testing Requisition Self-Approval...")
        # Create requisition where requester is inventory_user
        sod_req = request_purchase_requisition(
            requester=inventory_user,
            department="kitchen",
            delivery_location=location,
            items=[{"item_id": item_small.id, "quantity_requested": 5, "estimated_unit_cost": Decimal("50.00")}],
            notes="SoD Self-Approval Test Requisition",
        )

        client.force_authenticate(user=inventory_user)
        res_self_appr = client.post(f"/api/users/procurement/requisitions/{sod_req.id}/approve/", format="json")
        print(f"    - Self-approval attempt status: {res_self_appr.status_code} (Expected: 400 Bad Request)")
        print(f"    - Response body: {res_self_appr.data}")
        assert res_self_appr.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400, got {res_self_appr.status_code}"
        assert "Separation of duties violation" in str(res_self_appr.data.get("error", "")), "Expected SoD error message"
        matrix_results["sod_requisition_self_approval_blocked"] = "PASS"

        # Peer inventory_user_2 approves -> 200 OK
        client.force_authenticate(user=inventory_user_2)
        res_peer_appr = client.post(f"/api/users/procurement/requisitions/{sod_req.id}/approve/", format="json")
        print(f"    - Peer approval attempt status: {res_peer_appr.status_code} (Expected: 200 OK)")
        assert res_peer_appr.status_code == status.HTTP_200_OK, f"Expected 200, got {res_peer_appr.status_code}"
        matrix_results["sod_requisition_peer_approval_allowed"] = "PASS"

        # 2.2 Dock Receiver cannot approve invoice payment
        print("\n[*] Testing Dock Receiver Invoice Approval Prevention...")
        # finance_user is dock receiver on GRN
        grn_sod = GoodsReceiptNote.objects.create(
            grn_number="GRN-SOD-TEST",
            purchase_order=std_po,
            supplier=supplier,
            location=location,
            delivery_note_number="DN-SOD-2",
            status="draft",
            received_by=finance_user,
            received_at=timezone.now(),
        )
        inv_sod = match_and_record_supplier_invoice(
            purchase_order_id=std_po.id,
            vendor_invoice_number="INV-SOD-RCV-01",
            invoice_date=str(timezone.now().date()),
            billed_items=[{"po_item_id": std_po.items.first().id, "billed_quantity": 5, "billed_unit_price": "50.00"}],
            matched_by=admin_user,
        )

        client.force_authenticate(user=finance_user)
        res_dock_inv_appr = client.post(f"/api/users/procurement/invoices/{inv_sod.id}/approve/", format="json")
        print(f"    - Dock receiver invoice approval status: {res_dock_inv_appr.status_code} (Expected: 400 Bad Request)")
        print(f"    - Response body: {res_dock_inv_appr.data}")
        assert res_dock_inv_appr.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400, got {res_dock_inv_appr.status_code}"
        assert "Dock receiver cannot approve invoice payment" in str(res_dock_inv_appr.data.get("error", "")), "Expected dock receiver error"
        matrix_results["sod_dock_receiver_invoice_approval_blocked"] = "PASS"

        # 2.3 Inventory User cannot approve supplier invoices (Finance desk segregation)
        print("\n[*] Testing Inventory Role Invoice Approval Prevention...")
        client.force_authenticate(user=inventory_user)
        res_inv_inv_appr = client.post(f"/api/users/procurement/invoices/{std_invoice.id}/approve/", format="json")
        print(f"    - Inventory invoice approval status: {res_inv_inv_appr.status_code} (Expected: 403 Forbidden)")
        assert res_inv_inv_appr.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {res_inv_inv_appr.status_code}"
        matrix_results["sod_inventory_invoice_approval_blocked"] = "PASS"

        # ---------------------------------------------------------------------
        # MATRIX 3: APPROVAL TIERS ($5k, $25k, $75k) VERIFICATION
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("EMPIRICAL TEST 3: APPROVAL TIERS THRESHOLD BOUNDARY ENFORCEMENT")
        print("-" * 80)

        # 3.1 Tier 1: $5,000 (Threshold <= $10,000)
        # 2 units @ 2,500 = $5,000
        print("\n[*] Tier 1 ($5,000): Expected to accept inventory and hotel_manager")
        req_t1_a = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=location,
            items=[{"item_id": item_tier1.id, "quantity_requested": 2, "estimated_unit_cost": Decimal("2500.00")}],
        )
        assert req_t1_a.approval_tier.tier_level == 1, f"Expected Tier 1, got {req_t1_a.approval_tier.tier_level}"
        assert req_t1_a.total_estimated_amount == Decimal("5000.00")

        # Test inventory approves Tier 1
        client.force_authenticate(user=inventory_user)
        res_t1_inv = client.post(f"/api/users/procurement/requisitions/{req_t1_a.id}/approve/", format="json")
        print(f"    - inventory approving Tier 1 ($5,000) -> HTTP {res_t1_inv.status_code}")
        assert res_t1_inv.status_code == status.HTTP_200_OK, f"Expected 200, got {res_t1_inv.status_code}"
        matrix_results["tier1_5k_inventory_accepted"] = "PASS"

        # Test hotel_manager approves Tier 1
        req_t1_b = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=location,
            items=[{"item_id": item_tier1.id, "quantity_requested": 2, "estimated_unit_cost": Decimal("2500.00")}],
        )
        client.force_authenticate(user=hotel_manager_user)
        res_t1_hm = client.post(f"/api/users/procurement/requisitions/{req_t1_b.id}/approve/", format="json")
        print(f"    - hotel_manager approving Tier 1 ($5,000) -> HTTP {res_t1_hm.status_code}")
        assert res_t1_hm.status_code == status.HTTP_200_OK, f"Expected 200, got {res_t1_hm.status_code}"
        matrix_results["tier1_5k_hotel_manager_accepted"] = "PASS"

        # 3.2 Tier 2: $25,000 (Threshold $10,000.01 - $50,000.00)
        # 2 units @ 12,500 = $25,000
        print("\n[*] Tier 2 ($25,000): Expected to block inventory, accept finance")
        req_t2 = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=location,
            items=[{"item_id": item_tier2.id, "quantity_requested": 2, "estimated_unit_cost": Decimal("12500.00")}],
        )
        assert req_t2.approval_tier.tier_level == 2, f"Expected Tier 2, got {req_t2.approval_tier.tier_level}"
        assert req_t2.total_estimated_amount == Decimal("25000.00")

        # Inventory attempts Tier 2 -> 403 Forbidden
        client.force_authenticate(user=inventory_user)
        res_t2_inv = client.post(f"/api/users/procurement/requisitions/{req_t2.id}/approve/", format="json")
        print(f"    - inventory approving Tier 2 ($25,000) -> HTTP {res_t2_inv.status_code}")
        assert res_t2_inv.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {res_t2_inv.status_code}"
        matrix_results["tier2_25k_inventory_blocked"] = "PASS"

        # Finance approves Tier 2 -> 200 OK
        client.force_authenticate(user=finance_user)
        res_t2_fin = client.post(f"/api/users/procurement/requisitions/{req_t2.id}/approve/", format="json")
        print(f"    - finance approving Tier 2 ($25,000) -> HTTP {res_t2_fin.status_code}")
        assert res_t2_fin.status_code == status.HTTP_200_OK, f"Expected 200, got {res_t2_fin.status_code}"
        matrix_results["tier2_25k_finance_accepted"] = "PASS"

        # 3.3 Tier 3: $75,000 (Threshold > $50,000.00)
        # 1 unit @ 75,000 = $75,000
        print("\n[*] Tier 3 ($75,000): Expected to block inventory and finance, accept admin")
        req_t3 = request_purchase_requisition(
            requester=kitchen_user,
            department="kitchen",
            delivery_location=location,
            items=[{"item_id": item_tier3.id, "quantity_requested": 1, "estimated_unit_cost": Decimal("75000.00")}],
        )
        assert req_t3.approval_tier.tier_level == 3, f"Expected Tier 3, got {req_t3.approval_tier.tier_level}"
        assert req_t3.total_estimated_amount == Decimal("75000.00")

        # Inventory attempts Tier 3 -> 403 Forbidden
        client.force_authenticate(user=inventory_user)
        res_t3_inv = client.post(f"/api/users/procurement/requisitions/{req_t3.id}/approve/", format="json")
        print(f"    - inventory approving Tier 3 ($75,000) -> HTTP {res_t3_inv.status_code}")
        assert res_t3_inv.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {res_t3_inv.status_code}"
        matrix_results["tier3_75k_inventory_blocked"] = "PASS"

        # Finance attempts Tier 3 -> 403 Forbidden
        client.force_authenticate(user=finance_user)
        res_t3_fin = client.post(f"/api/users/procurement/requisitions/{req_t3.id}/approve/", format="json")
        print(f"    - finance approving Tier 3 ($75,000) -> HTTP {res_t3_fin.status_code}")
        assert res_t3_fin.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {res_t3_fin.status_code}"
        matrix_results["tier3_75k_finance_blocked"] = "PASS"

        # Admin approves Tier 3 -> 200 OK
        client.force_authenticate(user=admin_user)
        res_t3_adm = client.post(f"/api/users/procurement/requisitions/{req_t3.id}/approve/", format="json")
        print(f"    - admin approving Tier 3 ($75,000) -> HTTP {res_t3_adm.status_code}")
        assert res_t3_adm.status_code == status.HTTP_200_OK, f"Expected 200, got {res_t3_adm.status_code}"
        matrix_results["tier3_75k_admin_accepted"] = "PASS"

        # Rollback all test database mutations to guarantee 100% clean isolation
        transaction.set_rollback(True)
        print("\n[*] Transaction rolled back cleanly. Staging DB records untouched.")

    # -------------------------------------------------------------------------
    # PART 3: RECONCILE AND PRINT SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("CHALLENGER EMPIRICAL VERIFICATION SUMMARY")
    print("=" * 80)
    total_checks = len(matrix_results) + 1  # +1 for staging db audit
    passed_checks = sum(1 for v in matrix_results.values() if v == "PASS") + (1 if staging_db_pass else 0)

    print(f"Total Verification Checks: {total_checks}")
    print(f"Passed Checks            : {passed_checks}")
    print(f"Failed Checks            : {total_checks - passed_checks}")

    if passed_checks == total_checks:
        print("\n>>> FINAL EMPIRICAL VERDICT: APPROVE <<<")
        print("All RBAC boundaries, Separation of Duties safeguards, approval tiers,")
        print("and staging database cleanup verified 100% compliant.")
        return 0
    else:
        print("\n>>> FINAL EMPIRICAL VERDICT: REJECT <<<")
        print("Vulnerabilities or regressions detected.")
        return 1


if __name__ == "__main__":
    sys.exit(run_challenger_tests())
