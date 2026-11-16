import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from apps.inventory.services import calculate_authoritative_item_quantities
from hotel.models import InventoryItem

print(f"{'Code':<15} | {'Master':>7} | {'Physical':>8} | {'Active':>7} | {'Quar':>5} | {'Exp':>5} | {'InTr':>5} | {'LocSum':>7} | {'Consistent':>10} | Flags")
print("-" * 105)
for it in InventoryItem.objects.all().order_by('id'):
    q = calculate_authoritative_item_quantities(it)
    flags = ", ".join(q['reconciliation_flags']) if q['reconciliation_flags'] else "None"
    print(f"{it.item_code:<15} | {str(q['master_current_stock']):>7} | {str(q['on_hand_physical_stock']):>8} | {str(q['active_stock']):>7} | {str(q['quarantined_stock']):>5} | {str(q['expired_stock']):>5} | {str(q['in_transit_stock']):>5} | {str(q['location_stock_sum']):>7} | {str(q['is_consistent']):>10} | {flags}")
