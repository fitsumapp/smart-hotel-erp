from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MaintenanceLogDetailView, MaintenanceLogView, RoomHistoryView, RoomViewSet

router = DefaultRouter()
router.register(r"rooms", RoomViewSet, basename="room")

urlpatterns = [
    path("rooms/<int:room_id>/maintenance/", MaintenanceLogView.as_view(), name="room-maintenance"),
    path("maintenance/<int:log_id>/", MaintenanceLogDetailView.as_view(), name="maintenance-detail"),
    path("rooms/<int:room_id>/history/", RoomHistoryView.as_view(), name="room-history"),
] + router.urls
