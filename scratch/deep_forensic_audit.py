import os
import sys
import django

sys.path.insert(0, r"D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum, Q
from hotel.models import (
    InventoryItem, StockBatch, ItemLocationBalance, StockLocation,
    StockTransaction, GoodsReceiptNote, GoodsReceiptNoteItem,
    PurchaseOrder, PurchaseOrderItem, JournalEntry, JournalEntryItem,
    Account, InventoryWasteRecord
)

# Inspect related models if they exist
try:
    from hotel.models import StockTransfer, StockTransferItem
except ImportError:
    StockTransfer, StockTransferItem = None, None

try:
    from hotel.models import StocktakingSession, StocktakingCount
except ImportError:
    StocktakingSession, StocktakingCount = None, None

try:
    from apps.inventory.models import PhysicalStocktakingSession, StocktakeItemRecord
except ImportError:
    PhysicalStocktakingSession, StocktakeItemRecord = None, None

print("=== CHECKING ALL 27 ITEMS ===")
all_items = InventoryItem.objects.all().order_by('id')
print(f"Total items: {all_items.count()}")

discrepant_items_data = []

for item in all_items:
    batches = StockBatch.objects.filter(item=item)
    batch_total = batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')
    active_batches = batches.filter(status='active')
    active_batch_sum = active_batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')
    quar_batches = batches.filter(status='quarantined')
    quar_batch_sum = quar_batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')
    exp_batches = batches.filter(status='expired')
    exp_batch_sum = exp_batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')
    other_batches = batches.exclude(status__in=['active', 'quarantined', 'expired'])
    other_batch_sum = other_batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')

    loc_bals = ItemLocationBalance.objects.filter(item=item)
    loc_sum = loc_bals.aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

    # Valuation
    unit_cost = item.unit_cost or Decimal('0.00')
    master_val = item.current_stock * unit_cost
    active_val = sum((b.current_quantity * b.unit_cost) for b in active_batches)
    quar_val = sum((b.current_quantity * b.unit_cost) for b in quar_batches)
    exp_val = sum((b.current_quantity * b.unit_cost) for b in exp_batches)
    other_val = sum((b.current_quantity * b.unit_cost) for b in other_batches)
    total_batch_val = sum((b.current_quantity * b.unit_cost) for b in batches)

    has_discrepancy = (
        abs(item.current_stock - active_batch_sum) > Decimal('0.001') or
        abs(item.current_stock - batch_total) > Decimal('0.001') or
        abs(item.current_stock - loc_sum) > Decimal('0.001')
    )

    if has_discrepancy:
        discrepant_items_data.append({
            'item': item,
            'batches': batches,
            'active_batches': active_batches,
            'quar_batches': quar_batches,
            'exp_batches': exp_batches,
            'other_batches': other_batches,
            'loc_bals': loc_bals,
            'batch_total': batch_total,
            'active_batch_sum': active_batch_sum,
            'quar_batch_sum': quar_batch_sum,
            'exp_batch_sum': exp_batch_sum,
            'other_batch_sum': other_batch_sum,
            'loc_sum': loc_sum,
            'unit_cost': unit_cost,
            'master_val': master_val,
            'active_val': active_val,
            'quar_val': quar_val,
            'exp_val': exp_val,
            'total_batch_val': total_batch_val,
            'val_variance': master_val - active_val
        })

print(f"Discrepant items count: {len(discrepant_items_data)}")
for d in discrepant_items_data:
    item = d['item']
    print(f"ID {item.id} | {item.item_code} | {item.name}: Master={item.current_stock}, ActiveBatch={d['active_batch_sum']}, TotalBatch={d['batch_total']}, LocSum={d['loc_sum']}, Variance={d['val_variance']}")

