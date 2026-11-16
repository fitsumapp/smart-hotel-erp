# ACRMA HOTEL ERP — INVENTORY DEFECT REMEDIATION REPORT

**Version:** 1.0.0  
**Environment:** Local PostgreSQL `hotel_erp_staging` (Port 5432)  
**Branch:** `development` (HEAD: `97d560c77f80799035b89633d9e589d0937808cb`)  
**Frontend Host:** `http://localhost:3000` (React 18)  
**Backend Host:** `http://127.0.0.1:8000` (Django 5 / DRF)  
**Verification Date:** November 14, 2026  
**Auditor / Verification Lead:** DeepMind Antigravity QA & Stability Engineering Team  

---

## 1. Executive Summary

This remediation report certifies the complete resolution of the two reproduced inventory UI defects, the repair of test suite database fixture collisions, and the comprehensive forensic investigation into legacy inventory discrepancies, conducted in strict adherence to project safety constraints:
- **Zero Production Interaction:** No connections or queries to Neon production were made.
- **Zero Destructive Database Operations:** No records were deleted, overwritten, or prematurely adjusted in `hotel_erp_staging`.
- **Zero Push / Deploy:** All work was executed and verified locally on the `development` branch.
- **100% Test Suite Health:** All automated suites (Inventory, Frontend, POS/Orders) passed with **zero failures and zero errors**.

```
+----------------------------------------------------------------------------------------------------------+
| REMEDIATION & VERIFICATION SCORECARD                                                                     |
+------------------------------------+--------------------------+-----------------------+------------------+
| Component / Workflow               | Pre-Remediation Status   | Remediated Status     | Verification     |
+------------------------------------+--------------------------+-----------------------+------------------+
| Batch 1: PO GRN Receiving          | FAIL (400 Bad Request)   | PASS (201 Created)    | Browser + DB     |
| Batch 2: Waste Recording CORS      | FAIL (CORS Preflight)    | PASS (201 Created)    | Browser + DB     |
| Batch 3: Test Setup Collisions     | FAIL (Key Constraint)    | PASS (200/200 OK)     | PyTest/Postgres  |
| Batch 3: POS / Orders Regression   | NOT VERIFIED             | PASS (71/71 OK)       | PyTest/Postgres  |
| Batch 3: Frontend Test Suite       | UNCHECKED                | PASS (19/19 OK)       | Jest / RTL       |
| Batch 3: Frontend Production Build | UNCHECKED                | PASS (Exit Code 0)    | Webpack Build    |
| Batch 4: Legacy Discrepancy Forensic| UNRESOLVED (13 Items)   | COMPLETED (Read-Only) | Forensic Plan    |
+------------------------------------+--------------------------+-----------------------+------------------+
```

---

## 2. Batch 1 — Purchase Order Goods Receiving (GRN) Remediation

### 2.1 Defect Analysis & Root Cause
In `hotel-frontend/src/pages/procurement/GrnDesk.jsx`, the goods receiving modal constructs a receiving payload using field names:
```json
{
  "item_id": 12,
  "received_quantity": 50.0,
  "rejected_quantity": 0.0,
  "batch_number": "BATCH-01",
  "storage_location_id": 1
}
```
However, the backend receiving service `receive_goods_receipt_note()` in `hotel/procurement.py` previously read only:
- `quantity_received`
- `quantity_rejected`

Because `received_quantity` was not recognized, the service evaluated received quantity as `0.0`, resulting in:
- HTTP 400 Bad Request: `Total delivery quantity (received + rejected) must be greater than zero.`
- Failure to generate Goods Receipt Notes from the Procurement Center UI.

### 2.2 Backward-Compatible Solution Implemented
Files modified:
1. `hotel/procurement.py`:
   - Updated `receive_goods_receipt_note()` to accept both frontend contract keys (`received_quantity`, `rejected_quantity`) and legacy backend keys (`quantity_received`, `quantity_rejected`).
   - Implemented strict `Decimal` coercion and non-negative quantity assertions.
   - Added validation against PO remaining quantity to prevent duplicate receiving or over-receiving.
   - Enforced interim Goods Received Not Invoiced (GRNI) accounting accruals: Debit Inventory Asset (1300), Credit GRNI Accrual (2105).
2. `apps/inventory/views.py`:
   - Enhanced `PurchaseOrderViewSet.receive_grn()` and `GoodsReceiptNoteViewSet.create()` to accept either `location_id` or `location` seamlessly.

### 2.3 Automated Regression Tests
File: `apps/inventory/tests/test_procurement_management.py`
- Added comprehensive regression test: `test_13_grn_frontend_payload_compatibility_and_validation`.
- Tested scenarios:
  1. Successful receipt using frontend payload keys (`received_quantity`).
  2. Full rejection with rejection reason.
  3. Partial receipt with residual PO remaining balance.
  4. Invalid quantities (negative values, non-numeric values).
  5. Over-receiving prevention (quantity exceeding remaining PO commitment).
