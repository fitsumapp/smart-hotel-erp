from django.utils import timezone
from django.db.models import F
from .models import Room, Reservation, Order, InventoryItem, SystemSettings


def dashboard_callback(request, context):
    """Provides real-time KPI metrics and module statuses to the Unfold admin dashboard."""
    try:
        today = timezone.now().date()
        total_rooms = Room.objects.count()
        available_rooms = Room.objects.filter(status="Available").count()
        occupied_rooms = Room.objects.filter(status="Occupied").count()

        active_res = Reservation.objects.filter(status__in=["confirmed", "checked_in"]).count()
        pending_res = Reservation.objects.filter(status="pending").count()

        today_orders = Order.objects.filter(created_at__date=today).count()
        active_orders = Order.objects.filter(status__in=["pending", "preparing"]).count()

        low_stock = InventoryItem.objects.filter(current_stock__lte=F("min_reorder_level")).count()
        settings_obj = SystemSettings.objects.first()

        context.update({
            "hotel_name": settings_obj.hotel_name if settings_obj else "Smart Hotel ERP",
            "stats": {
                "total_rooms": total_rooms,
                "available_rooms": available_rooms,
                "occupied_rooms": occupied_rooms,
                "active_reservations": active_res,
                "pending_reservations": pending_res,
                "today_orders": today_orders,
                "active_orders": active_orders,
                "low_stock_count": low_stock,
            },
            "modules": {
                "rooms": settings_obj.module_rooms if settings_obj else True,
                "pos": settings_obj.module_pos if settings_obj else True,
                "inventory": settings_obj.module_inventory if settings_obj else True,
                "finance": settings_obj.module_finance if settings_obj else True,
            },
        })
    except Exception:
        # Failsafe in case database is migrating or empty
        pass

    return context
