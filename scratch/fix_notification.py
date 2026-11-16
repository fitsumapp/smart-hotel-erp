with open("hotel/inventory.py", "r", encoding="utf-8") as f:
    code = f.read()

target = '''            for alert in new_critical_alerts:
                for u in staff_users:
                    notifs.append(
                        Notification(
                            recipient=u,
                            notification_type="system",
                            title=f"Critical Expiry Alert: {alert.get_alert_type_display()}",
                            message=f"Batch #{alert.batch_number} of {alert.item.name} ({alert.current_quantity} {alert.item.unit}) at {alert.location.name if alert.location else 'Unknown Location'} requires immediate operational routing.",
                        )
                    )'''

replacement = '''            for alert in new_critical_alerts:
                msg = f"[Critical Expiry Alert] Batch #{alert.batch_number} of {alert.item.name} ({alert.current_quantity} {alert.item.unit}) at {alert.location.name if alert.location else 'Unknown Location'} requires immediate operational routing."
                for u in staff_users:
                    notifs.append(
                        Notification(
                            user_id_ref=u.id,
                            message=msg,
                        )
                    )'''

assert target in code, "Target not found in hotel/inventory.py"
code = code.replace(target, replacement, 1)

with open("hotel/inventory.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Fixed Notification instantiation in hotel/inventory.py!")

