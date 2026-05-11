import json
from rest_framework import serializers
from django.contrib.auth import get_user_model

from hotel.models import (
    MenuItem, Category, Room, RestaurantTable,
    OrderItem, Order, Notification, SystemSettings, Reservation,
    MaintenanceLog, RoomHistory, GuestProfile, FolioCharge, DayAuditLog,
)

User = get_user_model()


# ── 1. User ───────────────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "phone_number", "profile_picture", "is_active", "password",
            "tenant_schema", "is_platform_admin",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        is_active = validated_data.pop("is_active", False)
        user = User(**validated_data)
        user.is_active = is_active
        user.set_password(password)
        user.save()
        return user


# ── 2. Category ───────────────────────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


# ── 3. Menu Item ──────────────────────────────────────────────────────────────
class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "price", "category", "category_name", "image", "is_available"]


# ── 4. Room ───────────────────────────────────────────────────────────────────
class RoomSerializer(serializers.ModelSerializer):
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    floor_number = serializers.IntegerField(default=1)

    class Meta:
        model = Room
        fields = "__all__"

    def to_internal_value(self, data):
        if hasattr(data, "dict"):
            mutable_data = data.dict()
        else:
            mutable_data = data.copy()

        if "amenities" in mutable_data and isinstance(mutable_data.get("amenities"), str):
            try:
                if mutable_data["amenities"].strip():
                    mutable_data["amenities"] = json.loads(mutable_data["amenities"])
                else:
                    mutable_data["amenities"] = []
            except (ValueError, json.JSONDecodeError):
                mutable_data["amenities"] = []

        for field in ["instant_booking", "is_featured", "is_available_online"]:
            if field in mutable_data and isinstance(mutable_data[field], str):
                mutable_data[field] = mutable_data[field].lower() == "true"

        if "common_amenities" in mutable_data and isinstance(mutable_data.get("common_amenities"), str):
            try:
                if mutable_data["common_amenities"].strip():
                    mutable_data["common_amenities"] = json.loads(mutable_data["common_amenities"])
                else:
                    mutable_data["common_amenities"] = []
            except (ValueError, json.JSONDecodeError):
                mutable_data["common_amenities"] = []

        return super().to_internal_value(mutable_data)


# ── 5. Reservation ────────────────────────────────────────────────────────────
class ReservationSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source="room.name")
    room_number = serializers.ReadOnlyField(source="room.room_number")
    room_image = serializers.ImageField(source="room.main_image", read_only=True)

    class Meta:
        model = Reservation
        fields = "__all__"


# ── 6. Restaurant Table ───────────────────────────────────────────────────────
class RestaurantTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTable
        fields = "__all__"

    def to_internal_value(self, data):
        if hasattr(data, "dict"):
            mutable_data = data.dict()
        else:
            mutable_data = data.copy()

        if "capacity" in mutable_data and isinstance(mutable_data["capacity"], str):
            try:
                mutable_data["capacity"] = int(mutable_data["capacity"])
            except ValueError:
                pass

        return super().to_internal_value(mutable_data)


# ── 7. Order Item ─────────────────────────────────────────────────────────────
class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.ReadOnlyField(source="menu_item.name")

    class Meta:
        model = OrderItem
        fields = ["id", "menu_item", "menu_item_name", "quantity", "price_at_order"]


# ── 8. System Settings ────────────────────────────────────────────────────────
class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = "__all__"
        read_only_fields = ["logo"]


# ── 9. Order ──────────────────────────────────────────────────────────────────
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    waiter_name = serializers.ReadOnlyField(source="waiter_username")
    table_code = serializers.ReadOnlyField(source="table.table_code")
    hotel_info = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "table", "table_code", "waiter_id_ref", "waiter_name",
            "items", "sub_total", "service_charge_amount", "vat_amount",
            "total_amount", "status", "payment_status", "payment_method",
            "payment_reference", "tip_amount", "payment_page_token",
            "chapa_tx_ref", "chapa_checkout_url", "created_at", "hotel_info",
        ]

    def get_hotel_info(self, obj):
        settings_obj = SystemSettings.objects.first()
        if settings_obj:
            return {
                "hotel_name": settings_obj.hotel_name,
                "tin_number": settings_obj.tin_number,
                "address": settings_obj.address,
                "phone_number": settings_obj.phone_number,
                "fiscal_machine_no": settings_obj.fiscal_machine_no,
                "printer_paper_size": settings_obj.printer_paper_size,
            }
        return None


# ── 10. Notification ──────────────────────────────────────────────────────────
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user_id_ref", "message", "is_read", "created_at"]


# ── PMS Serializers ───────────────────────────────────────────────────────────

class MaintenanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceLog
        fields = "__all__"
        read_only_fields = ["reported_at"]


class RoomHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomHistory
        fields = "__all__"
        read_only_fields = ["created_at"]


class GuestProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestProfile
        fields = "__all__"
        read_only_fields = ["created_at"]


class FolioChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FolioCharge
        fields = "__all__"
        read_only_fields = ["added_at"]


class DayAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayAuditLog
        fields = "__all__"
