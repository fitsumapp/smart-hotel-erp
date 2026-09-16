from rest_framework import serializers
from hotel.models import AuditEvent

class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    class Meta:
        model = AuditEvent
        fields = ["id", "actor", "actor_username", "actor_role", "action", "entity_type",
                  "entity_id", "before_summary", "after_summary", "request_id",
                  "source_ip", "client_metadata", "reason", "created_at"]
        read_only_fields = fields
