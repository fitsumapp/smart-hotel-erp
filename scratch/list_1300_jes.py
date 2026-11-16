import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from hotel.models import JournalEntryItem, Account

acc_1300 = Account.objects.get(code='1300')
items = JournalEntryItem.objects.filter(account=acc_1300).select_related('entry').order_by('entry__date', 'id')

print(f"{'ID':<4} | {'Date':<10} | {'Entry No':<14} | {'Debit':>10} | {'Credit':>10} | {'Description'}")
print("-" * 90)
for j in items:
    print(f"{j.entry.id:<4} | {str(j.entry.date):<10} | {j.entry.entry_number:<14} | {float(j.amount_debit):>10.2f} | {float(j.amount_credit):>10.2f} | {j.entry.description}")

