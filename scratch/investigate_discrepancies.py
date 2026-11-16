import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db.models import Sum
from hotel.models import (
    InventoryItem, StockBatch, ItemLocationBalance, 
    StockTransaction, GoodsReceiptNoteItem, JournalEntryItem, Account
)
from decimal import Decimal
import json

print('=== 13 DISCREPANT ITEMS DEEP DIVE ===')
items = InventoryItem.objects.all().order_by('id')
discrepancies = []

for item in items:
    batches = StockBatch.objects.filter(item=item)
    batch_sum = batches.aggregate(s=Sum('current_quantity'))['s'] or Decimal('0.00')
    loc_bals = ItemLocationBalance.objects.filter(item=item)
    loc_sum = loc_bals.aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')
    
    if abs(item.current_stock - batch_sum) > Decimal('0.001') or abs(item.current_stock - loc_sum) > Decimal('0.001'):
        txs = StockTransaction.objects.filter(item=item).order_by('timestamp')
        grn_items = GoodsReceiptNoteItem.objects.filter(item=item)
        unit_cost = item.unit_cost or Decimal('0.00')
        master_val = item.current_stock * unit_cost
        batch_val = sum((b.current_quantity * b.unit_cost) for b in batches)
        
        info = {
            'id': item.id,
            'name': item.name,
            'code': item.item_code,
            'category': item.category.name if item.category else 'None',
            'unit': item.unit,
            'unit_cost': float(unit_cost),
            'current_stock': float(item.current_stock),
            'batch_sum': float(batch_sum),
            'loc_sum': float(loc_sum),
            'master_valuation': float(master_val),
            'batch_valuation': float(batch_val),
            'valuation_discrepancy': float(master_val - batch_val),
            'batches': [{'num': b.batch_number, 'qty': float(b.current_quantity), 'cost': float(b.unit_cost), 'status': b.status, 'is_legacy': b.is_legacy} for b in batches],
            'locations': [{'loc': lb.location.code, 'qty': float(lb.quantity)} for lb in loc_bals],
            'transactions': [{'type': t.transaction_type, 'qty': float(t.quantity), 'ref': t.reference_number, 'dir': t.adjustment_direction} for t in txs],
            'grn_count': grn_items.count()
        }
        discrepancies.append(info)

print(f'Total discrepant items found: {len(discrepancies)}')
for d in discrepancies:
    print('--------------------------------------------------')
    print(f"ID {d['id']} | {d['name']} ({d['code']}) [{d['category']}]")
    print(f"  Master Stock: {d['current_stock']} {d['unit']} @ {d['unit_cost']} ETB = {d['master_valuation']:.2f} ETB")
    print(f"  Batch Stock:  {d['batch_sum']} {d['unit']} = {d['batch_valuation']:.2f} ETB (Batches count: {len(d['batches'])})")
    print(f"  Location Stk: {d['loc_sum']} {d['unit']} (Locations count: {len(d['locations'])})")
    print(f"  Valuation Variance: {d['valuation_discrepancy']:.2f} ETB")
    print(f"  Batches: {d['batches']}")
    print(f"  Locations: {d['locations']}")
    print(f"  Transactions count: {len(d['transactions'])}")
    for t in d['transactions']:
        print(f"    - TX: {t['type']} qty={t['qty']} dir={t['dir']} ref={t['ref']}")

with open('scratch/discrepancies.json', 'w') as f:
    json.dump(discrepancies, f, indent=2)
print('\nWrote scratch/discrepancies.json')
