# ACRMA HOTEL ERP — INVENTORY MODULE INDEPENDENT ACCEPTANCE VERIFICATION

**Document Version:** 1.1.0  
**Verification Date:** November 14, 2026  
**Auditor / Agent:** Independent Verification Agent (Google DeepMind Team)  
**Target Repository:** `fitsumapp/smart-hotel-erp`  
**Active Working Branch:** `development` (HEAD: `97d560c77f80799035b89633d9e589d0937808cb`)  
**Target Database:** Local PostgreSQL 16 (`hotel_erp_staging` on `localhost:5432`)  
**Production Isolation:** Verified strictly isolated (Neon production was neither connected to nor modified; `DATABASE_URL` was unassigned)

---

## 1. EXECUTIVE SUMMARY & ACCEPTANCE VERDICT

### Acceptance Verdict: **CONDITIONAL ACCEPTANCE WITHHELD (NOT READY FOR 100% SIGN-OFF)**

The previously submitted `ACRMA_INVENTORY_MODULE_FINAL_REPORT.md` claimed **100% completion and operational readiness**, asserting that all 199 inventory unit/integration tests passed and all inventory workflows were fully stable.

An independent end-to-end verification was conducted against the live running application (`http://localhost:3000`), the Django REST API (`http://localhost:8000`), and the local PostgreSQL database (`hotel_erp_staging`).

### Key Verification Findings
1. **Core UI & Persistence Succeeded:** The core local failures originally reported (category creation failure and loss of stock operations upon reload) were **re-tested and verified working**. Categories, inventory items, suppliers, stock adjustments, two-phase stock transfers, and blind physical stocktaking now reliably persist across browser reloads.
2. **Defect 1 Reproduced in Procurement GRN Workflow (FAIL):** In the Procurement Center (`/procurement` -> "Receive Goods (GRN)" modal for Purchase Orders), receiving goods fails with **HTTP 400 Bad Request** (`"At least one unit must be received or rejected for '<Item Name>'"`). This defect is caused by an API parameter naming mismatch: the frontend React modal submits `received_quantity`, whereas the backend service `receive_goods_receipt_note()` strictly looks for `quantity_received`.
3. **Defect 2 Reproduced in Waste Recording (FAIL):** In the Inventory Dashboard (`/inventory` -> "Waste & Loss" tab), attempting to register a waste entry fails with a native browser error: `"Unable to connect to the server. Please check your network connection.."`. The browser console confirms a CORS preflight failure: `Access-Control-Allow-Headers` in Django does not permit the `idempotency-key` request header sent by the frontend. The record is blocked and never committed to the database.
4. **Automated Test Suite Claim vs. Reality (11 Errors):** The stabilization report claimed `199 / 199 PASSED (100% pass rate)`. However, executing `manage.py test apps.inventory.tests --noinput` revealed **11 ERRORS out of 199 tests** (188 passed, 11 errors). The 11 failures are caused by a hardcoded `StockLocation.objects.create(name="Main Central Store", code="STORE-MAIN", ...)` in the `setUp()` methods of three test files (`test_minibar_and_stock_control_phase4.py`, `test_opening_stock_and_procurement_phase3.py`, and `test_reporting_and_gl_reconciliation_phase5.py`), triggering a `psycopg2.errors.UniqueViolation` against migration `0043`'s seeded location.
5. **Sub-ledger Discrepancy in Staging Data:** An audit of all 27 inventory items in the staging database revealed that **13 items have valuation discrepancies** between `InventoryItem.current_stock`, `StockBatch.current_quantity`, and `ItemLocationBalance.quantity`. These 13 items carry legacy stock that was never backfilled with corresponding batch records or location balances.
6. **Double-Entry Equilibrium Preserved (PASS):** All **100 existing Journal Entries** in the database strictly balance ($\sum \text{Debits} == \sum \text{Credits}$).
7. **GL Reconciliation Detection (PASS):** The GL reconciliation service correctly identified the discrepancy between GL Account 1300 (`119,260.00 ETB`), Sub-ledger Batch Valuation (`196,780.00 ETB`), and Item Master Valuation (`298,390.00 ETB`), flagging `is_reconciled: False` and `status: "discrepancy_detected"`.
8. **POS Payment Decoupling (PASS):** All 71 tests in `apps.orders.tests` passed (100%), confirming that customer payments succeed without rollback when kitchen ingredients are depleted, durably logging `UnfulfilledStockDeduction` records.

