"""
Empirical Challenge Verification Script for Milestone 1 (DEF-01, DEF-02, DEF-03)
Author: Challenger M1-1
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import users.urls  # Break circular imports early
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status
from django.core.exceptions import ValidationError
from apps.identity.serializers import UserSerializer
from apps.orders.views import (
    MarkOrderServedView,
    MarkOrderItemServedView,
    RequestBillView,
    RecordCashHandoverView,
)
from hotel.models import RestaurantTable, Order, OrderItem, MenuItem, Category, CashHandover
from django.utils import timezone

User = get_user_model()

def run_def01_checks():
    print("=== DEF-01: Model & Serializer Verification ===")
    results = {}
    
    # 1. Verify User.ROLE_CHOICES
    role_choices_dict = dict(User.ROLE_CHOICES)
    assert "hotel_manager" in role_choices_dict, "hotel_manager missing from User.ROLE_CHOICES"
    assert role_choices_dict["hotel_manager"] == "Hotel Manager", f"Unexpected label: {role_choices_dict['hotel_manager']}"
    print("[PASS] User.ROLE_CHOICES contains ('hotel_manager', 'Hotel Manager')")
    results["role_choices"] = "PASS"

    # 2. Check User 12 (manager_proc2)
    u12 = User.objects.get(id=12)
    assert u12.username == "manager_proc2", f"Expected manager_proc2, got {u12.username}"
    assert u12.role == "hotel_manager", f"Expected hotel_manager, got {u12.role}"
    u12.full_clean()
    print(f"[PASS] User 12 ({u12.username}) role={u12.role} passed full_clean()")
    results["user_12_clean"] = "PASS"

    # 3. Check User 16 (sec_ops_manager)
    u16 = User.objects.get(id=16)
    assert u16.username == "sec_ops_manager", f"Expected sec_ops_manager, got {u16.username}"
    assert u16.role == "hotel_manager", f"Expected hotel_manager, got {u16.role}"
    u16.full_clean()
    print(f"[PASS] User 16 ({u16.username}) role={u16.role} passed full_clean()")
    results["user_16_clean"] = "PASS"

    # 4. UserSerializer with valid role "hotel_manager"
    valid_data = {
        "username": "test_hm_challenger",
        "email": "test_hm_challenger@example.com",
        "role": "hotel_manager",
    }
    s_valid = UserSerializer(data=valid_data)
    assert s_valid.is_valid(), f"UserSerializer invalid with hotel_manager: {s_valid.errors}"
    print("[PASS] UserSerializer valid with role='hotel_manager'")
    results["serializer_valid_role"] = "PASS"

    # 5. UserSerializer with invalid role "manager" (the old non-authoritative string)
    invalid_data = {
        "username": "test_inv_challenger",
        "email": "test_inv_challenger@example.com",
        "role": "manager",
    }
    s_invalid = UserSerializer(data=invalid_data)
    assert not s_invalid.is_valid(), "UserSerializer unexpectedly accepted invalid role 'manager'"
    assert "role" in s_invalid.errors, f"Expected role error in {s_invalid.errors}"
    print(f"[PASS] UserSerializer rejected invalid role='manager': {s_invalid.errors['role']}")
    results["serializer_invalid_manager"] = "PASS"

    # 6. UserSerializer with arbitrary invalid role "attacker"
    invalid_data2 = {
        "username": "test_inv2_challenger",
        "email": "test_inv2_challenger@example.com",
        "role": "attacker",
    }
    s_invalid2 = UserSerializer(data=invalid_data2)
    assert not s_invalid2.is_valid(), "UserSerializer unexpectedly accepted role 'attacker'"
    assert "role" in s_invalid2.errors
    print(f"[PASS] UserSerializer rejected invalid role='attacker': {s_invalid2.errors['role']}")
    results["serializer_invalid_attacker"] = "PASS"

    return results


def run_def02_checks():
    print("\n=== DEF-02: Hotel Manager API Access & User Administration Block ===")
    results = {}
    client = APIClient()
    u12 = User.objects.get(id=12)
    client.force_authenticate(user=u12)

    # 1. GET /users/dashboard-stats/
    r1 = client.get("/users/dashboard-stats/")
    print(f"GET /users/dashboard-stats/ -> HTTP {r1.status_code}")
    assert r1.status_code == status.HTTP_200_OK, f"Expected 200, got {r1.status_code}: {r1.content}"
    results["dashboard_stats"] = "PASS (200)"

    # 2. GET /users/orders/
    r2 = client.get("/users/orders/")
    print(f"GET /users/orders/ -> HTTP {r2.status_code}")
    assert r2.status_code == status.HTTP_200_OK, f"Expected 200, got {r2.status_code}: {r2.content}"
    results["orders_list"] = "PASS (200)"

    # 3. GET /users/reports/operations-timing/
    r3 = client.get("/users/reports/operations-timing/")
    print(f"GET /users/reports/operations-timing/ -> HTTP {r3.status_code}")
    assert r3.status_code == status.HTTP_200_OK, f"Expected 200, got {r3.status_code}: {r3.content}"
    results["operations_timing"] = "PASS (200)"

    # 4. User administration endpoint security check
    # Check UserViewSet list under /users/users/
    r_users_drf = client.get("/users/users/")
    print(f"GET /users/users/ (UserViewSet) -> HTTP {r_users_drf.status_code}")
    assert r_users_drf.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_users_drf.status_code}"
    results["user_admin_users_users"] = "PASS (403 Forbidden)"

    # Check UserViewSet list under /api/users/users/
    r_users_api = client.get("/api/users/users/")
    print(f"GET /api/users/users/ (UserViewSet) -> HTTP {r_users_api.status_code}")
    assert r_users_api.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_users_api.status_code}"
    results["user_admin_api_users_users"] = "PASS (403 Forbidden)"

    # Check UserViewSet list under /api/v1/users/
    r_users_v1 = client.get("/api/v1/users/")
    print(f"GET /api/v1/users/ (UserViewSet) -> HTTP {r_users_v1.status_code}")
    assert r_users_v1.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_users_v1.status_code}"
    results["user_admin_api_v1_users"] = "PASS (403 Forbidden)"

    # Note /api/users/ router root
    r_root = client.get("/api/users/")
    print(f"GET /api/users/ (DefaultRouter root) -> HTTP {r_root.status_code} ({r_root.data})")
    results["router_root_api_users"] = f"INFO ({r_root.status_code})"

    # 5. Negative check: regular waiter blocked from dashboard-stats
    waiter = User.objects.filter(role="waiter", is_active=True).first()
    assert waiter is not None, "No active waiter found for testing"
    waiter_client = APIClient()
    waiter_client.force_authenticate(user=waiter)
    r_waiter_stats = waiter_client.get("/users/dashboard-stats/")
    print(f"Waiter GET /users/dashboard-stats/ -> HTTP {r_waiter_stats.status_code}")
    assert r_waiter_stats.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403 for waiter on dashboard stats, got {r_waiter_stats.status_code}"
    results["waiter_blocked_dashboard_stats"] = "PASS (403 Forbidden)"

    return results


def run_def03_checks():
    print("\n=== DEF-03: Dining Supervisor Views & Waiter Isolation ===")
    results = {}
    from django.db import transaction

    u12 = User.objects.get(id=12) # hotel_manager
    waiter_a = User.objects.filter(role="waiter", is_active=True).first()
    waiter_b = User.objects.filter(role="waiter", is_active=True).exclude(id=waiter_a.id).first()
    kitchen_user = User.objects.filter(role="kitchen", is_active=True).first()
    table = RestaurantTable.objects.first()
    category = Category.objects.first()
    menu_item = MenuItem.objects.first()

    with transaction.atomic():
        client_b = APIClient()
        client_b.force_authenticate(user=waiter_b)

        client_hm = APIClient()
        client_hm.force_authenticate(user=u12)

        client_kitchen = APIClient()
        client_kitchen.force_authenticate(user=kitchen_user)

        # 1. TEST MarkOrderItemServedView
        order1 = Order.objects.create(
            table=table,
            waiter_id_ref=waiter_a.id,
            waiter_username=waiter_a.username,
            status="pending",
            sub_total=100.0,
            total_amount=115.0,
        )
        item1 = OrderItem.objects.create(
            order=order1,
            menu_item=menu_item,
            quantity=1,
            price_at_order=100.0,
            status="ready",  # Ready to be served
        )

        # Waiter B tries to serve Waiter A's item -> Must be 403 Forbidden
        r_item_b = client_b.post(f"/users/orders/items/{item1.id}/mark-served/")
        print(f"Waiter B mark-item-served for Waiter A's order -> HTTP {r_item_b.status_code}")
        assert r_item_b.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_item_b.status_code}"
        assert "not authorized to mark items served for another waiter" in str(r_item_b.data), str(r_item_b.data)
        results["item_served_waiter_denied"] = "PASS (403 Forbidden)"

        # Kitchen user tries to mark served -> Must be 403 Forbidden (not waiter/manager/admin)
        r_item_kit = client_kitchen.post(f"/users/orders/items/{item1.id}/mark-served/")
        print(f"Kitchen user mark-item-served -> HTTP {r_item_kit.status_code}")
        assert r_item_kit.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_item_kit.status_code}"
        results["item_served_kitchen_denied"] = "PASS (403 Forbidden)"

        # Hotel Manager marks item served -> Authorized (HTTP 200)
        r_item_hm = client_hm.post(f"/users/orders/items/{item1.id}/mark-served/")
        print(f"Hotel Manager mark-item-served -> HTTP {r_item_hm.status_code}")
        assert r_item_hm.status_code == status.HTTP_200_OK, f"Expected 200, got {r_item_hm.status_code}: {r_item_hm.content}"
        results["item_served_manager_allowed"] = "PASS (200 OK)"

        # 2. TEST MarkOrderServedView
        order2 = Order.objects.create(
            table=table,
            waiter_id_ref=waiter_a.id,
            waiter_username=waiter_a.username,
            status="pending",
            sub_total=100.0,
            total_amount=115.0,
        )
        item2 = OrderItem.objects.create(
            order=order2,
            menu_item=menu_item,
            quantity=1,
            price_at_order=100.0,
            status="ready",
        )

        # Waiter B tries to mark whole order served -> Must be 403 Forbidden
        r_ord_b = client_b.post(f"/users/orders/{order2.id}/mark-served/")
        print(f"Waiter B mark-order-served for Waiter A's order -> HTTP {r_ord_b.status_code}")
        assert r_ord_b.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_ord_b.status_code}"
        results["order_served_waiter_denied"] = "PASS (403 Forbidden)"

        # Hotel Manager marks whole order served -> Authorized (HTTP 200)
        r_ord_hm = client_hm.post(f"/users/orders/{order2.id}/mark-served/")
        print(f"Hotel Manager mark-order-served -> HTTP {r_ord_hm.status_code}")
        assert r_ord_hm.status_code == status.HTTP_200_OK, f"Expected 200, got {r_ord_hm.status_code}: {r_ord_hm.content}"
        results["order_served_manager_allowed"] = "PASS (200 OK)"

        # 3. TEST RequestBillView
        # order2 is now in status "served"
        # Waiter B tries to request bill for Waiter A's order -> Must be 403 Forbidden
        r_bill_b = client_b.post(f"/users/orders/{order2.id}/request-bill/")
        print(f"Waiter B request-bill for Waiter A's order -> HTTP {r_bill_b.status_code}")
        assert r_bill_b.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_bill_b.status_code}"
        results["request_bill_waiter_denied"] = "PASS (403 Forbidden)"

        # Hotel Manager requests bill -> Authorized (HTTP 200)
        r_bill_hm = client_hm.post(f"/users/orders/{order2.id}/request-bill/")
        print(f"Hotel Manager request-bill -> HTTP {r_bill_hm.status_code}")
        assert r_bill_hm.status_code == status.HTTP_200_OK, f"Expected 200, got {r_bill_hm.status_code}: {r_bill_hm.content}"
        results["request_bill_manager_allowed"] = "PASS (200 OK)"

        # 4. TEST RecordCashHandoverView
        # order2 is now in status "bill_requested"
        # Waiter B tries to record cash handover for Waiter A's order -> Must be 403 Forbidden
        r_handover_b = client_b.post(f"/users/orders/{order2.id}/cash-handover/", data={"amount": 115.0})
        print(f"Waiter B cash-handover for Waiter A's order -> HTTP {r_handover_b.status_code}")
        assert r_handover_b.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {r_handover_b.status_code}"
        results["cash_handover_waiter_denied"] = "PASS (403 Forbidden)"

        # Hotel Manager records cash handover -> Authorized (HTTP 200 or 201)
        r_handover_hm = client_hm.post(f"/users/orders/{order2.id}/cash-handover/", data={"amount": 115.0})
        print(f"Hotel Manager cash-handover -> HTTP {r_handover_hm.status_code}")
        assert r_handover_hm.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED], f"Expected 200/201, got {r_handover_hm.status_code}: {r_handover_hm.content}"
        results["cash_handover_manager_allowed"] = f"PASS ({r_handover_hm.status_code})"

        # Roll back transaction to not pollute DB
        transaction.set_rollback(True)

    return results

def run_adversarial_stress_tests():
    print("\n=== ADVERSARIAL STRESS TESTING: Edge Cases & Boundary Conditions ===")
    results = {}
    from django.db import transaction
    from hotel.models import StockLocation, StocktakeSession
    from users.permissions import HasStocktakeLocationPermission

    u12 = User.objects.get(id=12) # hotel_manager
    waiter_a = User.objects.filter(role="waiter", is_active=True).first()
    waiter_b = User.objects.filter(role="waiter", is_active=True).exclude(id=waiter_a.id).first()
    table = RestaurantTable.objects.first()
    menu_item = MenuItem.objects.first()

    client_hm = APIClient()
    client_hm.force_authenticate(user=u12)

    # Stress Test 1: Privilege Escalation Attempt via UserViewSet
    print("Stress Test 1: Hotel Manager attempting User Creation / Escalation...")
    r_create = client_hm.post("/users/users/", data={
        "username": "escalated_user",
        "email": "escalated@example.com",
        "role": "admin",
        "password": "ValidPassword123!"
    })
    print(f"Hotel Manager POST /users/users/ -> HTTP {r_create.status_code}")
    assert r_create.status_code == status.HTTP_403_FORBIDDEN, f"Privilege escalation failure! Got {r_create.status_code}"
    results["privilege_escalation_user_create"] = "PASS (403 Forbidden)"

    r_patch = client_hm.patch(f"/users/users/{u12.id}/", data={"is_superuser": True})
    print(f"Hotel Manager PATCH /users/users/{u12.id}/ -> HTTP {r_patch.status_code}")
    assert r_patch.status_code == status.HTTP_403_FORBIDDEN, f"Privilege escalation failure! Got {r_patch.status_code}"
    results["privilege_escalation_user_patch"] = "PASS (403 Forbidden)"

    with transaction.atomic():
        # Stress Test 2: Cannot serve order with unready (pending/preparing) items
        print("Stress Test 2: Serving Order with Pending Items...")
        order_unready = Order.objects.create(
            table=table,
            waiter_id_ref=waiter_a.id,
            waiter_username=waiter_a.username,
            status="pending",
            sub_total=100.0,
            total_amount=115.0,
        )
        item_pending = OrderItem.objects.create(
            order=order_unready,
            menu_item=menu_item,
            quantity=1,
            price_at_order=100.0,
            status="pending",
        )
        r_serve_pending = client_hm.post(f"/users/orders/{order_unready.id}/mark-served/")
        print(f"Hotel Manager mark-order-served on pending order -> HTTP {r_serve_pending.status_code}")
        assert r_serve_pending.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for pending items, got {r_serve_pending.status_code}"
        assert "Cannot mark entire order as served" in str(r_serve_pending.data)
        results["unready_order_serve_rejected"] = "PASS (400 Bad Request)"

        # Stress Test 3: Request Bill for unserved order (status="pending")
        print("Stress Test 3: Requesting Bill on Non-Served Order...")
        r_bill_unserved = client_hm.post(f"/users/orders/{order_unready.id}/request-bill/")
        print(f"Hotel Manager request-bill on pending order -> HTTP {r_bill_unserved.status_code}")
        assert r_bill_unserved.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for unserved order bill request, got {r_bill_unserved.status_code}"
        results["unserved_order_bill_rejected"] = "PASS (400 Bad Request)"

        # Stress Test 4: Cannot collect cash for already paid order
        print("Stress Test 4: Cash Handover for Already Paid Order...")
        order_paid = Order.objects.create(
            table=table,
            waiter_id_ref=waiter_a.id,
            waiter_username=waiter_a.username,
            status="served",
            payment_status="paid",
            sub_total=100.0,
            total_amount=115.0,
        )
        r_handover_paid = client_hm.post(f"/users/orders/{order_paid.id}/cash-handover/", data={"amount": 115.0})
        print(f"Hotel Manager cash-handover on paid order -> HTTP {r_handover_paid.status_code}")
        assert r_handover_paid.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for paid order cash handover, got {r_handover_paid.status_code}"
        results["paid_order_handover_rejected"] = "PASS (400 Bad Request)"

        # Stress Test 5: Unassigned location access check (DEF-05 regression boundary)
        print("Stress Test 5: Unassigned location (custodian=None) access by Waiter...")
        loc_unassigned = StockLocation.objects.filter(custodian__isnull=True).first()
        if not loc_unassigned:
            loc_unassigned = StockLocation.objects.create(name="Challenger Unassigned Store", location_type="warehouse", custodian=None)
        
        session_unassigned = StocktakeSession(location=loc_unassigned)
        perm = HasStocktakeLocationPermission()
        req_factory = APIRequestFactory()

        # Hotel Manager must pass
        req_hm = req_factory.get("/")
        req_hm.user = u12
        assert perm.has_permission(req_hm, None), "Hotel manager failed has_permission"
        assert perm.has_object_permission(req_hm, None, session_unassigned), "Hotel manager failed object permission on unassigned loc"
        print("[PASS] Hotel Manager holds global access to unassigned stock location")
        results["hotel_manager_unassigned_stock_access"] = "PASS (Allowed)"

        # Waiter MUST be denied
        req_waiter = req_factory.get("/")
        req_waiter.user = waiter_a
        waiter_has_perm = perm.has_permission(req_waiter, None)
        print(f"Waiter has_permission on Stocktake -> {waiter_has_perm}")
        assert not waiter_has_perm, "SECURITY FAILURE: Waiter allowed on Stocktake permission!"
        results["waiter_denied_stock_access"] = "PASS (Denied)"

        transaction.set_rollback(True)

    return results

if __name__ == "__main__":
    def01_res = run_def01_checks()
    def02_res = run_def02_checks()
    def03_res = run_def03_checks()
    stress_res = run_adversarial_stress_tests()
    print("\n==========================================")
    print("ALL EMPIRICAL CHALLENGE CHECKS & STRESS TESTS PASSED!")
    print("==========================================")
