from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import (
    Category, MenuItem, Room, RestaurantTable,
    Order, OrderItem, Notification, SystemSettings
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