---

## 2. GIT AND IMPLEMENTATION AUDIT

### 2.1 Branch and HEAD State
* **Active Branch:** `development` (Up to date with `origin/development`)
* **Current HEAD Commit:** `97d560c77f80799035b89633d9e589d0937808cb`
* **Commit Message:** `fix(frontend): resolve ESLint CI warnings and update browserslist database`
* **Author:** `innovatorAbel <afikadu333@gmail.com>`

### 2.2 Uncommitted & Modified Files
A total of **16 modified files** (1,585 insertions, 102 deletions) and several untracked test/documentation files exist in the working tree:

| File Path | Status | Impact / Purpose |
| :--- | :--- | :--- |
| `apps/inventory/selectors.py` | Modified | Inventory item query filters, location scoping |
| `apps/inventory/services.py` | Modified | Stock operations, FEFO allocation, GL reconciliation, opening stock |
| `apps/inventory/views.py` | Modified | ViewSets for categories, items, batches, transfers, GL reports |
| `apps/inventory/urls.py` | Modified | Registered REST routers for procurement, stocktaking, transfers |
| `apps/orders/models.py` | Modified | Added `UnfulfilledStockDeduction` model references |
| `apps/orders/services.py` | Modified | Decoupled POS payment from stock shortage (durably records shortages) |
| `apps/rooms/urls.py` & `views.py` | Modified | Minibar consumption and restocking API endpoints |
| `hotel-frontend/src/App.js` | Modified | Routes for transfers, stocktaking, procurement |
| `hotel-frontend/src/Sidebar.js` | Modified | Sidebar links to Procurement, Transfers, Stocktaking |
| `hotel-frontend/src/pages/InventoryDashboard.js` | Modified | Comprehensive 10-tab inventory management dashboard |
| `hotel/admin.py` | Modified | Django admin registrations for stock batches and locations |
| `hotel/inventory.py` | Modified | Core inventory transactions |
| `hotel/models.py` | Modified | Batch, location balance, transfer, and transaction models |
| `hotel/transfers.py` | Modified | Multi-location stock transfer logic |
| `hotel/migrations/0051_*.py` | Untracked | Schema migration for unfulfilled stock deductions |
| `hotel/migrations/0052_*.py` | Untracked | Schema migration for stock transaction types |

### 2.3 Migration Verification
Database migration inspection via `python manage.py showmigrations hotel` confirmed:
* `[X] 0051_unfulfilled_stock_deduction_and_order_status` — **APPLIED**
* `[X] 0052_alter_stocktransaction_transaction_type` — **APPLIED**
* Zero pending unapplied migrations across all Django applications.

### 2.4 Service, Endpoint, and Component Existence
All reported backend services, API endpoints, and frontend components were confirmed present:
* **Endpoints:** `/api/users/inventory-items/`, `/api/users/inventory-categories/`, `/api/users/suppliers/`, `/api/users/batches/`, `/api/users/transfers/`, `/api/users/procurement/orders/`, `/api/users/inventory-reports/gl-reconciliation/`.
* **Frontend Components:**
  * `hotel-frontend/src/pages/InventoryDashboard.js` (10 functional tabs).
  * `hotel-frontend/src/pages/transfers/StockTransferCenter.jsx`.
  * `hotel-frontend/src/pages/procurement/ProcurementCenter.jsx`, `GrnDesk.jsx`, `RfqDesk.jsx`.
  * `hotel-frontend/src/pages/stocktaking/StocktakeDashboard.jsx`.

---

## 3. LIVE BROWSER VERIFICATION & FAILURE REPRODUCTION

Verification was conducted on the live React frontend (`http://localhost:3000`) authenticated as `admin_proc2` (Role: `ADMIN`) using a dedicated Chrome session connected via Chrome DevTools Protocol.

### 3.1 Category Lifecycle & Persistence
* **Action:** Navigated to `http://localhost:3000/dashboard` -> `Inventory Control` -> `Category List` tab. Clicked `Add Category`. Submitted:
  * Name: `Verification Category Alpha`
  * Type: `Food & Beverage (F&B)`
  * Description: `Automated QA Verification Category`
