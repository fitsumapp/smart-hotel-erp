"""
hotel/models.py
— All hotel-specific (TENANT) models.
  Each hotel gets its own PostgreSQL schema — total data isolation.
  Uses settings.AUTH_USER_MODEL for cross-schema ForeignKeys to User.
"""
from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
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
        ("Dirty", "Dirty"),
        ("Inspected", "Inspected"),
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
        ("no_show", "No-Show"),
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
    no_show_at = models.DateTimeField(blank=True, null=True)
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
                "confirmed": {"checked_in", "cancelled", "no_show"},
                "checked_in": {"checked_out"},
                "checked_out": set(),
                "cancelled": set(),
                "no_show": set(),
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


# ── 4b. Dining Session ────────────────────────────────────────────────────────

class DiningSession(models.Model):
    SESSION_STATUS = [
        ("active", "Active"),
        ("closed", "Closed"),
    ]
    table = models.ForeignKey(RestaurantTable, on_delete=models.CASCADE, related_name="dining_sessions")
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default="active")
    opened_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the waiter who opened the session")
    opened_by_username = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the cashier who closed the session")

    class Meta:
        indexes = [
            models.Index(fields=["table", "status"], name="session_tbl_status_idx"),
            models.Index(fields=["status", "created_at"], name="session_stat_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["table"],
                condition=models.Q(status="active"),
                name="unique_active_session_per_table",
            )
        ]

    def __str__(self):
        return f"Session #{self.id} — Table {self.table.table_code} ({self.status})"


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
    session = models.ForeignKey(
        DiningSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Dining session this order round belongs to.",
    )

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
    bill_prepared_at = models.DateTimeField(null=True, blank=True)
    bill_prepared_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the cashier who prepared/issued the bill")

    # Order Lifecycle Timestamps (milestones aggregated from OrderItems)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    preparation_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ready_at = models.DateTimeField(null=True, blank=True, db_index=True)
    served_at = models.DateTimeField(null=True, blank=True, db_index=True)
    served_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the waiter who confirmed full customer delivery")

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
            models.Index(fields=["session"], name="ord_session_idx"),
            models.Index(fields=["status", "received_at", "served_at"], name="ord_timing_perf_idx"),
        ]

    def __str__(self):
        return f"Order {self.id} — Table {self.table.table_code} ({self.status})"

    def is_partially_served(self):
        items = list(self.items.all())
        if not items:
            return False
        non_cancelled = [it for it in items if it.status != "cancelled"]
        if not non_cancelled:
            return False
        served_count = sum(1 for it in non_cancelled if it.status == "served")
        return 0 < served_count < len(non_cancelled)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            allowed = {
                "pending": {"preparing", "ready", "served", "paid", "cancelled"},
                "preparing": {"ready", "served", "paid", "cancelled"},
                "ready": {"preparing", "served", "paid", "cancelled"},
                "served": {"preparing", "bill_requested", "paid", "cancelled"},
                "bill_requested": {"paid", "cancelled"},
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


# ── 5b. Cash Handover ─────────────────────────────────────────────────────────

class CashHandover(models.Model):
    """
    Auditable cash handover record tracking money collected by a waiter from a guest
    and physically received/verified by a cashier prior to settlement.
    """
    STATUS_CHOICES = [
        ("pending", "Pending Handover"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="cash_handovers")
    session = models.ForeignKey(DiningSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_handovers")
    waiter_id_ref = models.IntegerField(help_text="ID of the waiter who collected cash")
    waiter_username = models.CharField(max_length=150, blank=True)
    cashier_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of the cashier who verified and received cash")
    cashier_username = models.CharField(max_length=150, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "status"], name="handover_ord_stat_idx"),
            models.Index(fields=["status", "created_at"], name="handover_stat_time_idx"),
            models.Index(fields=["waiter_id_ref", "status"], name="handover_waiter_stat_idx"),
        ]

    def __str__(self):
        return f"CashHandover #{self.id} — Order #{self.order_id} ({self.status}) ETB {self.amount}"


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
    ITEM_STATUS = [
        ("pending", "Pending"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("served", "Served"),
        ("cancelled", "Cancelled"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ITEM_STATUS, default="pending")
    notes = models.CharField(max_length=255, blank=True, default="")

    # Item Lifecycle Timestamps (server-generated, timezone-aware, immutable once set)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    preparation_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ready_at = models.DateTimeField(null=True, blank=True, db_index=True)
    served_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Staff Attribution (cross-schema user integer references)
    prepared_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of kitchen staff who began cooking")
    ready_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of staff who marked item ready")
    served_by_id_ref = models.IntegerField(null=True, blank=True, help_text="ID of waiter who confirmed customer delivery")

    class Meta:
        indexes = [
            models.Index(fields=["status", "ready_at"], name="orditem_stat_ready_idx"),
            models.Index(fields=["order", "status"], name="orditem_order_stat_idx"),
        ]

    def get_station(self):
        if self.menu_item:
            if self.menu_item.category:
                st = (self.menu_item.category.station or "").strip()
                if st:
                    return st
                cat_name = (self.menu_item.category.name or "").lower()
                if any(k in cat_name for k in ["drink", "beverage", "juice", "beer", "wine", "bar", "cocktail", "soda", "coffee", "tea", "መጠጥ", "ቢራ", "ጭማቂ", "አረቄ"]):
                    return "Bar"
            item_name = (self.menu_item.name or "").lower()
            if any(k in item_name for k in ["drink", "beverage", "juice", "beer", "wine", "bar", "cocktail", "soda", "coffee", "tea", "መጠጥ", "ቢራ", "ጭማቂ", "አረቄ"]):
                return "Bar"
        return "Kitchen"

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
    # Active System Modules (Super Admin Module Control)
    module_rooms = models.BooleanField(default=True, verbose_name="Enable Rooms & Reservations")
    module_pos = models.BooleanField(default=True, verbose_name="Enable Restaurant POS & Kitchen/Bar")
    module_inventory = models.BooleanField(default=True, verbose_name="Enable Inventory & Stock Control")
    module_finance = models.BooleanField(default=True, verbose_name="Enable Finance & Accounting")

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

    # Inventory Waste Controls
    near_expiry_warning_days = models.PositiveIntegerField(
        default=30,
        help_text="Configurable surveillance window in days before batch expiry to trigger near-expiry warnings."
    )

    waste_approval_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1000.00"),
        help_text="Loss threshold in ETB above which inventory waste requires manager approval."
    )

    # KDS & BDS Performance Targets
    kds_prep_target_minutes = models.PositiveIntegerField(
        default=15, help_text="Target food preparation time in minutes for Kitchen items."
    )
    kds_delay_warning_minutes = models.PositiveIntegerField(
        default=20, help_text="Threshold in minutes to flag a kitchen ticket as delayed."
    )
    bar_fulfillment_target_minutes = models.PositiveIntegerField(
        default=5, help_text="Target fulfillment time in minutes for Bar items."
    )
    bar_delay_warning_minutes = models.PositiveIntegerField(
        default=10, help_text="Threshold in minutes to flag a bar ticket as delayed."
    )

    # Operational Business Date (PMS Night Audit Engine)
    current_business_date = models.DateField(
        default=timezone.now,
        help_text="Active PMS business date for operations. Advanced by Night Audit.",
    )

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj

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
    units_per_pack = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.00,
        help_text="Units per pack/crate (e.g. 24 bottles per pack)"
    )
    is_perishable = models.BooleanField(
        default=False, help_text="True if item expires (dairy, meat, produce, etc.)"
    )
    shelf_life_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Typical shelf life in days if perishable"
    )
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


