import os, sys, inspect
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

import users.permissions as uperms

print("=== PERMISSION CLASSES IN users/permissions.py ===")
for name, cls in inspect.getmembers(uperms, inspect.isclass):
    if issubclass(cls, uperms.BasePermission) and cls != uperms.BasePermission:
        print(f"\n--- {name} ---")
        lines = inspect.getsourcelines(cls)[0]
        print("".join(lines))