* **Result:** **PASS**. The category was created immediately via `POST /api/users/inventory-categories/` (HTTP 201 Created).
* **Browser Reload Persistence:** **PASS**. Full page reload was executed (`navigate_page(type="reload")`). `Verification Category Alpha` persisted in the table with correct item counts (`0 items`) and active status.

### 3.2 Inventory Item Lifecycle & Assignment
* **Action:** Navigated to `Ingredients & Stock List` tab -> Clicked `Add New Item`. Submitted:
  * Name: `Verification Item Alpha`
  * SKU / Code: `VERIF-ITEM-001`
  * Category: `Verification Category Alpha`
  * Unit: `Pieces (pcs)`
  * Reorder Level: `10`
  * Cost Price: `50.00 ETB`
  * Selling Price: `75.00 ETB`
* **Result:** **PASS**. Item created with `current_stock = 0.00 pcs` and automatically categorized under Low Stock Warnings.
* **Browser Reload Persistence:** **PASS**. Item persisted after page reload.
* **Editing Verification:** **PASS**. Clicked `Edit`, updated name to `Verification Item Alpha Edited`, saved. Update reflected immediately and persisted across reload.
* **Deletion Verification:** **PASS**. Clicked `Delete`, accepted browser confirmation dialog. Item was cleanly deleted from both database and table.

### 3.3 Supplier Lifecycle
* **Action:** Navigated to `Supplier List` tab -> Clicked `Add Supplier`. Submitted:
  * Supplier Name: `Verification Supplier Ltd`
  * Contact Person: `John Verifier`
  * Phone: `+251911223344`
  * Email: `verifier@example.com`
* **Result:** **PASS**. Supplier created successfully (`POST /api/users/suppliers/` HTTP 201 Created). Active Supplier counter incremented from 13 to 14.
* **Browser Reload Persistence:** **PASS**. Supplier persisted across page reload.
* **Editing Verification:** **PASS**. Edited Contact Person to `John Verifier Edited` and saved; persisted across reload.

### 3.4 Stock Adjustment & Stock Ledger
* **Action:** Navigated to `Stock Actions` tab -> Selected item `Challenge Test Item (CHAL-ITEM-01)` (baseline stock: `10.00 pcs`), Location: `Main Central Store (STORE-MAIN)`, Quantity: `10 pcs`, Unit Cost: `50.00 ETB`, Supplier: `Verification Supplier Ltd`. Clicked `Record Stock-In`.
* **Result:** **PASS**. Browser alert `Stock Received Successfully!` was displayed.
* **Stock Quantity Verification:** Stock balance increased from `10.00 pcs` to `20.00 pcs` (Valuation: `+500.00 ETB`).
* **Stock Ledger Audit Trail:** Navigated to `Stock Ledger` tab. A new `StockTransaction` record was verified:
  * Type: `Stock-In` | Quantity: `+10.00 pcs` | Valuation: `500.00 ETB` | Location: `Main Central Store` | Logged By: `admin_proc2`.
* **Browser Reload Persistence:** **PASS**. Persisted after full reload.

### 3.5 Goods Receipt Note (GRN) & Receiving Workflows
* **Direct Dock Intake (`Batches & Expiry` tab):** **PASS**.
  * Created new batch intake for `Challenge Test Item`: `15 pcs` at `50.00 ETB` (`750.00 ETB`), Batch: `BATCH-VERIF-002`, Ref: `GRN-20261114-002`, Location: `Main Central Store`.
  * Current stock updated from `20.00 pcs` to `35.00 pcs`. Global inventory valuation updated from `297,640.00 ETB` to `298,390.00 ETB`.
  * Total batches counter incremented from 40 to 41 (Active: 37 to 38).
  * Stock Ledger recorded transaction with batch and invoice notes.
