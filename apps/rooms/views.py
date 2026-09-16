"""Rooms API views extracted from the legacy facade."""
# Shared imports and compatibility helpers live in users.views during migration.
from users.views import *  # noqa: F401,F403

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsReservationOperator]


class MaintenanceLogView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        logs = MaintenanceLog.objects.filter(room=room)
        return Response(MaintenanceLogSerializer(logs, many=True).data)

    def post(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        data = request.data.copy()
        data["room"] = room.id
        data.setdefault("reported_by", request.user.username)
        serializer = MaintenanceLogSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class MaintenanceLogDetailView(APIView):
    permission_classes = [IsReservationOperator]

    def patch(self, request, log_id):
        try:
            log = MaintenanceLog.objects.get(id=log_id)
        except MaintenanceLog.DoesNotExist:
            return Response({"error": "Log not found."}, status=404)
        serializer = MaintenanceLogSerializer(log, data=request.data, partial=True)
        if serializer.is_valid():
            if request.data.get("status") == "resolved" and not log.resolved_at:
                log.resolved_at = timezone.now()
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class RoomHistoryView(APIView):
    permission_classes = [IsReservationOperator]

    def get(self, request, room_id):
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)
        history = RoomHistory.objects.filter(room=room)
        return Response(RoomHistorySerializer(history, many=True).data)


