"""Orders serializers."""
from users.serializers import *  # noqa: F401,F403

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

    class Meta:
        model = OrderItem
        fields = ["id", "menu_item", "menu_item_name", "quantity", "price_at_order"]


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = "__all__"
        read_only_fields = ["logo"]


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