* **Procurement Center PO Receiving Modal (`/procurement`):** **FAIL (REPRODUCED DEFECT 1)**.
  * Navigated to `Procurement & Sourcing` -> Goods Receiving Desk -> Selected pending Purchase Order `PO-20261104-D59E15`.
  * In the modal, selected Location `Main Central Store`, entered `50` kg for `Pure Butter 82% Fat`, Batch `BATCH-2611-119`. Clicked `Confirm Delivery & Post GRNI`.
  * **Network Request:** `POST http://localhost:8000/api/v1/procurement/orders/2/receive-grn/`
  * **Payload:**
    ```json
    {
      "location_id": 1,
      "notes": "Received in good condition and verified against delivery note.",
      "items": [
        {
          "po_item_id": 2,
          "received_quantity": "50.0000",
          "batch_number": "BATCH-2611-119",
          "expiry_date": null
        }
      ]
    }
    ```
  * **HTTP Status:** `400 Bad Request`
  * **Response Body:**
    ```json
    {
      "error": "At least one unit must be received or rejected for 'Pure Butter 82% Fat'."
    }
    ```
  * **Browser Console:** `Failed to load resource: the server responded with a status of 400 (Bad Request)`
  * **Database Verification:** Zero GRN rows created; PO status remained `"Awaiting Delivery"`.
  * **Root Cause:** In `GrnDesk.jsx`, the payload is formatted as `received_quantity`, while `receive_goods_receipt_note()` in `hotel/procurement.py` (line 489) reads `it_data.get("quantity_received", 0)`.

### 3.6 Waste Recording & Approval Workflow
* **Action:** Navigated to `/inventory` -> "Waste & Loss" tab -> Clicked "Register Waste Entry".
  * Item: `Challenge Test Item (CHAL-ITEM-01)` | Qty: `2 pcs` | Category: `Food Spoilage or Expiry` | Reason: `"Verification Spoilage"`.
  * Clicked "Confirm & Record Waste".
* **Result:** **FAIL (REPRODUCED DEFECT 2)**.
  * **Browser Alert:** `"Unable to connect to the server. Please check your network connection.."`
  * **Network Request:** `POST http://localhost:8000/api/users/waste-records/` -> Status: `(failed) net::ERR_FAILED`
  * **Browser Console Error:**
    ```text
    Access to XMLHttpRequest at 'http://localhost:8000/api/users/waste-records/' from origin 'http://localhost:3000' 
    has been blocked by CORS policy: Request header field idempotency-key is not allowed by 
    Access-Control-Allow-Headers in preflight response.
    ```
  * **Database Verification:** `InventoryWasteRecord.objects.filter(notes__icontains='Verification Spoilage').count() == 0`. Record was never committed.
  * **Root Cause:** `core/settings.py` defines `CORS_ALLOW_HEADERS = list(default_headers) + ["x-tenant-schema", "cache-control", "pragma"]`, omitting `"idempotency-key"`. The browser rejects the preflight request.

### 3.7 Multi-Location Transfers (Two-Phase Custody)
* **Action:** Navigated to `/transfers` (`Stock Transfers & Locations`).
  * **Phase 1 (Requisition):** Created requisition `TRF-20261114-84996A` from `Main Central Store (STORE-MAIN)` to `Main Kitchen Pantry (KITCHEN-MAIN)` for `2 pcs` of `Challenge Test Item`. Status: `Requested`.
  * **Phase 2 (Dispatch):** Clicked "Dispatch" -> Locked goods into in-transit custody. Status: `In Transit` (Dispatched by: `admin_proc2`).
  * **Phase 3 (Receiving Bay):** Clicked "Receive" -> Reconciled 2 pcs intact, 0 damaged. Status: `Completed`.
* **Database Verification:** `StockTransfer.objects.get(transfer_number='TRF-20261114-84996A').status == 'completed'`.
* **Browser Reload Persistence:** **PASS**. Row 1 persisted with status `Completed` after full reload.

### 3.8 Physical Stocktaking (Dual-Mode Blind Count)
* **Action:** Navigated to `/stocktaking` (`Physical Stocktaking`).
  * Created session `STK-20261114-24070E` ("QA Verification Count Session") for `Main Kitchen Pantry` under `Blind Count Mode`.
  * Counter entered `2.00 pcs` for `CHAL-ITEM-01` (theoretical stock hidden). Submitted and locked counts.
  * Status transitioned to `UNDER REVIEW`.
  * Separation-of-Duties Enforcement Verified: Approver alert displayed preventing self-review when `admin_proc2` attempted sign-off.
* **Browser Reload Persistence:** **PASS**. Session persisted with status `Under Review` after full reload.

---

## 4. ACTUAL STOCK OPERATIONS AUDIT

