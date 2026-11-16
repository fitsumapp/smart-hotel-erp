# ACRMA HOTEL ERP — INVENTORY MODULE FUNCTIONAL AUDIT

**Date:** 2026-11-12  
**Target Architecture:** Django 5.2 / DRF | React 19 | PostgreSQL 16 (`hotel_erp_staging`)  
**Branch:** `development` (HEAD: `97d560c`)  
**Audit Scope:** Complete Inventory Lifecycle, Stock Balances, Valuation, Procurement, Transfers, Waste, Expiry, POS Integration, Accounting GL Entries, and Frontend Portals.

---

## 1. Executive Summary

The ACRMA Hotel ERP inventory system possesses strong core foundations in models and services:
- An authoritative stock mutation engine (`record_stock_change` in `hotel/integrity.py`) with FIFO/FEFO batch allocation, multi-layer batch consumption, and immutable audit logs.
- Decoupled POS payment settlement (completed in Batch 1) with `UnfulfilledStockDeduction` exception recording and zero payment rollbacks.
- Robust procurement workflow with 3-way invoice matching (`hotel/procurement.py`), RFQs, quotations, and GRN dock intake.
- Blind and visible physical stocktaking with two-phase recount discrepancies and automated variance journal entries (`hotel/stocktaking.py`).
- Persistent expiry alerts and batch quarantine safeguards (`hotel/inventory.py`).

However, the audit reveals critical functional, architectural, and frontend gaps:
1. **Unbounded Stock Ledger API & Missing Pagination:** The stock transaction ledger endpoint `/users/stock-transactions/` serves raw unpaginated querysets (due to `V1PageNumberPagination` only activating on `/api/v1/`). Frontend `InventoryDashboard.js` directly expects arrays and lacks server-side pagination, date range filtering, and location filtering.
2. **Transfer Mutation Disconnect & Missing Ledger Entries:** `hotel/transfers.py` mutates `BatchLocationBalance` and `ItemLocationBalance` directly, but never writes corresponding `StockTransaction` audit records for transfer dispatches and receipts. Furthermore, transit damage decrements `current_stock` directly with `F()` without writing a `StockTransaction` for the loss, causing a permanent divergence between `expected_stock()` and `current_stock`.
3. **Missing Stock Transfer UI in React Frontend:** Although the backend provides full endpoints for Requisition, Dispatch, Receipt, and Cancellation (`StockTransferViewSet`), there is **no user interface in the React application** for warehouse/department transfers.
4. **Missing Opening Stock Bulk Import:** Opening stock entry via CSV/Excel with batch, expiry, location, and cost valuation is missing from both backend and frontend.
5. **PO PDF Generation & Supplier Dispatch:** Purchase order approval and GRN work, but there is no server-side PO PDF generation endpoint or printable PO format for vendor dispatch.
6. **Stock Valuation & GL Reconciliation Reporting:** While transactions post to GL accounts 1300, 2010, 5000, 5010, and 5020, there is no unified server-side stock movement report (Opening + Purchases + Transfers In - Transfers Out - Sales - Waste ± Adjustments = Closing) and no automated Inventory-to-GL reconciliation report comparing Account 1300 balance against batch valuation.

---

## 2. Detailed Audit by Functional Area

### 2.1 Item, Category, Unit & Supplier Management
- **Status:** **Fully Implemented & Stable**
- **Models:** `InventoryCategory`, `Supplier`, `InventoryItem` in `hotel/models.py`.
- **Backend API:** `InventoryCategoryViewSet`, `SupplierViewSet`, `InventoryItemViewSet`.
- **Frontend:** `InventoryDashboard.js` (tabs: `items`, `categories`, `suppliers`).
- **Audit Findings:**
  - CRUD operations, search, and category-level min/max stock thresholds function cleanly.
  - Multi-category supply relationships work via `Supplier.supplied_categories`.
  - Item deactivation and soft protection work properly.

---

### 2.2 Stock Locations & Warehouse Management
- **Status:** **Partially Implemented**
- **Models:** `StockLocation` (code, name, location_type, is_active, custodian).
- **Backend API:** `StockLocationViewSet` (`/api/users/locations/`).
- **Frontend:** Locations are fetched in `InventoryDashboard.js` for dropdowns, but there is no dedicated Location Management screen or safe deactivation/custodian assignment UI.
- **Defects & Gaps:**
  - `StockLocationViewSet.destroy()` allows hard-deleting a location if not constrained, which could fail violently or leave orphan records. Needs safe deactivation (`is_active=False`).
  - No location-level inventory dashboard showing on-hand stock and valuation per store/kitchen/bar.

---