# ── 16b. Stock Location ─────────────────────────────────────────────────────

class StockLocation(models.Model):
    LOCATION_TYPES = [
        ("warehouse", "Central Warehouse / Main Store"),
        ("kitchen", "Kitchen Production Pantry"),
        ("bar", "Bar Station"),
        ("housekeeping", "Housekeeping Storage"),
        ("minibar", "Minibar Pantry"),
        ("scrap", "Waste / Scrap Area"),
        ("other", "Other Sub-Store"),
    ]
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="e.g. STORE-MAIN, KITCHEN-MAIN")
    name = models.CharField(max_length=150)
    location_type = models.CharField(max_length=30, choices=LOCATION_TYPES, default="warehouse")
    is_active = models.BooleanField(default=True)
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="managed_stock_locations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Stock Location"
        verbose_name_plural = "Stock Locations"

    def __str__(self):
        return f"{self.name} ({self.code})"


# ── 16c. Stock Batch / Lot ──────────────────────────────────────────────────

class StockBatch(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("depleted", "Depleted"),
        ("quarantined_expired", "Quarantined (Expired)"),
        ("unverified_quarantine", "Unverified Quarantine (Legacy Perishable)"),
        ("recalled", "Recalled / Safety Hold"),
    ]
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=100, db_index=True)
    supplier_batch_number = models.CharField(max_length=100, blank=True, null=True, help_text="Vendor lot/batch reference")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="batches")
    initial_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    current_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    received_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)

    # Legacy & Verification Tracking
    is_legacy = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="active", db_index=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="verified_batches"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date", "received_date", "id"]
        indexes = [
            models.Index(fields=["item", "status"], name="batch_item_status_idx"),
            models.Index(fields=["item", "expiry_date"], name="batch_item_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(current_quantity__gte=0), name="batch_stock_nonnegative"),
            models.CheckConstraint(condition=models.Q(current_quantity__lte=models.F("initial_quantity")), name="batch_stock_le_initial"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="batch_cost_nonnegative"),
            models.UniqueConstraint(fields=["item", "batch_number"], name="uniq_item_batch_number"),
        ]

    def __str__(self):
        return f"Batch {self.batch_number} - {self.item.name} ({self.current_quantity} {self.item.unit})"


# ── 16d. Batch Location Balance ─────────────────────────────────────────────

class BatchLocationBalance(models.Model):
    batch = models.ForeignKey(StockBatch, on_delete=models.CASCADE, related_name="location_balances")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="batch_balances")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = [("batch", "location")]
        indexes = [
            models.Index(fields=["location", "batch"], name="blb_loc_batch_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="blb_quantity_nonnegative"),
        ]

    def __str__(self):
        return f"{self.location.code} - {self.batch.batch_number}: {self.quantity}"


# ── 16e. Item Location Balance ──────────────────────────────────────────────

class ItemLocationBalance(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="location_balances")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="item_balances")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = [("item", "location")]
        indexes = [
            models.Index(fields=["location", "item"], name="ilb_loc_item_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ilb_quantity_nonnegative"),
        ]

    def __str__(self):
        return f"{self.location.code} - {self.item.name}: {self.quantity} {self.item.unit}"


