from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import SecurityAuditEvent, User


class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    model = User
    list_display = ["username", "display_role", "email", "phone_number", "display_active", "display_verified"]
    list_filter = ["role", "is_staff", "is_active", "is_verified"]
    list_filter_submit = True
    search_fields = ["username", "email", "first_name", "last_name", "phone_number"]
    ordering = ["username"]

    fieldsets = (
        ("Account Credentials", {
            "fields": ("username", "password"),
        }),
        ("Personal Information", {
            "fields": ("first_name", "last_name", "email", "phone_number", "profile_picture"),
        }),
        ("Role & Permissions", {
            "fields": ("role", "is_active", "is_staff", "is_superuser", "is_verified", "groups", "user_permissions"),
        }),
        ("Activity Timestamps", {
            "fields": ("last_login", "date_joined"),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Hotel Staff Details", {
            "fields": ("role", "email", "first_name", "last_name", "phone_number"),
        }),
    )

    @display(
        description="Role",
        label={
            User.ADMIN: "danger",
            User.FINANCE: "info",
            User.RECEPTION: "success",
            User.CASHIER: "warning",
            User.WAITER: "secondary",
            User.KITCHEN: "warning",
            User.BAR: "info",
            User.INVENTORY: "primary",
            User.DELIVERY: "secondary",
            User.CUSTOMER: "secondary",
        },
    )
    def display_role(self, obj):
        return obj.role

    @display(description="Active", boolean=True)
    def display_active(self, obj):
        return obj.is_active

    @display(description="Verified", boolean=True)
    def display_verified(self, obj):
        return obj.is_verified


admin.site.register(User, CustomUserAdmin)


@admin.register(SecurityAuditEvent)
class SecurityAuditEventAdmin(ModelAdmin):
    list_display = ["id", "display_action", "actor", "display_actor_role", "target_user", "created_at"]
    list_filter = ["action", "actor_role", "created_at"]
    list_filter_submit = True
    search_fields = ["action", "actor__username", "target_user__username", "request_id"]
    readonly_fields = [field.name for field in SecurityAuditEvent._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(
        description="Action",
        label={
            "login": "success",
            "login_failed": "danger",
            "logout": "secondary",
            "role_change": "warning",
        },
    )
    def display_action(self, obj):
        return obj.action

    @display(
        description="Actor Role",
        label={
            "admin": "danger",
            "finance": "info",
            "reception": "success",
            "cashier": "warning",
            "waiter": "secondary",
        },
    )
    def display_actor_role(self, obj):
        return obj.actor_role or "—"

