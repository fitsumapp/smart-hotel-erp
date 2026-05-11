"""
hotel/models.py
— All hotel-specific (TENANT) models.
  Each hotel gets its own PostgreSQL schema — total data isolation.
  Uses settings.AUTH_USER_MODEL for cross-schema ForeignKeys to User.
"""
from django.conf import settings
from django.db import models
from uuid import uuid4


# ── 1. Category ───────────────────────────────────────────────────────────────

class Category(models.Model):
    STATION_CHOICES = [("Kitchen", "Kitchen"), ("Bar", "Bar")]
    name = models.CharField(max_length=100)
    station = models.CharField(max_length=20, choices=STATION_CHOICES)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="category_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.name} ({self.station})"


# ── 2. Menu Item ──────────────────────────────────────────────────────────────

class MenuItem(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

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

    main_image = models.ImageField(upload_to="rooms/main/", blank=True, null=True)
    image_2 = models.ImageField(upload_to="rooms/extra/", blank=True, null=True)
    image_3 = models.ImageField(upload_to="rooms/extra/", blank=True, null=True)
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

    def __str__(self):
        return f"Reservation {self.confirmation_code or self.id} - Room {self.room.room_number}"

    def save(self, *args, **kwargs):
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

    def __str__(self):
        return f"Order {self.id} — Table {self.table.table_code} ({self.status})"

    def ensure_payment_page_token(self):
        if not self.payment_page_token:
            self.payment_page_token = uuid4().hex
        return self.payment_page_token


# ── 6. Order Item ─────────────────────────────────────────────────────────────

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
    notes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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
    id_scan = models.ImageField(upload_to="guest_ids/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.id_type}: {self.id_number}"


# ── 12. Folio Charge ──────────────────────────────────────────────────────────

class FolioCharge(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="folio_charges")
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    added_by = models.CharField(max_length=150, blank=True)  # denormalized, cross-schema safe
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]

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

    def __str__(self):
        return f"Audit {self.audit_date} — {'Closed' if self.is_closed else 'Open'}"

