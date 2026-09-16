from rest_framework import generics
from users.permissions import IsHotelAdmin
from hotel.models import AuditEvent
from .serializers import AuditEventSerializer

class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [IsHotelAdmin]
    def get_queryset(self):
        params = self.request.query_params
        queryset = AuditEvent.objects.select_related("actor").all()
        if params.get("request_id"):
            queryset = queryset.filter(request_id=params["request_id"][:80])
        if params.get("action"):
            queryset = queryset.filter(action=params["action"][:100])
        if params.get("entity_type"):
            queryset = queryset.filter(entity_type=params["entity_type"][:100])
        if params.get("entity_id"):
            queryset = queryset.filter(entity_id=params["entity_id"][:100])
        if params.get("actor"):
            queryset = queryset.filter(actor_id=params["actor"])
        return queryset
