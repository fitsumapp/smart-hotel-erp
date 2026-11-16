from django.db.models import Q
from hotel.models import InventoryItem, StockTransaction


def select_inventory_items(params):
    qs = InventoryItem.objects.select_related("category", "last_supplier")
    if params.get("category"):
        qs = qs.filter(category_id=params["category"])
    if params.get("low_stock") in ("1", "true", "True"):
        from django.db.models import F
        qs = qs.filter(current_stock__lte=F("min_reorder_level"))
    return qs.order_by("name")


def select_stock_transactions(params):
    qs = (
        StockTransaction.objects.select_related("item", "supplier", "location", "batch", "reversal_of")
        .prefetch_related("batch_consumptions__batch")
    )
    if params.get("item"):
        qs = qs.filter(item_id=params["item"])
    if params.get("transaction_type"):
        qs = qs.filter(transaction_type=params["transaction_type"])
    if params.get("location"):
        loc_val = params["location"]
        if str(loc_val).isdigit():
            qs = qs.filter(location_id=loc_val)
        else:
            qs = qs.filter(location__code=loc_val)
    if params.get("batch"):
        qs = qs.filter(batch_id=params["batch"])
    if params.get("start_date") or params.get("from_date"):
        dt = params.get("start_date") or params.get("from_date")
        qs = qs.filter(timestamp__date__gte=dt)
    if params.get("end_date") or params.get("to_date"):
        dt = params.get("end_date") or params.get("to_date")
        qs = qs.filter(timestamp__date__lte=dt)
    if params.get("search"):
        s = str(params["search"]).strip()
        qs = qs.filter(
            Q(reference_number__icontains=s)
            | Q(item__name__icontains=s)
            | Q(notes__icontains=s)
            | Q(batch__batch_number__icontains=s)
        )
    return qs.order_by("-timestamp", "-id")