| Workflow | Method / Interface | Result | Evidence & Observations |
| :--- | :--- | :--- | :--- |
| **Opening Stock Import** | `POST /api/users/inventory-items/import-opening-stock/` | **PASS** | Validated bulk intake creates batches, location balances, initial StockTransactions, and Opening Equity JV (Dr 1300 / Cr 3000). Duplicate intake blocked unless `overwrite=True`. |
| **Stock Receiving (Dock)** | `POST /api/users/batches/` | **PASS** | Live browser dock batch receipt verified with lot numbers, barcode tracking, and automatic valuation update (+15 pcs, +750.00 ETB). Persists across reload. |
| **Stock Receiving (PO GRN)**| `POST /api/v1/procurement/orders/{id}/receive-grn/` | **FAIL** | Schema parameter mismatch (`received_quantity` vs `quantity_received`) triggers HTTP 400. |
| **Multi-Location Transfers** | Live Browser (`/transfers`) | **PASS** | Complete Requisition -> Dispatch -> In-Transit -> Door Intake cycle verified (`TRF-20261114-84996A`). Persists across reload. |
| **Waste Recording (UI)** | Live Browser (`/inventory`) | **FAIL** | CORS preflight blocks `idempotency-key` header; record rejected. |
| **Waste Recording (Backend)**| Automated Integration Test | **PASS** | Backend service handles waste write-offs with balancing JV: Dr 5100 (Waste Loss) / Cr 1300 (Inventory Asset). |
| **Physical Stocktaking** | Live Browser (`/stocktaking`) | **PASS** | Blind count session created, counted, locked, and guarded by SoD controls (`STK-20261114-24070E`). Persists across reload. |
| **Batch Allocation & Expiry** | `allocate_stock_batches()` | **PASS** | FEFO (First-Expired, First-Out) algorithm strictly prioritizes batches with earliest expiration. Expired and quarantined batches are automatically omitted. |
| **POS Ingredient Deduction** | `apps/orders/services.py:process_order_settlement` | **PASS** | 71/71 tests passed. Shortages durably recorded as `UnfulfilledStockDeduction` without rolling back payments. |
| **Stock Ledger & Reports** | `/api/users/inventory-reports/stock-movement/` | **PASS** | Bounded pagination, multi-criteria filtering, and mathematical balance formula ($Closing = Opening + Purchases + TransfersIn - TransfersOut - Issuances - Waste \pm Adjustments$) verified. |

---

## 5. ACCOUNTING AND DATA INTEGRITY AUDIT

### 5.1 Double-Entry Journal Entry Equilibrium
* **Total Journal Entries Inspected:** 100 entries.
* **Unbalanced Entries:** **0 entries** ($\sum \text{Debits} == \sum \text{Credits}$ across all 100 entries).
* **Sample Balanced Entry:**
  * Entry: `#JV-20261104-0001`
  * Debit: Account 1300 (Inventory Asset) = `12,500.00 ETB`
  * Credit: Account 2000 (Accounts Payable) = `12,500.00 ETB`
  * Net Discrepancy: `0.00 ETB`

### 5.2 Sub-ledger vs. Master vs. Location Balance Alignment
A comprehensive database audit was executed across all 27 inventory items in `hotel_erp_staging`:
* **Items Matching All Balances:** 14 items (52%)
* **Items with Discrepancies:** **13 items (48%)**

#### Discrepancy Breakdown (Sample of Identified Records):
| Item ID | Item Name | `current_stock` | $\sum$ Batches | $\sum$ Location Balances | Diagnosis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `6` | Prime Beef Tenderloin | `10.00 kg` | `0.00 kg` | `0.00 kg` | Legacy item: stock present in master, zero batches or location balances created. |
| `7` | Russet Potatoes | `50.00 kg` | `0.00 kg` | `0.00 kg` | Legacy item: unbatched and unassigned to locations. |
| `15` | Staging Basmati Rice 25kg | `50.00 bags` | `0.00 bags` | `50.00 bags` | Location balance present, but missing batch records. |
| `18` | Prime Beef Tenderloin (P2) | `45.00 kg` | `18.00 kg` | `45.00 kg` | Batch balance (`18.00`) is depleted/unaligned with master (`45.00`). |
| `3` | Artisan Sparkling Soda | `48.00 pcs` | `48.00 pcs` | `68.00 pcs` | Location balance (`68.00`) exceeds item master stock (`48.00`). |
| `5` | Fresh Whole Milk 1L | `175.00 L` | `245.00 L` | `175.00 L` | Batches sum to `245.00`, exceeding physical stock of `175.00`. |

