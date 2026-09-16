"""
users/models.py — Shared (PUBLIC schema) User model only.
All hotel-specific models are in hotel/models.py (TENANT_APPS).
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


from core.storage import secure_profile_pic_path
from core.validators import validate_file_signature, validate_upload_size


class User(AbstractUser):
    ADMIN = "admin"
    RECEPTION = "reception"
    WAITER = "waiter"
    CASHIER = "cashier"
    KITCHEN = "kitchen"
    BAR = "bar"
    INVENTORY = "inventory"
    DELIVERY = "delivery"
    FINANCE = "finance"
    CUSTOMER = "customer"

    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (RECEPTION, "Reception"),
        (WAITER, "Waiter"),
        (CASHIER, "Cashier"),
        (KITCHEN, "Kitchen"),
        (BAR, "Bar"),
        (INVENTORY, "Inventory"),
        (DELIVERY, "Delivery"),
        (FINANCE, "Finance"),
        (CUSTOMER, "Customer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=WAITER)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to=secure_profile_pic_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    is_verified = models.BooleanField(default=False)
    # Legacy plaintext field retained temporarily for migration compatibility; never populated.
    otp_code = models.CharField(max_length=6, blank=True, null=True, editable=False)
    otp_hash = models.CharField(max_length=128, blank=True, default="", editable=False)
    otp_expires_at = models.DateTimeField(blank=True, null=True, editable=False)
    otp_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    otp_sent_at = models.DateTimeField(blank=True, null=True, editable=False)
    otp_used_at = models.DateTimeField(blank=True, null=True, editable=False)
    mfa_hash = models.CharField(max_length=128, blank=True, default="", editable=False)
    mfa_expires_at = models.DateTimeField(blank=True, null=True, editable=False)
    mfa_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    locked_until = models.DateTimeField(blank=True, null=True, editable=False)
    token_version = models.PositiveIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=False)


    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), condition=~Q(email=""), name="unique_user_email_ci"),
        ]

    def __str__(self):
        return f"{self.username} [{self.role}]"


class AuthenticationAttempt(models.Model):
    identifier_hash = models.CharField(max_length=64)
    ip_hash = models.CharField(max_length=64)
    failure_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["identifier_hash", "ip_hash"], name="unique_auth_attempt_identity")]


class SecurityAuditEvent(models.Model):
    actor = models.ForeignKey("User", on_delete=models.PROTECT, null=True, blank=True, related_name="security_actions")
    target_user = models.ForeignKey("User", on_delete=models.PROTECT, null=True, blank=True, related_name="security_events")
    action = models.CharField(max_length=80)
    actor_role = models.CharField(max_length=20, blank=True, default="")
    request_id = models.CharField(max_length=80, blank=True, default="")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    safe_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "created_at"], name="security_action_time_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Security audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Security audit events are immutable.")
