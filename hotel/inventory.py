from decimal import Decimal

from django.db import transaction

from .models import InventoryItem, StockTransaction


def transaction_delta(entry):
    if entry.reversal_of_id:
        original_incoming = entry.reversal_of.transaction_type in ("purchase", "adjustment")
        return -entry.quantity if original_incoming else entry.quantity
    return entry.quantity if entry.transaction_type in ("purchase", "adjustment") else -entry.quantity


def expected_stock(item):
    balance = Decimal(str(item.opening_stock))
    entries = item.transactions.select_related("reversal_of").order_by("timestamp", "pk")
    return balance + sum((transaction_delta(entry) for entry in entries), Decimal("0"))


@transaction.atomic
def reconcile_stock(*, repair=False):
    mismatches = []
    for item in InventoryItem.objects.select_for_update().order_by("pk"):
        expected = expected_stock(item)
        if item.current_stock != expected:
            mismatches.append({"id": item.pk, "code": item.item_code, "cached": item.current_stock, "expected": expected})
            if repair:
                item.current_stock = expected
                item.save(update_fields=["current_stock", "last_stocked_at"])
    return mismatches
