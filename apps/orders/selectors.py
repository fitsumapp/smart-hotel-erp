from hotel.models import Order


ORDERING = {
    "created_at": "created_at",
    "-created_at": "-created_at",
    "total_amount": "total_amount",
    "-total_amount": "-total_amount",
    "status": "status",
}


def select_admin_orders(params):
    qs = Order.objects.prefetch_related("items__menu_item").select_related("table")
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("payment_status"):
        qs = qs.filter(payment_status=params["payment_status"])
    if params.get("start_date"):
        qs = qs.filter(created_at__date__gte=params["start_date"])
    if params.get("end_date"):
        qs = qs.filter(created_at__date__lte=params["end_date"])
    return qs.order_by(ORDERING.get(params.get("ordering"), "-created_at"))