### 5.3 General Ledger (Account 1300) Reconciliation
Execution of `generate_gl_reconciliation_report()` returned:
* **Report Status:** `discrepancy_detected`
* **Is Reconciled:** `False`
* **General Ledger Account 1300 Balance:** `119,260.00 ETB`
* **Sub-ledger Active Batch Valuation:** `196,780.00 ETB`
* **Item Master Stock Valuation:** `298,390.00 ETB`
* **GL vs. Sub-ledger Batch Variance:** `-77,520.00 ETB`
* **Master vs. Sub-ledger Batch Variance:** `+101,610.00 ETB`
* **Assessment:** The reconciliation service functions as intended by accurately calculating and highlighting these financial variances.

### 5.4 Idempotency & Duplicate Request Protection
* **StockTransaction Model:** Protected by `idempotency_key` (`unique=True`, `db_index=True`) and SHA-256 `payload_hash`.
* **Opening Stock Intake:** Protected by duplicate check; attempting to re-import existing items throws `ValidationError` unless `overwrite=True`.
* **POS Payment Idempotency:** Guarded by `PaymentAttempt` and `order.idempotency_key`, preventing double inventory deductions upon webhook replays.

---

## 6. DEFECT REGISTER & RECOMMENDATIONS

Before full operational acceptance can be granted, the following defects must be addressed:

### Defect 1: Procurement PO GRN Payload Schema Mismatch
* **Severity:** High (Blocks receiving goods from approved Purchase Orders).
* **Location:** `hotel/procurement.py:489` and `hotel-frontend/src/pages/procurement/GrnDesk.jsx`.
* **Description:** Frontend submits `received_quantity` and `rejected_quantity`, but the backend service reads `it_data.get("quantity_received", 0)` and `it_data.get("quantity_rejected", 0)`.
* **Recommended Fix:** Update `hotel/procurement.py` to support both naming conventions:
  ```python
  qty_recv_raw = it_data.get("quantity_received") if "quantity_received" in it_data else it_data.get("received_quantity", 0)
  qty_rej_raw = it_data.get("quantity_rejected") if "quantity_rejected" in it_data else it_data.get("rejected_quantity", 0)
  ```

### Defect 2: CORS Preflight Blocks `idempotency-key` in Waste Recording
* **Severity:** High (Blocks users from submitting waste and loss records in the browser).
* **Location:** `core/settings.py:502` (`CORS_ALLOW_HEADERS`).
* **Description:** The React frontend sends an `idempotency-key` header with POST requests to prevent duplicates. Django's `CORS_ALLOW_HEADERS` does not include `idempotency-key`, causing browser preflight checks to fail with `net::ERR_FAILED`.
* **Recommended Fix:** Add `"idempotency-key"` to `CORS_ALLOW_HEADERS` in `core/settings.py`:
  ```python
  CORS_ALLOW_HEADERS = list(default_headers) + [
      "x-tenant-schema",
      "cache-control",
      "pragma",
      "idempotency-key",
  ]
  ```

### Defect 3: Backend Test Suite Hardcoded Unique Constraint Collision (11 Errors)
* **Severity:** Medium (Invalidates 100% automated test pass claims).
* **Location:**
  * `apps/inventory/tests/test_minibar_and_stock_control_phase4.py`
  * `apps/inventory/tests/test_opening_stock_and_procurement_phase3.py`
  * `apps/inventory/tests/test_reporting_and_gl_reconciliation_phase5.py`
* **Description:** The `setUp()` methods execute `StockLocation.objects.create(name="Main Central Store", code="STORE-MAIN", ...)`. Because `STORE-MAIN` is seeded by migration `0043`, PostgreSQL raises `IntegrityError: duplicate key value violates unique constraint "hotel_stocklocation_code_key"`.
* **Recommended Fix:** Replace `create()` with `get_or_create()` in the test `setUp()` methods:
  ```python
  self.loc_main, _ = StockLocation.objects.get_or_create(
      code="STORE-MAIN",
      defaults={"name": "Main Central Store", "is_active": True}
  )
  ```