# ── 17. Stock Transaction ────────────────────────────────────────────────────

class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("purchase", "Purchase (Stock-In)"),
        ("issuance", "Issuance (Stock-Out)"),
        ("adjustment", "Adjustment (Audit/Damage)"),
        ("sale_deduction", "Auto-Deduct (Sales)"),
        ("loss", "Waste & Loss (Stock-Out)"),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    ADJUSTMENT_DIRECTIONS = [
        ("increase", "Increase"),
        ("decrease", "Decrease"),
    ]
    adjustment_direction = models.CharField(
        max_length=10, choices=ADJUSTMENT_DIRECTIONS, null=True, blank=True,
        help_text="Required for adjustments: 'increase' adds stock, 'decrease' deducts stock."
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True, db_index=True)
    payload_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_transactions", help_text="Physical store/location"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_transactions", help_text="Primary stock batch if single-batch"
    )
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


# ── 17b. Stock Batch Consumption ────────────────────────────────────────────

class StockBatchConsumption(models.Model):
    transaction = models.ForeignKey(StockTransaction, on_delete=models.CASCADE, related_name="batch_consumptions")
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, related_name="consumptions")
    quantity_consumed = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction", "batch"], name="sbc_tx_batch_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_consumed__gt=0), name="sbc_qty_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="sbc_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(total_cost__gte=0), name="sbc_total_nonnegative"),
        ]

    def __str__(self):
        return f"TX #{self.transaction_id} consumed {self.quantity_consumed} from Batch #{self.batch_id}"


# ── 17.5 Inventory Expiry & Batch Alerts ─────────────────────────────────────────

class InventoryExpiryAlert(models.Model):
    ALERT_TYPES = [
        ("expired", "Expired Stock"),
        ("near_expiry_1", "Expiring Within 1 Day"),
        ("near_expiry_7", "Expiring Within 7 Days"),
        ("near_expiry_14", "Expiring Within 14 Days"),
        ("near_expiry_30", "Expiring Within 30 Days"),
        ("unknown_expiry", "Perishable Stock - Unknown Expiry"),
    ]
    STATUS_CHOICES = [
        ("active", "Active Alert"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed by Staff"),
    ]

    batch = models.ForeignKey(
        StockBatch, on_delete=models.CASCADE, related_name="expiry_alerts"
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="expiry_alerts"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="expiry_alerts"
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES, db_index=True)
    threshold_days = models.IntegerField(default=0, help_text="Threshold in days (0=expired, -1=unknown)")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "alert_type"], name="exp_alert_status_type_idx"),
            models.Index(fields=["batch", "alert_type", "status"], name="exp_alert_batch_type_idx"),
        ]

    def __str__(self):
        return f"[{self.status.upper()}] {self.get_alert_type_display()} - Batch {self.batch_number} ({self.item.name})"



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


# ── 21b. Inventory Waste Record ───────────────────────────────────────────────