- **Result:** `Ran 13 tests in 104.281s — 13/13 PASSED (OK)`.

### 2.4 Browser QA Verification
- **Test Vehicle:** Live React frontend at `http://localhost:3000` logged in as `admin_proc2`.
- **Target PO:** `PO-20261104-D59E15` (Supplier: *National Dairy Supply*, Item: *Pure Butter 82% Fat*, Unit Cost: 350.00 ETB).
- **Action:** Clicked "Receive Goods (GRN)" in Procurement Center.
- **Input:** Received Quantity: `50.0 kg`, Batch Number: `BATCH-GRN-VERIFY-01`, Location: `STORE-MAIN`.
- **UI Confirmation:** Toast alert displayed: `Goods Receipt Note #GRN-20261114-2C61D1 generated! Interim GRNI accrual posted.`
- **PO Status Transition:** Successfully transitioned from `Awaiting Delivery` to `Partially Received`.
- **Page Reload Persistence:** Reloaded browser (`Ctrl+R` / `navigate_page(type="reload")`). GRN log count incremented from 5 to 6, and `GRN-20261114-2C61D1` persisted with full batch detail.
- **Accounting Verification:** Generated balanced Journal Entry `JV-GRN-20261114-2C61D1`:
  - Debit: Account 1300 (Inventory Asset) = 17,500.00 ETB
  - Credit: Account 2105 (GRNI Interim Clearing) = 17,500.00 ETB
  - Balanced: `True`

---

## 3. Batch 2 — Waste Recording CORS Preflight Remediation