### Defect 4: Staging Database Legacy Stock Records Lack Batches / Location Balances
* **Severity:** Medium (Causes valuation variance between Sub-ledger and GL).
* **Location:** `hotel_erp_staging` PostgreSQL database.
* **Description:** 13 legacy items carry positive stock on `InventoryItem.current_stock` without corresponding `StockBatch` or `ItemLocationBalance` rows.
* **Recommended Fix:** Run a one-off database migration or management command to generate initial legacy batches and location balances for unbatched items having `current_stock > 0`.

---

## 7. FINAL ACCEPTANCE STATUS MATRIX

| # | Workflow / Domain | Classification | Verification Method | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Authentication & RBAC Navigation** | **PASS** | Live Browser (React + CDP) | Authenticated as `admin_proc2`; redirected to `/dashboard`. |
| 2 | **Category Management & Persistence** | **PASS** | Live Browser + PostgreSQL | Created category; persisted across full browser page reload. |
| 3 | **Item Creation, Editing, & Deletion** | **PASS** | Live Browser + PostgreSQL | Full CRUD verified; persists across reload. |
| 4 | **Supplier Management & Persistence** | **PASS** | Live Browser + PostgreSQL | Create & edit verified; counter and details persist. |
| 5 | **Stock Adjustment & Ledger Logging** | **PASS** | Live Browser + PostgreSQL | Stock adjusted (+10 pcs); recorded in Stock Ledger; persists. |
| 6 | **Direct Batch Dock Intake** | **PASS** | Live Browser + PostgreSQL | Direct GRN batch intake (+15 pcs); valuation updated; persists. |
| 7 | **Purchase Order GRN Receiving** | **FAIL** | Live Browser (React + DRF) | Schema mismatch (`received_quantity` vs `quantity_received`) -> HTTP 400. |
| 8 | **Waste Recording (UI Flow)** | **FAIL** | Live Browser (React + DRF) | CORS preflight blocks `idempotency-key` header -> `net::ERR_FAILED`. |
| 9 | **Stock Transfers (Inter-Location)** | **PASS** | Live Browser + PostgreSQL | Requisition -> Dispatch -> Bay Intake (`TRF-20261114-84996A`) verified. |
| 10 | **Physical Stocktaking (Dual-Mode)** | **PASS** | Live Browser + PostgreSQL | Blind count session (`STK-20261114-24070E`) counted, locked, SoD enforced. |
| 11 | **Opening Stock Bulk Intake** | **PASS** | Automated Integration Test | Bulk import, equity JV, duplicate protection verified. |
| 12 | **Batch Allocation Engine (FEFO)** | **PASS** | Automated Integration Test | Earliest expiry prioritized; expired/quarantined excluded. |
| 13 | **POS Ingredient Shortage Handling** | **PASS** | Automated Integration Suite (`apps.orders.tests`: 71/71 PASSED) | Payments decoupled; shortages recorded as `UnfulfilledStockDeduction`. |
| 14 | **Double-Entry Journal Equilibrium** | **PASS** | Database Audit (PostgreSQL) | 100/100 journal entries balance ($\sum \text{Dr} == \sum \text{Cr}$). |
| 15 | **GL Sub-ledger Reconciliation** | **PASS** | Database & API Audit | Discrepancies detected and reported with accurate variance math. |
| 16 | **Backend Inventory Test Suite** | **PARTIAL** | Django Test Runner (`manage.py`) | 188 passed, **11 errors** due to test setup collision. |

---

## 8. CONCLUSION & NEXT STEPS

* **Operational Readiness:** **81.25% Verified**.
* The original reported defects regarding category saving and stock adjustment persistence have been **resolved and verified**.
* However, **two blocking defects were uncovered and reproduced in the live UI**:
  1. PO Goods Receiving modal fails with HTTP 400 due to parameter mismatch (`received_quantity` vs `quantity_received`).
  2. Waste recording in the UI fails due to missing `idempotency-key` in Django's CORS allowed headers.
* Additionally:
  3. The automated test suite has 11 setup collision errors (`STORE-MAIN`).
  4. 13 legacy items in the staging database carry unbatched stock causing GL variances.
* In accordance with project rules, **zero code has been modified during this verification**, no deployment was initiated, and Neon production remains completely isolated.
