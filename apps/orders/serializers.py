from rest_framework import serializers
from .models import Category, MenuItem, Notification, Order, OrderItem, RestaurantTable, SystemSettings

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "price", "category", "category_name", "image", "is_available"]


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


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.ReadOnlyField(source="menu_item.name")
    category_name = serializers.ReadOnlyField(source="menu_item.category.name")
    station = serializers.SerializerMethodField()
    category_station = serializers.SerializerMethodField()

    def get_station(self, obj):
        if obj.menu_item and obj.menu_item.category:
            st = (obj.menu_item.category.station or "").strip()
            if st:
                return st
            cat_name = (obj.menu_item.category.name or "").lower()
            if any(k in cat_name for k in ["drink", "beverage", "juice", "beer", "wine", "bar", "cocktail", "soda", "coffee", "tea", "መጠጥ", "ቢራ", "ጭማቂ"]):
                return "Bar"
        return "Kitchen"

    def get_category_station(self, obj):
        return self.get_station(obj)

    class Meta:
        model = OrderItem
        fields = [
            "id", "menu_item", "menu_item_name", "category_name",
            "station", "category_station", "quantity", "price_at_order"
        ]


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = "__all__"
        read_only_fields = ["logo"]


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    waiter_name = serializers.SerializerMethodField()
    table_code = serializers.ReadOnlyField(source="table.table_code")
    hotel_info = serializers.SerializerMethodField()

    def get_items(self, obj):
        station = self.context.get("station") if hasattr(self, "context") and self.context else None
        serializer = OrderItemSerializer(obj.items.all(), many=True)
        if not station:
            return serializer.data

        station_lower = station.lower()
        filtered = []
        for it in serializer.data:
            st = (it.get("station") or "Kitchen").lower()
            if station_lower == "bar" and st == "bar":
                filtered.append(it)
            elif station_lower == "kitchen" and st != "bar":
                filtered.append(it)
        return filtered

    def get_waiter_name(self, obj):
        if obj.waiter_username:
            return obj.waiter_username
        if obj.waiter_id_ref:
            from users.models import User
            w = User.objects.filter(id=obj.waiter_id_ref).first()
            if w:
                return w.username
        return ""

    class Meta:
        model = Order
        fields = [
            "id", "table", "table_code", "waiter_id_ref", "waiter_name",
            "items", "sub_total", "service_charge_amount", "vat_amount",
            "total_amount", "status", "payment_status", "payment_method",
            "payment_reference", "tip_amount", "payment_page_token",
            "chapa_tx_ref", "chapa_checkout_url", "created_at", "hotel_info",
        ]

    # Cache settings per serializer context to avoid N+1 queries
    _cached_settings = None

    def get_hotel_info(self, obj):
        if OrderSerializer._cached_settings is None:
            OrderSerializer._cached_settings = SystemSettings.objects.first()
        settings_obj = OrderSerializer._cached_settings
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


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user_id_ref", "message", "is_read", "created_at"]


