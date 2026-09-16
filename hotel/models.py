"""
hotel/models.py
— All hotel-specific (TENANT) models.
  Each hotel gets its own PostgreSQL schema — total data isolation.
  Uses settings.AUTH_USER_MODEL for cross-schema ForeignKeys to User.
"""
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from uuid import uuid4
from django.utils import timezone
from core.storage import (
    private_storage,
    secure_private_guest_id_path,
    secure_category_image_path,
    secure_menu_item_image_path,
    secure_room_image_path,
)
from core.validators import validate_file_signature, validate_upload_size


# ── 1. Category ───────────────────────────────────────────────────────────────

class Category(models.Model):
    STATION_CHOICES = [("Kitchen", "Kitchen"), ("Bar", "Bar")]
    name = models.CharField(max_length=100)
    station = models.CharField(max_length=20, choices=STATION_CHOICES)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(
        upload_to=secure_category_image_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            # Filter by station (Kitchen vs Bar) — used on the POS menu page
            models.Index(fields=["station"], name="cat_station_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.station})"


# ── 2. Menu Item ──────────────────────────────────────────────────────────────

class MenuItem(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    image = models.ImageField(
        upload_to=secure_menu_item_image_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Used by POS to fetch all available items for a given category
            models.Index(fields=["category", "is_available"], name="mi_cat_avail_idx"),
        ]

    def __str__(self):
        return self.name


# ── 3. Room ───────────────────────────────────────────────────────────────────

class Room(models.Model):
    DEPOSIT_TYPE_CHOICES = [
        ("Fixed", "Fixed"),
        ("Percentage", "Percentage"),
    ]

    BOOKING_SOURCE_CHOICES = [
        ("front_desk", "Front Desk"),
        ("online", "Online"),
    ]

    STATUS_CHOICES = [
        ("Available", "Available"),
        ("Occupied", "Occupied"),
        ("Cleaning", "Cleaning"),
        ("Maintenance", "Maintenance"),
        ("Reserved", "Reserved"),
    ]

    name = models.CharField(max_length=100)
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=50)
    floor_number = models.IntegerField(default=1)
    description = models.TextField(blank=True, null=True)

    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    weekend_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    holiday_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percent = models.IntegerField(default=0)
    extra_bed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_adults = models.IntegerField(default=2)
    max_children = models.IntegerField(default=1)
    bed_type = models.CharField(max_length=50, default="King")
    num_beds = models.IntegerField(default=1)
    amenities = models.JSONField(default=list, blank=True)

    main_image = models.ImageField(
        upload_to=secure_room_image_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    image_2 = models.ImageField(
        upload_to=secure_room_image_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    image_3 = models.ImageField(
        upload_to=secure_room_image_path,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    video_url = models.URLField(max_length=500, blank=True, null=True)
    view_360_url = models.URLField(max_length=500, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Available")
    instant_booking = models.BooleanField(default=True)
    is_available_online = models.BooleanField(default=False)
    online_deposit_type = models.CharField(max_length=20, choices=DEPOSIT_TYPE_CHOICES, default="Fixed")
    advance_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_stay = models.IntegerField(default=1)
    tags = models.CharField(max_length=100, blank=True, null=True)
    check_in_time = models.TimeField(default="14:00")
    check_out_time = models.TimeField(default="11:00")
    cancellation_policy = models.TextField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    common_amenities = models.JSONField(default=list, blank=True)
    booking_source = models.CharField(max_length=20, choices=BOOKING_SOURCE_CHOICES, default="front_desk")

    class Meta:
        indexes = [
            # Dashboard: filter rooms by status (Available / Occupied / etc.)
            models.Index(fields=["status"], name="room_status_idx"),
            # Public booking engine: filter by is_available_online + status
            models.Index(fields=["is_available_online", "status"], name="room_online_status_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.room_number})"


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("checked_in", "Checked In"),
        ("checked_out", "Checked Out"),
        ("cancelled", "Cancelled"),
    ]
    SOURCE_CHOICES = [
        ("public", "Public Booking Engine"),
        ("reception", "Reception"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="reservations")
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone = models.CharField(max_length=50, blank=True, null=True)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    adults = models.IntegerField(default=1)
    children = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="public")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    confirmation_code = models.CharField(max_length=32, unique=True, blank=True, null=True)
    qr_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    public_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    chapa_tx_ref = models.CharField(max_length=120, blank=True, null=True, unique=True)
    chapa_checkout_url = models.URLField(max_length=500, blank=True, null=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    checked_in_at = models.DateTimeField(blank=True, null=True)
    checked_out_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Front-desk view: filter by status (confirmed, checked_in, etc.)
            models.Index(fields=["status"], name="res_status_idx"),
            # Date-range queries for availability checks and reports
            models.Index(fields=["check_in_date", "check_out_date"], name="res_dates_idx"),
            # Room-level queries: all reservations for a given room + status
            models.Index(fields=["room", "status"], name="res_room_status_idx"),
            # Revenue reports filtered by creation date
            models.Index(fields=["created_at"], name="res_created_idx"),
            # Payment tracking
            models.Index(fields=["payment_status"], name="res_pay_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(check_out_date__gt=models.F("check_in_date")), name="reservation_checkout_after_checkin"),
            models.CheckConstraint(condition=models.Q(adults__gte=1), name="reservation_adults_gte_1"),
            models.CheckConstraint(condition=models.Q(children__gte=0), name="reservation_children_gte_0"),
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="reservation_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(deposit_amount__gte=0), name="reservation_deposit_nonnegative"),
        ]

    def __str__(self):
        return f"Reservation {self.confirmation_code or self.id} - Room {self.room.room_number}"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            allowed = {
                "pending": {"confirmed", "cancelled"},
                "confirmed": {"checked_in", "cancelled"},
                "checked_in": {"checked_out"},
                "checked_out": set(),
                "cancelled": set(),
            }
            if previous and self.status != previous and self.status not in allowed.get(previous, set()):
                raise ValidationError(f"Cannot transition reservation from {previous} to {self.status}.")
        self.ensure_tokens()
        super().save(*args, **kwargs)

    def ensure_tokens(self):
        if not self.confirmation_code:
            self.confirmation_code = uuid4().hex[:10].upper()
        if not self.qr_token:
            self.qr_token = uuid4().hex
        if not self.public_token:
            self.public_token = uuid4().hex


# ── 4. Restaurant Table ───────────────────────────────────────────────────────

class RestaurantTable(models.Model):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("occupied", "Occupied"),
        ("reserved", "Reserved"),
    ]
    table_code = models.CharField(max_length=20, unique=True)
    label_name = models.CharField(max_length=50)
    capacity = models.IntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label_name} ({self.table_code})"


# ── 5. Order ──────────────────────────────────────────────────────────────────

class Order(models.Model):
    ORDER_STATUS = [
        ("pending", "Pending"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("served", "Served"),
        ("bill_requested", "Bill Requested"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]
    PAYMENT_STATUS_CHOICES = [("pending", "Pending"), ("paid", "Paid")]
    PAYMENT_METHOD_CHOICES = [("Cash", "Cash"), ("Chapa", "Chapa"), ("Telebirr", "Telebirr"), ("Card", "Card")]

    table = models.ForeignKey(RestaurantTable, on_delete=models.CASCADE, related_name="orders")

    # Cross-schema reference: User lives in public schema, Order lives in tenant schema
    # Store user IDs as integers to avoid cross-schema FK constraint issues
    waiter_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the waiter (users.User)")
    cashier_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the cashier (users.User)")
    waiter_username = models.CharField(max_length=150, blank=True)  # denormalized for display

    status = models.CharField(max_length=20, choices=ORDER_STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    service_charge_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    payment_page_token = models.CharField(max_length=64, blank=True, null=True, unique=True)
    chapa_tx_ref = models.CharField(max_length=120, blank=True, null=True, unique=True)
    chapa_checkout_url = models.URLField(max_length=500, blank=True, null=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    idempotency_fingerprint = models.CharField(max_length=64, blank=True, default="")
    service_charge_rate_snapshot = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    vat_rate_snapshot = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    financials_finalized_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [
            # KDS / waiter views: open orders per table
            models.Index(fields=["table", "status"], name="ord_table_status_idx"),
            # Cashier view: unpaid orders
            models.Index(fields=["payment_status"], name="ord_pay_status_idx"),
            # Finance reports: paid orders within a date range
            models.Index(fields=["status", "payment_status"], name="ord_status_pay_idx"),
            # Dashboard trend chart (orders by day)
            models.Index(fields=["created_at"], name="ord_created_idx"),
            # Waiter-specific order history
            models.Index(fields=["waiter_id_ref"], name="ord_waiter_idx"),
            models.Index(fields=["payment_status", "updated_at"], name="ord_pay_updated_idx"),
            models.Index(fields=["waiter_id_ref", "payment_status", "updated_at"], name="ord_wait_pay_upd_idx"),
        ]

    def __str__(self):
        return f"Order {self.id} — Table {self.table.table_code} ({self.status})"

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            allowed = {
                "pending": {"preparing", "paid", "cancelled"},
                "preparing": {"ready", "paid", "cancelled"},
                "ready": {"served", "paid", "cancelled"},
                "served": {"bill_requested", "paid"},
                "bill_requested": {"paid"},
                "paid": set(), "cancelled": set(),
            }
            if original and self.status != original.status and self.status not in allowed.get(original.status, set()):
                raise ValidationError(f"Cannot transition order from {original.status} to {self.status}.")
            protected = (
                "sub_total", "service_charge_amount", "vat_amount", "total_amount",
                "service_charge_rate_snapshot", "vat_rate_snapshot",
            )
            if original and original.financials_finalized_at and any(
                getattr(original, field) != getattr(self, field) for field in protected
            ):
                raise ValidationError("Finalized order financial snapshots are immutable.")
        super().save(*args, **kwargs)

    def ensure_payment_page_token(self):
        if not self.payment_page_token:
            self.payment_page_token = uuid4().hex
        return self.payment_page_token


# ── 6. Order Item ─────────────────────────────────────────────────────────────

class PaymentAttempt(models.Model):
    """Persistent payment identity; financial identity fields never change."""
    STATUS_CHOICES = [("created", "Created"), ("initiated", "Initiated"), ("verified", "Verified"), ("failed", "Failed")]
    PURPOSE_CHOICES = [("order", "Order"), ("reservation_deposit", "Reservation Deposit"), ("checkin", "Check-In"), ("checkout", "Checkout")]
    provider = models.CharField(max_length=30, default="chapa")
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default="order")
    order = models.ForeignKey(Order, on_delete=models.PROTECT, null=True, blank=True, related_name="payment_attempts")
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, null=True, blank=True, related_name="payment_attempts")
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="ETB")
    provider_tx_ref = models.CharField(max_length=120, unique=True)
    idempotency_key = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    provider_event_ref = models.CharField(max_length=160, null=True, blank=True, unique=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    safe_metadata = models.JSONField(default=dict, blank=True)
    accounting_entry = models.OneToOneField("JournalEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="payment_attempt")
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_status = models.CharField(max_length=30, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(order__isnull=False, reservation__isnull=True) | models.Q(order__isnull=True, reservation__isnull=False)),
                name="payment_attempt_exactly_one_target",
            ),
            models.CheckConstraint(condition=models.Q(expected_amount__gt=0), name="payment_attempt_amount_positive"),
            models.UniqueConstraint(fields=["provider", "idempotency_key"], name="unique_provider_idempotency_key"),
            models.CheckConstraint(condition=models.Q(status__in=["created", "initiated", "verified", "failed"]), name="payment_attempt_status_valid"),
            models.CheckConstraint(condition=models.Q(purpose__in=["order", "reservation_deposit", "checkin", "checkout"]), name="payment_attempt_purpose_valid"),
        ]
        indexes = [models.Index(fields=["provider", "status"], name="payattempt_provider_status_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            immutable = ("provider", "purpose", "order_id", "reservation_id", "expected_amount", "currency", "provider_tx_ref", "idempotency_key", "accounting_entry_id")
            if any(getattr(original, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Payment identity and expected-value fields are immutable.")
            transitions = {"created": {"initiated", "verified", "failed"}, "initiated": {"verified", "failed"}, "verified": set(), "failed": {"initiated"}}
            if self.status != original.status and self.status not in transitions.get(original.status, set()):
                raise ValidationError(f"Cannot transition payment attempt from {original.status} to {self.status}.")
            allowed = {"status", "provider_event_ref", "verified_at", "safe_metadata", "last_reconciled_at", "reconciliation_status", "updated_at"}
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and not set(update_fields).issubset(allowed):
                raise ValidationError("Only payment processing fields may be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment history is immutable and cannot be deleted.")


class PaymentWebhookEvent(models.Model):
    STATUS_CHOICES = [("received", "Received"), ("processed", "Processed"), ("rejected", "Rejected"), ("failed", "Failed")]
    provider = models.CharField(max_length=30, default="chapa")
    event_ref = models.CharField(max_length=160)
    tx_ref = models.CharField(max_length=120, blank=True, default="")
    payload_hash = models.CharField(max_length=64)
    signature_valid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")
    attempt = models.ForeignKey(PaymentAttempt, on_delete=models.PROTECT, null=True, blank=True, related_name="webhook_events")
    safe_summary = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_ref"], name="unique_provider_webhook_event"), models.CheckConstraint(condition=models.Q(status__in=["received", "processed", "rejected", "failed"]), name="webhook_event_status_valid")]
        indexes = [models.Index(fields=["provider", "status", "received_at"], name="webhook_provider_status_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            immutable = ("provider", "event_ref", "tx_ref", "payload_hash", "signature_valid", "received_at")
            if any(getattr(original, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Webhook receipt identity is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Webhook receipts are immutable and cannot be deleted.")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} × {self.menu_item.name}"


# ── 7. Notification ───────────────────────────────────────────────────────────

class Notification(models.Model):
    # User ID reference (cross-schema, stored as int)
    user_id_ref = models.IntegerField(help_text="ID of the recipient (users.User)")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Notification bell: unread notifications for a specific user
            models.Index(fields=["user_id_ref", "is_read"], name="notif_user_read_idx"),
        ]

    def __str__(self):
        return f"Notification→user:{self.user_id_ref}: {self.message[:60]}"


# ── 8. System Settings ────────────────────────────────────────────────────────

class SystemSettings(models.Model):
    # Hotel identity (for receipts)
    hotel_name = models.CharField(max_length=255, default="ATLAS INTERNATIONAL HOTEL PLC")
    tin_number = models.CharField(max_length=15, default="0002915740", verbose_name="TIN Number")
    address = models.TextField(default="Bole Sub-City, Woreda 03, H.No 033")
    phone_number = models.CharField(max_length=50, default="0116187432")
    logo = models.ImageField(upload_to="settings/", blank=True, null=True)
    enabled_features = models.JSONField(default=list, blank=True)

    # Tax
    vat_enabled = models.BooleanField(default=True)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    service_charge_enabled = models.BooleanField(default=True)
    service_charge_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)

    # Fiscal device
    fiscal_machine_no = models.CharField(max_length=50, default="FG10004841")
    reading_number = models.CharField(max_length=20, default="0107")
    erca_label = models.CharField(max_length=20, default="ERCA")
    currency_symbol = models.CharField(max_length=10, default="ETB")

    # POS printer
    POS_MACHINE_CHOICES = [
        ("none", "No POS Machine"),
        ("thermal", "Generic Thermal Printer (Raw)"),
        ("fiscal", "Fiscal Printer (API/Serial)"),
    ]
    pos_machine_type = models.CharField(max_length=50, choices=POS_MACHINE_CHOICES, default="thermal")
    pos_device_ip = models.GenericIPAddressField(blank=True, null=True)
    
    PRINTER_PAPER_SIZE_CHOICES = [
        ("58mm", "58mm"),
        ("80mm", "80mm"),
    ]
    printer_paper_size = models.CharField(max_length=10, choices=PRINTER_PAPER_SIZE_CHOICES, default="80mm")

    def __str__(self):
        return f"Settings — {self.hotel_name}"

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"


# ── 9. Maintenance Log ────────────────────────────────────────────────────────

class MaintenanceLog(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="maintenance_logs")
    issue_title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    reported_by = models.CharField(max_length=150, blank=True)  # denormalized, cross-schema safe
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-reported_at"]
        indexes = [
            # Filter open/in-progress maintenance tasks per room
            models.Index(fields=["room", "status"], name="maint_room_status_idx"),
        ]

    def __str__(self):
        return f"{self.issue_title} — Room {self.room.room_number} ({self.status})"


# ── 10. Room History ──────────────────────────────────────────────────────────

class RoomHistory(models.Model):
    EVENT_CHOICES = [
        ("checkin", "Check-In"),
        ("checkout", "Check-Out"),
        ("maintenance", "Maintenance"),
        ("cleaning", "Cleaning"),
    ]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="history_logs")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    guest_name = models.CharField(max_length=200, blank=True)
    check_in_date = models.DateField(blank=True, null=True)
    check_out_date = models.DateField(blank=True, null=True)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    notes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Room history report: all events for one room ordered by date
            models.Index(fields=["room", "created_at"], name="rhist_room_date_idx"),
            # Filter by event type (checkin / checkout / maintenance)
            models.Index(fields=["event_type"], name="rhist_event_idx"),
            models.Index(fields=["event_type", "created_at"], name="rhist_event_created_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} — Room {self.room.room_number} — {self.created_at.date()}"


# ── 11. Guest Profile ─────────────────────────────────────────────────────────

class GuestProfile(models.Model):
    ID_TYPE_CHOICES = [
        ("national_id", "National ID"),
        ("passport", "Passport"),
        ("driving_license", "Driving License"),
        ("other", "Other"),
    ]
    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="guest_profile", null=True, blank=True
    )
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    id_type = models.CharField(max_length=30, choices=ID_TYPE_CHOICES, default="national_id")
    id_number = models.CharField(max_length=100, blank=True)
    id_scan = models.ImageField(
        upload_to=secure_private_guest_id_path,
        storage=private_storage,
        validators=[validate_file_signature, validate_upload_size],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Guest search by name or phone at front desk
            models.Index(fields=["full_name"], name="guest_name_idx"),
            models.Index(fields=["phone"], name="guest_phone_idx"),
        ]

    def __str__(self):
        return f"{self.full_name} — {self.id_type}: {self.id_number}"


# ── 12. Folio Charge ──────────────────────────────────────────────────────────

class FolioCharge(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="folio_charges")
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    added_by = models.CharField(max_length=150, blank=True)  # denormalized, cross-schema safe
    added_at = models.DateTimeField(auto_now_add=True)
    inventory_item = models.ForeignKey('InventoryItem', on_delete=models.SET_NULL, null=True, blank=True, related_name="folio_charges")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)

    class Meta:
        ordering = ["added_at"]
        indexes = [
            # Folio: all charges for a given reservation
            models.Index(fields=["reservation"], name="folio_res_idx"),
            models.Index(fields=["added_at"], name="folio_added_idx"),
        ]

    def __str__(self):
        return f"{self.description} — ETB {self.amount} (Res #{self.reservation_id})"


# ── 13. Day Audit Log ─────────────────────────────────────────────────────────

class DayAuditLog(models.Model):
    audit_date = models.DateField(unique=True)
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.CharField(max_length=150, blank=True)  # denormalized
    total_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_chapa = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_telebirr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_card = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_room_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-audit_date"]
        indexes = [
            # Quick lookup for today's audit and closed-day checks
            models.Index(fields=["audit_date", "is_closed"], name="audit_date_closed_idx"),
        ]

    def __str__(self):
        return f"Audit {self.audit_date} — {'Closed' if self.is_closed else 'Open'}"


# ── 14. Inventory Category ───────────────────────────────────────────────────

class InventoryCategory(models.Model):
    CATEGORY_TYPES = [
        ("f_and_b", "Food & Beverage"),
        ("housekeeping", "Housekeeping & Rooms"),
    ]
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default="f_and_b")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Inventory Categories"

    def __str__(self):
        return self.name


# ── 15. Supplier ──────────────────────────────────────────────────────────────

class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tin_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Supplier TIN")
    supplied_categories = models.ManyToManyField(
        InventoryCategory,
        blank=True,
        related_name="suppliers",
        verbose_name="Supplied Ingredient Categories"
    )
    supply_items = models.TextField(
        blank=True, null=True,
        verbose_name="Specific Items Supplied",
        help_text="Comma-separated list of specific items this supplier provides"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



# ── 16. Inventory Item ────────────────────────────────────────────────────────

class InventoryItem(models.Model):
    UNIT_CHOICES = [
        ("kg", "Kilogram (kg)"),
        ("g", "Gram (g)"),
        ("l", "Liter (L)"),
        ("ml", "Milliliter (ml)"),
        ("pcs", "Pieces (pcs)"),
        ("pack", "Packs (pack)"),
        ("bottle", "Bottles (bottle)"),
    ]

    item_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(InventoryCategory, on_delete=models.CASCADE, related_name="inventory_items")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="pcs")
    
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    opening_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    min_reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Price charged to guests (e.g. minibar / room service items)"
    )
    
    last_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplied_items")
    last_stocked_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(current_stock__gte=0), name="inventory_stock_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="inventory_unit_cost_nonnegative"),
        ]

    @property
    def total_value(self):
        return self.current_stock * self.unit_cost

    def __str__(self):
        return f"{self.name} ({self.item_code}) - {self.current_stock} {self.unit}"


# ── 17. Stock Transaction ────────────────────────────────────────────────────

class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("purchase", "Purchase (Stock-In)"),
        ("issuance", "Issuance (Stock-Out)"),
        ("adjustment", "Adjustment (Audit/Damage)"),
        ("sale_deduction", "Auto-Deduct (Sales)"),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text="Invoice # or Order #")
    notes = models.TextField(blank=True, null=True)
    destination_dept = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., Housekeeping, Kitchen, Bar")
    destination_room = models.CharField(max_length=20, blank=True, null=True, help_text="e.g., Room 104")
    logged_by_username = models.CharField(max_length=150, blank=True)
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="reversed_by",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            # Inventory ledger: all transactions for one item
            models.Index(fields=["item", "transaction_type"], name="stx_item_type_idx"),
            # Finance expense reports: purchase transactions within a date range
            models.Index(fields=["transaction_type", "timestamp"], name="stx_type_ts_idx"),
            # Supplier purchase history
            models.Index(fields=["supplier"], name="stx_supplier_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="stock_transaction_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="stock_transaction_cost_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(reversal_of__isnull=True) | models.Q(transaction_type="adjustment"),
                name="stock_reversal_must_be_adjustment",
            ),
        ]

    def __str__(self):
        return f"{self.transaction_type.upper()} - {self.quantity} {self.item.unit} of {self.item.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Stock ledger entries are immutable; create a reversing adjustment.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock ledger entries are immutable; create a reversing adjustment.")


# ── 18. Recipe BOM ───────────────────────────────────────────────────────────

class RecipeBOM(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="ingredients_bom")
    ingredient = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="mapped_menu_items")
    quantity_required = models.DecimalField(max_digits=8, decimal_places=3, help_text="Quantity of ingredient required for 1 portion")

    class Meta:
        unique_together = ('menu_item', 'ingredient')


    def __str__(self):
        return f"Recipe: {self.menu_item.name} uses {self.quantity_required} of {self.ingredient.name}"



# ── 19. Chart of Accounts ──────────────────────────────────────────────────────

class Account(models.Model):
    TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("revenue", "Revenue"),
        ("expense", "Expense"),
    ]
    code = models.CharField(max_length=20, unique=True, help_text="e.g., 1000, 2000, 5000")
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    # Pre-computed balance — updated atomically by hotel.signals whenever a
    # JournalEntryItem linked to this account is saved or deleted.
    # Do NOT update this field directly; always go through journal entries.
    cached_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        editable=False,  # Hidden from admin forms — managed by signal only
        help_text="Pre-computed ledger balance. Managed automatically by signals.",
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_account_type_display()})"

    def get_balance(self) -> "Decimal":
        """Return the cached (pre-computed) balance for this account.

        Safe read-only accessor.  The value is kept current by
        ``hotel.signals.update_account_balance`` and is recalculated from
        scratch during migrations so it is always consistent.
        """
        return self.cached_balance

    # ── Kept for backwards-compat / one-off recalculation ─────────────────────
    def recompute_balance(self) -> "Decimal":
        """Recompute balance from raw ledger items and persist it.

        Call this only in management commands or data-repair scripts —
        **never** in hot paths.  Normal real-time updates are handled by
        the Django signal in hotel/signals.py.
        """
        from decimal import Decimal
        from django.db.models import Sum

        debits  = self.ledger_items.aggregate(t=Sum("amount_debit"))["t"]  or Decimal("0.00")
        credits = self.ledger_items.aggregate(t=Sum("amount_credit"))["t"] or Decimal("0.00")

        if self.account_type in ("asset", "expense"):
            self.cached_balance = debits - credits
        else:
            self.cached_balance = credits - debits

        self.save(update_fields=["cached_balance"])
        return self.cached_balance


# ── 20. Journal Entry ──────────────────────────────────────────────────────────

class JournalEntry(models.Model):
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="reversed_by",
    )
    posted_at = models.DateTimeField(default=timezone.now, editable=False)

    entry_number = models.CharField(max_length=50, unique=True, blank=True, help_text="e.g., JV-0001")
    date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "Journal Entries"
        indexes = [
            # General Ledger filtered by date range
            models.Index(fields=["date"], name="je_date_idx"),
        ]

    def __str__(self):
        return f"{self.entry_number} — {self.date} — {self.description[:40] if self.description else 'No Description'}"

    def save(self, *args, **kwargs):
        if not self.entry_number:
            import uuid
            self.entry_number = f"JV-{uuid.uuid4().hex[:8].upper()}"
        elif not kwargs.pop("allow_immutable_update", False):
            raise ValidationError("Posted journal entries are immutable; create a reversal instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted journal entries are immutable; create a reversal instead.")


