"""
tenants/permissions.py
— Feature-gated permission classes.

Usage in any DRF view:
    class HasPOSAccess(HasFeatureAccess):
        feature_code = "pos"

    class MyView(APIView):
        permission_classes = [IsAuthenticated, HasPOSAccess]
"""
from rest_framework.permissions import BasePermission


def get_current_hotel():
    """
    Returns the Hotel (Tenant) object for the currently active schema.
    Returns None when running in the public schema.
    """
    try:
        from django_tenants.utils import get_tenant
        from django.db import connection
        return get_tenant(connection)
    except Exception:
        return None


class HasFeatureAccess(BasePermission):
    """
    Base permission — subclass and set `feature_code`.
    Grants access only if the current tenant has that feature enabled.
    Platform super-admins (is_platform_admin=True) bypass all checks.
    """
    feature_code = None   # override in subclass

    def has_permission(self, request, view):
        # Super-admin bypasses all feature checks
        user = request.user
        if user and user.is_authenticated and getattr(user, "is_platform_admin", False):
            return True

        hotel = get_current_hotel()

        # Public schema (no tenant) — deny by default
        if hotel is None:
            return False

        # Suspended hotel
        if not hotel.is_active:
            return False

        # No feature_code set — just check hotel is active
        if self.feature_code is None:
            return True

        return hotel.has_feature(self.feature_code)


# ── Pre-built permission classes for every package ────────────────────────────

class HasPOSAccess(HasFeatureAccess):
    feature_code = "pos"

class HasInventoryAccess(HasFeatureAccess):
    feature_code = "inventory"

class HasFinanceAccess(HasFeatureAccess):
    feature_code = "finance"

class HasKitchenDisplayAccess(HasFeatureAccess):
    feature_code = "kitchen_display"

class HasBarAccess(HasFeatureAccess):
    feature_code = "bar"

class HasReservationAccess(HasFeatureAccess):
    feature_code = "reservation"

class HasHousekeepingAccess(HasFeatureAccess):
    feature_code = "housekeeping"

class HasLaundryAccess(HasFeatureAccess):
    feature_code = "laundry"

class HasSpaAccess(HasFeatureAccess):
    feature_code = "spa"

class HasGymAccess(HasFeatureAccess):
    feature_code = "gym"

class HasParkingAccess(HasFeatureAccess):
    feature_code = "parking"

class HasRoomServiceAccess(HasFeatureAccess):
    feature_code = "room_service"

class HasDeliveryAccess(HasFeatureAccess):
    feature_code = "delivery"

class HasCRMAccess(HasFeatureAccess):
    feature_code = "crm"

class HasLoyaltyAccess(HasFeatureAccess):
    feature_code = "loyalty"

class HasPayrollAccess(HasFeatureAccess):
    feature_code = "payroll"

class HasProcurementAccess(HasFeatureAccess):
    feature_code = "procurement"

class HasReportingAccess(HasFeatureAccess):
    feature_code = "reporting"

class HasMultiBranchAccess(HasFeatureAccess):
    feature_code = "multi_branch"

class HasGuestPortalAccess(HasFeatureAccess):
    feature_code = "guest_portal"
