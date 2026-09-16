"""Reporting serializers."""
from users.serializers import *  # noqa: F401,F403

class DayAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayAuditLog
        fields = "__all__"


