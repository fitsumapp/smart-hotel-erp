from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MaintenanceLogDetailView, MaintenanceLogView, RoomHistoryView, RoomViewSet,
    HousekeepingTaskListView, HousekeepingTaskDetailView, HousekeepingTaskInspectView,
    MinibarItemsView, MinibarCandidateInventoryView, MinibarConsumeView,
    LostAndFoundListView, LostAndFoundClaimView,
)

router = DefaultRouter()
router.register(r"rooms", RoomViewSet, basename="room")

urlpatterns = [
    path("rooms/<int:room_id>/maintenance/", MaintenanceLogView.as_view(), name="room-maintenance"),
    path("maintenance/<int:log_id>/", MaintenanceLogDetailView.as_view(), name="maintenance-detail"),
    path("rooms/<int:room_id>/history/", RoomHistoryView.as_view(), name="room-history"),
    # Housekeeping & Minibar Management (Phase 2)
    path("housekeeping/tasks/", HousekeepingTaskListView.as_view(), name="hk-tasks-list"),
    path("housekeeping/tasks/<int:pk>/", HousekeepingTaskDetailView.as_view(), name="hk-tasks-detail"),
    path("housekeeping/tasks/<int:pk>/inspect/", HousekeepingTaskInspectView.as_view(), name="hk-tasks-inspect"),
    path("minibar/items/", MinibarItemsView.as_view(), name="minibar-items"),
    path("minibar/candidates/", MinibarCandidateInventoryView.as_view(), name="minibar-candidates"),
    path("minibar/consume/", MinibarConsumeView.as_view(), name="minibar-consume"),
    path("lost-and-found/", LostAndFoundListView.as_view(), name="lost-and-found-list"),
    path("lost-and-found/<int:pk>/claim/", LostAndFoundClaimView.as_view(), name="lost-and-found-claim"),
] + router.urls
