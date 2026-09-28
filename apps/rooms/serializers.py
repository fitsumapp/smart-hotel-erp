"""Rooms serializers."""
from users.serializers import *  # noqa: F401,F403

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


class HousekeepingTaskSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.room_number", read_only=True)
    room_type = serializers.CharField(source="room.room_type", read_only=True)
    room_status = serializers.CharField(source="room.status", read_only=True)
    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = HousekeepingTask
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class MinibarItemSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.room_number", read_only=True, allow_null=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_code = serializers.CharField(source="item.item_code", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    inventory_stock = serializers.DecimalField(source="item.current_stock", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = MinibarItem
        fields = "__all__"
        read_only_fields = ["last_restocked_at"]


class LostAndFoundItemSerializer(serializers.ModelSerializer):
    room_number = serializers.CharField(source="room.room_number", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LostAndFoundItem
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


