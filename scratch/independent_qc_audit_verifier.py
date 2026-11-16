"""
Independent QC Audit Verifier - Read-Only / Transactional Rollback
Verifies DEF-01, DEF-02, DEF-03, DEF-04, DEF-05 without modifying persistent database state.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
from django.urls import get_resolver
get_resolver().url_patterns

from django.db import transaction
from django.utils import timezone
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, force_authenticate
from rest_framework import status

from hotel.models import (
    StockLocation, StockBatch, InventoryItem, InventoryCategory,
    StocktakeSession, StocktakeItem, StocktakeSchedule,
    InventoryExpiryAlert, SystemSettings, Account, JournalEntry
)
from apps.inventory.views import (
    StocktakeSessionViewSet, StocktakeScheduleViewSet,
    InventoryExpiryAlertViewSet, PurchaseRequisitionViewSet,
    PurchaseOrderViewSet, SupplierInvoiceViewSet,
    RequestForQuotationViewSet, SupplierQuotationViewSet
)
from hotel.inventory import evaluate_inventory_expiry_alerts
from hotel.stocktaking import create_stocktake_session, cancel_stocktake_session

User = get_user_model()
factory = RequestFactory()

results = {}

def log_result(name, passed, details):
    results[name] = {"passed": passed, "details": details}
    status_str = "[PASS]" if passed else "[FAIL]"
    print(f"{status_str} {name}: {details}")

# ==========================================
# DEF-01: Stocktake actions and ViewSet integrity
# ==========================================
def verify_def_01():
    print("\n--- Verifying DEF-01: Actions & ViewSet Integrity ---")
    session_actions = StocktakeSessionViewSet.get_extra_actions()
    action_names = {a.__name__ for a in session_actions}
    expected = {"record_counts", "request_recount", "submit_recount", "approve", "cancel"}
    missing = expected - action_names
    if missing:
        log_result("DEF-01: Stocktake Actions Registered", False, f"Missing actions: {missing}")
    else:
        log_result("DEF-01: Stocktake Actions Registered", True, f"All 5 actions registered: {expected}")

    # Check procurement actions
    proc_checks = [
        (PurchaseRequisitionViewSet, {"approve", "reject", "convert_to_po"}),
        (PurchaseOrderViewSet, {"receive_grn"}),
        (SupplierInvoiceViewSet, {"match_and_record", "approve"}),
        (RequestForQuotationViewSet, {"publish", "close_rfq"}),
        (SupplierQuotationViewSet, {"evaluate", "award_quotations", "convert_to_po"}),
    ]
    all_proc_ok = True
    for viewset_cls, expected_acts in proc_checks:
        registered = {a.__name__ for a in viewset_cls.get_extra_actions()}
        if not expected_acts.issubset(registered):
            all_proc_ok = False
            log_result(f"DEF-01: {viewset_cls.__name__} Actions", False, f"Missing {expected_acts - registered}")
    if all_proc_ok:
        log_result("DEF-01: Procurement Actions Registered", True, "All procurement actions registered.")

# ==========================================
# DEF-02: Audit deletion protection
# ==========================================
def verify_def_02():
    print("\n--- Verifying DEF-02: Audit Deletion Protection ---")
    with transaction.atomic():
        try:
            admin_user = User.objects.filter(role="admin").first()
            if not admin_user:
                admin_user = User.objects.create_superuser("audit_admin", "audit_admin@example.com", "pass123")
            
            loc = StockLocation.objects.first()
            cat = InventoryCategory.objects.first()
            item = InventoryItem.objects.first()

            # Create draft session
            session = create_stocktake_session(
                location=loc,
                counting_mode="blind",
                category=cat,
                created_by=admin_user,
            )
            stocktake_item = session.items.first()

            # 1. Test uncounted draft deletion
            client = APIClient()
            client.force_authenticate(user=admin_user)
            
            # Record a count to simulate counted session
            stocktake_item.counted_quantity = Decimal("10.00")
            stocktake_item.save()
            session.status = "counted"
            session.is_mode_locked = True
            session.save()

            # Attempt DELETE on counted session
            res_counted = client.delete(f"/users/stocktaking/sessions/{session.id}/")
            counted_blocked = (res_counted.status_code == status.HTTP_400_BAD_REQUEST)
            log_result("DEF-02: Counted Session Deletion Block", counted_blocked,
                       f"Status: {res_counted.status_code}, Msg: {res_counted.data.get('error')}")

            # Change to under_review
            session.status = "under_review"
            session.save()
            res_review = client.delete(f"/users/stocktaking/sessions/{session.id}/")
            review_blocked = (res_review.status_code == status.HTTP_400_BAD_REQUEST)
            log_result("DEF-02: Under-Review Session Deletion Block", review_blocked,
                       f"Status: {res_review.status_code}")

            # Change to approved
            session.status = "approved"
            session.save()
            res_app = client.delete(f"/users/stocktaking/sessions/{session.id}/")
            app_blocked = (res_app.status_code == status.HTTP_400_BAD_REQUEST)
            log_result("DEF-02: Approved Session Deletion Block", app_blocked,
                       f"Status: {res_app.status_code}")

            # Change to cancelled
            session.status = "cancelled"
            session.save()
            res_can = client.delete(f"/users/stocktaking/sessions/{session.id}/")
            can_blocked = (res_can.status_code == status.HTTP_400_BAD_REQUEST)
            log_result("DEF-02: Cancelled Session Deletion Block", can_blocked,
                       f"Status: {res_can.status_code}")

            # Verify child item remains intact
            items_intact = StocktakeItem.objects.filter(session_id=session.id).count() > 0
            log_result("DEF-02: Child StocktakeItem Records Intact", items_intact,
                       f"Stocktake items count: {StocktakeItem.objects.filter(session_id=session.id).count()}")

            # Test safe deletion of uncounted draft
            draft_session = create_stocktake_session(
                location=loc,
                counting_mode="blind",
                category=cat,
                created_by=admin_user,
            )
            d_id = draft_session.id
            res_draft_del = client.delete(f"/users/stocktaking/sessions/{d_id}/")
            draft_del_ok = (res_draft_del.status_code == status.HTTP_204_NO_CONTENT)
            still_exists = StocktakeSession.objects.filter(id=d_id).exists()
            log_result("DEF-02: Safe Uncounted Draft Deletion", draft_del_ok and not still_exists,
                       f"Status: {res_draft_del.status_code}, Session still exists: {still_exists}")

        finally:
            transaction.set_rollback(True)

# ==========================================
# DEF-03: Expiry alert dismissal lifecycle
# ==========================================
def verify_def_03():
    print("\n--- Verifying DEF-03: Expiry Alert Dismissal Lifecycle ---")
    with transaction.atomic():
        try:
            today = timezone.now().date()
            item = InventoryItem.objects.filter(is_perishable=True).first()
            if not item:
                item = InventoryItem.objects.create(
                    name="QC Test Perishable",
                    sku="QC-PERISH-01",
                    is_perishable=True,
                    unit="kg",
                    cost_price=Decimal("10.00"),
                )
            
            loc = StockLocation.objects.first()
            batch = StockBatch.objects.create(
                item=item,
                batch_number="QC-BATCH-DEF03",
                expiry_date=today + timedelta(days=20),
                initial_quantity=Decimal("50.00"),
                current_quantity=Decimal("50.00"),
                unit_cost=Decimal("10.00"),
                received_date=today,
                status="active",
            )
            
            # Initial scan -> creates near_expiry_30 alert
            eval_1 = evaluate_inventory_expiry_alerts()
            alert = InventoryExpiryAlert.objects.filter(batch=batch, alert_type="near_expiry_30").first()
            log_result("DEF-03: Initial Alert Created", alert is not None and alert.status == "active",
                       f"Alert ID: {alert.id if alert else 'None'}, Type: near_expiry_30")

            # Dismiss alert
            alert.status = "dismissed"
            alert.dismissed_at = timezone.now()
            alert.save()

            # Rescan 1
            eval_2 = evaluate_inventory_expiry_alerts()
            active_dupes = InventoryExpiryAlert.objects.filter(batch=batch, alert_type="near_expiry_30", status="active").count()
            log_result("DEF-03: Rescan 1 - No Duplicate Active Alert", active_dupes == 0,
                       f"Active count: {active_dupes}")

            # Rescan 2
            eval_3 = evaluate_inventory_expiry_alerts()
            active_dupes2 = InventoryExpiryAlert.objects.filter(batch=batch, alert_type="near_expiry_30", status="active").count()
            log_result("DEF-03: Rescan 2 - Persistence Confirmed", active_dupes2 == 0,
                       f"Active count: {active_dupes2}")

            # Test quantity change while dismissed
            batch.current_quantity = Decimal("35.00")
            batch.save()
            eval_4 = evaluate_inventory_expiry_alerts()
            alert.refresh_from_db()
            qty_synced = (alert.current_quantity == Decimal("35.00") and alert.status == "dismissed")
            log_result("DEF-03: Quantity Synced Non-Destructively While Dismissed", qty_synced,
                       f"Qty: {alert.current_quantity}, Status: {alert.status}")

            # Test zero stock depletion -> resolves alert
            batch.current_quantity = Decimal("0.00")
            batch.status = "depleted"
            batch.save()
            eval_5 = evaluate_inventory_expiry_alerts()
            alert.refresh_from_db()
            resolved_ok = (alert.status == "resolved" and alert.resolution_reason == "batch_consumed_or_depleted")
            log_result("DEF-03: Zero Stock Resolves Dismissed Alert", resolved_ok,
                       f"Status: {alert.status}, Reason: {alert.resolution_reason}")

            # Test restocking -> new active alert created
            batch.current_quantity = Decimal("25.00")
            batch.status = "active"
            batch.save()
            eval_6 = evaluate_inventory_expiry_alerts()
            new_active_alert = InventoryExpiryAlert.objects.filter(batch=batch, alert_type="near_expiry_30", status="active").first()
            log_result("DEF-03: Restocking Creates New Active Alert", new_active_alert is not None,
                       f"New active alert ID: {new_active_alert.id if new_active_alert else 'None'}")

            # Test warning tier escalation: batch expiry moves to 5 days (near_expiry_7)
            # Dismiss current near_expiry_30 alert
            if new_active_alert:
                new_active_alert.status = "dismissed"
                new_active_alert.save()
            batch.expiry_date = today + timedelta(days=5)
            batch.save()
            eval_7 = evaluate_inventory_expiry_alerts()
            escalated_alert = InventoryExpiryAlert.objects.filter(batch=batch, alert_type="near_expiry_7", status="active").first()
            log_result("DEF-03: Warning Tier Escalation Not Suppressed By Prior Dismissal", escalated_alert is not None,
                       f"Escalated alert found: {escalated_alert.alert_type if escalated_alert else 'None'}")

        finally:
            transaction.set_rollback(True)

# ==========================================
# DEF-04: Location permissions & Horizontal Scoping
# ==========================================
def verify_def_04():
    print("\n--- Verifying DEF-04: Location Permissions & Horizontal Scoping ---")
    with transaction.atomic():
        try:
            loc_a = StockLocation.objects.create(name="QC Location A", code="QC-LOC-A", location_type="store")
            loc_b = StockLocation.objects.create(name="QC Location B", code="QC-LOC-B", location_type="store")

            user_a = User.objects.create_user("custodian_a", "custodian_a@example.com", "pass123", role="inventory", is_active=True)
            user_b = User.objects.create_user("custodian_b", "custodian_b@example.com", "pass123", role="inventory", is_active=True)
            user_admin = User.objects.create_user("qc_admin", "qc_admin@example.com", "pass123", role="admin", is_active=True)
            user_manager = User.objects.create_user("qc_mgr", "qc_mgr@example.com", "pass123", role="hotel_manager", is_active=True)

            loc_a.custodian = user_a
            loc_a.save()
            loc_b.custodian = user_b
            loc_b.save()

            sched_a = StocktakeSchedule.objects.create(
                location=loc_a,
                frequency="daily",
                scheduled_time="02:00:00",
                next_run_at=timezone.now() + timedelta(days=1),
                created_by=user_a,
                assigned_staff=user_a,
            )

            client = APIClient()

            # 1. Test object-level write (pause action)
            # user_b attempts to pause sched_a -> should return 404 or 403 (unauthorized)
            client.force_authenticate(user=user_b)
            res_b_pause = client.post(f"/users/stocktaking/schedules/{sched_a.id}/pause/")
            log_result("DEF-04: Unauthorized Staff Write Blocked (404/403)", res_b_pause.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
                       f"Status: {res_b_pause.status_code}")

            # Custodian user_a pauses sched_a -> should return 200
            client.force_authenticate(user=user_a)
            res_a_pause = client.post(f"/users/stocktaking/schedules/{sched_a.id}/pause/")
            log_result("DEF-04: Custodian Staff Write Allowed (200)", res_a_pause.status_code == status.HTTP_200_OK,
                       f"Status: {res_a_pause.status_code}")

            # Admin pauses sched_a -> should return 200
            client.force_authenticate(user=user_admin)
            res_adm_pause = client.post(f"/users/stocktaking/schedules/{sched_a.id}/activate/")
            log_result("DEF-04: Administrator Write Allowed (200)", res_adm_pause.status_code == status.HTTP_200_OK,
                       f"Status: {res_adm_pause.status_code}")

            # 2. Test horizontal list filtering (Crucial QC check!)
            client.force_authenticate(user=user_b)
            res_b_list = client.get("/users/stocktaking/schedules/")
            items_list = res_b_list.data if isinstance(res_b_list.data, list) else res_b_list.data.get("results", [])
            schedules_returned = [s["id"] for s in items_list if isinstance(s, dict) and "id" in s]
            sched_a_exposed = (sched_a.id in schedules_returned)
            log_result("DEF-04: Schedule List Scoping Inspection", not sched_a_exposed,
                       f"Schedule A (Location A) returned to Custodian B: {sched_a_exposed}. (Total returned: {len(schedules_returned)})")

            # 3. Test horizontal retrieve scoping (IDOR protection)
            res_b_retrieve = client.get(f"/users/stocktaking/schedules/{sched_a.id}/")
            log_result("DEF-04: Schedule Retrieve Scoping Inspection", res_b_retrieve.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
                       f"Status: {res_b_retrieve.status_code} (Protected against IDOR cross-location access)")

        finally:
            transaction.set_rollback(True)

# ==========================================
# DEF-05: Configurable warning thresholds
# ==========================================
def verify_def_05():
    print("\n--- Verifying DEF-05: Configurable Warning Thresholds ---")
    with transaction.atomic():
        try:
            today = timezone.now().date()
            admin_user = User.objects.filter(role="admin").first()
            if not admin_user:
                admin_user = User.objects.create_superuser("audit_admin5", "audit_admin5@example.com", "pass123")

            client = APIClient()
            client.force_authenticate(user=admin_user)

            # Test GET /users/settings/
            res_get = client.get("/users/settings/")
            has_field = "near_expiry_warning_days" in res_get.data
            default_val = res_get.data.get("near_expiry_warning_days")
            log_result("DEF-05: API Settings Serializer Field Present", has_field,
                       f"Field present: {has_field}, Current value: {default_val}")

            # Test POST /users/settings/ with custom value
            res_post = client.post("/users/settings/", {"near_expiry_warning_days": 14}, format="json")
            updated_val = res_post.data.get("near_expiry_warning_days")
            log_result("DEF-05: API Custom Threshold Configuration", updated_val == 14,
                       f"Updated value returned: {updated_val}")

            # Test behavior with near_expiry_warning_days = 14
            item = InventoryItem.objects.filter(is_perishable=True).first()
            batch = StockBatch.objects.create(
                item=item,
                batch_number="QC-DEF05-TEST",
                expiry_date=today + timedelta(days=20),
                initial_quantity=Decimal("10.00"),
                current_quantity=Decimal("10.00"),
                unit_cost=Decimal("10.00"),
                received_date=today,
                status="active",
            )

            # Batch expires in 20 days. Since threshold is 14 days, it should NOT trigger near_expiry_30
            eval_res = evaluate_inventory_expiry_alerts()
            alert_14 = InventoryExpiryAlert.objects.filter(batch=batch, status="active").first()
            log_result("DEF-05: Clamped Window (14 days) Suppresses 20-day Alert", alert_14 is None,
                       f"Alert created: {alert_14.alert_type if alert_14 else 'None'}")

            # Now expand threshold to 30 days
            res_post30 = client.post("/users/settings/", {"near_expiry_warning_days": 30}, format="json")
            eval_res30 = evaluate_inventory_expiry_alerts()
            alert_30 = InventoryExpiryAlert.objects.filter(batch=batch, status="active").first()
            log_result("DEF-05: Expanded Window (30 days) Generates 20-day Alert", alert_30 is not None,
                       f"Alert created: {alert_30.alert_type if alert_30 else 'None'}")

        finally:
            transaction.set_rollback(True)

if __name__ == "__main__":
    verify_def_01()
    verify_def_02()
    verify_def_03()
    verify_def_04()
    verify_def_05()
    print("\n==========================================")
    print("INDEPENDENT QC VERIFIER EXECUTION FINISHED")
    print("==========================================")