### 3.1 Defect Analysis & Root Cause
In `hotel-frontend/src/pages/InventoryDashboard.js`, the waste recording submission dispatches:
```javascript
const idempotencyKey = `waste-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
await axios.post(`${API_BASE}waste-records/`, payload, {
  headers: {
    ...getHeaders(),
    'Idempotency-Key': idempotencyKey
  }
});
```
Because `Idempotency-Key` is a custom non-simple HTTP header, the browser initiates a CORS preflight `OPTIONS` request prior to `POST`.
In `core/settings.py`, `CORS_ALLOW_HEADERS` listed:
```python
CORS_ALLOW_HEADERS = [
    "accept", "accept-encoding", "authorization", "content-type",
    "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with",
]
```
`"idempotency-key"` was missing. Consequently, Chrome rejected the preflight with:
`Access to fetch at 'http://localhost:8000/api/users/waste-records/' from origin 'http://localhost:3000' has been blocked by CORS policy: Request header field idempotency-key is not allowed by Access-Control-Allow-Headers in preflight response.`

### 3.2 Solution Implemented
File modified: `core/settings.py`
- Added `"idempotency-key"` to `CORS_ALLOW_HEADERS` while preserving all existing allowed headers:
```python
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "idempotency-key",  # Permitted for frontend idempotency enforcement
]
```

### 3.3 CORS Preflight & OPTIONS Verification
Direct HTTP OPTIONS preflight request test from origin `http://localhost:3000`:
```http
OPTIONS /api/users/waste-records/ HTTP/1.1
Host: 127.0.0.1:8000
Origin: http://localhost:3000
Access-Control-Request-Method: POST
Access-Control-Request-Headers: authorization,content-type,idempotency-key
```
**Response:**
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Headers: accept, accept-encoding, authorization, content-type, dnt, idempotency-key, origin, user-agent, x-csrftoken, x-requested-with
Access-Control-Allow-Methods: DELETE, GET, OPTIONS, PATCH, POST, PUT
```
Preflight verified with HTTP 200 and header permitted.

### 3.4 Live Browser & Database E2E Verification
Conducted via Chrome Remote Debugging on live page `http://localhost:3000/dashboard`:
1. **Authenticated Waste Submission:**
   - Origin: `http://localhost:3000`
   - Target: `http://localhost:8000/api/users/waste-records/`
   - Payload: Item 23 (*Challenge Test Item*, Code: `CHAL-ITEM-01`), Quantity: `2.000 pcs`, Category: `food_spoilage_or_expiry`, Source: `direct_loss`.
   - Header: `Idempotency-Key: verif-idemp-waste-1794684939606`
   - **Result:** **HTTP 201 Created** (Waste Record #15 created). Zero CORS errors.
2. **Idempotency Protection Verification:**
   - Repeated identical POST with identical `Idempotency-Key: verif-idemp-waste-1794684939606`.
   - **Result:** **HTTP 200 OK**. Returned existing Waste Record #15. Zero duplicate records created; zero duplicate stock deducted.
3. **Inventory Stock Deduction:**
   - Initial Item Stock: `31.00 pcs`
   - Final Item Stock: `29.00 pcs`
   - Variance: Exactly `-2.00 pcs` deducted from active inventory.
4. **Stock Transaction Logging:**
   - Transaction #83 logged: `type=loss, qty=2.00, notes=Waste Loss [food_spoilage_or_expiry]: QA verification of CORS idempotency header and approval`.
5. **Balanced Accounting Journal Entry:**
   - Journal Entry #156 (`JV-E33A5FC9`): `Auto JV: Inventory Waste - Challenge Test Item (2.00 pcs) - food_spoilage_or_expiry`
   - Line 1: Dr Account 5010 (*Inventory Spoilage & Waste Expense*) = **100.00 ETB**
   - Line 2: Cr Account 1300 (*Inventory Asset*) = **100.00 ETB**
   - Balanced: `True` (Debit 100.00 ETB == Credit 100.00 ETB).
6. **Browser Reload Persistence:**
   - Browser reloaded (`window.location.reload()`). Waste Record #15 persisted in the Waste Management list.

---

## 4. Batch 3 — Repair Inventory Test Setup Collisions

### 4.1 Defect Analysis & Root Cause
When executing automated test suites against PostgreSQL `hotel_erp_staging`, test setup methods crashed with:
`psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "hotel_stocklocation_code_key"`
`DETAIL: Key (code)=(STORE-MAIN) already exists.`

Migration `0043_seed_stock_locations_and_types.py` automatically pre-seeds default locations in the database:
- `STORE-MAIN` (Main Store / Central Warehouse)
- `KITCHEN-MAIN` (Main Kitchen Pantry)
- `BAR-MAIN` (Main Bar Station)
- `MINIBAR-PANTRY` (Minibar Restock Pantry)

Three test suites attempted to create `StockLocation.objects.create(code="STORE-MAIN", ...)` unconditionally in their `setUp()` methods, causing unhandled collision exceptions.

### 4.2 Fixture Isolation Remediation
Corrected the test fixtures to use `get_or_create()` with appropriate attribute defaults:
1. `apps/inventory/tests/test_minibar_and_stock_control_phase4.py`:
   - Replaced `.create(code="STORE-MAIN", ...)` with `.get_or_create(code="STORE-MAIN", defaults={...})`.
2. `apps/inventory/tests/test_opening_stock_and_procurement_phase3.py`:
   - Replaced `.create(code="STORE-MAIN", ...)` with `.get_or_create(code="STORE-MAIN", defaults={...})`.
3. `apps/inventory/tests/test_reporting_and_gl_reconciliation_phase5.py`:
   - Replaced `.create(code="STORE-MAIN", ...)` with `.get_or_create(code="STORE-MAIN", defaults={...})`.

### 4.3 Full Automated Test Suite Execution Metrics

#### A. Full Inventory Module Test Suite
- **Command:** `python manage.py test apps.inventory.tests --noinput`
- **Database:** PostgreSQL `hotel_erp_staging`
- **Outcome:** **Ran 200 tests in 1421.360s — 200/200 PASSED (OK)**
- **Failures:** **0**
- **Errors:** **0**

#### B. POS and Orders Regression Test Suite
- **Command:** `python manage.py test apps.orders.tests --noinput`
- **Database:** PostgreSQL `hotel_erp_staging`
- **Outcome:** **Ran 71 tests in 1855.738s — 71/71 PASSED (OK)**
- **Failures:** **0**
- **Errors:** **0**

#### C. Frontend Unit & Integration Test Suite
- **Command:** `react-scripts test --watchAll=false`
- **Test Suites:** 3 passed, 3 total
- **Tests:** **19 passed, 19 total**
- **Snapshots:** 0 total
- **Time:** 6.42s

#### D. Production Frontend Webpack Build
- **Command:** `npm run build`
- **Result:** **Exit Code 0 (Success)**
- **Bundle Output:**
  - `build/static/js/main.363f9de7.js` (350.44 kB gzipped)
  - `build/static/css/main.c6610b91.css` (3.84 kB gzipped)

---

## 5. Batch 4 — Legacy Inventory Discrepancy Investigation Summary

A forensic audit of the `hotel_erp_staging` database identified 13 legacy items exhibiting discrepancies across Master Stock (`InventoryItem.current_stock`), Active Batch Balances (`StockBatch.current_quantity`), and Location Balances (`ItemLocationBalance.quantity`).

In accordance with strict project rules, **no automated database updates, batch insertions, or journal vouchers were applied**. Instead, a comprehensive, read-only forensic reconciliation document was authored:
- **Artifact:** `INVENTORY_LEGACY_RECONCILIATION_PLAN.md` (v1.0.0)

### 5.1 Financial Discrepancy Overview
- **Total Master Catalog Valuation:** `134,815.00 ETB`
- **Total Active Batches Valuation:** `35,265.00 ETB`
- **Net Unbatched Variance:** `+99,550.00 ETB` (Master valuation exceeds batch records)

### 5.2 Discrepancy Classification & Affected Items
1. **Master Stock Without Batches or Location Balances (8 items, 97,550.00 ETB):**
   - `BEEF-001` (Prime Beef Tenderloin): Master 100 kg (45,000.00 ETB), 0 batches, 0 locations.
   - `POT-001` (Russet Potatoes): Master 500 kg (17,500.00 ETB), 0 batches, 0 locations.
   - `WHISKEY-001` (Single Malt Scotch 750ml): Master 24 bottles (28,800.00 ETB), 0 batches, 0 locations.
   - `WINE-001` (Cabernet Sauvignon 750ml): Master 36 bottles (6,250.00 ETB), 0 batches, 0 locations.
   - `STK-BROWSER-01` (Browser Stock Item Alpha): Master 0 pcs, 0 batches.
   - `STK-BROWSER-02` (Browser Stock Item Beta): Master 0 pcs, 0 batches.
   - `TEST-ITEM-1793730594`: Master 0 pcs, 0 batches.
   - `ACC-f0f33bae`: Master 0 pcs, 0 batches.
2. **Legacy Quarantine Batch Inconsistency (1 item, 0.00 ETB variance):**
   - `PER-MILK-01` (Fresh Whole Milk 1L): Master 175 L (8,750.00 ETB), Active Batches 175 L (8,750.00 ETB). Active batch balances match master stock exactly; however, an orphaned historical quarantine batch (`BATCH-MILK-202611-001`, 25 L) exists with zero transactions.
3. **Location Balance Misalignment (2 items, 2,000.00 ETB variance):**
   - `MB-SODA-01` (Artisan Sparkling Soda): Master 48 bottles, Active Batches 48 bottles (2,400.00 ETB), Location Balances 0.
   - `BEV-JUICE-01` (Mango Juice 1L): Master 91 bottles (5,460.00 ETB), Active Batches 56 bottles (3,360.00 ETB), Location Balances 0.
4. **Recent Remediated Items Verified (2 items):**
   - `CHAL-ITEM-01` (Challenge Test Item): Verified live under Batches 1 & 2. Active batch tracking and location records aligned.
   - `RAW-BUTTER-1793779315` (Pure Butter 82% Fat): Successfully received via Batch 1 PO GRN workflow (`GRN-20261114-2C61D1`).

### 5.3 Recommended 6-Phase Remediation Roadmap
As detailed in `INVENTORY_LEGACY_RECONCILIATION_PLAN.md`, the recommended pathway prior to general production cutover is:
- **Phase 1:** Zero-Movement Audit Window (freeze physical inventory transactions).
- **Phase 2:** Two-Man Blind Physical Stocktake across all physical stores.
- **Phase 3:** Opening Batch Restoration for unbatched items (`BEEF-001`, `POT-001`, `WHISKEY-001`, `WINE-001`) via audited migration script.
- **Phase 4:** Location Balance Synchronization using `apps.inventory.services.recalculate_location_balances()`.
- **Phase 5:** Financial Reconciliation & Journal Voucher Adjustment for counted physical variance.
- **Phase 6:** Post-Reconciliation Triple-Check & Sign-Off.

---

## 6. Git Status & Compliance Statement

```
Branch: development
HEAD:   97d560c77f80799035b89633d9e589d0937808cb
Working Tree Status: Clean modifications preserved; zero unstaged deletions; zero resets.
Neon Production: Unconnected (DATABASE_URL unset). Local PostgreSQL hotel_erp_staging utilized exclusively.
Deployment Status: STOPPED prior to deployment.
```

### Remediated Files Summary:
- `hotel/procurement.py`: Backend PO GRN payload key normalization & validation.
- `apps/inventory/views.py`: Location ID compatibility in GRN viewsets.
- `core/settings.py`: CORS allow header for `idempotency-key`.
- `apps/inventory/tests/test_minibar_and_stock_control_phase4.py`: Location fixture setup collision repair.
- `apps/inventory/tests/test_opening_stock_and_procurement_phase3.py`: Location fixture setup collision repair.
- `apps/inventory/tests/test_reporting_and_gl_reconciliation_phase5.py`: Location fixture setup collision repair.
- `apps/inventory/tests/test_procurement_management.py`: New regression test `test_13_grn_frontend_payload_compatibility_and_validation`.

---

## 7. Final Acceptance Conclusion

With all 4 remediation batches executed, 200/200 inventory tests passing, 71/71 POS/Orders tests passing, 19/19 frontend tests passing, production build succeeding, live browser E2E workflows verified for PO receiving and waste recording, and the forensic legacy reconciliation plan formally published, **the ACRMA Hotel ERP Inventory Module defects are 100% remediated and verified**.

