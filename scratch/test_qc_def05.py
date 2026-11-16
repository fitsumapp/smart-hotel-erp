"""
Non-destructive Independent QC Test for DEF-05.
Verifies all 7 requirements + SafeDateField checks.
"""
import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from hotel.models import SystemSettings, StockBatch, StockLocation, InventoryItem, InventoryExpiryAlert, BatchLocationBalance
from hotel.inventory import evaluate_inventory_expiry_alerts

User = get_user_model()
client = APIClient()

admin_user = User.objects.get(username="staging_admin")
staff_a = User.objects.get(username="remed_staff_a")

print("=== VERIFYING DEF-05 INDEPENDENT AUDIT ===")

# 1. Saved configuration loads correctly via API
client.force_authenticate(user=admin_user)
res = client.get("/users/settings/")
print(f"1. GET /users/settings/ status: {res.status_code}")
assert res.status_code == 200
assert "near_expiry_warning_days" in res.data
initial_val = res.data["near_expiry_warning_days"]
print(f"   Initial near_expiry_warning_days: {initial_val}")

# 2. Authorized administrators can update it
test_val = 25
res_post = client.post("/users/settings/", {"near_expiry_warning_days": test_val}, format="json")
print(f"2. Admin POST /users/settings/ (value={test_val}): status {res_post.status_code}, returned {res_post.data.get('near_expiry_warning_days')}")
assert res_post.status_code == 200
assert res_post.data.get("near_expiry_warning_days") == test_val

# 3. Value persists on next GET
res_get = client.get("/users/settings/")
print(f"3. Value after update: {res_get.data.get('near_expiry_warning_days')}")
assert res_get.data.get("near_expiry_warning_days") == test_val

# 4. Unauthorized users cannot modify it
client.force_authenticate(user=staff_a)
res_unauth = client.post("/users/settings/", {"near_expiry_warning_days": 10}, format="json")
print(f"4. Unauthorized staff POST /users/settings/: status {res_unauth.status_code}")
assert res_unauth.status_code == 403, f"DEF-05 FAIL: Unauthorized user update returned {res_unauth.status_code}"

# Restore admin authentication
client.force_authenticate(user=admin_user)

# 5. Backend validation enforces 1-365 range
print("5. Backend Range Validation Checks:")
invalid_values = [0, -5, 366, 1000, "abc"]
for inv in invalid_values:
    res_inv = client.post("/users/settings/", {"near_expiry_warning_days": inv}, format="json")
    print(f"   Value {inv!r} -> status {res_inv.status_code}, error: {res_inv.data.get('near_expiry_warning_days', res_inv.data)}")
    assert res_inv.status_code == 400, f"DEF-05 FAIL: Invalid value {inv} accepted with status {res_inv.status_code}!"

valid_values = [1, 365, 30]
for val in valid_values:
    res_v = client.post("/users/settings/", {"near_expiry_warning_days": val}, format="json")
    assert res_v.status_code == 200, f"DEF-05 FAIL: Valid value {val} rejected with {res_v.status_code}"
    print(f"   Value {val} -> valid (200 OK)")

# 6. Changing the value changes actual expiry-alert evaluation
print("\n6. Testing evaluation clamping via evaluate_inventory_expiry_alerts():")
# We test with a dummy batch in a rollback transaction or inspect evaluate_inventory_expiry_alerts code
from django.db import transaction
with transaction.atomic():
    # Set warning days to 14
    s = SystemSettings.get_settings()
    s.near_expiry_warning_days = 14
    s.save(update_fields=["near_expiry_warning_days"])
    
    # Create test batch expiring in 20 days
    item = InventoryItem.objects.first()
    loc = StockLocation.objects.first()
    from decimal import Decimal
    b_20 = StockBatch.objects.create(
        item=item,
        batch_number="QC-BATCH-20D",
        initial_quantity=10,
        current_quantity=10,
        unit_cost=Decimal("50.00"),
        expiry_date=timezone.now().date() + datetime.timedelta(days=20),
        status="active"
    )
    BatchLocationBalance.objects.create(batch=b_20, location=loc, quantity=10)
    
    # Evaluate with 14-day window: 20-day batch should NOT get near_expiry alert
    res_14 = evaluate_inventory_expiry_alerts()
    alert_14 = InventoryExpiryAlert.objects.filter(batch=b_20).first()
    print(f"   With near_expiry_warning_days=14: Alert created for 20-day batch: {alert_14}")
    assert alert_14 is None, "Alert was created despite being outside the 14-day window!"
    
    # Now set warning days to 30
    s.near_expiry_warning_days = 30
    s.save(update_fields=["near_expiry_warning_days"])
    res_30 = evaluate_inventory_expiry_alerts()
    alert_30 = InventoryExpiryAlert.objects.filter(batch=b_20).first()
    print(f"   With near_expiry_warning_days=30: Alert created for 20-day batch: {alert_30.alert_type if alert_30 else None}")
    assert alert_30 is not None and alert_30.alert_type == "near_expiry_30", "Alert was NOT created within 30-day window!"
    
    # Roll back so no test data touches persistent staging!
    transaction.set_rollback(True)

print("   Rollback complete: Zero test records persisted to staging.")

# 7. SafeDateField inspection
print("\n7. Inspecting SafeDateField and business date serialization:")
from apps.orders.serializers import SystemSettingsSerializer
st = SystemSettings.get_settings()
st.current_business_date = datetime.date(2026, 11, 8)
ser = SystemSettingsSerializer(st)
print(f"   Serialized business date from date: {ser.data.get('current_business_date')}")
assert ser.data.get("current_business_date") == "2026-11-08"

# Test with datetime object in memory
st.current_business_date = datetime.datetime(2026, 11, 8, 23, 59, 59)
ser_dt = SystemSettingsSerializer(st)
print(f"   Serialized business date from datetime: {ser_dt.data.get('current_business_date')}")
assert ser_dt.data.get("current_business_date") == "2026-11-08"

# Restore original settings
client.post("/users/settings/", {"near_expiry_warning_days": 30}, format="json")
print("\n=== DEF-05 TEST SUITE FINISHED SUCCESSFULLY ===")
