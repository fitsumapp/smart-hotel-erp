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


