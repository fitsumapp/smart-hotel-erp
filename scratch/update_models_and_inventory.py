import re

# 1. Update hotel/models.py
with open("hotel/models.py", "r", encoding="utf-8") as f:
    models_code = f.read()

if "near_expiry_warning_days = models.PositiveIntegerField" not in models_code:
    target = 'waste_approval_threshold = models.DecimalField('
    replacement = '''near_expiry_warning_days = models.PositiveIntegerField(
        default=30,
        help_text="Configurable surveillance window in days before batch expiry to trigger near-expiry warnings."
    )

    waste_approval_threshold = models.DecimalField('''
    models_code = models_code.replace(target, replacement, 1)
    with open("hotel/models.py", "w", encoding="utf-8") as f:
        f.write(models_code)
    print("Updated hotel/models.py with near_expiry_warning_days!")
else:
    print("hotel/models.py already has near_expiry_warning_days.")

# 2. Update hotel/inventory.py
with open("hotel/inventory.py", "r", encoding="utf-8") as f:
    inv_code = f.read()

# Replace evaluate_inventory_expiry_alerts function completely
func_start = inv_code.find("def evaluate_inventory_expiry_alerts():")
if func_start != -1:
    # Find decorator
    dec_start = inv_code.rfind("@transaction.atomic", 0, func_start)
    prefix = inv_code[:dec_start]
    
    new_func = '''@transaction.atomic
def evaluate_inventory_expiry_alerts():
    """
    Scans all StockBatch records and generates persistent, idempotent InventoryExpiryAlerts.
    Categorizes batches into:
      - 'expired' (expiry_date < today)
      - 'near_expiry_1' (0 <= (expiry_date - today).days <= 1)
      - 'near_expiry_7' (1 < (expiry_date - today).days <= 7)
      - 'near_expiry_14' (7 < (expiry_date - today).days <= 14)
      - 'near_expiry_30' (14 < (expiry_date - today).days <= 30)
      - 'unknown_expiry' (item.is_perishable and (expiry_date is None or is_legacy))

    Resolves alerts when batch quantity becomes 0, is wasted, or is verified.
    Supports configurable surveillance window via SystemSettings (DEF-05).
    Maintains dismissed alerts without reactivation loop (DEF-03).
    Never deletes or alters inventory stock.
    """
    from django.utils import timezone
    from decimal import Decimal
    from hotel.models import (
        StockBatch, InventoryExpiryAlert, BatchLocationBalance, Notification, SystemSettings
    )
    from django.contrib.auth import get_user_model

    today = timezone.now().date()
    created_count = 0
    updated_count = 0
    resolved_count = 0

    # Read configurable warning window from SystemSettings (DEF-05)
    try:
        sys_settings = SystemSettings.get_settings()
        max_warning_days = getattr(sys_settings, "near_expiry_warning_days", 30) or 30
    except Exception:
        max_warning_days = 30

    # 1. Resolve alerts for batches that are now zero or depleted/recalled/wasted
    unresolved_alerts = InventoryExpiryAlert.objects.filter(status__in=["active", "dismissed"]).select_related("batch", "item")
    for alert in unresolved_alerts:
        b = alert.batch
        if b.current_quantity <= Decimal("0.00") or b.status in ("depleted", "recalled"):
            alert.status = "resolved"
            alert.resolved_at = timezone.now()
            alert.resolution_reason = "batch_consumed_or_depleted"
            alert.save(update_fields=["status", "resolved_at", "resolution_reason", "updated_at"])
            resolved_count += 1
        elif alert.alert_type == "unknown_expiry" and b.expiry_date is not None and not b.is_legacy and b.status == "active":
            alert.status = "resolved"
            alert.resolved_at = timezone.now()
            alert.resolution_reason = "expiry_date_verified"
            alert.save(update_fields=["status", "resolved_at", "resolution_reason", "updated_at"])
            resolved_count += 1

    # 2. Scan active batches with positive stock
    candidate_batches = StockBatch.objects.filter(
        current_quantity__gt=Decimal("0.00")
    ).select_related("item", "supplier").prefetch_related("location_balances__location")

    new_critical_alerts = []

    for batch in candidate_batches:
        item = batch.item
        # Primary location if location balance exists
        loc = None
        first_bal = batch.location_balances.filter(quantity__gt=Decimal("0.00")).first()
        if first_bal:
            loc = first_bal.location

        # Determine which alert types apply (clamped by max_warning_days)
        target_alerts = []
        if batch.expiry_date:
            days_until_exp = (batch.expiry_date - today).days
            if days_until_exp < 0:
                target_alerts.append(("expired", 0, batch.expiry_date))
            elif days_until_exp <= 1 and max_warning_days >= 1:
                target_alerts.append(("near_expiry_1", 1, batch.expiry_date))
            elif days_until_exp <= 7 and max_warning_days >= 7:
                target_alerts.append(("near_expiry_7", 7, batch.expiry_date))
            elif days_until_exp <= 14 and max_warning_days >= 14:
                target_alerts.append(("near_expiry_14", 14, batch.expiry_date))
            elif days_until_exp <= max_warning_days:
                target_alerts.append(("near_expiry_30", min(30, max_warning_days), batch.expiry_date))
        else:
            # Perishable item with no expiry date or unverified legacy
            if item.is_perishable or batch.is_legacy or batch.status == "unverified_quarantine":
                target_alerts.append(("unknown_expiry", -1, None))

        # Reconcile alerts for this batch
        for alert_type, threshold, exp_d in target_alerts:
            # DEF-03: Inspect existing alert to prevent reactivation of staff-dismissed alerts
            existing_alert = InventoryExpiryAlert.objects.filter(
                batch=batch,
                alert_type=alert_type,
            ).order_by("-created_at").first()

            if existing_alert:
                if existing_alert.status == "dismissed":
                    # DEF-03: Staff-dismissed alert remains dismissed.
                    # Do not resurrect as active; update on-hand quantity and location if changed.
                    changed = False
                    if existing_alert.current_quantity != batch.current_quantity:
                        existing_alert.current_quantity = batch.current_quantity
                        changed = True
                    if loc and existing_alert.location_id != loc.id:
                        existing_alert.location = loc
                        changed = True
                    if changed:
                        existing_alert.save(update_fields=["current_quantity", "location", "updated_at"])
                        updated_count += 1
                elif existing_alert.status == "active":
                    # Update quantity and location if changed
                    changed = False
                    if existing_alert.current_quantity != batch.current_quantity:
                        existing_alert.current_quantity = batch.current_quantity
                        changed = True
                    if loc and existing_alert.location_id != loc.id:
                        existing_alert.location = loc
                        changed = True
                    if changed:
                        existing_alert.save(update_fields=["current_quantity", "location", "updated_at"])
                        updated_count += 1
                elif existing_alert.status == "resolved":
                    # Batch was previously resolved/depleted, but now has positive stock again
                    alert = InventoryExpiryAlert.objects.create(
                        batch=batch,
                        item=item,
                        location=loc,
                        alert_type=alert_type,
                        threshold_days=threshold,
                        batch_number=batch.batch_number,
                        expiry_date=exp_d,
                        current_quantity=batch.current_quantity,
                        status="active",
                    )
                    created_count += 1
                    if alert_type in ("expired", "near_expiry_1", "unknown_expiry"):
                        new_critical_alerts.append(alert)
            else:
                # No existing alert for this batch and alert_type -> create new active alert
                alert = InventoryExpiryAlert.objects.create(
                    batch=batch,
                    item=item,
                    location=loc,
                    alert_type=alert_type,
                    threshold_days=threshold,
                    batch_number=batch.batch_number,
                    expiry_date=exp_d,
                    current_quantity=batch.current_quantity,
                    status="active",
                )
                created_count += 1
                if alert_type in ("expired", "near_expiry_1", "unknown_expiry"):
                    new_critical_alerts.append(alert)

    # Send Notification to relevant staff for critical alerts
    if new_critical_alerts:
        User = get_user_model()
        staff_users = list(User.objects.filter(role__in=["admin", "inventory", "kitchen"], is_active=True))
        if staff_users:
            notifs = []
            for alert in new_critical_alerts:
                for u in staff_users:
                    notifs.append(
                        Notification(
                            recipient=u,
                            notification_type="system",
                            title=f"Critical Expiry Alert: {alert.get_alert_type_display()}",
                            message=f"Batch #{alert.batch_number} of {alert.item.name} ({alert.current_quantity} {alert.item.unit}) at {alert.location.name if alert.location else 'Unknown Location'} requires immediate operational routing.",
                        )
                    )
            if notifs:
                Notification.objects.bulk_create(notifs, ignore_conflicts=True)

    active_total = InventoryExpiryAlert.objects.filter(status="active").count()
    return {
        "created": created_count,
        "updated": updated_count,
        "resolved": resolved_count,
        "active_total": active_total,
    }
'''
    with open("hotel/inventory.py", "w", encoding="utf-8") as f:
        f.write(prefix + new_func + "\n")
    print("Updated hotel/inventory.py with DEF-03 and DEF-05 fixes!")

