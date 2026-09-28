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


# ── Housekeeping, Minibar & Lost and Found Views ──────────────────────────────

from decimal import Decimal
from django.utils import timezone
from django.db import transaction, models
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from hotel.models import (
    Room, Reservation, FolioCharge, InventoryItem, StockTransaction,
    HousekeepingTask, MinibarItem, LostAndFoundItem, RoomHistory
)
from .serializers import (
    HousekeepingTaskSerializer, MinibarItemSerializer, LostAndFoundItemSerializer
)

DEFAULT_HOUSEKEEPING_CHECKLIST = [
    {"id": "linen", "label": "Bed linen & pillowcases replaced", "done": False},
    {"id": "bathroom", "label": "Bathroom & toilet sanitized", "done": False},
    {"id": "towels", "label": "Fresh towels & bath mats placed", "done": False},
    {"id": "toiletries", "label": "Amenities & toiletries replenished", "done": False},
    {"id": "minibar", "label": "Minibar checked & consumption recorded", "done": False},
    {"id": "floors", "label": "Room floors vacuumed / mopped", "done": False},
    {"id": "surfaces", "label": "Furniture & mirrors dusted and cleaned", "done": False},
    {"id": "trash", "label": "Trash bins emptied & relined", "done": False},
    {"id": "appliances", "label": "Lights, TV, AC & door locks checked", "done": False},
]


class HousekeepingTaskListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = HousekeepingTask.objects.select_related("room").all()
        status_param = request.query_params.get("status")
        room_id = request.query_params.get("room_id")
        assigned_to = request.query_params.get("assigned_to")

        if status_param:
            qs = qs.filter(status=status_param)
        if room_id:
            qs = qs.filter(room_id=room_id)
        if assigned_to:
            qs = qs.filter(assigned_to_username__iexact=assigned_to)

        serializer = HousekeepingTaskSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        room_id = data.get("room")
        if not room_id:
            return Response({"error": "room is required"}, status=400)

        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=404)

        if not data.get("checklist") or len(data.get("checklist")) == 0:
            data["checklist"] = DEFAULT_HOUSEKEEPING_CHECKLIST

        data["assigned_by_username"] = request.user.username or "Admin"

        serializer = HousekeepingTaskSerializer(data=data)
        if serializer.is_valid():
            task = serializer.save()
            if room.status in ["Available", "Dirty", "Inspected"]:
                room.status = "Cleaning"
                room.save(update_fields=["status"])
            return Response(HousekeepingTaskSerializer(task).data, status=201)
        return Response(serializer.errors, status=400)


class HousekeepingTaskDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            task = HousekeepingTask.objects.select_related("room").get(id=pk)
        except HousekeepingTask.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)
        return Response(HousekeepingTaskSerializer(task).data)

    def patch(self, request, pk):
        try:
            task = HousekeepingTask.objects.select_related("room").get(id=pk)
        except HousekeepingTask.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)

        data = request.data.copy()
        new_status = data.get("status")

        if new_status == "in_progress" and not task.started_at:
            task.started_at = timezone.now()
        elif new_status == "cleaned":
            task.completed_at = timezone.now()
            if task.room.status != "Occupied":
                task.room.status = "Cleaning"
                task.room.save(update_fields=["status"])

        serializer = HousekeepingTaskSerializer(task, data=data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(HousekeepingTaskSerializer(updated).data)
        return Response(serializer.errors, status=400)


class HousekeepingTaskInspectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            task = HousekeepingTask.objects.select_related("room").get(id=pk)
        except HousekeepingTask.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)

        approved = request.data.get("approved", True)
        notes = request.data.get("notes", "")

        task.inspected_by_username = request.user.username or "Supervisor"
        task.inspected_at = timezone.now()
        task.inspection_notes = notes

        if approved:
            task.status = "inspected"
            if task.room.status != "Occupied":
                task.room.status = "Available"
                task.room.save(update_fields=["status"])
            RoomHistory.objects.create(
                room=task.room,
                event_type="cleaning",
                notes=f"Inspection passed: {task.get_task_type_display()} by {request.user.username}",
            )
        else:
            task.status = "failed"
            if task.room.status != "Occupied":
                task.room.status = "Cleaning"
                task.room.save(update_fields=["status"])

        task.save()
        return Response(HousekeepingTaskSerializer(task).data)


class MinibarItemsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        room_id = request.query_params.get("room_id")
        qs = MinibarItem.objects.select_related("room", "item").all()
        if room_id:
            qs = qs.filter(room_id=room_id)
        serializer = MinibarItemSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        data["last_checked_by"] = request.user.username or "Staff"
        serializer = MinibarItemSerializer(data=data)
        if serializer.is_valid():
            item = serializer.save()
            return Response(MinibarItemSerializer(item).data, status=201)
        return Response(serializer.errors, status=400)


class MinibarCandidateInventoryView(APIView):
    """Returns inventory items suitable for minibar (drinks, snacks, etc.)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = InventoryItem.objects.filter(
            models.Q(category__category_type="f_and_b") | models.Q(selling_price__gt=0)
        ).order_by("name")
        data = [
            {
                "id": it.id,
                "name": it.name,
                "item_code": it.item_code,
                "unit": it.unit,
                "current_stock": float(it.current_stock),
                "selling_price": float(it.selling_price or 0.0),
                "unit_cost": float(it.unit_cost or 0.0),
            }
            for it in items
        ]
        return Response(data)


class MinibarConsumeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        room_id = request.data.get("room_id")
        items_consumed = request.data.get("items", [])
        notes = request.data.get("notes", "Minibar consumption")

        if not room_id or not items_consumed:
            return Response({"error": "room_id and items are required."}, status=400)

        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)

        reservation = Reservation.objects.filter(
            room=room, status="checked_in"
        ).order_by("-check_in_date").first()

        created_charges = []
        with transaction.atomic():
            for entry in items_consumed:
                item_id = entry.get("item_id")
                qty = Decimal(str(entry.get("quantity", 1)))
                if qty <= 0:
                    continue

                try:
                    inv_item = InventoryItem.objects.select_for_update().get(id=item_id)
                except InventoryItem.DoesNotExist:
                    continue

                price = Decimal(str(entry.get("price") or inv_item.selling_price or "0.00"))
                line_total = price * qty

                if reservation:
                    folio_charge = FolioCharge.objects.create(
                        reservation=reservation,
                        description=f"Minibar: {inv_item.name} (x{qty})",
                        amount=line_total,
                        added_by=request.user.username or "Housekeeping",
                        inventory_item=inv_item,
                        quantity=qty,
                    )
                    created_charges.append({
                        "id": folio_charge.id,
                        "description": folio_charge.description,
                        "amount": float(folio_charge.amount),
                        "quantity": float(qty),
                    })

                inv_item.current_stock = max(Decimal("0.00"), inv_item.current_stock - qty)
                inv_item.save(update_fields=["current_stock"])

                StockTransaction.objects.create(
                    item=inv_item,
                    transaction_type="issuance",
                    quantity=qty,
                    unit_cost=inv_item.unit_cost,
                    destination_room=room.room_number,
                    notes=f"{notes} — Room {room.room_number}",
                    logged_by_username=request.user.username or "Housekeeping",
                )

                mb_record = MinibarItem.objects.filter(room=room, item=inv_item).first()
                if mb_record:
                    mb_record.current_quantity = max(0, mb_record.current_quantity - int(qty))
                    mb_record.last_checked_by = request.user.username or "Housekeeping"
                    mb_record.save(update_fields=["current_quantity", "last_checked_by", "last_restocked_at"])

        return Response({
            "message": "Minibar consumption recorded successfully.",
            "room_number": room.room_number,
            "reservation_id": reservation.id if reservation else None,
            "guest_name": reservation.guest_name if reservation else "No Active Guest",
            "charges": created_charges,
        })


class LostAndFoundListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = LostAndFoundItem.objects.select_related("room").all()
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        serializer = LostAndFoundItemSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        data.setdefault("found_by_name", request.user.username or "Staff")
        serializer = LostAndFoundItemSerializer(data=data)
        if serializer.is_valid():
            item = serializer.save()
            return Response(LostAndFoundItemSerializer(item).data, status=201)
        return Response(serializer.errors, status=400)


class LostAndFoundClaimView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            item = LostAndFoundItem.objects.get(id=pk)
        except LostAndFoundItem.DoesNotExist:
            return Response({"error": "Item not found."}, status=404)

        item.claimed_by = request.data.get("claimed_by", "")
        item.claimant_phone = request.data.get("claimant_phone", "")
        item.claimed_at = timezone.now()
        item.status = "claimed"
        if request.data.get("notes"):
            item.notes = (item.notes + "\n" if item.notes else "") + f"Claim notes: {request.data.get('notes')}"
        item.save()
        return Response(LostAndFoundItemSerializer(item).data)


