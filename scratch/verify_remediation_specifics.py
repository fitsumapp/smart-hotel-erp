import os, sys, django
sys.path.insert(0, os.path.abspath("."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from hotel.models import (
    StockLocation, InventoryCategory, InventoryItem, StockBatch,
    InventoryExpiryAlert, StocktakeSession, StocktakeItem, StocktakeSchedule,
    SystemSettings
)
from hotel.stocktaking import create_stocktake_session, record_counts
from hotel.inventory import evaluate_inventory_expiry_alerts
from users.models import User

print("======================================================================")
print("RUNNING REMEDIATION SPECIFIC VERIFICATION CHECKS")
print("======================================================================")

today = timezone.now().date()
client = APIClient()

# Create unique test users
admin_user, _ = User.objects.get_or_create(username="remed_admin", defaults={"role": "admin", "is_active": True})
staff_a, _ = User.objects.get_or_create(username="remed_staff_a", defaults={"role": "inventory", "is_active": True})
staff_b, _ = User.objects.get_or_create(username="remed_staff_b", defaults={"role": "inventory", "is_active": True})

# Setup test categories and locations
cat, _ = InventoryCategory.objects.get_or_create(name="Remediation Test Cat")
loc_a, _ = StockLocation.objects.get_or_create(code="REMED-LOC-A", defaults={"name": "Store A", "custodian": staff_a})
loc_b, _ = StockLocation.objects.get_or_create(code="REMED-LOC-B", defaults={"name": "Store B", "custodian": staff_b})
if loc_a.custodian != staff_a:
    loc_a.custodian = staff_a
    loc_a.save()
if loc_b.custodian != staff_b:
    loc_b.custodian = staff_b
    loc_b.save()

import time
ts = int(time.time())

# -----------------------------------------------------------------------------
# 1. DEF-02: Prevent Destructive Deletion of Stocktake Sessions and Audits
# -----------------------------------------------------------------------------
print("\n--- Check 1: DEF-02 Audit Deletion Protection ---")
item, _ = InventoryItem.objects.get_or_create(
    item_code=f"REMED-ITM-{ts}",
    defaults={"name": "Test Item 01", "category": cat, "unit": "pcs", "current_stock": Decimal("50.00"), "unit_cost": Decimal("100.00")}
)
session = create_stocktake_session(location=loc_a, category=cat, counting_mode="blind", created_by=admin_user)
record_counts(session_id=session.pk, counts_data=[{"item_id": item.pk, "counted_quantity": Decimal("48.00")}], user=staff_a)

session.refresh_from_db()
print(f"Created Session #{session.session_number} in status '{session.status}' with items: {session.items.count()}")

# Authenticate as admin and attempt DELETE
client.force_authenticate(user=admin_user)
del_res = client.delete(f"/users/stocktaking/sessions/{session.id}/")
print(f"Attempted DELETE on counted session: HTTP {del_res.status_code}")
assert del_res.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400, got {del_res.status_code}"
assert "Historical inventory audits cannot be deleted" in str(del_res.data) or "locked mode" in str(del_res.data)

# Verify records still exist in database
session.refresh_from_db()
assert session.items.count() > 0, "Audit items were erroneously deleted!"
print("PASS: Counted/under-review session deletion strictly blocked, audit items intact!")

# -----------------------------------------------------------------------------
# 2. DEF-03: Expiry-Alert Dismissal Persistence & Zero-Reactivation
# -----------------------------------------------------------------------------
print("\n--- Check 2: DEF-03 Dismissal Persistence & Zero-Reactivation ---")
exp_batch = StockBatch.objects.create(
    batch_number=f"REMED-BATCH-DISMISS-{ts}",
    item=item,
    current_quantity=Decimal("15.00"),
    initial_quantity=Decimal("15.00"),
    unit_cost=Decimal("100.00"),
    received_date=today,
    expiry_date=today + timezone.timedelta(days=5), # Near expiry 7d tier
    status="active",
)

# Step 1: Evaluate alerts
res1 = evaluate_inventory_expiry_alerts()
print(f"Initial Scan: created={res1['created']}, active_total={res1['active_total']}")
alert = InventoryExpiryAlert.objects.filter(batch=exp_batch, status="active").first()
assert alert is not None, "Alert was not created on initial scan!"
alert_id = alert.id
print(f"Active Alert #{alert_id} created for batch {exp_batch.batch_number}")

# Step 2: Dismiss alert via API
client.force_authenticate(user=admin_user)
dismiss_res = client.post(f"/users/inventory/expiry-alerts/{alert_id}/dismiss/", {"reason": "Reviewed and kept for special dinner service"})
assert dismiss_res.status_code == status.HTTP_200_OK, f"Dismiss failed: {dismiss_res.status_code}"
alert.refresh_from_db()
assert alert.status == "dismissed", f"Expected dismissed, got {alert.status}"
print(f"Alert #{alert_id} successfully transitioned to 'dismissed'.")

# Step 3: Run evaluate 3 repeated times
for i in range(1, 4):
    res_repeat = evaluate_inventory_expiry_alerts()
    print(f"Repeat Scan #{i}: created={res_repeat['created']}, updated={res_repeat['updated']}")
    alert.refresh_from_db()
    assert alert.status == "dismissed", f"Alert was resurrected on repeat scan #{i}!"
    active_dups = InventoryExpiryAlert.objects.filter(batch=exp_batch, status="active").count()
    assert active_dups == 0, f"Unwanted active duplicate alert created for batch! Count: {active_dups}"

print("PASS: Dismissed alert remained dismissed across 3 repeated scans with ZERO active duplicate alerts!")

# -----------------------------------------------------------------------------
# 3. DEF-04: Location-Based Object Permissions
# -----------------------------------------------------------------------------
print("\n--- Check 3: DEF-04 Location-Based Object Permissions ---")
sched_a = StocktakeSchedule.objects.create(
    name="Store A Weekly Count",
    frequency="weekly",
    location=loc_a,
    category=cat,
    counting_mode="blind",
    assigned_staff=staff_a,
    created_by=staff_a,
    scheduled_time="08:00:00",
    day_of_week=0,
    next_run_at=timezone.now() + timezone.timedelta(days=1),
)

# Staff B (custodian of Store B) attempts to pause Store A's schedule
client.force_authenticate(user=staff_b)
pause_res = client.post(f"/users/stocktaking/schedules/{sched_a.id}/pause/")
print(f"Staff B attempting to pause Store A schedule: HTTP {pause_res.status_code}")
assert pause_res.status_code == status.HTTP_403_FORBIDDEN, f"Expected 403, got {pause_res.status_code}"

# Staff A (custodian and assignee of Store A) pauses Store A schedule
client.force_authenticate(user=staff_a)
pause_res_ok = client.post(f"/users/stocktaking/schedules/{sched_a.id}/pause/")
print(f"Staff A (custodian) pausing Store A schedule: HTTP {pause_res_ok.status_code}")
assert pause_res_ok.status_code == status.HTTP_200_OK, f"Expected 200, got {pause_res_ok.status_code}"

# Admin pauses Store A schedule
client.force_authenticate(user=admin_user)
act_res_admin = client.post(f"/users/stocktaking/schedules/{sched_a.id}/activate/")
print(f"Admin activating Store A schedule: HTTP {act_res_admin.status_code}")
assert act_res_admin.status_code == status.HTTP_200_OK, f"Expected 200, got {act_res_admin.status_code}"

print("PASS: Location-based object permissions enforced: unauthorized staff blocked (403), custodian and admin authorized (200)!")

# -----------------------------------------------------------------------------
# 4. DEF-05: Configurable Warning Thresholds via SystemSettings
# -----------------------------------------------------------------------------
print("\n--- Check 4: DEF-05 Configurable Warning Thresholds ---")
sys_settings = SystemSettings.get_settings()
orig_threshold = sys_settings.near_expiry_warning_days

# Create batch expiring in 25 days (normally near_expiry_30)
batch_25d = StockBatch.objects.create(
    batch_number=f"REMED-BATCH-THRESH-25D-{ts}",
    item=item,
    current_quantity=Decimal("10.00"),
    initial_quantity=Decimal("10.00"),
    unit_cost=Decimal("100.00"),
    received_date=today,
    expiry_date=today + timezone.timedelta(days=25),
    status="active",
)

# Set threshold to 14 days (should suppress alerts > 14 days)
sys_settings.near_expiry_warning_days = 14
sys_settings.save(update_fields=["near_expiry_warning_days"])
evaluate_inventory_expiry_alerts()
alert_25d = InventoryExpiryAlert.objects.filter(batch=batch_25d).first()
print(f"With near_expiry_warning_days=14: Alert for 25d batch exists? {alert_25d is not None}")
assert alert_25d is None, "Alert was generated despite being outside configurable threshold window!"

# Set threshold to 30 days
sys_settings.near_expiry_warning_days = 30
sys_settings.save(update_fields=["near_expiry_warning_days"])
evaluate_inventory_expiry_alerts()
alert_25d_active = InventoryExpiryAlert.objects.filter(batch=batch_25d).first()
print(f"With near_expiry_warning_days=30: Alert for 25d batch exists? {alert_25d_active is not None}")
assert alert_25d_active is not None, "Alert was not generated when within threshold window!"

# Restore setting
sys_settings.near_expiry_warning_days = orig_threshold
sys_settings.save(update_fields=["near_expiry_warning_days"])

print("PASS: Configurable expiry threshold window dynamically controls alert evaluation!")

print("\n======================================================================")
print("ALL REMEDIATION SPECIFIC CHECKS PASSED (4/4 - 100%)")
print("======================================================================")
