"""Reservations serializers."""
from users.serializers import *  # noqa: F401,F403

class ReservationSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source="room.name")
    room_number = serializers.ReadOnlyField(source="room.room_number")
    room_image = serializers.ImageField(source="room.main_image", read_only=True)

    class Meta:
        model = Reservation
        fields = "__all__"


class GuestProfileSerializer(serializers.ModelSerializer):
    id_scan = serializers.ImageField(write_only=True, required=False, allow_null=True)
    id_scan_url = serializers.SerializerMethodField()

    def get_id_scan_url(self, obj):
        if not obj.id_scan:
            return None
        return f"/api/v1/guest-profiles/{obj.pk}/id-scan/"

    class Meta:
        model = GuestProfile
        fields = "__all__"
        read_only_fields = ["created_at"]


class FolioChargeSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.ReadOnlyField(source="inventory_item.name")

    class Meta:
        model = FolioCharge
        fields = "__all__"
        read_only_fields = ["added_at"]


