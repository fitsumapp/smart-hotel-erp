import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Count
from hotel.models import StockLocation, StocktakeSession, StocktakeSchedule

User = get_user_model()

print("=== 1. ROLE CHOICES IN USER MODEL ===")
for code, label in User.ROLE_CHOICES:
    print(f"  {code:15}: {label}")

print("\n=== 2. ACTUAL ROLES IN DATABASE ===")
for row in User.objects.values('role').annotate(count=Count('id')).order_by('-count'):
    print(f"  {row['role']:15}: {row['count']} users")

print("\n=== 3. SUPERUSER & STAFF FLAGS ===")
for u in User.objects.filter(is_superuser=True):
    print(f"  Superuser: ID={u.id}, username={u.username}, role={u.role}, is_staff={u.is_staff}, is_active={u.is_active}")

for u in User.objects.filter(is_staff=True, is_superuser=False):
    print(f"  Staff: ID={u.id}, username={u.username}, role={u.role}, is_active={u.is_active}")

print("\n=== 4. USERS WITH ROLES NOT IN ROLE_CHOICES ===")
valid_roles = {code for code, _ in User.ROLE_CHOICES}
invalid_users = User.objects.exclude(role__in=valid_roles)
print(f"  Count of users with undefined roles: {invalid_users.count()}")
for u in invalid_users:
    print(f"  ID={u.id}, username={u.username}, role={u.role}")

print("\n=== 5. ALL USERS AND THEIR ROLES & LOCATIONS ===")
for u in User.objects.all().order_by('id'):
    managed_locs = [l.code for l in u.managed_stock_locations.all()]
    print(f"  ID={u.id:2} | username={u.username:20} | role={u.role:15} | super={str(u.is_superuser):5} | staff={str(u.is_staff):5} | active={str(u.is_active):5} | locs={managed_locs}")