class InventoryWasteRecord(models.Model):
    WASTE_CATEGORIES = [
        ("food_spoilage_or_expiry", "Food Spoilage or Expiry"),
        ("unissued_prep_loss", "Preparation / Trimming Loss (Unissued Stock)"),
        ("breakage_or_damage", "Breakage or Accidental Damage"),
        ("spillage", "Spillage"),
        ("other", "Other Confirmed Loss"),
    ]

    WASTE_SOURCES = [
        ("direct_loss", "Direct Stock Loss (Deducts Store Stock)"),
        ("kitchen_prep_waste", "Kitchen Preparation Waste (Already Issued Stock)"),
    ]

    idempotency_key = models.CharField(max_length=120, unique=True, db_index=True)
    payload_hash = models.CharField(max_length=64)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="waste_records")
    entered_quantity = models.DecimalField(max_digits=10, decimal_places=3)
    entered_unit = models.CharField(max_length=20, choices=InventoryItem.UNIT_CHOICES)
    base_quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Normalized to InventoryItem.unit")

    waste_category = models.CharField(max_length=40, choices=WASTE_CATEGORIES)
    waste_source = models.CharField(max_length=30, choices=WASTE_SOURCES)

    unit_cost_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost_loss = models.DecimalField(max_digits=12, decimal_places=2)

    stock_deducted = models.BooleanField(default=False)
    stock_transaction = models.OneToOneField(
        StockTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="waste_record"
    )
    source_dispatch = models.ForeignKey(
        StockTransaction, on_delete=models.PROTECT, null=True, blank=True, related_name="child_prep_wastes",
        help_text="Reference to the parent kitchen issuance for kitchen_prep_waste"
    )
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="waste_records"
    )

    notes = models.TextField(blank=True, default="")
    storage_area = models.CharField(max_length=100, blank=True, default="")
    reported_by_username = models.CharField(max_length=150, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    is_reversed = models.BooleanField(default=False)
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversed_by"
    )
    reversal_reason = models.TextField(blank=True, default="")
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by_username = models.CharField(max_length=150, blank=True)

    # Workflow & Approval Controls
    STATUS_CHOICES = [
        ("approved", "Approved"),
        ("pending_review", "Pending Review"),
        ("rejected", "Rejected"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_review", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_waste_records"
    )
    reviewed_by_username = models.CharField(max_length=150, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    is_self_reviewed = models.BooleanField(default=False, help_text="True if superuser exercised self-review exception")
    self_review_justification = models.TextField(blank=True, default="", help_text="Justification provided when superuser self-reviews")

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["waste_category", "recorded_at"], name="waste_cat_time_idx"),
            models.Index(fields=["source_dispatch"], name="waste_dispatch_idx"),
            models.Index(fields=["item", "waste_source"], name="waste_item_src_idx"),
            models.Index(fields=["status", "recorded_at"], name="waste_status_time_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(entered_quantity__gt=0), name="waste_entered_qty_positive"),
            models.CheckConstraint(condition=models.Q(base_quantity__gt=0), name="waste_base_qty_positive"),
            models.CheckConstraint(condition=models.Q(total_cost_loss__gte=0), name="waste_cost_nonnegative"),
        ]

    def __str__(self):
        return f"WASTE #{self.id} — {self.base_quantity} {self.item.unit} of {self.item.name} ({self.waste_category})"


# ── 21b. Stock Transfer Management ─────────────────────────────────────────

class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("in_transit", "In Transit (Dispatched)"),
        ("completed", "Completed (Received)"),
        ("partially_received", "Partially Received (Breakage/Shortage Recorded)"),
        ("rejected", "Rejected at Destination"),
        ("cancelled", "Cancelled"),
    ]
    transfer_number = models.CharField(max_length=64, unique=True, db_index=True)
    source_location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="transfers_dispatched"
    )
    destination_location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="transfers_received"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_transfers_requested"
    )
    requested_at = models.DateTimeField(default=timezone.now)

    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_transfers_dispatched"
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_transfers_received"
    )
    received_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_location", "status"], name="st_src_status_idx"),
            models.Index(fields=["destination_location", "status"], name="st_dest_status_idx"),
            models.Index(fields=["transfer_number"], name="st_num_idx"),
        ]

    def __str__(self):
        return f"{self.transfer_number} ({self.source_location.code} -> {self.destination_location.code}): {self.status}"


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="transfer_items")
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, null=True, blank=True, related_name="transfer_items")

    quantity_requested = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_dispatched = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    quantity_damaged = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    waste_record = models.ForeignKey(
        InventoryWasteRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="transfer_items"
    )
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["transfer", "item"], name="sti_trf_item_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_requested__gt=0), name="sti_qty_req_positive"),
            models.CheckConstraint(condition=models.Q(quantity_dispatched__gte=0), name="sti_qty_disp_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_received__gte=0), name="sti_qty_recv_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_damaged__gte=0), name="sti_qty_dam_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="sti_cost_nonnegative"),
        ]

    def __str__(self):
        return f"{self.transfer.transfer_number} - {self.item.name} (Req: {self.quantity_requested}, Disp: {self.quantity_dispatched}, Recv: {self.quantity_received})"


# ── 21d. Configurable Procurement & 3-Way Match GRNI ──────────────────────────────

class ProcurementApprovalPolicy(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    currency = models.CharField(max_length=10, default="ETB")
    price_tolerance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="Acceptable unit price variance percentage for 3-way matching",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class ProcurementApprovalTier(models.Model):
    policy = models.ForeignKey(ProcurementApprovalPolicy, on_delete=models.CASCADE, related_name="tiers")
    tier_level = models.PositiveIntegerField(help_text="Ascending hierarchy level (1, 2, 3...)")
    name = models.CharField(max_length=100)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Null represents an unlimited upper ceiling")
    required_role = models.CharField(max_length=50, help_text="User role required to approve at this tier (e.g. inventory, kitchen, finance, admin)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tier_level"]
        constraints = [
            models.UniqueConstraint(fields=["policy", "tier_level"], name="unique_tier_per_policy"),
            models.CheckConstraint(condition=models.Q(min_amount__gte=0), name="tier_min_amount_nonnegative"),
        ]

    def __str__(self):
        ceiling = f"{self.max_amount} {self.policy.currency}" if self.max_amount is not None else "Unlimited"
        return f"{self.name} (Lvl {self.tier_level}): {self.min_amount} - {ceiling} [{self.required_role}]"


class PurchaseRequisition(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("converted_to_po", "Converted to Purchase Order"),
        ("cancelled", "Cancelled"),
    ]

    requisition_number = models.CharField(max_length=50, unique=True, db_index=True)
    department = models.CharField(max_length=50, default="general")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_requisitions")
    requested_at = models.DateTimeField(default=timezone.now)
    approval_tier = models.ForeignKey(ProcurementApprovalTier, on_delete=models.SET_NULL, null=True, blank=True, related_name="requisitions")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_requisitions")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    total_estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="pr_status_idx"),
            models.Index(fields=["department"], name="pr_dept_idx"),
        ]

    def __str__(self):
        return f"{self.requisition_number} ({self.department}) - {self.status} [{self.total_estimated_amount}]"


