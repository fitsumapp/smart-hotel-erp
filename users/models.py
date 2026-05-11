"""
users/models.py — Shared (PUBLIC schema) User model only.
All hotel-specific models are in hotel/models.py (TENANT_APPS).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
import random


class User(AbstractUser):
    ADMIN = "admin"
    RECEPTION = "reception"
    WAITER = "waiter"
    CASHIER = "cashier"
    KITCHEN = "kitchen"
    BAR = "bar"
    INVENTORY = "inventory"
    DELIVERY = "delivery"
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
        (CUSTOMER, "Customer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=WAITER)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile_pics/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    is_active = models.BooleanField(default=False)

    # ── Multi-Tenant SaaS fields ──────────────────────────────────────────────
    # True for Platform Super-Admins who can access all hotel schemas
    is_platform_admin = models.BooleanField(
        default=False,
        help_text="Platform super-admin — bypasses all tenant/feature checks.",
    )
    # The PostgreSQL schema name this user belongs to (e.g. 'hotel_atlas').
    # Empty string means a platform-level user (no specific hotel).
    tenant_schema = models.CharField(
        max_length=63,
        blank=True,
        default="",
        help_text="Schema name of the hotel this user belongs to.",
    )

    def __str__(self):
        return f"{self.username} [{self.role}]"

    def generate_otp(self):
        self.otp_code = str(random.randint(100000, 999999))
        self.save()
