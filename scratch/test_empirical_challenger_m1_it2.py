"""
scratch/test_empirical_challenger_m1_it2.py
Empirical Challenger Test Suite for Milestone 1 Iteration 2
Comprehensive verification across the full Milestone 1 role & permission matrix.
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

import users.urls  # Ensure all URL routes and routers are registered
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from users.permissions import HasStocktakeLocationPermission, IsFinanceStaff, IsHotelAdmin
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
    RestaurantTable,
    Order,
    OrderItem,
    MenuItem,
    Category,
    CashHandover,
)
from hotel.stocktaking import (
    create_stocktake_session,
    record_counts,
    approve_stocktake_session,
)
from hotel.procurement import approve_purchase_requisition

User = get_user_model()


def test_section_1_hotel_manager_operational_and_restricted():
    print("\n" + "=" * 70)
    print("SECTION 1: Hotel Manager Operational Access & Security Boundary Checks")
    print("=" * 70)
    results = {}
    client = APIClient()

    # User 12: manager_proc2 (role: hotel_manager, superuser: False)
    u12 = User.objects.get(id=12)
    assert u12.username == "manager_proc2", f"User 12 username expected manager_proc2, got {u12.username}"
    assert u12.role == "hotel_manager", f"User 12 role expected hotel_manager, got {u12.role}"
    assert not u12.is_superuser, "User 12 must not be superuser"
    client.force_authenticate(user=u12)
    print(f"Authenticated as User 12: {u12.username} (role={u12.role}, superuser={u12.is_superuser})")

    # 1.1 GET /users/dashboard-stats/ -> HTTP 200 OK
    r_stats = client.get("/users/dashboard-stats/")
    print(f"1.1 GET /users/dashboard-stats/ -> HTTP {r_stats.status_code}")
    assert r_stats.status_code == status.HTTP_200_OK, f"Expected 200, got {r_stats.status_code}"
    results["1.1_dashboard_stats_200"] = "PASS"

    # 1.2 GET /users/orders/ -> HTTP 200 OK
    r_orders = client.get("/users/orders/")
    print(f"1.2 GET /users/orders/ -> HTTP {r_orders.status_code}")
    assert r_orders.status_code == status.HTTP_200_OK, f"Expected 200, got {r_orders.status_code}"
    results["1.2_orders_list_200"] = "PASS"

    # 1.3 GET /users/reports/operations-timing/ -> HTTP 200 OK
    r_timing = client.get("/users/reports/operations-timing/")
    print(f"1.3 GET /users/reports/operations-timing/ -> HTTP {r_timing.status_code}")
    assert r_timing.status_code == status.HTTP_200_OK, f"Expected 200, got {r_timing.status_code}"
    results["1.3_operations_timing_200"] = "PASS"

    # 1.4 Dining Supervisory Actions (MarkOrderServed, RequestBill, RecordCashHandover)
    with transaction.atomic():
        waiter_a = User.objects.filter(role="waiter", is_active=True).first()
        table = RestaurantTable.objects.first()
        menu_item = MenuItem.objects.first()

        order = Order.objects.create(
            table=table,
            waiter_id_ref=waiter_a.id,
            waiter_username=waiter_a.username,
            status="pending",
            sub_total=50.0,
            total_amount=57.5,
        )
        item = OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=1,
            price_at_order=50.0,
            status="ready",
        )

        # 1.4a MarkItemServed
        r_item_served = client.post(f"/users/orders/items/{item.id}/mark-served/")
        print(f"1.4a POST /users/orders/items/{item.id}/mark-served/ -> HTTP {r_item_served.status_code}")
        assert r_item_served.status_code == status.HTTP_200_OK, f"Expected 200, got {r_item_served.status_code}"

        # 1.4b MarkOrderServed
        r_ord_served = client.post(f"/users/orders/{order.id}/mark-served/")
        print(f"1.4b POST /users/orders/{order.id}/mark-served/ -> HTTP {r_ord_served.status_code}")
        assert r_ord_served.status_code == status.HTTP_200_OK, f"Expected 200, got {r_ord_served.status_code}"

        # 1.4c RequestBill
        r_bill = client.post(f"/users/orders/{order.id}/request-bill/")
        print(f"1.4c POST /users/orders/{order.id}/request-bill/ -> HTTP {r_bill.status_code}")
        assert r_bill.status_code == status.HTTP_200_OK, f"Expected 200, got {r_bill.status_code}"

        # 1.4d RecordCashHandover
        r_handover = client.post(f"/users/orders/{order.id}/cash-handover/", data={"amount": 57.5})
        print(f"1.4d POST /users/orders/{order.id}/cash-handover/ -> HTTP {r_handover.status_code}")
        assert r_handover.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), f"Expected 200/201, got {r_handover.status_code}"

        results["1.4_dining_supervisory_allowed"] = "PASS"
        transaction.set_rollback(True)

    # 1.5 POST /users/settings/ -> HTTP 403 Forbidden
    r_settings = client.post("/users/settings/", {"hotel_name": "Unauthorized Modification"}, format="json")
    print(f"1.5 POST /users/settings/ -> HTTP {r_settings.status_code}")
    assert r_settings.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_settings.status_code}"
    results["1.5_settings_post_403"] = "PASS"

    # 1.6 User Management Endpoints (/api/users/, /api/users/users/, /users/users/)
    r_users_drf = client.get("/users/users/")
    r_api_users_users = client.get("/api/users/users/")
    r_api_users_root = client.get("/api/users/")
    print(f"1.6a GET /users/users/ (UserViewSet) -> HTTP {r_users_drf.status_code}")
    print(f"1.6b GET /api/users/users/ (UserViewSet) -> HTTP {r_api_users_users.status_code}")
    print(f"1.6c GET /api/users/ (DefaultRouter root) -> HTTP {r_api_users_root.status_code}")
    assert r_users_drf.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_users_drf.status_code}"
    assert r_api_users_users.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_api_users_users.status_code}"
    results["1.6_user_management_403"] = "PASS"

    # 1.7 POST /users/finance/payroll/ -> HTTP 403 Forbidden
    payload_payroll = {
        "employee_name": "Challenger Leak Probe",
        "department": "kitchen",
        "role_title": "Cook",
        "basic_salary": "1000.00",
        "gross_pay": "1000.00",
        "net_pay": "900.00",
        "pay_period_start": "2026-11-01",
        "pay_period_end": "2026-11-30",
        "status": "draft",
    }
    r_payroll = client.post("/users/finance/payroll/", payload_payroll, format="json")
    print(f"1.7 POST /users/finance/payroll/ -> HTTP {r_payroll.status_code}")
    assert r_payroll.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_payroll.status_code}"
    results["1.7_payroll_post_403"] = "PASS"

    # 1.8 Negative checks: other finance endpoints blocked for hotel_manager
    r_journal = client.get("/users/finance/journal-entries/")
    r_expenses = client.get("/users/finance/expenses/")
    r_tax = client.get("/users/finance/tax-report/")
    print(f"1.8a GET /users/finance/journal-entries/ -> HTTP {r_journal.status_code}")
    print(f"1.8b GET /users/finance/expenses/ -> HTTP {r_expenses.status_code}")
    print(f"1.8c GET /users/finance/tax-report/ -> HTTP {r_tax.status_code}")
    assert r_journal.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_journal.status_code}"
    assert r_expenses.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_expenses.status_code}"
    assert r_tax.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_tax.status_code}"
    results["1.8_financial_endpoints_blocked_403"] = "PASS"

    return results


def test_section_2_stock_permissions_and_unassigned_locations():
    print("\n" + "=" * 70)
    print("SECTION 2: Stock Permissions, Unassigned Location Protection & SoD")
    print("=" * 70)
    results = {}
    rf = APIRequestFactory()
    perm = HasStocktakeLocationPermission()

    # Load users
    admin_user = User.objects.get(id=1)
    hm_user = User.objects.get(id=12)
    inv_user = User.objects.filter(role="inventory", is_active=True).first()
    kitchen_user = User.objects.filter(role="kitchen", is_active=True).first()
    waiter_user = User.objects.filter(role="waiter", is_active=True).first()
    bar_user = User.objects.filter(role="bar", is_active=True).first()
    cashier_user = User.objects.filter(role="cashier", is_active=True).first()

    # Setup unassigned location (custodian=None)
    unassigned_loc, _ = StockLocation.objects.get_or_create(
        code="CHAL-UNASSIGNED-LOC",
        defaults={"name": "Challenger Unassigned Store", "location_type": "storage", "custodian": None}
    )
    unassigned_loc.custodian = None
    unassigned_loc.save()

    unassigned_session = StocktakeSession(location=unassigned_loc, status="draft")

    # 2.1 Global access check for admin, hotel_manager, inventory
    global_users = [
        ("admin", admin_user),
        ("hotel_manager", hm_user),
        ("inventory", inv_user),
    ]
    for role_name, u in global_users:
        req = rf.get("/api/inventory/stocktake-sessions/")
        req.user = u
        has_p = perm.has_permission(req, None)
        has_obj = perm.has_object_permission(req, None, unassigned_session)
        print(f"2.1 {role_name}: has_permission={has_p}, has_obj(unassigned)={has_obj}")
        assert has_p is True, f"{role_name} expected has_permission=True"
        assert has_obj is True, f"{role_name} expected has_object_permission=True on unassigned location"

    results["2.1_global_access_admin_hm_inv"] = "PASS"

    # 2.2 Departmental staff access denied on unassigned location (has_permission and API)
    client = APIClient()
    dept_users = [
        ("waiter", waiter_user),
        ("kitchen", kitchen_user),
        ("bar", bar_user),
        ("cashier", cashier_user),
    ]
    for dept_role, dept_u in dept_users:
        req = rf.get("/api/inventory/stocktake-sessions/")
        req.user = dept_u
        has_p = perm.has_permission(req, None)
        has_obj = perm.has_object_permission(req, None, unassigned_session)
        print(f"2.2 {dept_role}: has_permission={has_p}, has_obj(unassigned)={has_obj}")
        assert has_p is False, f"{dept_role} should have has_permission=False on Stocktake"
        assert has_obj is False, f"{dept_role} should have has_object_permission=False on unassigned location"

        client.force_authenticate(user=dept_u)
        r_create = client.post(
            "/api/users/stocktaking/sessions/",
            {"location": unassigned_loc.id, "counting_mode": "blind", "title": f"Unauthorized {dept_role}"},
            format="json"
        )
        print(f"2.2 Dept {dept_role} POST /api/users/stocktaking/sessions/ -> HTTP {r_create.status_code}")
        assert r_create.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_create.status_code}"

    results["2.2_dept_staff_blocked_on_unassigned"] = "PASS"

    # 2.3 Separation of Duties (SoD) Count Self-Approval
    with transaction.atomic():
        cat, _ = InventoryCategory.objects.get_or_create(name="Challenger SoD Cat", defaults={"category_type": "operational"})
        inv_item, _ = InventoryItem.objects.get_or_create(
            item_code="CHAL-SOD-ITEM-01",
            defaults={"name": "SoD Item", "category": cat, "current_stock": Decimal("15.00"), "unit_cost": Decimal("20.00")}
        )

        # Count submitter = inv_user
        session_sod = create_stocktake_session(
            location=unassigned_loc,
            category=cat,
            counting_mode="blind",
            title="Empirical SoD Test Session",
            created_by=inv_user,
        )
        record_counts(
            session_id=session_sod.id,
            counts_data=[{"item_id": inv_item.id, "counted_quantity": Decimal("15.00")}],
            user=inv_user,
        )
        session_sod.refresh_from_db()
        assert session_sod.counted_by == inv_user

        # 2.3a Normal self-approval by count submitter must raise PermissionDenied
        self_appr_blocked = False
        try:
            approve_stocktake_session(
                session_id=session_sod.id,
                supervisor=inv_user,
                notes="Challenger self-approval probe",
            )
        except PermissionDenied as e:
            self_appr_blocked = True
            print(f"2.3a Self-approval blocked with PermissionDenied: {e}")
        assert self_appr_blocked, "Self-approval by inv_user did NOT raise PermissionDenied!"

        # 2.3b Non-superuser emergency self-approval must raise PermissionDenied
        emerg_blocked = False
        try:
            approve_stocktake_session(
                session_id=session_sod.id,
                supervisor=inv_user,
                emergency_self_approval=True,
                justification="Emergency non-superuser justification 123456789",
            )
        except PermissionDenied as e:
            emerg_blocked = True
            print(f"2.3b Non-superuser emergency self-approval blocked: {e}")
        assert emerg_blocked, "Non-superuser emergency self-approval did NOT raise PermissionDenied!"

        # 2.3c Superuser emergency self-approval with short justification (<15 chars) raises ValidationError
        session_su_sod = create_stocktake_session(
            location=unassigned_loc,
            category=cat,
            counting_mode="blind",
            title="Superuser SoD Test Session",
            created_by=admin_user,
        )
        record_counts(
            session_id=session_su_sod.id,
            counts_data=[{"item_id": inv_item.id, "counted_quantity": Decimal("15.00")}],
            user=admin_user,
        )
        session_su_sod.refresh_from_db()
        assert session_su_sod.counted_by == admin_user

        su_short_blocked = False
        try:
            approve_stocktake_session(
                session_id=session_su_sod.id,
                supervisor=admin_user,
                emergency_self_approval=True,
                justification="too short",
            )
        except ValidationError as e:
            su_short_blocked = True
            print(f"2.3c Superuser short justification rejected with ValidationError: {e}")
        assert su_short_blocked, "Superuser short justification did NOT raise ValidationError!"

        # 2.3d Independent supervisory approval by hotel_manager succeeds
        approved_session = approve_stocktake_session(
            session_id=session_sod.id,
            supervisor=hm_user,
            notes="Valid independent review by hotel_manager",
        )
        approved_session.refresh_from_db()
        assert approved_session.status == "approved"
        assert approved_session.reviewed_by == hm_user
        print(f"2.3d Independent approval succeeded: status={approved_session.status}, reviewed_by={approved_session.reviewed_by.username}")

        # 2.4 Approved Session Deletion Protection
        client.force_authenticate(user=admin_user)
        r_del = client.delete(f"/api/users/stocktaking/sessions/{approved_session.id}/")
        print(f"2.4 DELETE approved stocktake session -> HTTP {r_del.status_code}")
        assert r_del.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 Bad Request, got {r_del.status_code}"

        results["2.3_sod_and_deletion_protections"] = "PASS"
        transaction.set_rollback(True)

    return results


def test_section_3_supplier_architecture():
    print("\n" + "=" * 70)
    print("SECTION 3: Supplier Identity Architecture & Access Restrictions")
    print("=" * 70)
    results = {}
    client = APIClient()

    # User 21: sec_supplier_alpha (role: customer)
    supplier_user = User.objects.get(id=21)
    assert supplier_user.username == "sec_supplier_alpha"
    assert supplier_user.role == "customer", f"Supplier role expected 'customer', got '{supplier_user.role}'"
    assert not supplier_user.is_staff, "Supplier user must not have is_staff=True"
    assert not supplier_user.is_superuser, "Supplier user must not have is_superuser=True"
    print(f"Supplier user {supplier_user.username}: role={supplier_user.role}, is_staff={supplier_user.is_staff}, is_superuser={supplier_user.is_superuser}")
    results["3.1_supplier_user_attributes"] = "PASS"

    # 3.2 Supplier blocked from stocktaking sessions
    client.force_authenticate(user=supplier_user)
    r_stock = client.get("/api/users/stocktaking/sessions/")
    print(f"3.2 Supplier GET /api/users/stocktaking/sessions/ -> HTTP {r_stock.status_code}")
    assert r_stock.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_stock.status_code}"
    results["3.2_supplier_stocktake_blocked_403"] = "PASS"

    # 3.3 Supplier blocked from procurement approvals
    inv_user = User.objects.filter(role="inventory", is_active=True).first()
    tier, _ = ProcurementApprovalTier.objects.get_or_create(
        tier_level=1,
        defaults={"name": "Tier 1 - Operations", "threshold_amount": Decimal("10000.00"), "required_role": "inventory"}
    )
    with transaction.atomic():
        pr = PurchaseRequisition.objects.create(
            requisition_number="PR-SUPP-TEST-01",
            requested_by=inv_user,
            department="kitchen",
            total_estimated_amount=Decimal("500.00"),
            approval_tier=tier,
            status="pending_approval",
        )

        supp_appr_blocked = False
        try:
            approve_purchase_requisition(
                requisition_id=pr.id,
                approver=supplier_user,
                notes="Supplier unauthorized approval probe",
            )
        except PermissionDenied as e:
            supp_appr_blocked = True
            print(f"3.3a Supplier approval blocked via approve_purchase_requisition: {e}")
        assert supp_appr_blocked, "Supplier approval was NOT blocked by approve_purchase_requisition!"

        # API endpoint check
        r_pr_appr = client.post(f"/api/users/procurement/requisitions/{pr.id}/approve/", {"notes": "API test"}, format="json")
        print(f"3.3b Supplier POST /api/users/procurement/requisitions/{pr.id}/approve/ -> HTTP {r_pr_appr.status_code}")
        assert r_pr_appr.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN), f"Expected 400 or 403, got {r_pr_appr.status_code}"

        results["3.3_supplier_procurement_approval_blocked"] = "PASS"
        transaction.set_rollback(True)

    # 3.4 Supplier model architecture: zero foreign keys to User model
    supplier_fields = [f.name for f in Supplier._meta.get_fields()]
    has_user_fk = any("user" in f.lower() for f in supplier_fields)
    print(f"3.4 Supplier fields: {supplier_fields}. User FK present: {has_user_fk}")
    assert not has_user_fk, "Supplier model must not contain foreign keys to User!"
    results["3.4_supplier_model_architecture"] = "PASS"

    return results


def main():
    print("=" * 70)
    print("ACRMA HOTEL ERP — EMPIRICAL CHALLENGER VERIFICATION (M1-It2-2)")
    print("=" * 70)

    res1 = test_section_1_hotel_manager_operational_and_restricted()
    res2 = test_section_2_stock_permissions_and_unassigned_locations()
    res3 = test_section_3_supplier_architecture()

    all_results = {**res1, **res2, **res3}
    print("\n" + "=" * 70)
    print("SUMMARY OF EMPIRICAL CHALLENGE CHECKS:")
    print("=" * 70)
    for test_name, test_status in all_results.items():
        print(f"  {test_name:<45}: {test_status}")

    all_passed = all(status == "PASS" for status in all_results.values())
    print("\n" + "=" * 70)
    print(f"OVERALL EMPIRICAL VERDICT: {'ALL PASS' if all_passed else 'FAILURES DETECTED'}")
    print("=" * 70)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
