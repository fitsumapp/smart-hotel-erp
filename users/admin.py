# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import User

class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    model = User
    list_display = ['username', 'email', 'role', 'is_staff', 'is_verified']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'tenant_schema', 'is_platform_admin', 'phone_number', 'profile_picture', 'otp_code', 'is_verified')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'tenant_schema', 'is_platform_admin', 'email', 'first_name', 'last_name')}),
    )

admin.site.register(User, CustomUserAdmin)