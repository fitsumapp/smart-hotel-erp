import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tenants.models import Hotel, Domain
from users.models import User

# 1. Create Public Tenant
try:
    public_tenant = Hotel.objects.get(schema_name="public")
    print("Public tenant already exists.")
except Hotel.DoesNotExist:
    public_tenant = Hotel(
        schema_name="public",
        name="Smart Hotel ERP Platform",
        is_active=True,
    )
    public_tenant.save()
    
    # Needs a domain depending on how the platform admin runs.
    Domain.objects.create(
        domain="localhost",
        tenant=public_tenant,
        is_primary=True
    )
    print("Public tenant created.")


# 2. Create Atlas Hotel Tenant
try:
    atlas_tenant = Hotel.objects.get(schema_name="hotel_atlas")
    print("Atlas tenant already exists.")
except Hotel.DoesNotExist:
    atlas_tenant = Hotel(
        schema_name="hotel_atlas",
        name="Atlas International Hotel PLC",
        subscription_plan="premium"
    )
    # the schema and migrations will be created automatically in save()
    atlas_tenant.save()
    
    # enable some features
    atlas_tenant.enable_feature("pos")
    atlas_tenant.enable_feature("inventory")
    
    Domain.objects.create(
        domain="atlas.localhost",
        tenant=atlas_tenant,
        is_primary=True
    )
    print("Atlas Hotel tenant created.")

# 3. Create Super Admin
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@atlas.com", "admin123", role="admin", is_platform_admin=True)
    print("Superuser created (admin / admin123)")