### 2.3 Stock Ledger, Pagination & Immutability
- **Status:** **Partially Implemented / High Concurrency & Memory Risk**
- **Models:** `StockTransaction` (`hotel/models.py:1099`).
- **Backend API:** `StockTransactionViewSet` in `apps/inventory/views.py`.
- **Selector:** `select_stock_transactions` in `apps/inventory/selectors.py`.
- **Frontend:** Tab `ledger` in `InventoryDashboard.js`.
- **Defects & Gaps:**
  - **No Server-Side Pagination on Default Route:** `core/api.py:V1PageNumberPagination` explicitly bypasses pagination if the request path does not start with `/api/v1/`. Because frontend calls `/users/stock-transactions/`, all transactions are dumped into memory in a single response.
  - **Unstable Ordering:** `select_stock_transactions` orders by `-timestamp` only. Needs deterministic tie-breaker `-id` for stable pagination across transactions with the exact same millisecond.
  - **Missing Query Filters:** No filtering by date range (`start_date`, `end_date`), location (`location_id`), or text search across item name, reference number, or notes.
  - **Frontend Table Crash Risk:** In `InventoryDashboard.js:231`, `setLedger(ledgerRes.data || [])` assumes an array. If paginated data `{count, results}` is returned without adaptation, `ledger.map()` crashes.

---

### 2.4 Stock Transfer Management (Two-Phase Custody)
- **Status:** **Backend Implemented / Missing Ledger Audit & Missing Frontend UI**
- **Models:** `StockTransfer`, `StockTransferItem` (`hotel/models.py:1547`).
- **Service:** `hotel/transfers.py` (`request_stock_transfer`, `dispatch_stock_transfer`, `receive_stock_transfer`, `cancel_stock_transfer`).
- **Backend API:** `StockTransferViewSet` (`/api/users/transfers/`).
- **Frontend:** **Completely Missing** (no transfer center or requisition screen exists in React).
- **Defects & Gaps:**
  - **Missing Audit Records:** `dispatch_stock_transfer` and `receive_stock_transfer` update `BatchLocationBalance` and `ItemLocationBalance` directly, but **do not write `StockTransaction` entries** representing the movement between locations.
  - **Divergence on Transit Damage:** In `receive_stock_transfer:289`, damaged stock is deducted via `InventoryItem.objects.filter(pk=it.item.pk).update(current_stock=F("current_stock") - qty_dam)` and creates an `InventoryWasteRecord`, but **never calls `record_stock_change(transaction_type="loss")` or creates a `StockTransaction`**. As a result, `expected_stock()` differs from `current_stock`.
  - **Missing Frontend Interface:** Storekeepers and department heads have no way to request, dispatch, or acknowledge receipt of transfers from the browser without using Django admin or API tools.

---

### 2.5 Opening Stock & Data Intake
- **Status:** **Missing Bulk Intake**
- **Models:** `InventoryItem.opening_stock` (editable=False).
- **Backend API:** Missing opening stock batch import endpoint.
- **Frontend:** Missing CSV/Excel upload modal for initial stocktake.
- **Defects & Gaps:**
  - Initial hotel go-live requires importing opening stock balances with location, batch number, expiry date, unit cost, and total value.
  - No validation or duplicate detection for opening stock intake.

---

### 2.6 Procurement & Goods Receiving (GRN)
- **Status:** **Fully Implemented Backend / High Frontend Coverage**
- **Models:** `ProcurementApprovalPolicy`, `PurchaseRequisition`, `RequestForQuotation`, `SupplierQuotation`, `PurchaseOrder`, `GoodsReceiptNote`, `SupplierInvoice`.
- **Services:** `hotel/procurement.py` (comprehensive 3-way matching and approval tier engine).
- **Frontend:** `ProcurementCenter.jsx`, `RequisitionDesk.jsx`, `RfqDesk.jsx`, `QuotationDesk.jsx`, `AwardMatrixDesk.jsx`, `GrnDesk.jsx`, `InvoiceMatchingDesk.jsx`.
- **Defects & Gaps:**
  - Purchase order PDF generation is missing. Approvers and procurement officers cannot generate a printable or downloadable PDF purchase order to dispatch to suppliers.
  - Spot purchase direct intake without multi-day RFQ/Quotation workflow needs a streamlined one-click PO->GRN path.

---

### 2.7 Batch, FIFO/FEFO, Expiry & Spoilage Control
- **Status:** **Fully Implemented Backend & Good Frontend Coverage**
- **Models:** `StockBatch`, `BatchLocationBalance`, `StockBatchConsumption`, `InventoryExpiryAlert`, `InventoryWasteRecord`.
- **Services:** `hotel/integrity.py`, `hotel/inventory.py`.
- **Frontend:** `InventoryDashboard.js` (batches list, expiry verification modal, persistent alert banner and evaluation, waste & loss desk with supervisor approvals).
- **Audit Findings:**
  - Strict FIFO/FEFO batch allocation functions reliably during sales, issuance, and transfer dispatch.
  - Expired and unverified legacy perishable batches are strictly locked out from POS auto-deductions and issuance.
  - Waste management records losses to Account 5010 and supports supervisor approval/rejection.

---