class PurchaseRequisitionItem(models.Model):
    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="requisition_items")
    quantity_requested = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_requested__gt=0), name="pri_qty_req_positive"),
            models.CheckConstraint(condition=models.Q(estimated_unit_cost__gte=0), name="pri_cost_nonnegative"),
        ]

    def __str__(self):
        return f"{self.requisition.requisition_number} - {self.item.name} ({self.quantity_requested} {self.item.unit})"


# ── 21.3 Request for Quotation (RFQ) ─────────────────────────────────────────

class RequestForQuotation(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published / Open for Bids"),
        ("closed", "Closed / Bidding Concluded"),
        ("awarded", "Awarded / Quotations Selected"),
        ("cancelled", "Cancelled"),
    ]

    rfq_number = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    requisitions = models.ManyToManyField(
        PurchaseRequisition,
        related_name="rfqs",
        blank=True,
        help_text="Approved purchase requisitions aggregated into this RFQ",
    )
    is_public_bidding = models.BooleanField(
        default=False,
        help_text="If False, only explicitly invited suppliers may submit quotes",
    )
    invited_suppliers = models.ManyToManyField(
        Supplier,
        related_name="invited_rfqs",
        blank=True,
        help_text="Vendors authorized to participate in competitive bidding",
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    submission_deadline = models.DateTimeField(
        db_index=True, help_text="Deadline after which no bids are accepted"
    )
    delivery_location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="rfqs",
        help_text="Destination storage location (e.g. STORE-MAIN)",
    )
    terms_and_conditions = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_rfqs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="rfq_status_idx"),
            models.Index(fields=["submission_deadline"], name="rfq_deadline_idx"),
        ]

    def __str__(self):
        return f"{self.rfq_number} - {self.title} ({self.status})"


class RequestForQuotationItem(models.Model):
    rfq = models.ForeignKey(
        RequestForQuotation, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="rfq_items"
    )
    requisition_item = models.ForeignKey(
        PurchaseRequisitionItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfq_lines",
        help_text="Specific department requisition item being fulfilled",
    )
    target_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    specifications = models.TextField(
        blank=True,
        default="",
        help_text="Detailed grade, packaging, or brand specifications",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rfq", "item"], name="uniq_rfq_line_item"
            ),
            models.CheckConstraint(
                condition=models.Q(target_quantity__gt=0),
                name="rfqi_qty_positive",
            ),
        ]

    def clean(self):
        if self.requisition_item:
            if self.requisition_item.requisition.status != "approved":
                raise ValidationError(
                    f"Requisition {self.requisition_item.requisition.requisition_number} "
                    f"must be in 'approved' status (current: {self.requisition_item.requisition.status})."
                )
            if self.item_id and self.requisition_item.item_id != self.item_id:
                raise ValidationError(
                    f"RFQ item '{self.item}' does not match requisition line item '{self.requisition_item.item}'."
                )

    def __str__(self):
        return f"{self.rfq.rfq_number} - {self.item.name} ({self.target_quantity} {self.item.unit})"


# ── 21.4 Supplier Quotation & Quotation Items ─────────────────────────────────

