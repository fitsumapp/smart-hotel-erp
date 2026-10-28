from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryCategoryViewSet,
    InventoryDashboardStatsView,
    InventoryItemViewSet,
    InventoryWasteRecordViewSet,
    RecipeBOMViewSet,
    StockTransactionViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register(r"inventory-categories", InventoryCategoryViewSet, basename="inventorycategory")
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"inventory-items", InventoryItemViewSet, basename="inventoryitem")
router.register(r"stock-transactions", StockTransactionViewSet, basename="stocktransaction")
router.register(r"recipes", RecipeBOMViewSet, basename="recipebom")
router.register(r"waste-records", InventoryWasteRecordViewSet, basename="wasterecord")

urlpatterns = [path("inventory/dashboard-stats/", InventoryDashboardStatsView.as_view(), name="inventory-dashboard-stats")] + router.urls
