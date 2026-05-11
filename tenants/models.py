"""
tenants/models.py
— Public schema models: Hotel (Tenant), Domain, Package
  These live in the shared/public PostgreSQL schema.
  Only the Platform Super-Admin interacts with these.
"""
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


# ── Available Packages / Modules ──────────────────────────────────────────
PACKAGE_CHOICES = [
    ("dashboard",       "Dashboard & Overview"),
    ("orders",          "Order Management"),
    ("payments",        "Payment Handling"),
    ("food_beverage",   "Food and Beverage (Menus, Categories, Tables)"),
    ("rooms",           "Room Management (Rooms, Bookings, Check-ins)"),
    ("analytics",       "Analytics & Reporting"),
    ("users",           "User Management"),
    ("settings",        "System Settings"),
]

ALL_PACKAGE_CODES = [code for code, _ in PACKAGE_CHOICES]


class Package(models.Model):
    """A licensable feature/module that can be toggled per hotel."""
    name = models.CharField(max_length=100)
    code = models.SlugField(unique=True, choices=PACKAGE_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this package is available for sale on the platform.",
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "Package / Module"
        verbose_name_plural = "Packages / Modules"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Hotel(TenantMixin):
    """
    Represents one hotel customer (tenant).
    Each hotel gets its own PostgreSQL schema for full data isolation.

    schema_name  → e.g. 'hotel_atlas'   (auto-managed by TenantMixin)
    Domain model → e.g. 'atlas.myerp.com' → maps to this Hotel
    """
    name = models.CharField(max_length=200, verbose_name="Hotel Name")
    enabled_features = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of active package codes for this hotel. "
            "Example: [\"pos\", \"inventory\", \"kitchen_display\"]"
        ),
    )
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to="hotel_logos/", blank=True, null=True)

    # Billing / subscription
    is_active = models.BooleanField(default=True, help_text="Suspend a hotel without deleting data.")
    subscription_plan = models.CharField(max_length=50, default="starter")
    created_at = models.DateTimeField(auto_now_add=True)

    # TenantMixin requires this
    auto_create_schema = True

    class Meta:
        verbose_name = "Hotel (Tenant)"
        verbose_name_plural = "Hotels (Tenants)"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.schema_name}]"

    def has_feature(self, code: str) -> bool:
        """Check if a specific package/module is enabled for this hotel."""
        return code in (self.enabled_features or [])

    def enable_feature(self, code: str):
        features = list(self.enabled_features or [])
        if code not in features:
            features.append(code)
            self.enabled_features = features
            self.save(update_fields=["enabled_features"])

    def disable_feature(self, code: str):
        features = list(self.enabled_features or [])
        if code in features:
            features.remove(code)
            self.enabled_features = features
            self.save(update_fields=["enabled_features"])


class Domain(DomainMixin):
    """
    Maps a subdomain (e.g. atlas.myerp.com) to a Hotel tenant.
    Multiple domains can point to the same hotel (e.g. www.atlas.com).
    """
    class Meta:
        verbose_name = "Domain"
        verbose_name_plural = "Domains"
