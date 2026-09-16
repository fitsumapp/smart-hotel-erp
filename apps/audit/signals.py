"""Automatic auditing for security-sensitive business entities."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.observability import metrics
from hotel.models import (
    AuditEvent, Budget, ExpenseTransaction, InventoryItem, JournalEntry,
    PaymentAttempt, PayrollEntry, Reservation, Room, StockTransaction,
    SystemSettings,
)
from users.models import User
from .services import record_audit_event

TRACKED = (User, Room, Reservation, PaymentAttempt, SystemSettings, InventoryItem,
           StockTransaction, JournalEntry, ExpenseTransaction, Budget, PayrollEntry)
SENSITIVE_FIELDS = {
    "password", "otp_code", "otp_hash", "mfa_hash", "qr_token", "public_token",
    "chapa_checkout_url", "safe_metadata", "notes", "guest_email", "guest_phone",
    "guest_name", "employee_name", "address", "phone_number", "profile_picture",
}
SAFE_LIMIT = 30

def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        if name in SENSITIVE_FIELDS:
            continue
        value = getattr(instance, field.attname, None)
        if value is not None:
            data[name] = str(value)[:200]
        if len(data) >= SAFE_LIMIT:
            break
    return data

@receiver(pre_save)
def capture_before(sender, instance, **kwargs):
    if sender not in TRACKED or not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).first()
    instance._audit_before = _snapshot(previous) if previous else {}

@receiver(post_save)
def write_business_audit(sender, instance, created, raw=False, **kwargs):
    if raw or sender not in TRACKED or isinstance(instance, AuditEvent):
        return
    before = getattr(instance, "_audit_before", {})
    after = _snapshot(instance)
    changed = {key: value for key, value in after.items() if before.get(key) != value}
    old = {key: before.get(key) for key in changed}
    if not created and not changed:
        return
    action = f"{sender._meta.model_name}.{'created' if created else 'updated'}"
    record_audit_event(action=action, entity_type=sender._meta.label, entity_id=instance.pk, before=old, after=after if created else changed)
    if sender is PaymentAttempt:
        metrics.increment(f"payment_{instance.status}_total")
    if sender is Reservation and not created and "status" in changed:
        metrics.increment(f"reservation_{instance.status}_total")
    if sender is StockTransaction and created:
        metrics.increment("stock_transactions_total")
