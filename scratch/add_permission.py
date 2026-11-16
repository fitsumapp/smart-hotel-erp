with open('users/permissions.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_class = '''

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
        from rest_framework.permissions import SAFE_METHODS

        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}:
            return True

        # Non-admin inventory staff: check location custodian or ownership
        location = getattr(obj, "location", None)
        if location and location.custodian and location.custodian == user:
            return True
        if getattr(obj, "created_by", None) == user:
            return True
        if getattr(obj, "assigned_staff", None) == user:
            return True
        if getattr(obj, "counted_by", None) == user:
            return True
        # If location has no specific custodian assigned, general inventory staff are permitted
        if location and location.custodian is None:
            return True

        return False
'''

if 'HasStocktakeLocationPermission' not in text:
    with open('users/permissions.py', 'w', encoding='utf-8') as f:
        f.write(text.strip() + new_class + '\n')
    print('Added HasStocktakeLocationPermission successfully!')
else:
    print('Already present.')

