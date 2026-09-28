"""Room-domain service boundary reserved for room state operations."""
from hotel.models import HousekeepingTask


DEFAULT_HOUSEKEEPING_CHECKLIST = [
    {"id": "linen", "label": "Bed linen & pillowcases replaced", "done": False},
    {"id": "bathroom", "label": "Bathroom & toilet sanitized", "done": False},
    {"id": "towels", "label": "Fresh towels & bath mats placed", "done": False},
    {"id": "toiletries", "label": "Amenities & toiletries replenished", "done": False},
    {"id": "minibar", "label": "Minibar checked & consumption recorded", "done": False},
    {"id": "floors", "label": "Room floors vacuumed / mopped", "done": False},
    {"id": "surfaces", "label": "Furniture & mirrors dusted and cleaned", "done": False},
    {"id": "trash", "label": "Trash bins emptied & relined", "done": False},
    {"id": "appliances", "label": "Lights, TV, AC & door locks checked", "done": False},
]


def create_checkout_housekeeping_task(room, guest_name="", actor_username="Front Desk"):
    """Auto-generates a high-priority checkout cleaning task for housekeeping."""
    existing = HousekeepingTask.objects.filter(
        room=room,
        status__in=["pending", "in_progress"],
    ).first()
    if existing:
        return existing

    return HousekeepingTask.objects.create(
        room=room,
        task_type="checkout_cleaning",
        priority="high",
        status="pending",
        assigned_by_username=actor_username or "Front Desk",
        notes=f"Auto-generated checkout cleaning for Room {room.room_number}. Previous guest: {guest_name or 'N/A'}",
        checklist=DEFAULT_HOUSEKEEPING_CHECKLIST,
    )
