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
    qs = StockTransaction.objects.select_related("item", "supplier")
    if params.get("item"):
        qs = qs.filter(item_id=params["item"])
    if params.get("transaction_type"):
        qs = qs.filter(transaction_type=params["transaction_type"])
    return qs.order_by("-timestamp")
