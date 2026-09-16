from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import (
    Category, MenuItem, Room, RestaurantTable,
    Order, OrderItem, Notification, PaymentAttempt, PaymentWebhookEvent, SystemSettings, AuditEvent
)

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0

@admin.register(SystemSettings)
class SystemSettingsAdmin(ModelAdmin):
    list_display = ["hotel_name", "tin_number", "phone_number", "vat_enabled", "pos_machine_type"]

@admin.register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ["name", "room_number", "room_type", "status", "base_price"]
    list_filter = ["status", "room_type"]
    search_fields = ["name", "room_number"]

@admin.register(RestaurantTable)
class RestaurantTableAdmin(ModelAdmin):
    list_display = ["label_name", "table_code", "capacity", "status"]
    list_filter = ["status"]
    search_fields = ["label_name", "table_code"]

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ["id", "table", "status", "payment_status", "total_amount", "created_at"]
    list_filter = ["status", "payment_status", "payment_method"]
    search_fields = ["id", "payment_reference"]
    inlines = [OrderItemInline]

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "station"]
    list_filter = ["station"]
    search_fields = ["name"]

@admin.register(MenuItem)
class MenuItemAdmin(ModelAdmin):
    list_display = ["name", "category", "price", "is_available"]
    list_filter = ["is_available", "category"]
    search_fields = ["name"]

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ["id", "user_id_ref", "message", "is_read", "created_at"]
    list_filter = ["is_read"]


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ModelAdmin):
    list_display = ["id", "provider", "purpose", "provider_tx_ref", "status", "expected_amount", "currency", "verified_at"]
    list_filter = ["provider", "purpose", "status", "currency", "reconciliation_status"]
    search_fields = ["provider_tx_ref", "idempotency_key", "provider_event_ref"]
    readonly_fields = [field.name for field in PaymentAttempt._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(ModelAdmin):
    list_display = ["id", "provider", "event_ref", "tx_ref", "status", "received_at", "processed_at"]
    list_filter = ["provider", "status", "signature_valid"]
    search_fields = ["event_ref", "tx_ref", "payload_hash"]
    readonly_fields = [field.name for field in PaymentWebhookEvent._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ["id", "action", "entity_type", "entity_id", "actor", "actor_role", "request_id", "created_at"]
    list_filter = ["action", "entity_type", "actor_role", "created_at"]
    search_fields = ["request_id", "entity_type", "entity_id", "actor__username"]
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
    actions = None
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
