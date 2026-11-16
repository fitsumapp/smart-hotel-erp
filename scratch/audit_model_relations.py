import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from hotel.models import (
    StockLocation, StocktakeSession, StocktakeSchedule,
    PurchaseRequisition, PurchaseOrder, GoodsReceiptNote,
    SupplierInvoice, InventoryWasteRecord, StockTransfer
)

User = get_user_model()

print("=== USER FIELDS & RELATIONS ===")
for f in User._meta.get_fields():
    if f.is_relation:
        print(f"  Relation: {f.name} -> {f.related_model.__name__ if f.related_model else 'None'} (field={f.remote_field.name if f.remote_field else 'None'})")
    else:
        print(f"  Field: {f.name} ({f.get_internal_type()})")

print("\n=== STOCKLOCATION MODEL ===")
for f in StockLocation._meta.fields:
    print(f"  {f.name}: {f.get_internal_type()} (rel={f.related_model.__name__ if f.related_model else 'None'})")

print("\n=== STOCKTAKESESSION MODEL ===")
for f in StocktakeSession._meta.fields:
    print(f"  {f.name}: {f.get_internal_type()} (rel={f.related_model.__name__ if f.related_model else 'None'})")

print("\n=== STOCKTAKESCHEDULE MODEL ===")
for f in StocktakeSchedule._meta.fields:
    print(f"  {f.name}: {f.get_internal_type()} (rel={f.related_model.__name__ if f.related_model else 'None'})")

print("\n=== PURCHASEREQUISITION MODEL ===")
for f in PurchaseRequisition._meta.fields:
    print(f"  {f.name}: {f.get_internal_type()} (rel={f.related_model.__name__ if f.related_model else 'None'})")
