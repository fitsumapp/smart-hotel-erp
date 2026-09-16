from hotel.models import DayAuditLog


def select_day_audits(params):
    qs = DayAuditLog.objects.all()
    if params.get("is_closed") in ("true", "false"):
        qs = qs.filter(is_closed=params["is_closed"] == "true")
    if params.get("start_date"):
        qs = qs.filter(audit_date__gte=params["start_date"])
    if params.get("end_date"):
        qs = qs.filter(audit_date__lte=params["end_date"])
    return qs.order_by("-audit_date")
