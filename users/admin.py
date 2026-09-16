# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import SecurityAuditEvent, User

class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    model = User
    list_display = ['username', 'email', 'role', 'is_staff', 'is_verified']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone_number', 'profile_picture', 'otp_code', 'is_verified')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'email', 'first_name', 'last_name')}),
    )

admin.site.register(User, CustomUserAdmin)

@admin.register(SecurityAuditEvent)
class SecurityAuditEventAdmin(ModelAdmin):
    list_display = ["id", "action", "actor", "target_user", "actor_role", "created_at"]
    list_filter = ["action", "actor_role", "created_at"]
    search_fields = ["action", "actor__username", "target_user__username", "request_id"]
    readonly_fields = [field.name for field in SecurityAuditEvent._meta.fields]
    actions = None
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
