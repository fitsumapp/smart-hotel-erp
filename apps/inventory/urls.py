from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BatchLocationBalanceViewSet,
    GoodsReceiptNoteViewSet,
    InventoryCategoryViewSet,
    InventoryDashboardStatsView,
    InventoryExpiryAlertViewSet,
    InventoryItemViewSet,
    InventoryWasteRecordViewSet,
    ItemLocationBalanceViewSet,
    ProcurementApprovalPolicyViewSet,
    PurchaseOrderViewSet,
    PurchaseRequisitionViewSet,
    RecipeBOMViewSet,
    RequestForQuotationViewSet,
    StockBatchViewSet,
    StockLocationViewSet,
    StocktakeScheduleViewSet,
    StocktakeSessionViewSet,
    StockTransactionViewSet,
    StockTransferViewSet,
    SupplierInvoiceViewSet,
    SupplierQuotationViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register(r"inventory-categories", InventoryCategoryViewSet, basename="inventorycategory")
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"inventory-items", InventoryItemViewSet, basename="inventoryitem")
router.register(r"stock-transactions", StockTransactionViewSet, basename="stocktransaction")
router.register(r"recipes", RecipeBOMViewSet, basename="recipebom")
router.register(r"waste-records", InventoryWasteRecordViewSet, basename="wasterecord")
router.register(r"locations", StockLocationViewSet, basename="stocklocation")
router.register(r"batches", StockBatchViewSet, basename="stockbatch")
router.register(r"batch-location-balances", BatchLocationBalanceViewSet, basename="batchlocationbalance")
router.register(r"item-location-balances", ItemLocationBalanceViewSet, basename="itemlocationbalance")
router.register(r"transfers", StockTransferViewSet, basename="stocktransfer")

# Phase 1.4: Configurable Procurement & 3-Way Matching
router.register(r"procurement/policies", ProcurementApprovalPolicyViewSet, basename="procurementpolicy")
router.register(r"procurement/requisitions", PurchaseRequisitionViewSet, basename="purchaserequisition")
router.register(r"procurement/rfqs", RequestForQuotationViewSet, basename="rfq")
router.register(r"procurement/quotations", SupplierQuotationViewSet, basename="supplierquotation")
router.register(r"rfqs", RequestForQuotationViewSet, basename="rfq_alias")
router.register(r"quotations", SupplierQuotationViewSet, basename="supplierquotation_alias")
router.register(r"procurement/orders", PurchaseOrderViewSet, basename="purchaseorder")
router.register(r"procurement/grns", GoodsReceiptNoteViewSet, basename="goodsreceiptnote")
router.register(r"procurement/invoices", SupplierInvoiceViewSet, basename="supplierinvoice")

# Phase 1.5: Dual-Mode Physical Stocktaking (Blind & Visible)
router.register(r"stocktaking/sessions", StocktakeSessionViewSet, basename="stocktakesession")
router.register(r"stocktaking-sessions", StocktakeSessionViewSet, basename="stocktakesession_alias")
router.register(r"stocktaking/schedules", StocktakeScheduleViewSet, basename="stocktakeschedule")

# Persistent Expiry Alerts & Batch Safeguards
router.register(r"inventory/expiry-alerts", InventoryExpiryAlertViewSet, basename="inventoryexpiryalert")

urlpatterns = [path("inventory/dashboard-stats/", InventoryDashboardStatsView.as_view(), name="inventory-dashboard-stats")] + router.urls