# ── 21. Journal Entry Item ─────────────────────────────────────────────────────

class JournalEntryItem(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="items")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="ledger_items")
    amount_debit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        indexes = [
            # Signal & balance queries: all line items for one account
            models.Index(fields=["account"], name="jei_account_idx"),
            # All line items belonging to one journal entry header
            models.Index(fields=["entry"], name="jei_entry_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_debit__gte=0), name="journal_item_debit_nonnegative"),
            models.CheckConstraint(condition=models.Q(amount_credit__gte=0), name="journal_item_credit_nonnegative"),
            models.CheckConstraint(
                condition=(models.Q(amount_debit__gt=0) | models.Q(amount_credit__gt=0)),
                name="journal_item_has_amount",
            ),
        ]

    def __str__(self):
        return f"{self.entry.entry_number} - {self.account.name}: Dr {self.amount_debit} / Cr {self.amount_credit}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Posted journal lines are immutable; create a reversal instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted journal lines are immutable; create a reversal instead.")


# ── 22. Expense Transaction ─────────────────────────────────────────────────────

class ExpenseTransaction(models.Model):
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="expenses_logged", limit_choices_to={"account_type": "expense"})
    payment_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="expenses_paid", limit_choices_to={"account_type__in": ["asset", "liability"]})

    
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Receipt / Invoice No.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            # Expense reports filtered by date range
            models.Index(fields=["date"], name="exp_date_idx"),
            # Expenses per account (P&L statement)
            models.Index(fields=["expense_account"], name="exp_account_idx"),
            # Expenses per supplier
            models.Index(fields=["supplier"], name="exp_supplier_idx"),
        ]

    def __str__(self):
        return f"Expense: {self.description} — {self.amount} ({self.date})"