class SupplierQuotation(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted / Received"),
        ("under_evaluation", "Under Evaluation"),
        ("accepted", "Accepted / Awarded"),
        ("partially_awarded", "Partially Awarded"),
        ("converted_to_po", "Converted to Purchase Order"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    quotation_number = models.CharField(
        max_length=50, unique=True, db_index=True, help_text="e.g. SQ-20261103-XXXX"
    )
    supplier_reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Vendor proforma/quote reference number",
    )
    rfq = models.ForeignKey(
        RequestForQuotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotations",
        help_text="Linked competitive RFQ (if sourced via tender)",
    )
    requisition = models.ForeignKey(
        PurchaseRequisition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_quotations",
        help_text="Linked requisition (if direct sole-source)",
    )
    sole_source_justification = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory justification when RFQ is bypassed",
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="quotations"
    )

    # Contractual Terms
    quotation_date = models.DateField(default=timezone.now)
    valid_until = models.DateField(
        db_index=True, help_text="Hard deadline; bids cannot be accepted after"
    )
    delivery_lead_time_days = models.PositiveIntegerField(
        default=1, help_text="Guaranteed delivery lead time in days"
    )
    payment_terms = models.CharField(
        max_length=100,
        default="Net 30",
        help_text="e.g. Net 30, Cash on Delivery, 50% Advance",
    )
    warranty_terms = models.CharField(max_length=200, blank=True, default="")

    # Currency & Landed Cost
    currency = models.CharField(max_length=10, default="ETB")
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("1.0000"),
        help_text="Exchange rate to ETB on quotation date",
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    tax_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    shipping_and_handling = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    customs_and_duties = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_quoted_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_landed_cost_etb = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # State & Decision
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_quotations",
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluation_notes = models.TextField(
        blank=True, default="", help_text="Comparative scoring and rationale"
    )

    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_quotations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    acceptance_justification = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory managerial rationale why this bid was awarded",
    )

    rejection_reason = models.TextField(blank=True, default="")
    rejected_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_quotations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="sq_status_idx"),
            models.Index(fields=["valid_until"], name="sq_validity_idx"),
            models.Index(fields=["supplier"], name="sq_supplier_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_quoted_amount__gte=0),
                name="sq_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_landed_cost_etb__gte=0),
                name="sq_landed_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="sq_fx_positive",
            ),
        ]

    def clean(self):
        if not self.rfq and not (self.requisition and self.sole_source_justification):
            raise ValidationError(
                "Every quotation must be linked to an RFQ or provide a verified "
                "Requisition and Sole Source Justification."
            )
        if self.valid_until and self.valid_until < self.quotation_date:
            raise ValidationError("valid_until date cannot precede quotation_date.")

    def save(self, *args, **kwargs):
        allow_override = getattr(self, "_allow_immutable_override", False)
        self._allow_immutable_override = False

        # Immutability Safeguard: Protect awarded, converted, rejected, or expired quotations from mutation
        if self.pk and not allow_override:
            old = SupplierQuotation.objects.filter(pk=self.pk).values("status", "quotation_number").first()
            if old and old["status"] in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
                allowed_transitions = {
                    ("accepted", "converted_to_po"),
                    ("partially_awarded", "converted_to_po"),
                }
                if (old["status"], self.status) not in allowed_transitions:
                    raise ValidationError(
                        f"Quotation {old['quotation_number']} is in terminal/locked status "
                        f"'{old['status']}' and cannot be modified."
                    )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not getattr(self, "_allow_immutable_override", False):
            if self.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
                raise ValidationError(
                    f"Quotation {self.quotation_number} is in status '{self.status}' and cannot be deleted."
                )
        super().delete(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.quotation_number} - {self.supplier.name} ({self.status}) ["
            f" {self.total_quoted_amount} {self.currency}]"
        )


class SupplierQuotationItem(models.Model):
    AWARD_STATUS_CHOICES = [
        ("pending", "Pending Evaluation"),
        ("awarded", "Awarded"),
        ("rejected", "Not Awarded"),
    ]

    quotation = models.ForeignKey(
        SupplierQuotation, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="quotation_lines"
    )
    rfq_item = models.ForeignKey(
        RequestForQuotationItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quoted_lines",
    )

    quoted_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    quoted_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    offered_brand_or_spec = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Specific vendor brand or packaging specification offered",
    )
    lead_time_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Item-specific lead time if different"
    )
    award_status = models.CharField(
        max_length=20, choices=AWARD_STATUS_CHOICES, default="pending"
    )
    is_converted_to_po = models.BooleanField(default=False)
    converted_purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sourced_quote_items",
        help_text="Purchase Order generated from this awarded quotation line (supports split awards)",
    )
    converted_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quotation", "item"], name="uniq_quote_item"
            ),
            models.CheckConstraint(
                condition=models.Q(quoted_quantity__gt=0),
                name="sqi_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quoted_unit_price__gte=0),
                name="sqi_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percentage__gte=0) & models.Q(discount_percentage__lte=100),
                name="sqi_discount_range",
            ),
        ]

    def save(self, *args, **kwargs):
        allow_override = getattr(self, "_allow_immutable_override", False)
        allow_conversion = getattr(self, "_allow_conversion_update", False)
        allow_award = getattr(self, "_allow_award_update", False)
        self._allow_immutable_override = False
        self._allow_conversion_update = False
        self._allow_award_update = False

        if self.pk and not allow_override:
            if self.quotation.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"]:
                if not allow_conversion and not allow_award:
                    raise ValidationError(
                        f"Quotation {self.quotation.quotation_number} is locked; items cannot be modified."
                    )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not getattr(self, "_allow_immutable_override", False):
            if self.quotation.status in ["accepted", "partially_awarded", "converted_to_po", "rejected", "expired"] or self.award_status == "awarded":
                raise ValidationError(
                    f"Awarded quotation items cannot be deleted from quotation {self.quotation.quotation_number}."
                )
        super().delete(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.quotation.quotation_number} - {self.item.name} ("
            f" {self.quoted_quantity} @ {self.quoted_unit_price})"
        )


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued / Ordered"),
        ("partially_received", "Partially Received"),
        ("received", "Fully Received"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    po_number = models.CharField(max_length=50, unique=True, db_index=True)
    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")
    originating_quotation = models.ForeignKey(
        SupplierQuotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
        help_text="Originating supplier quotation if sourced through bidding or quotation",
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    delivery_location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_pos")
    issued_at = models.DateTimeField(null=True, blank=True)
    delivery_due_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, default="Net 30")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")
    cancellation_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="po_status_idx"),
            models.Index(fields=["supplier"], name="po_supplier_idx"),
        ]

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name} ({self.status}) [{self.total_amount}]"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="po_items")
    originating_quote_item = models.ForeignKey(
        SupplierQuotationItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="po_items",
        help_text="Originating quotation line item",
    )
    quantity_ordered = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_ordered__gt=0), name="poi_qty_ord_positive"),
            models.CheckConstraint(condition=models.Q(quantity_received__gte=0), name="poi_qty_recv_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="poi_price_nonnegative"),
        ]

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.item.name} (Ordered: {self.quantity_ordered}, Recv: {self.quantity_received})"


