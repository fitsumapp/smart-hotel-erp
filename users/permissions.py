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
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in {"admin", "finance"}))


class IsInventoryManager(BasePermission):
    message = "Inventory manager or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in {"admin", "inventory"}))


class IsSupplierOperator(BasePermission):
    """Allow active inventory staff, finance staff, or hotel administrators access to suppliers."""

    message = "Inventory, finance, or hotel administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.is_superuser
                or user.role in {"admin", "inventory", "finance"}
            )
        )


class IsWaiterOrAdmin(BasePermission):
    message = "Waiter or hotel administrator access is required."
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in {"admin", "waiter"}))


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

