"""Reusable role-based permissions for the users API."""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsHotelAdmin(BasePermission):
    """Allow only active hotel administrators or Django superusers."""

    message = "Hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.is_superuser or user.role == "admin")
        )


class IsHotelManagerOrAdmin(BasePermission):
    """Allow active hotel managers, hotel administrators, or Django superusers."""

    message = "Hotel manager or administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"})
        )


class IsCashierOrAdmin(BasePermission):
    """Allow active cashiers, hotel administrators, or superusers."""

    message = "Cashier or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.is_superuser or user.role in {"admin", "cashier"})
        )


class IsReservationOperator(BasePermission):
    """Allow only active receptionists and hotel administrators."""

    message = "Reception or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active
            and (user.is_superuser or user.role in {"admin", "reception"})
        )


class IsKitchenBarOrAdmin(BasePermission):
    """Allow active kitchen/bar operators or hotel administrators."""

    message = "Kitchen, bar, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.role in {"admin", "kitchen", "bar"}
            )
        )


class IsFinanceStaff(BasePermission):
    message = "Finance or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and
            (user.is_superuser or getattr(user, "role", "") in {"admin", "finance"})
        )


class IsInventoryManager(BasePermission):
    message = "Inventory manager or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}))


class IsProcurementOperator(BasePermission):
    message = "Procurement officer, inventory manager, or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}))


class IsProcurementOrFinanceOperator(BasePermission):
    message = "Procurement, finance, or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "finance", "hotel_manager"}))


class IsBatchOperator(BasePermission):
    """Allow active inventory staff, kitchen staff, or hotel administrators access to stock batches."""

    message = "Inventory, kitchen, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.role in {"admin", "inventory", "kitchen"}
            )
        )


class IsSupplierOperator(BasePermission):
    """Allow active inventory staff, finance staff, hotel managers, or hotel administrators access to suppliers."""

    message = "Inventory, finance, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or getattr(user, "role", "") in {"admin", "inventory", "finance", "hotel_manager"}
            )
        )


class IsPurchaseRequisitionStaff(BasePermission):
    """
    Allow administrative and procurement staff full access.
    Allow active operational departmental staff (kitchen, bar, housekeeping) to submit and view scoped requisitions.
    Strictly deny external customers (customer role) and dining line staff (waiter, cashier).
    """

    message = "Staff procurement requisition access is required."

    ALLOWED_DEPARTMENTAL_ROLES = {
        "admin",
        "hotel_manager",
        "inventory",
        "finance",
        "kitchen",
        "bar",
        "housekeeping",
    }

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.is_superuser:
            return True
        return getattr(user, "role", "") in self.ALLOWED_DEPARTMENTAL_ROLES


class IsWaiterOrAdmin(BasePermission):
    message = "Waiter or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "waiter"}))


class IsReceptionOrAdmin(IsReservationOperator):
    pass


class IsAdminOrReadOnly(BasePermission):
    """Allow read access to anyone (waiters, cashiers, guests), but only hotel admins can modify."""

    message = "Hotel administrator access is required to modify."

    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.is_superuser or getattr(user, "role", "") == "admin")
        )


class IsHousekeepingOperator(BasePermission):
    """Allow active housekeeping staff, receptionists, or hotel administrators."""

    message = "Housekeeping, reception, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.role in {"admin", "reception", "housekeeping"}
            )
        )


class IsHousekeepingOrAdmin(IsHousekeepingOperator):
    pass


class IsRoomOperator(BasePermission):
    """
    Allow reception and admin full management access.
    Allow housekeeping read-only access (GET/HEAD/OPTIONS) to room lists and details.
    """

    message = "Reception or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.is_superuser or user.role in {"admin", "reception"}:
            return True
        if request.method in SAFE_METHODS and user.role == "housekeeping":
            return True
        return False

class HasStocktakeLocationPermission(BasePermission):
    """
    Object-level permission ensuring staff only modify schedules/sessions
    for locations they are assigned to, created, or where they are custodian,
    while administrators retain global management access.
    """

    message = "Location custodian, schedule assignee, or hotel administrator access is required for this operation."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}
            )
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False

        if user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager", "inventory"}:
            return True

        # Non-management staff: check location custodian, assignment, or ownership
        location = getattr(obj, "location", None)
        if location and location.custodian and location.custodian == user:
            return True
        if getattr(obj, "created_by", None) == user:
            return True
        if getattr(obj, "assigned_staff", None) == user:
            return True
        if getattr(obj, "counted_by", None) == user:
            return True
        schedule = getattr(obj, "schedule", None)
        if schedule and getattr(schedule, "assigned_staff", None) == user:
            return True

        return False