# ── 23. Budget ─────────────────────────────────────────────────────────────────

class Budget(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="budgets")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    year = models.IntegerField()
    month = models.IntegerField(help_text="1 to 12")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("account", "year", "month"),)
        ordering = ["-year", "-month", "account__code"]
        indexes = [
            # Budget vs actual reports for a given year/month
            models.Index(fields=["year", "month"], name="budget_ym_idx"),
        ]

    def __str__(self):
        return f"Budget: {self.account.name} — M{self.month}/{self.year} — {self.amount}"


# ── 24. Payroll Entry ─────────────────────────────────────────────────────────

class PayrollEntry(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    DEPARTMENT_CHOICES = [
        ('reception', 'Reception / Front Office'),
        ('kitchen', 'Kitchen'),
        ('bar', 'Bar'),
        ('housekeeping', 'Housekeeping'),
        ('maintenance', 'Maintenance'),
        ('accounts', 'Accounts & Finance'),
        ('management', 'Management'),
        ('security', 'Security'),
        ('waiter', 'Waiter / Service Staff'),
        ('other', 'Other'),
    ]

    employee_name = models.CharField(max_length=200)
    employee_id   = models.CharField(max_length=50, blank=True, null=True)
    department    = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, default='other')
    position      = models.CharField(max_length=100, blank=True)

    pay_period_start = models.DateField()
    pay_period_end   = models.DateField()
    payment_date     = models.DateField(blank=True, null=True)

    # Earnings
    basic_salary  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_pay  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances    = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Deductions
    income_tax       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_employee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Computed (auto-filled on save)
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay   = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes  = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pay_period_end", "employee_name"]
        verbose_name_plural = "Payroll Entries"
        indexes = [
            # Payroll report: entries for a given pay period
            models.Index(fields=["pay_period_start", "pay_period_end"], name="pay_period_idx"),
            # Filter by department or status
            models.Index(fields=["department"], name="pay_dept_idx"),
            models.Index(fields=["status"], name="pay_status_idx"),
        ]

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.gross_pay = (
            Decimal(str(self.basic_salary)) +
            Decimal(str(self.overtime_pay)) +
            Decimal(str(self.bonus)) +
            Decimal(str(self.allowances))
        )
        total_deductions = (
            Decimal(str(self.income_tax)) +
            Decimal(str(self.pension_employee)) +
            Decimal(str(self.other_deductions))
        )
        self.net_pay = self.gross_pay - total_deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payroll: {self.employee_name} — {self.pay_period_start} → {self.pay_period_end}"



class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are immutable.")
    def delete(self):
        raise ValidationError("Audit events are immutable.")


class AuditEvent(models.Model):
    """Append-only, secret-safe business audit record."""
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="business_audit_events")
    actor_role = models.CharField(max_length=20, blank=True, default="")
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    before_summary = models.JSONField(default=dict, blank=True)
    after_summary = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=80, blank=True, default="")
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    client_metadata = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["request_id", "created_at"], name="audit_request_time_idx"),
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
            models.Index(fields=["action", "created_at"], name="audit_action_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable.")
