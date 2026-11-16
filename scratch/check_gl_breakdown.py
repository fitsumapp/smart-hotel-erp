import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from hotel.models import InventoryItem, StockBatch, JournalEntryItem, Account

acc_1300 = Account.objects.get(code='1300')
items = InventoryItem.objects.all().order_by('id')

print(f"{'Code':<25} | {'Master Val':>12} | {'Active Batch Val':>16} | {'GL 1300 Dr':>12} | {'GL 1300 Cr':>12} | {'Net GL 1300':>12}")
print("-" * 105)

total_m_val = 0
total_b_val = 0

for item in items:
    m_val = float(item.current_stock) * float(item.unit_cost)
    b_val = sum(float(b.current_quantity) * float(b.unit_cost) for b in item.batches.filter(status='active'))
    total_m_val += m_val
    total_b_val += b_val
    
    # Check journal entries related to this item
    jes = JournalEntryItem.objects.filter(account=acc_1300, entry__description__icontains=item.name)
    dr = sum(float(j.amount_debit) for j in jes)
    cr = sum(float(j.amount_credit) for j in jes)
    net = dr - cr
    print(f"{item.item_code:<25} | {m_val:>12.2f} | {b_val:>16.2f} | {dr:>12.2f} | {cr:>12.2f} | {net:>12.2f}")

print("-" * 105)
print(f"{'TOTAL':<25} | {total_m_val:>12.2f} | {total_b_val:>16.2f} | {'':>12} | {'':>12} | {float(acc_1300.cached_balance):>12.2f}")