class GoodsReceiptNote(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved / Stock Received"),
        ("cancelled", "Cancelled"),
    ]

    grn_number = models.CharField(max_length=50, unique=True, db_index=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="grns")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="grns")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="grns")
    delivery_note_number = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_grns")
    received_at = models.DateTimeField(default=timezone.now)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="grns")
    total_received_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="grn_status_idx"),
            models.Index(fields=["purchase_order"], name="grn_po_idx"),
        ]

    def __str__(self):
        return f"{self.grn_number} (PO: {self.purchase_order.po_number}) - {self.status}"


class GoodsReceiptNoteItem(models.Model):
    grn = models.ForeignKey(GoodsReceiptNote, on_delete=models.CASCADE, related_name="items")
    po_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name="grn_items")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="grn_items")
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_rejected = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    rejection_reason = models.CharField(max_length=255, blank=True, default="")
    batch = models.ForeignKey(StockBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="grn_items")
    batch_number = models.CharField(max_length=100)
    supplier_batch_number = models.CharField(max_length=100, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_received__gte=0), name="grni_qty_recv_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_rejected__gte=0), name="grni_qty_rej_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="grni_cost_nonnegative"),
        ]

    def __str__(self):
        return f"{self.grn.grn_number} - {self.item.name} (Recv: {self.quantity_received}, Rej: {self.quantity_rejected})"


class SupplierInvoice(models.Model):
    MATCH_STATUS_CHOICES = [
        ("unmatched", "Unmatched"),
        ("matched", "3-Way Matched"),
        ("variance_flagged", "Variance Flagged"),
        ("approved", "Approved for Payment"),
        ("rejected", "Rejected"),
    ]

    internal_number = models.CharField(max_length=50, unique=True, db_index=True)
    vendor_invoice_number = models.CharField(max_length=100, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="invoices")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    match_status = models.CharField(max_length=30, choices=MATCH_STATUS_CHOICES, default="unmatched", db_index=True)
    matched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="matched_invoices")
    matched_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_invoices")
    approved_at = models.DateTimeField(null=True, blank=True)
    variance_notes = models.TextField(blank=True, default="")
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_invoices")
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["match_status"], name="sinv_match_status_idx"),
            models.Index(fields=["supplier", "vendor_invoice_number"], name="sinv_supp_invnum_idx"),
        ]

    def __str__(self):
        return f"{self.internal_number} ({self.vendor_invoice_number}) - {self.supplier.name} [{self.total_amount}]"


class SupplierInvoiceItem(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="items")
    po_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name="invoice_items")
    grn_item = models.ForeignKey(GoodsReceiptNoteItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_items")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    billed_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    billed_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    price_variance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_matched = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(billed_quantity__gt=0), name="sii_qty_positive"),
            models.CheckConstraint(condition=models.Q(billed_unit_price__gte=0), name="sii_price_nonnegative"),
        ]

    def __str__(self):
        return f"{self.invoice.internal_number} - {self.item.name} (Billed: {self.billed_quantity} @ {self.billed_unit_price})"


# ── 21.5 Physical Stocktaking (Dual-Mode Blind & Visible) ─────────────────────────

class StocktakeSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    COUNTING_MODES = [
        ("blind", "Blind Count (Theoretical Qty Masked)"),
        ("visible", "Visible Count (Theoretical Qty Displayed)"),
    ]
    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ]

    name = models.CharField(max_length=255)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily", db_index=True)
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="stocktake_schedules")
    category = models.ForeignKey(
        InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stocktake_schedules", help_text="Optional category scope"
    )
    counting_mode = models.CharField(max_length=20, choices=COUNTING_MODES, default="blind")
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_stocktake_schedules", help_text="Designated counter for generated sessions"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    scheduled_time = models.TimeField(default="06:00", help_text="Local execution time in hotel timezone (HH:MM)")
    day_of_week = models.IntegerField(
        null=True, blank=True,
        help_text="0=Monday, 6=Sunday (Weekly schedules only)"
    )
    day_of_month = models.IntegerField(
        null=True, blank=True,
        help_text="Day of the month 1..31 (Monthly schedules only)"
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="success")
    last_error_message = models.TextField(blank=True, default="")
    next_run_at = models.DateTimeField(db_index=True, help_text="Calculated next run timestamp in hotel timezone")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_stocktake_schedules"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_run_at", "name"]
        indexes = [
            models.Index(fields=["is_active", "next_run_at"], name="stk_sched_active_next_idx"),
            models.Index(fields=["frequency", "is_active"], name="stk_sched_freq_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()}) - Next: {self.next_run_at}"


class StocktakeSession(models.Model):
    COUNTING_MODES = [
        ("blind", "Blind Count (Theoretical Qty Masked)"),
        ("visible", "Visible Count (Theoretical Qty Displayed)"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft / Scheduled"),
        ("in_progress", "Counting in Progress"),
        ("under_review", "Count Submitted / Under Supervisor Review"),
        ("recount_required", "Recount Required"),
        ("approved", "Approved & Stock Adjusted"),
        ("cancelled", "Cancelled"),
    ]

    session_number = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="stocktake_sessions"
    )
    category = models.ForeignKey(
        InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stocktake_sessions", help_text="Optional category scope"
    )
    counting_mode = models.CharField(max_length=20, choices=COUNTING_MODES, default="blind")
    is_mode_locked = models.BooleanField(
        default=False,
        help_text="Permanently locked once physical counting commences (Owner Decision D-4)"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)

    schedule = models.ForeignKey(
        StocktakeSchedule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sessions", help_text="Originating automated schedule (if generated)"
    )
    scheduled_date = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="Scheduled target business date"
    )


    snapshot_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_stocktakes"
    )
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="counted_stocktakes"
    )
    counted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_stocktakes"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    variance_approval_notes = models.TextField(blank=True, default="")

    total_theoretical_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_counted_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_variance_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stocktake_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="stk_session_status_idx"),
            models.Index(fields=["location", "status"], name="stk_loc_status_idx"),
        ]

    def __str__(self):
        return f"{self.session_number} - {self.location.name} ({self.get_counting_mode_display()}) [{self.status}]"