### 2.8 Physical Stocktaking (Dual Mode: Blind & Visible)
- **Status:** **Fully Implemented Backend & Dedicated Frontend**
- **Models:** `StocktakeSession`, `StocktakeCount`, `StocktakeSchedule`.
- **Services:** `hotel/stocktaking.py`.
- **Frontend:** `StocktakeCenter.jsx`, `StocktakeCountDesk.jsx`, `StocktakeVarianceDesk.jsx`.
- **Audit Findings:**
  - Blind mode hides expected system counts from count staff; visible mode displays them for fast audits.
  - Two-phase recount discrepancies allow supervisor-requested recounts before variance sign-off.
  - Session approval automatically generates adjustment stock transactions and posts balanced GL entries to Account 5020 (Variance Expense) and 1300 (Inventory Asset).

---

### 2.9 POS Inventory Integration & Shortage Decoupling
- **Status:** **Fully Stabilized in Batch 1**
- **Models:** `Order.inventory_deduction_status`, `UnfulfilledStockDeduction`.
- **Services:** `apps/orders/services.py:finalize_paid_order`.
- **Tests:** `test_pos_payment_reliability.py` (7/7 passed), `test_cross_module_inventory_integration.py` (10/10 passed).
- **Audit Findings:**
  - Shortages no longer reverse payments; customers can pay via Cash, Room Charge, or Chapa regardless of ingredient stock.
  - Shortages are captured durably in `UnfulfilledStockDeduction`.
  - Savepoint atomicity ensures multi-ingredient recipes do not leave corrupted or partial stock balances.
  - Webhook idempotency and double-spend protection are preserved.

---

### 2.10 Inventory Valuation & Accounting Integration
- **Status:** **Partially Implemented Backend / Missing Reporting Interface**
- **Chart of Accounts:**
  - `1000`: Cash / Bank
  - `1200`: Accounts Receivable (Guest Folio)
  - `1300`: Inventory Asset (General Ledger balance)
  - `2000`: Accounts Payable
  - `2010`: Goods Received Not Invoiced (GRNI Accrual)
  - `4000`: Sales Revenue (Food & Beverage)
  - `5000`: Cost of Goods Sold (COGS)
  - `5010`: Spoilage, Breakage & Waste Expense
  - `5020`: Stocktaking Variance Expense
- **Defects & Gaps:**
  - No server-side monthly stock movement report calculating Opening Balance + Purchases + Inward Transfers - Outward Transfers - POS Sales - Waste ± Adjustments = Closing Balance.
  - No server-side Inventory-to-GL reconciliation tool comparing General Ledger Account 1300 against total batch inventory valuation (`sum(current_quantity * unit_cost)`).

---

## 3. Summary of Confirmed Defects & Architecture Risks

| Defect ID | Severity | Area | Description |
| :--- | :--- | :--- | :--- |
| **DEF-STX-01** | High | Stock Ledger API | Unbounded memory dump on `/users/stock-transactions/`. Missing server-side pagination, date range filtering, location filtering, and stable ordering. |
| **DEF-TRF-01** | High | Stock Transfers | `hotel/transfers.py` modifies location balances without logging `StockTransaction` ledger entries. Transit damage modifies `current_stock` directly without creating a `StockTransaction`, breaking stock reconciliation. |
| **DEF-TRF-02** | High | Frontend | Complete absence of a Stock Transfer UI in React. Staff cannot requisition, dispatch, or receive stock transfers from the browser. |
| **DEF-OPN-01** | Medium | Opening Stock | Missing bulk CSV/Excel opening stock intake endpoint and validation engine. |
| **DEF-PO-01** | Medium | Procurement | Missing Purchase Order PDF generation and export for supplier dispatch. |
| **DEF-REP-01** | High | Reporting & Valuation | Missing server-side Monthly Stock Movement Report and Inventory-to-GL Reconciliation API. |
| **DEF-LOC-01** | Medium | Stock Locations | Missing safe deactivation (`is_active=False`) and location-level balance views. |

---

## 4. Remediation Plan Across Phases 1 to 6

- **Phase 1: Stock Ledger and Data Integrity:** Add bounded server-side pagination (`V1PageNumberPagination` / custom pagination for legacy endpoints), date/location/type filtering, stable ordering (`-timestamp, -id`), and fix `hotel/transfers.py` to record `StockTransaction` for transfers and transit damage.
- **Phase 2: Location and Transfer Management:** Build the React Stock Transfer Center (`StockTransferCenter.jsx`), add location management, and wire dispatch/receiving/damage workflows with full audit logging.
- **Phase 3: Opening Stock and Procurement:** Implement CSV opening stock bulk import with batch/expiry/location validation, unit conversions, and Purchase Order PDF generation.
- **Phase 4: Stock Control:** Enhance batch management, minibar replenishment, and verification.
- **Phase 5: Reporting and Accounting:** Build server-side Monthly Stock Movement Report API and Inventory-to-GL Reconciliation report.
- **Phase 6: Complete Inventory QA:** Run full PostgreSQL test suites, verify browser workflows, frontend build/lint, and produce the final delivery report.

