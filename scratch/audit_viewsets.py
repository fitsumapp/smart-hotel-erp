import os, sys, inspect
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()
import core.urls

import apps.inventory.views as inv_views
import apps.orders.views as ord_views
import apps.rooms.views as rm_views
import apps.reservations.views as res_views
import apps.reporting.views as rep_views
import users.views as usr_views
from rest_framework import viewsets
from rest_framework.views import APIView

modules = [
    ("Inventory", inv_views),
    ("Orders", ord_views),
    ("Rooms", rm_views),
    ("Reservations", res_views),
    ("Reporting", rep_views),
    ("Users", usr_views),
]

print("=== VIEWSETS AND API VIEWS PERMISSION MAPPING ===")
for mod_name, mod in modules:
    print(f"\n--- MODULE: {mod_name} ---")
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, (viewsets.ViewSetMixin, APIView)) and cls.__module__ == mod.__name__:
            perm_classes = getattr(cls, "permission_classes", [])
            perm_names = [p.__name__ if hasattr(p, "__name__") else str(p) for p in perm_classes]
            print(f"  {name:35} -> {perm_names}")
