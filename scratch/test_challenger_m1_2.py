"""
scratch/test_challenger_m1_2.py
Empirical Challenger Test Suite for Milestone 1:
Validates DEF-04, DEF-05, and DEF-06 under adversarial and boundary conditions.
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

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from users.permissions import HasStocktakeLocationPermission
from hotel.models import (
    StockLocation,
    StocktakeSession,
    StocktakeItem,
    InventoryItem,
    InventoryCategory,
    PurchaseRequisition,
    ProcurementApprovalTier,
    Supplier,
    SupplierQuotation,
)
from hotel.stocktaking import (
    create_stocktake_session,
    record_counts,
    approve_stocktake_session,
)
from hotel.procurement import approve_purchase_requisition

User = get_user_model()

def run_all_challenges():
    results = {}
    print("=" * 70)
    print("STARTING EMPIRICAL CHALLENGER VERIFICATION (M1-2)")
    print("=" * 70)

    # Load test users
    admin_user = User.objects.get(id=1) # staging_admin, superuser=True, role=admin
    hm_user = User.objects.get(id=12) # manager_proc2, superuser=False, role=hotel_manager
    inv_user = User.objects.filter(role="inventory").first() # staging_controller
    kitchen_user = User.objects.filter(role="kitchen").first() # staging_chef
    waiter_user = User.objects.filter(role="waiter").first() # staging_waiter
    cashier_user = User.objects.filter(role="cashier").first() # staging_cashier
    bar_user = User.objects.filter(role="bar").first() # staging_bartender
    supplier_user = User.objects.get(id=21) # sec_supplier_alpha, role=customer

    print(f"Loaded Users:")
    print(f"  Admin: {admin_user.username} (id={admin_user.id}, role={admin_user.role}, superuser={admin_user.is_superuser})")
    print(f"  Hotel Manager: {hm_user.username} (id={hm_user.id}, role={hm_user.role}, superuser={hm_user.is_superuser})")
    print(f"  Inventory: {inv_user.username} (id={inv_user.id}, role={inv_user.role})")
    print(f"  Kitchen: {kitchen_user.username} (id={kitchen_user.id}, role={kitchen_user.role})")
    print(f"  Waiter: {waiter_user.username} (id={waiter_user.id}, role={waiter_user.role})")
    print(f"  Cashier: {cashier_user.username} (id={cashier_user.id}, role={cashier_user.role})")
    print(f"  Bar: {bar_user.username} (id={bar_user.id}, role={bar_user.role})")
    print(f"  Supplier: {supplier_user.username} (id={supplier_user.id}, role={supplier_user.role})")

    # -------------------------------------------------------------
    # CHALLENGE 1: DEF-05 Single-Hotel Global Stock Permissions
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("CHALLENGE 1: HasStocktakeLocationPermission Matrix")
    print("-" * 60)
    
    perm = HasStocktakeLocationPermission()
    rf = APIRequestFactory()

    # Find or create unassigned location (custodian = None)
    unassigned_loc, _ = StockLocation.objects.get_or_create(
        code="UNASSIGNED-TEST-LOC",
        defaults={"name": "Unassigned Test Store", "location_type": "storage", "custodian": None}
    )
    unassigned_loc.custodian = None
    unassigned_loc.save()

    # Find or create assigned location (custodian = kitchen_user)
    assigned_loc, _ = StockLocation.objects.get_or_create(
        code="ASSIGNED-KITCHEN-LOC",
        defaults={"name": "Kitchen Test Store", "location_type": "storage", "custodian": kitchen_user}
    )
    assigned_loc.custodian = kitchen_user
    assigned_loc.save()

    # Mock sessions
    unassigned_session = StocktakeSession(location=unassigned_loc, status="draft")
    assigned_session = StocktakeSession(location=assigned_loc, status="draft")

    test_roles = [
        ("admin", admin_user, True, True, True),
        ("hotel_manager", hm_user, True, True, True),
        ("inventory", inv_user, True, True, True),
        ("kitchen", kitchen_user, False, False, False), # on unassigned session: False, has_permission: False
        ("waiter", waiter_user, False, False, False),
        ("cashier", cashier_user, False, False, False),
        ("bar", bar_user, False, False, False),
        ("supplier_customer", supplier_user, False, False, False),
    ]

    ch1_success = True
    for role_label, user_obj, exp_perm, exp_obj_unassigned, exp_obj_assigned in test_roles:
        req = rf.get("/api/inventory/stocktake-sessions/")
        req.user = user_obj
        has_p = perm.has_permission(req, None)
        has_obj_un = perm.has_object_permission(req, None, unassigned_session)
        has_obj_as = perm.has_object_permission(req, None, assigned_session)

        expected_as = exp_obj_assigned
        if role_label == "kitchen":
            expected_as = True # custodian match in has_object_permission
        
        status_perm = (has_p == exp_perm)
        status_un = (has_obj_un == exp_obj_unassigned)
        status_as = (has_obj_as == expected_as)

        ok = status_perm and status_un and status_as
        if not ok:
            ch1_success = False
        print(f"[{'PASS' if ok else 'FAIL'}] Role {role_label}: has_permission={has_p} (exp={exp_perm}), "
              f"has_obj(unassigned)={has_obj_un} (exp={exp_obj_unassigned}), "
              f"has_obj(assigned)={has_obj_as} (exp={expected_as})")

    results["CHALLENGE_1_PERMISSION_MATRIX"] = "PASS" if ch1_success else "FAIL"

    # -------------------------------------------------------------
    # CHALLENGE 2: DEF-05 Unassigned Store Fallback Removal via REST API
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("CHALLENGE 2: Unassigned Store Fallback Removal via REST API")
    print("-" * 60)

    client = APIClient()
    ch2_success = True

    departmental_users = [
        ("kitchen", kitchen_user),
        ("waiter", waiter_user),
        ("cashier", cashier_user),
        ("bar", bar_user),
    ]

    for dept_role, dept_user in departmental_users:
        client.force_authenticate(user=dept_user)
        # Attempt to list stocktake sessions
        res_list = client.get("/api/users/stocktaking/sessions/")
        # Attempt to create stocktake session for unassigned location
        res_create = client.post(
            "/api/users/stocktaking/sessions/",
            {"location": unassigned_loc.id, "counting_mode": "blind", "title": "Unauthorized Test"},
            format="json",
        )
        # Attempt to create schedule for unassigned location
        res_sched = client.post(
            "/api/users/stocktaking/schedules/",
            {"location": unassigned_loc.id, "frequency": "daily", "name": "Unauthorized Sched"},
            format="json",
        )

        # Both must return 403 Forbidden because HasStocktakeLocationPermission.has_permission returns False!
        list_blocked = res_list.status_code == status.HTTP_403_FORBIDDEN
        create_blocked = res_create.status_code == status.HTTP_403_FORBIDDEN
        sched_blocked = res_sched.status_code == status.HTTP_403_FORBIDDEN

        ok = list_blocked and create_blocked and sched_blocked
        if not ok:
            ch2_success = False
        print(f"[{'PASS' if ok else 'FAIL'}] Dept role {dept_role}: "
              f"list_status={res_list.status_code} (exp=403), "
              f"create_status={res_create.status_code} (exp=403), "
              f"sched_status={res_sched.status_code} (exp=403)")

    # Test that inventory and hotel_manager CAN access and create for unassigned location
    client.force_authenticate(user=inv_user)
    res_inv_list = client.get("/api/users/stocktaking/sessions/")
    res_inv_create = client.post(
        "/api/users/stocktaking/sessions/",
        {"location": unassigned_loc.id, "counting_mode": "blind", "title": "Inventory Unassigned Test"},
        format="json",
    )
    inv_ok = (res_inv_list.status_code == 200 and res_inv_create.status_code == 201)
    if not inv_ok:
        ch2_success = False
    print(f"[{'PASS' if inv_ok else 'FAIL'}] Inventory user: "
          f"list_status={res_inv_list.status_code} (exp=200), "
          f"create_status={res_inv_create.status_code} (exp=201)")

    created_inv_session_id = res_inv_create.data.get("id") if res_inv_create.status_code == 201 else None

    client.force_authenticate(user=hm_user)
    res_hm_list = client.get("/api/users/stocktaking/sessions/")
    res_hm_create = client.post(
        "/api/users/stocktaking/sessions/",
        {"location": unassigned_loc.id, "counting_mode": "blind", "title": "HM Unassigned Test"},
        format="json",
    )
    hm_ok = (res_hm_list.status_code == 200 and res_hm_create.status_code == 201)
    if not hm_ok:
        ch2_success = False
    print(f"[{'PASS' if hm_ok else 'FAIL'}] Hotel Manager user: "
          f"list_status={res_hm_list.status_code} (exp=200), "
          f"create_status={res_hm_create.status_code} (exp=201)")

    created_hm_session_id = res_hm_create.data.get("id") if res_hm_create.status_code == 201 else None

    results["CHALLENGE_2_FALLBACK_REMOVAL"] = "PASS" if ch2_success else "FAIL"

    # -------------------------------------------------------------
    # CHALLENGE 3: DEF-05 SoD & Deletion Protections
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("CHALLENGE 3: Separation of Duties & Deletion Protections")
    print("-" * 60)
    ch3_success = True

    # 3.1 SoD Test on approve_stocktake_session
    # Prepare a test category and item if needed
    cat, _ = InventoryCategory.objects.get_or_create(name="Challenge Cat", defaults={"category_type": "operational"})
    inv_item, _ = InventoryItem.objects.get_or_create(
        item_code="CHAL-ITEM-01",
        defaults={"name": "Challenge Test Item", "category": cat, "current_stock": Decimal("10.00"), "unit_cost": Decimal("50.00")}
    )

    # Create session with counted_by = inv_user
    session_sod = create_stocktake_session(
        location=unassigned_loc,
        category=cat,
        counting_mode="blind",
        title="SoD Test Session",
        created_by=inv_user,
    )
    # Add count
    record_counts(
        session_id=session_sod.id,
        counts_data=[{"item_id": inv_item.id, "counted_quantity": Decimal("10.00")}],
        user=inv_user,
    )
    session_sod.refresh_from_db()
    assert session_sod.counted_by == inv_user, "counted_by should be inv_user"
    assert session_sod.status == "under_review", f"status should be under_review, got {session_sod.status}"

    # Test 3.1.1: Self-approval by count submitter (inv_user) must raise PermissionDenied
    try:
        approve_stocktake_session(
            session_id=session_sod.id,
            supervisor=inv_user,
            notes="Attempting self approval",
        )
        print("[FAIL] Self-approval by inv_user did NOT raise PermissionDenied!")
        ch3_success = False
    except PermissionDenied as e:
        print(f"[PASS] Self-approval blocked with PermissionDenied: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected exception on self-approval: {type(e)}: {e}")
        ch3_success = False

    # Test 3.1.2: Emergency self approval by non-superuser must still raise PermissionDenied
    try:
        approve_stocktake_session(
            session_id=session_sod.id,
            supervisor=inv_user,
            emergency_self_approval=True,
            justification="Emergency self approval by non-superuser",
        )
        print("[FAIL] Emergency self-approval by non-superuser was NOT blocked!")
        ch3_success = False
    except PermissionDenied as e:
        print(f"[PASS] Non-superuser emergency self-approval blocked: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected exception on non-superuser emergency self-approval: {type(e)}: {e}")
        ch3_success = False

    # Test 3.1.3: Superuser self approval without justification (< 15 chars) raises ValidationError
    # First set counted_by = admin_user
    session_su_sod = create_stocktake_session(
        location=unassigned_loc,
        category=cat,
        counting_mode="blind",
        title="Superuser SoD Session",
        created_by=admin_user,
    )
    record_counts(
        session_id=session_su_sod.id,
        counts_data=[{"item_id": inv_item.id, "counted_quantity": Decimal("10.00")}],
        user=admin_user,
    )
    try:
        approve_stocktake_session(
            session_id=session_su_sod.id,
            supervisor=admin_user,
            emergency_self_approval=True,
            justification="short",
        )
        print("[FAIL] Superuser emergency self-approval with short justification was NOT rejected!")
        ch3_success = False
    except ValidationError as e:
        print(f"[PASS] Superuser emergency self-approval short justification rejected: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected exception: {type(e)}: {e}")
        ch3_success = False

    # Test 3.1.4: Valid approval by separate supervisor (hm_user != inv_user) succeeds!
    try:
        appr_session = approve_stocktake_session(
            session_id=session_sod.id,
            supervisor=hm_user,
            notes="Authorized independent supervisory approval",
        )
        appr_session.refresh_from_db()
        if appr_session.status == "approved" and appr_session.reviewed_by == hm_user:
            print(f"[PASS] Independent supervisory approval by hotel_manager succeeded: status={appr_session.status}, reviewed_by={appr_session.reviewed_by.username}")
        else:
            print(f"[FAIL] Supervisory approval did not set status='approved': {appr_session.status}")
            ch3_success = False
    except Exception as e:
        print(f"[FAIL] Supervisory approval raised exception: {type(e)}: {e}")
        ch3_success = False

    # 3.2 Deletion Protection Tests on StocktakeSessionViewSet.destroy
    print("\n-- Deletion Protection (destroy action) --")
    client.force_authenticate(user=admin_user)

    # Test 3.2.1: Deleting approved session must return HTTP 400 Bad Request
    res_del_approved = client.delete(f"/api/users/stocktaking/sessions/{session_sod.id}/")
    ok_del_appr = (res_del_approved.status_code == status.HTTP_400_BAD_REQUEST)
    if not ok_del_appr:
        ch3_success = False
    print(f"[{'PASS' if ok_del_appr else 'FAIL'}] DELETE approved session {session_sod.id}: status={res_del_approved.status_code} (exp=400)")

    # Test 3.2.2: Deleting under_review session must return HTTP 400 Bad Request
    session_ur = create_stocktake_session(
        location=unassigned_loc,
        category=cat,
        counting_mode="blind",
        title="Under Review Deletion Test",
        created_by=inv_user,
    )
    record_counts(
        session_id=session_ur.id,
        counts_data=[{"item_id": inv_item.id, "counted_quantity": Decimal("10.00")}],
        user=inv_user,
    )
    res_del_ur = client.delete(f"/api/users/stocktaking/sessions/{session_ur.id}/")
    ok_del_ur = (res_del_ur.status_code == status.HTTP_400_BAD_REQUEST)
    if not ok_del_ur:
        ch3_success = False
    print(f"[{'PASS' if ok_del_ur else 'FAIL'}] DELETE under_review session {session_ur.id}: status={res_del_ur.status_code} (exp=400)")

    # Test 3.2.3: Deleting draft session with counted items or locked mode must return HTTP 400
    session_draft_locked = create_stocktake_session(
        location=unassigned_loc,
        category=cat,
        counting_mode="blind",
        title="Draft Locked Deletion Test",
        created_by=inv_user,
    )
    session_draft_locked.is_mode_locked = True
    session_draft_locked.save()
    res_del_locked = client.delete(f"/api/users/stocktaking/sessions/{session_draft_locked.id}/")
    ok_del_locked = (res_del_locked.status_code == status.HTTP_400_BAD_REQUEST)
    if not ok_del_locked:
        ch3_success = False
    print(f"[{'PASS' if ok_del_locked else 'FAIL'}] DELETE draft mode-locked session: status={res_del_locked.status_code} (exp=400)")

    # Test 3.2.4: Deleting pure uncounted draft session returns HTTP 204 No Content
    session_draft_clean = create_stocktake_session(
        location=unassigned_loc,
        category=cat,
        counting_mode="blind",
        title="Pure Draft Deletion Test",
        created_by=inv_user,
    )
    res_del_clean = client.delete(f"/api/users/stocktaking/sessions/{session_draft_clean.id}/")
    ok_del_clean = (res_del_clean.status_code == status.HTTP_204_NO_CONTENT)
    if not ok_del_clean:
        ch3_success = False
    print(f"[{'PASS' if ok_del_clean else 'FAIL'}] DELETE clean draft session: status={res_del_clean.status_code} (exp=204)")

    # Clean up created sessions from challenge 2
    if created_inv_session_id:
        client.delete(f"/api/users/stocktaking/sessions/{created_inv_session_id}/")
    if created_hm_session_id:
        client.delete(f"/api/users/stocktaking/sessions/{created_hm_session_id}/")

    results["CHALLENGE_3_SOD_AND_DELETION"] = "PASS" if ch3_success else "FAIL"

    # -------------------------------------------------------------
    # CHALLENGE 4: DEF-06 External Supplier Identity Architecture
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("CHALLENGE 4: DEF-06 External Supplier Identity Architecture")
    print("-" * 60)
    ch4_success = True

    # 4.1 Verify supplier user attributes
    supplier_role_ok = (supplier_user.role == "customer" and not supplier_user.is_staff and not supplier_user.is_superuser)
    if not supplier_role_ok:
        ch4_success = False
    print(f"[{'PASS' if supplier_role_ok else 'FAIL'}] sec_supplier_alpha (id=21) role is '{supplier_user.role}', is_staff={supplier_user.is_staff}, is_superuser={supplier_user.is_superuser}")

    # 4.2 Verify supplier cannot access stocktaking
    client.force_authenticate(user=supplier_user)
    res_supp_stock = client.get("/api/users/stocktaking/sessions/")
    supp_stock_blocked = (res_supp_stock.status_code == status.HTTP_403_FORBIDDEN)
    if not supp_stock_blocked:
        ch4_success = False
    print(f"[{'PASS' if supp_stock_blocked else 'FAIL'}] Supplier GET /api/users/stocktaking/sessions/: status={res_supp_stock.status_code} (exp=403)")

    # 4.3 Verify supplier cannot approve purchase requisition
    tier, _ = ProcurementApprovalTier.objects.get_or_create(
        tier_level=1,
        defaults={"name": "Tier 1 - Operations", "threshold_amount": Decimal("10000.00"), "required_role": "inventory"}
    )
    pr, _ = PurchaseRequisition.objects.get_or_create(
        requisition_number="PR-TEST-CHAL-01",
        defaults={
            "requested_by": inv_user,
            "department": "kitchen",
            "total_estimated_amount": Decimal("500.00"),
            "approval_tier": tier,
            "status": "pending_approval",
        }
    )
    pr.status = "pending_approval"
    pr.save()

    # Attempt approval directly via python function
    try:
        approve_purchase_requisition(
            requisition_id=pr.id,
            approver=supplier_user,
            notes="Unauthorized supplier approval attempt",
        )
        print("[FAIL] Supplier approval did NOT raise PermissionDenied!")
        ch4_success = False
    except PermissionDenied as e:
        print(f"[PASS] Supplier approval blocked via approve_purchase_requisition: {e}")
    except Exception as e:
        print(f"[FAIL] Unexpected exception on supplier approval: {type(e)}: {e}")
        ch4_success = False

    # Attempt approval via API endpoint
    res_pr_appr = client.post(f"/api/users/procurement/requisitions/{pr.id}/approve/", {"notes": "API test"}, format="json")
    supp_pr_blocked = (res_pr_appr.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
    if not supp_pr_blocked:
        ch4_success = False
    print(f"[{'PASS' if supp_pr_blocked else 'FAIL'}] Supplier POST /api/users/procurement/requisitions/{pr.id}/approve/: status={res_pr_appr.status_code} (exp=400/403)")

    # 4.4 Model architecture check: Supplier has no FK to User
    supplier_fields = [f.name for f in Supplier._meta.get_fields()]
    has_user_fk = any("user" in f.lower() for f in supplier_fields)
    model_arch_ok = not has_user_fk
    if not model_arch_ok:
        ch4_success = False
    print(f"[{'PASS' if model_arch_ok else 'FAIL'}] Supplier model fields: {supplier_fields}. User FK absent: {not has_user_fk}")

    results["CHALLENGE_4_SUPPLIER_IDENTITY"] = "PASS" if ch4_success else "FAIL"

    # -------------------------------------------------------------
    # CHALLENGE 5: DEF-04 Inventory Role Scope & Frontend Routing
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("CHALLENGE 5: DEF-04 Inventory Role Scope & Frontend Routing")
    print("-" * 60)
    ch5_success = True

    # 5.1 Backend inventory access without admin role
    client.force_authenticate(user=inv_user)
    endpoints = [
        ("Stocktake Sessions", "/api/users/stocktaking/sessions/", 200),
        ("Purchase Requisitions", "/api/users/procurement/requisitions/", 200),
        ("RFQs", "/api/users/procurement/rfqs/", 200),
        ("Quotations", "/api/users/procurement/quotations/", 200),
        ("Award Matrices", "/api/users/procurement/invoices/", 200), # supplier-invoices / 3-way match
        ("Inventory Items", "/api/users/inventory-items/", 200),
        ("Stock Locations", "/api/users/locations/", 200),
        ("Stock Transfers", "/api/users/transfers/", 200),
    ]

    for name, ep, exp_status in endpoints:
        res = client.get(ep)
        ok = (res.status_code == exp_status)
        if not ok:
            ch5_success = False
        print(f"[{'PASS' if ok else 'FAIL'}] Inventory user GET {name} ({ep}): status={res.status_code} (exp={exp_status})")

    # 5.2 Verify inventory user is blocked from technical admin endpoints
    res_admin_users = client.get("/api/users/users/")
    admin_blocked = (res_admin_users.status_code == status.HTTP_403_FORBIDDEN)
    if not admin_blocked:
        ch5_success = False
    print(f"[{'PASS' if admin_blocked else 'FAIL'}] Inventory user GET /api/users/users/: status={res_admin_users.status_code} (exp=403)")

    # 5.3 Verify static frontend files
    app_js_path = os.path.join(BASE_DIR, "hotel-frontend", "src", "App.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_js_content = f.read()

    sidebar_js_path = os.path.join(BASE_DIR, "hotel-frontend", "src", "Sidebar.js")
    with open(sidebar_js_path, "r", encoding="utf-8") as f:
        sidebar_js_content = f.read()

    app_has_inventory_tab = "case 'inventory':" in app_js_content and "DashboardLayout" in app_js_content
    app_sets_active_tab = "setActiveTab('inventory')" in app_js_content
    sidebar_has_inventory_filter = "userRole === 'inventory'" in sidebar_js_content
    sidebar_limits_reports = "child.id !== 'report_inventory'" in sidebar_js_content

    frontend_ok = app_has_inventory_tab and app_sets_active_tab and sidebar_has_inventory_filter and sidebar_limits_reports
    if not frontend_ok:
        ch5_success = False
    print(f"[{'PASS' if frontend_ok else 'FAIL'}] Frontend static checks: "
          f"app_has_inventory_tab={app_has_inventory_tab}, "
          f"app_sets_active_tab={app_sets_active_tab}, "
          f"sidebar_has_inventory_filter={sidebar_has_inventory_filter}, "
          f"sidebar_limits_reports={sidebar_limits_reports}")

    results["CHALLENGE_5_INVENTORY_SCOPE"] = "PASS" if ch5_success else "FAIL"

    # -------------------------------------------------------------
    # OVERALL SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHALLENGE RESULTS SUMMARY:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    
    all_passed = all(v == "PASS" for v in results.values())
    print(f"OVERALL STATUS: {'ALL CHALLENGES PASSED' if all_passed else 'SOME CHALLENGES FAILED'}")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    success = run_all_challenges()
    sys.exit(0 if success else 1)
