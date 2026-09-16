from hotel.models import Reservation


ORDERING = {
    "created_at": "created_at",
    "-created_at": "-created_at",
    "check_in_date": "check_in_date",
    "-check_in_date": "-check_in_date",
    "check_out_date": "check_out_date",
}


def select_reservations(params):
    qs = Reservation.objects.select_related("room")
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("payment_status"):
        qs = qs.filter(payment_status=params["payment_status"])
    if params.get("room"):
        qs = qs.filter(room_id=params["room"])
    if params.get("check_in_from"):
        qs = qs.filter(check_in_date__gte=params["check_in_from"])
    if params.get("check_in_to"):
        qs = qs.filter(check_in_date__lte=params["check_in_to"])
    return qs.order_by(ORDERING.get(params.get("ordering"), "-created_at"))