class StocktakeItem(models.Model):
    session = models.ForeignKey(
        StocktakeSession, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="stocktake_entries"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stocktake_entries"
    )
    theoretical_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    recounted_quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    unit_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    variance_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    variance_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    requires_recount = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["item__name"]
        indexes = [
            models.Index(fields=["session", "item"], name="stk_item_session_idx"),
        ]

    def __str__(self):
        return f"{self.session.session_number} - {self.item.name} (Theor: {self.theoretical_quantity}, Final: {self.final_quantity})"


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


# ── 23. Housekeeping Task ────────────────────────────────────────────────────

class HousekeepingTask(models.Model):
    TASK_TYPES = [
        ("checkout_cleaning", "Checkout Cleaning"),
        ("stayover_cleaning", "Stayover / Daily Cleaning"),
        ("deep_cleaning", "Deep Cleaning"),
        ("touch_up", "Touch Up / Inspection"),
        ("turndown", "Turn-Down Service"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent (Incoming Guest)"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("cleaned", "Cleaned (Awaiting Inspection)"),
        ("inspected", "Inspected & Approved"),
        ("failed", "Inspection Failed / Re-clean"),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="housekeeping_tasks")
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default="stayover_cleaning")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    assigned_to_username = models.CharField(max_length=150, blank=True, default="")
    assigned_by_username = models.CharField(max_length=150, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    checklist = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    inspected_by_username = models.CharField(max_length=150, blank=True, default="")
    inspected_at = models.DateTimeField(null=True, blank=True)
    inspection_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["room", "status"], name="hk_room_status_idx"),
            models.Index(fields=["status"], name="hk_status_idx"),
            models.Index(fields=["assigned_to_username"], name="hk_assigned_idx"),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} — Room {self.room.room_number} ({self.status})"


# ── 24. Minibar Item ─────────────────────────────────────────────────────────

class MinibarItem(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="minibar_items",
        help_text="Specific room, or blank for hotel-wide default standard template"
    )
    item = models.ForeignKey(
        'InventoryItem',
        on_delete=models.CASCADE,
        related_name="minibar_items"
    )
    standard_quantity = models.IntegerField(default=2, help_text="Standard stock count for this item in minibar")
    current_quantity = models.IntegerField(default=2, help_text="Current stock count in minibar")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Charge price to guest")
    last_restocked_at = models.DateTimeField(auto_now=True)
    last_checked_by = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        ordering = ["room", "item__name"]
        indexes = [
            models.Index(fields=["room"], name="minibar_room_idx"),
        ]

    def __str__(self):
        room_label = f"Room {self.room.room_number}" if self.room else "Standard Template"
        return f"{self.item.name} ({room_label}): {self.current_quantity}/{self.standard_quantity}"


# ── 25. Lost and Found Item ──────────────────────────────────────────────────

class LostAndFoundItem(models.Model):
    STATUS_CHOICES = [
        ("stored", "In Safe Storage"),
        ("claimed", "Claimed / Returned"),
        ("disposed", "Disposed / Donated"),
    ]
    item_name = models.CharField(max_length=200)
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lost_and_found_items"
    )
    location_found = models.CharField(max_length=200, blank=True, default="")
    found_by_name = models.CharField(max_length=150)
    found_date = models.DateField(default=timezone.now)
    guest_name = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    storage_location = models.CharField(max_length=100, default="Housekeeping Safe Locker")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="stored")
    claimed_by = models.CharField(max_length=200, blank=True, default="")
    claimed_at = models.DateTimeField(null=True, blank=True)
    claimant_phone = models.CharField(max_length=50, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-found_date", "-created_at"]
        indexes = [
            models.Index(fields=["status"], name="lost_found_status_idx"),
            models.Index(fields=["room"], name="lost_found_room_idx"),
        ]

    def __str__(self):
        return f"{self.item_name} ({self.get_status_display()}) — Found {self.found_date}"
