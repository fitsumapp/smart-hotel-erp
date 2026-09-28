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

        maintenance_rooms = Room.objects.filter(status="Maintenance").count()
        active_res = Reservation.objects.filter(status__in=["confirmed", "checked_in"]).count()
        pending_res = Reservation.objects.filter(status="pending").count()

        today_orders = Order.objects.filter(created_at__date=today).count()
        active_orders = Order.objects.filter(status__in=["pending", "preparing"]).count()

        low_stock = InventoryItem.objects.filter(current_stock__lte=F("min_reorder_level")).count()
        settings_obj = SystemSettings.objects.first()

        now = timezone.now()
        first_of_month = now.replace(day=1)
        date_range_str = f"{first_of_month.strftime('%b %d, %Y')} - {now.strftime('%b %d, %Y')}"

        occ_pct = round((occupied_rooms / total_rooms * 100)) if total_rooms else 0
        avail_pct = 100 - occ_pct if total_rooms else 100

        context.update({
            "hotel_name": settings_obj.hotel_name if settings_obj else "Smart Hotel ERP",
            "date_range": date_range_str,
            "stats": {
                "total_rooms": total_rooms,
                "available_rooms": available_rooms,
                "occupied_rooms": occupied_rooms,
                "maintenance_rooms": maintenance_rooms,
                "occupied_pct": occ_pct,
                "available_pct": avail_pct,
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
