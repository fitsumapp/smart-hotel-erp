"""
tenants/admin.py
— Platform Super-Admin interface (PUBLIC schema only).
  Accessible at: http://localhost.example.com/admin/
  Allows toggling hotel modules, creating tenants, managing packages.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from .models import Hotel, Domain, Package, PACKAGE_CHOICES
from .forms import HotelAdminForm


# ── Package Admin ─────────────────────────────────────────────────────────────

@admin.register(Package)
class PackageAdmin(ModelAdmin):
    list_display = ["name", "code", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    ordering = ["code"]


# ── Domain Inline ─────────────────────────────────────────────────────────────

class DomainInline(TabularInline):
    model = Domain
    extra = 1
    fields = ["domain", "is_primary"]

@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    list_display = ["domain", "is_primary", "tenant"]
    search_fields = ["domain"]


# ── Hotel (Tenant) Admin ───────────────────────────────────────────────────────

@admin.register(Hotel)
class HotelAdmin(ModelAdmin):
    form = HotelAdminForm
    list_display = [
        "name", "schema_name", "subscription_plan",
        "is_active", "feature_badges", "created_at",
    ]
    list_filter = ["is_active", "subscription_plan"]
    search_fields = ["name", "schema_name", "contact_email"]
    readonly_fields = ["created_at"]
    inlines = [DomainInline]

    fieldsets = (
        ("Hotel Info", {
            "fields": ("name", "schema_name", "logo", "contact_email", "contact_phone", "address"),
        }),
        ("Hotel Admin Account", {
            "fields": ("admin_email", "admin_password"),
            "description": "Credentials for the hotel owner to log into their React dashboard.",
        }),
        ("Subscription & Status", {
            "fields": ("is_active", "subscription_plan"),
        }),
        ("Enabled Modules / Packages", {
            "fields": ("enabled_features",),
            "description": "Select the modules/packages to enable for this hotel.",
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        # Now the schema is created. We can safely create the admin user.
        email = form.cleaned_data.get("admin_email")
        password = form.cleaned_data.get("admin_password")
        
        if email:
            from users.models import User
            from django.contrib.auth.hashers import make_password
            
            user = User.objects.filter(tenant_schema=obj.schema_name, role="admin").first()
            if not user:
                user = User(
                    username=email,
                    email=email,
                    tenant_schema=obj.schema_name,
                    role="admin",
                    is_active=True,
                    is_verified=True,
                )
            else:
                user.username = email
                user.email = email
                user.is_active = True
                user.is_verified = True
                
            if password:
                user.password = make_password(password)
                
            user.save()

        # Update Tenant-specific SystemSettings (Logo, Name, Address)
        from django_tenants.utils import schema_context
        from hotel.models import SystemSettings
        
        with schema_context(obj.schema_name):
            settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
            settings_obj.hotel_name = obj.name
            settings_obj.address = obj.address or settings_obj.address
            settings_obj.phone_number = obj.contact_phone or settings_obj.phone_number
            settings_obj.enabled_features = obj.enabled_features or []
            
            # Use the provided logo if available
            if obj.logo:
                settings_obj.logo = obj.logo
                
            settings_obj.save()

    def feature_badges(self, obj):
        features = obj.enabled_features or []
        if not features:
            return mark_safe('<span style="color:#999">None</span>')
        badges = "".join(
            f'<span style="background:#0ea5e9;color:#fff;padding:2px 7px;'
            f'border-radius:10px;font-size:11px;margin:1px;display:inline-block">'
            f'{code}</span>'
            for code in features
        )
        return mark_safe(badges)

    feature_badges.short_description = "Active Modules"
