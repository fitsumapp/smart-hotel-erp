with open('users/permissions.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """    def has_object_permission(self, request, view, obj):
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

        return False"""

replacement = """    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False

        if user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}:
            return True

        # Non-admin inventory staff: check location custodian, assignment, or ownership
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
        # If location has no specific custodian assigned, general inventory staff are permitted
        if location and location.custodian is None:
            return True

        return False"""

assert target in text, "Target string not found in users/permissions.py"
updated = text.replace(target, replacement, 1)

with open('users/permissions.py', 'w', encoding='utf-8', newline='') as f:
    f.write(updated)

print("Updated users/permissions.py successfully!")

