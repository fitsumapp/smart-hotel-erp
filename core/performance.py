"""Shared bounded-query helpers for expensive APIs."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

DEFAULT_REPORT_DAYS = 31
MAX_REPORT_DAYS = 366

def bounded_date_range(params, *, default_start=None, default_end=None, max_days=MAX_REPORT_DAYS):
    end = default_end or timezone.localdate()
    start = default_start or end - timedelta(days=DEFAULT_REPORT_DAYS - 1)
    try:
        if params.get("start_date"):
            start = date.fromisoformat(str(params["start_date"]))
        if params.get("end_date"):
            end = date.fromisoformat(str(params["end_date"]))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"date_range": "Use ISO date format YYYY-MM-DD."}) from exc
    if start > end or (end - start).days + 1 > max_days:
        raise ValidationError({"date_range": f"Date range must be valid and cannot exceed {max_days} days."})
    return start, end



def datetime_bounds(start, end):
    """Return an index-friendly inclusive/exclusive timezone-aware range."""
    from datetime import datetime, time
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start, time.min), tz),
        timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz),
    )
