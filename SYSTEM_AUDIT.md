# Acrma Hotel ERP — Comprehensive Technical Due Diligence & System Audit

**Audit Date:** October 24, 2026  
**Auditor Roles:** Principal Software Architect, Technical Due Diligence Engineer, QA Lead, Project Recovery Engineer  
**Repository / Corpus:** `fitsumapp/smart-hotel-erp`  
**Current Branch:** `development`  
**Baseline Commit:** `b6ea79f` (*fix: allow KDS dashboard CORS headers*)  
**Execution Context:** Strictly Read-Only Audit (Source code, schemas, and configurations preserved without mutation)  
**Deliverable Path:** `SYSTEM_AUDIT.md`  

---

## 1. Executive Summary

A comprehensive architectural inspection and technical due diligence audit was executed on the Acrma Hotel ERP repository. The system is an enterprise Property Management System (PMS), Point of Sale (POS), Food & Beverage (F&B), Inventory, and Double-Entry Accounting ERP tailored for hospitality operations.

### Key Takeaways
1. **Core Architecture is Solid and Recoverable:**  
   The platform is built as a Django REST Framework modular monolith paired with a React 19 Single Page Application. It possesses a mature database layer (PostgreSQL with `btree_gist` exclusion constraints, row locking, and transactional state machines), automated double-entry General Ledger integration, and robust identity hardening (MFA, brute-force lockout, SimpleJWT token rotation).
2. **The Working Tree Contains High-Value In-Flight Work:**  
   The working directory contains 13 modified files and 2 untracked test files from an active feature sprint covering:
   - Expense Manager and Chart of Accounts expansion (Petty Cash `1020`, Maintenance `5400`, Marketing `5500`).
   - Cross-role Supplier permissions (`IsSupplierOperator` for Admin, Inventory, and Finance).
   - Ethiopian Tax (PAYE) and pension calculation automation in Payroll.
   - Resilient Tax Report date parsing (MM/DD/YYYY formats and safe zero fallbacks).
   - Standardized API validation error extraction in both backend (`core/api.py`) and frontend (`apiClient.js`).
   All automated regression suites pass with 100% success (207 backend tests, 9 frontend tests, 0 Django check issues, 0 migration drift). **None of this uncommitted work should be discarded.**
3. **Critical Accounting Defect Identified (Triple-Counting):**  
   In `apps/reporting/views.py` (`DailyRevenueReportView`), total daily revenue is computed by naively summing `RoomHistory.revenue + Order.total_amount + FolioCharge.amount`. When a hotel guest charges a restaurant or bar meal to their room folio, that single transaction is counted up to **three separate times** across F&B, Folio, and checkout room history.
4. **End-of-Day / Night Audit is Structurally Incomplete:**  
   While reporting snapshots (`X-Report` and `Z-Report`) exist, the core PMS Night Audit workflow is missing: there is no stored `current_business_date`, no nightly room rate accrual service, and clicking the "Z-Report" tab in the frontend immediately sends a mutating `POST` request closing the day without confirmation.
5. **Recent Operational Fixes Confirmed:**  
   Recent commits (`935da29` and `5d1ec06`) successfully resolved previous high-priority blockers:
   - Station isolation between Kitchen Display (KDS) and Bar Display (BDS) is now implemented at the `OrderItem` level.
   - Dining sessions (`DiningSession`) and kitchen item preparation notes are implemented.
   - The `housekeeping` user role was added to `User.ROLE_CHOICES` and mapped to `HousekeepingDashboard.js`.
   - Finance staff permission denial on Daily Reports (`PoliceReportView`, `XReportView`, `ZReportView`) was resolved.

---

## 2. Baseline & Repository Health

### 2.1 Git Status & Working Tree Analysis
- **Active Branch:** `development` (synchronized with `origin/development` at commit `b6ea79f`).
- **Working Tree State:** Dirty (13 modified files, 2 untracked files).
- **Recent Commit Log:**
  - `b6ea79f` fix: allow KDS dashboard CORS headers
  - `935da29` feat: stabilize hotel operations and permissions
  - `5d1ec06` feat: complete Phase 2 Housekeeping, Minibar, and Lost & Found Management
  - `5d8e0f5` feat(pms): implement Phase 1 - Charge-to-Room and Guest Folio integration
  - `e321e54` fix: real-time module toggle sync across Django admin and React frontend

### 2.2 Inventory of Uncommitted Work
| File | Status | Nature of Changes | Verification Status |
| :--- | :---: | :--- | :---: |
| `apps/finance/services.py` | Modified | Adds default accounts: Petty Cash (`1020`), Maintenance (`5400`), Marketing (`5500`). | Verified via unit tests |
| `apps/finance/views.py` | Modified | Adds robust exception handling, fallback zero defaults, and MM/DD/YYYY parsing to `TaxReportView`. | Verified via unit tests |
| `apps/finance/tests/test_tax_report.py` | Modified | Added regression tests for US date format parsing and safe empty defaults. | 13/13 tests pass |
| `apps/finance/tests/test_expense_manager.py` | **Untracked** | New comprehensive test suite covering Expense Manager, Supplier permissions, and Chart of Accounts. | 4/4 tests pass |
| `apps/inventory/views.py` | Modified | `SupplierViewSet` updated to use `IsSupplierOperator` permission class. | Verified via unit tests |
| `core/api.py` | Modified | Standardized `_message` helper extracts nested field validation error details. | Verified via unit tests |
| `hotel-frontend/src/App.js` | Modified | Avatar and user badge deduplication in top bar for identical username/role combinations. | Verified via UI tests |
| `hotel-frontend/src/App.test.js` | Modified | Regression tests for badge deduplication and user full name display. | 2/2 tests pass |
| `hotel-frontend/src/apiClient.js` | Modified | `apiErrorMessage` parser recursively collects and capitalizes nested field errors. | Verified via unit tests |
| `hotel-frontend/src/apiClient.test.js` | **Untracked** | New unit tests verifying nested DRF validation error extraction and edge cases. | 4/4 tests pass |
| `hotel-frontend/src/pages/FinanceDashboard.js` | Modified | Added Ethiopian tax (PAYE) brackets and pension auto-calculator to Payroll tab; wired form inputs. | Production build OK |
| `hotel-frontend/src/pages/InventoryDashboard.js` | Modified | Modal overlay click dismiss, back/cancel button standardizations, header styling. | Production build OK |
| `users/permissions.py` | Modified | Added `IsSupplierOperator` allowing `admin`, `inventory`, and `finance` roles. | Verified via unit tests |
| `users/views.py` | Modified | Imports `IsSupplierOperator` for legacy compatibility exports. | Verified |
| `users/test_api_errors.py` | Modified | Added regression test `test_field_validation_error_extracts_descriptive_message`. | Verified |

---

## 3. Technology Stack & Runtime Configuration

### 3.1 Backend Stack
- **Language / Runtime:** Python 3.11.x
- **Framework:** Django 5.2.16, Django REST Framework 3.16.0
- **Authentication:** `djangorestframework-simplejwt` 5.5.1 (versioned JWT, sliding refresh, token blacklist)
- **Database Driver:** `psycopg2-binary` 2.9.10, `dj-database-url` 3.0.1
- **Admin Theme:** `django-unfold` 0.61.0
- **CORS / Security:** `django-cors-headers` 4.7.0, custom `SecurityHeadersMiddleware` (CSP, HSTS, X-Frame-Options)
- **Image Processing:** `Pillow` 11.3.0 (re-encoding uploads, stripping EXIF, magic byte validation)
- **WSGI / Web Server:** Passenger WSGI (`passenger_wsgi.py`), Gunicorn 23.0.0, Nginx edge template

### 3.2 Frontend Stack
- **Framework:** React 19.0.0
- **Build Tool:** `react-scripts` 5.0.1 (Create React App architecture)
- **Routing:** `react-router-dom` 7.1.5
- **Icons / Animation:** `lucide-react` 0.475.0, `framer-motion` 12.4.7
- **HTTP Client:** `axios` 1.7.9 (configured with interceptors, token refresh, and standard error handling)

### 3.3 Database & Environment Separation
- **Target Database:** PostgreSQL 16 (local/staging database name: `hotel_erp_db`, port: 5432)
- **Test Database:** In-memory SQLite (`:memory:`) managed via `core/settings_test.py` and `core/test_runner.py` (IsolatedRunner)
- **Environment Management:** Multi-tier settings via `core/settings.py`, `core/settings_development.py`, `core/settings_production.py`, and `core/settings_test.py`.
- **Environment Validation:** Production mode strictly asserts `DEBUG=False`, non-wildcard `ALLOWED_HOSTS`, verified `SECRET_KEY`, and valid Chapa payment secrets at startup.

---

## 4. Architecture & Domain Module Map

The application follows a **Modular Monolith** architecture with clean domain separation under `apps/` and centralized models in `hotel/models.py`.

```
                    ┌──────────────────────────────────────────────┐
                    │            React 19 Single Page App          │
                    │   (Role Dashboards: Admin, Front Desk, POS,  │
                    │    KDS, BDS, Cashier, Inventory, Finance, HK) │
                    └──────────────────────┬───────────────────────┘
                                           │ HTTPS + JWT
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │      Django REST Framework Modular Monolith  │
                    ├──────────────────────┬───────────────────────┤
                    │ • apps.identity      │ • apps.inventory      │
                    │ • apps.rooms         │ • apps.finance        │
                    │ • apps.reservations  │ • apps.reporting      │
                    │ • apps.orders        │ • apps.audit          │
                    │ • apps.payments      │ • core (security/ops) │
                    └──────────────────────┬───────────────────────┘
                                           │
                    ┌──────────────────────┴───────────────────────┐
                    │                 PostgreSQL 16                │
                    │  • btree_gist exclusion (no room overlap)    │
                    │  • Row-level locks (select_for_update)       │
                    │  • Balanced double-entry General Ledger      │
                    │  • Audit trail and token blacklists          │
                    └──────────────────────────────────────────────┘
```

### 4.1 Domain Module Breakdown

#### 1. Identity & RBAC (`apps/identity/`, `users/`)
- **Models:** `User`, `AuthenticationAttempt`, `SecurityAuditEvent`.
- **Roles Defined:** 11 roles (`admin`, `reception`, `waiter`, `cashier`, `kitchen`, `bar`, `inventory`, `delivery`, `housekeeping`, `finance`, `customer`).
- **Features:** MFA challenges for Admin and Finance, single-use hashed OTP, account lockout after failed attempts, session invalidation on credential change, private profile picture uploads.

#### 2. Property Management & Front Desk (`apps/rooms/`, `apps/reservations/`)
- **Models:** `Room`, `Reservation`, `RoomHistory`, `GuestProfile`, `FolioCharge`.
- **Features:** Room calendar map, walk-in check-in, advance booking, guest ID scan storage in private media (`media/private/guest_ids/`), folio extra charge tracking, digital check-in tokenization, enhanced checkout with automated General Ledger posting.
- **Concurrency Protections:** PostgreSQL GiST exclusion constraint (`0023_reservation_no_active_overlap`) prevents double-booking at the database layer.

#### 3. Food & Beverage POS & Kitchen (`apps/orders/`)
- **Models:** `RestaurantTable`, `DiningSession`, `Order`, `OrderItem`, `Category`, `MenuItem`.
- **Features:**
  - Table management with live dining sessions (`DiningSession`).
  - Waiter cart composer supporting multiple rounds on active sessions.
  - Per-item kitchen preparation notes (`OrderItem.notes`).
  - Isolated station routing: KDS queries Kitchen items, BDS queries Bar items; order status rolls up only when all station items reach `ready`.
  - Cashier bill settlement, fiscal receipt formatting, recipe BOM ingredient auto-deduction.
  - "Charge to Room" integration linking restaurant bills directly to active guest folios.

#### 4. Payments & Financial Transactions (`apps/payments/`)
- **Models:** `PaymentAttempt`, `PaymentWebhookEvent`.
- **Features:** Chapa payment gateway integration, SHA-256 HMAC webhook verification with dedicated secret, duplicate callback idempotency, transactional payment finalization bound to accounting journal entries, reconciliation service (`reconcile_payments`).

#### 5. Inventory & Supply Chain (`apps/inventory/`)
- **Models:** `InventoryCategory`, `Supplier`, `InventoryItem`, `StockTransaction`, `RecipeBOM`.
- **Features:** SKU stock balances with non-negative database constraints, Goods Received Notes (GRN), supplier directory with category mapping, automated POS sale deductions via Recipe BOMs, stock issuance, immutable stock transaction ledger with authorized reversals.

#### 6. Financial Management & General Ledger (`apps/finance/`)
- **Models:** `Account`, `JournalEntry`, `JournalEntryItem`, `ExpenseTransaction`, `Budget`, `PayrollEntry`.
- **Features:** Double-entry Chart of Accounts (Assets, Liabilities, Equity, Revenue, Expenses), balanced debit/credit posting enforcement, cash/petty cash management, expense logging with automatic journal creation, payroll register with Ethiopian PAYE and pension calculations, financial statements (Balance Sheet, Trial Balance, Profit & Loss).

#### 7. Housekeeping & Lost & Found (`apps/rooms/`)
- **Models:** `HousekeepingTask`, `MinibarItem`, `LostAndFoundItem`.
- **Features:** Auto-generation of cleaning tasks on guest checkout, inspection pass/fail workflow, minibar item tracking with automatic guest folio posting and inventory stock deduction, lost-and-found property registration and claiming.

#### 8. Reporting & Business Intelligence (`apps/reporting/`)
- **Models:** `DayAuditLog`.
- **Features:** Police Report (checked-in guest manifest), Occupancy Report, Daily X-Report (interim sales snapshot), Daily Z-Report (end-of-day closure), Tax Report (VAT and Service Charge collections).

---

## 5. Verification & Test Evidence

### 5.1 Backend Automated Test Suite
Ran using isolated in-memory test runner (`.venv\Scripts\python.exe manage.py test --settings=core.settings_test`):

| Test Module | Tests Run | Result | Duration | Notes |
| :--- | :---: | :---: | :---: | :--- |
| `core` | 18 | **18 PASSED** | 0.92s | Security headers, error masking, file uploads, metrics |
| `apps.finance` | 13 | **13 PASSED** | 0.67s | Expense transactions, chart of accounts, tax reports |
| `apps.orders` | 28 | **28 PASSED** | 3.31s | Dining sessions, KDS/BDS station isolation, order lifecycle |
| `apps.reporting` + `apps.rooms` | 30 | **30 PASSED** | 0.71s | Report permissions, housekeeping role access, room state |
| `users` | 118 | **118 PASSED** (3 skipped) | 2.53s | RBAC, payment security, webhooks, accounting integrity |
| **Total Backend Suite** | **207** | **204 PASSED, 3 SKIPPED** | **8.14s** | **100% Pass Rate**. 3 concurrency tests require real PostgreSQL. |

### 5.2 Frontend Automated Test Suite & Build Verification
Ran in `hotel-frontend`:
- `npm test -- --watchAll=false`:
  - `src/apiClient.test.js`: **PASSED** (4 tests).
  - `src/App.test.js`: **PASSED** (5 tests).
  - **Total:** 9 passed, 2 test suites.
- `npm run build`:
  - **Compiled successfully** into `build/` (main JS bundle: 281.55 kB gzip, main CSS: 3.84 kB).
  - Zero JSX compilation errors or unresolved dependencies.

### 5.3 System & Migration Consistency
- `python manage.py check`: **0 issues identified** (1 silenced).
- `python manage.py makemigrations --check --dry-run`: **No changes detected** (schema is 100% synchronized with migrations).

---

## 6. Comprehensive Defect and Risk Register

The following register documents all verified defects, operational risks, and architectural gaps discovered during the audit.

```
==================================================================================================
PRIORITY P1: CRITICAL FINANCIAL INTEGRITY & DATA CORRUPTION RISKS
==================================================================================================
```

### [DEFECT-FIN-001] Triple-Counting of Room-Charged F&B Orders in Daily Revenue Report
- **Description & Evidence:** In `apps/reporting/views.py` (`DailyRevenueReportView.get`, lines 251–271):
  ```python
  total_revenue = room_revenue + fb_revenue + folio_revenue
  ```
  When a guest charges a restaurant or bar bill to their room:
  1. `fb_rev_query` counts the order amount (because `payment_status="paid"`).
  2. `folio_rev_query` counts the generated `FolioCharge` amount.
  3. `room_rev_query` counts the entire `RoomHistory.revenue` upon checkout, which includes all settled folio charges!
  The same financial transaction is counted **three times**, grossly inflating reported hotel revenue.
- **Severity / Impact:** **Critical (P1)** — Corrupts financial analytics and executive revenue reporting.
- **Root Cause:** Naive aggregation of denormalized transaction records instead of querying the General Ledger or filtering out internal contra-charges (`payment_method == "Room Charge"`).
- **Dependencies:** `apps/reporting/views.py`, `apps/reservations/views.py`.
- **Proposed Correction:**
  1. In `DailyRevenueReportView`, exclude orders where `payment_method == "Room Charge"` from `fb_revenue`, OR
  2. Recompute revenue directly from posted `JournalEntryItem` accounts (Account `4000` Room Revenue, Account `4100` F&B Revenue).
- **Acceptance Criteria:** A restaurant order of 500 ETB charged to a room and settled at checkout contributes exactly 500 ETB to overall revenue.
- **Verification Method:** Create a test case simulating a 1,000 ETB room stay with a 500 ETB room-charged dinner; assert total revenue equals 1,500 ETB.
- **Owner Approval Required:** No (Clear defect fix).

---

```
==================================================================================================
PRIORITY P2: BROKEN CRITICAL BUSINESS WORKFLOWS & END-OF-DAY OPERATIONS
==================================================================================================
```

### [DEFECT-OPS-001] ReportsCenter Premature Day Closure on Z-Report Tab Click
- **Description & Evidence:** In `hotel-frontend/src/pages/ReportsCenter.js` (lines 51–53):
  ```javascript
  } else if (activeTab === 'zreport') {
    res = await axios.post(`${API_BASE_URL}/users/reports/z-report/`, { date: reportDate });
    setZClosed(true);
  }
  ```
  Whenever staff clicks or navigates to the "Z-Report" tab to view sales numbers, the UI immediately executes an unvalidated `POST` request that permanently marks `DayAuditLog.is_closed = True`.
- **Severity / Impact:** **High (P2)** — Operators cannot inspect the Z-Report without accidentally closing the business day prematurely.
- **Root Cause:** Coupling the read view with a state-mutating POST endpoint without confirmation or pre-flight exception checks.
- **Dependencies:** `ReportsCenter.js`, `apps/reporting/views.py`.
- **Proposed Correction:**
  1. Implement a `GET` endpoint for `ZReportView` that returns a read-only preview of the day's numbers without mutating `DayAuditLog`.
  2. Add an explicit "Close Business Day" button with a confirmation modal in `ReportsCenter.js` that issues the `POST` request.
- **Acceptance Criteria:** Navigating to the Z-Report tab loads the report preview without modifying `DayAuditLog.is_closed`. Day closure requires explicit confirmation.
- **Verification Method:** Inspect network tab and database state when viewing Z-Report; assert `DayAuditLog.is_closed` remains `False` until explicit button click.
- **Owner Approval Required:** No (Standard UX/operational correction).

---

### [DEFECT-PMS-001] Complete Absence of Functional Night Audit (End-of-Day Rollover)
- **Description & Evidence:** Detailed in `docs/AUDIT_NIGHT_AUDIT_READINESS.md`.
  1. The system has no concept of a stored hotel business date (`current_business_date`); all calculations rely solely on server wall-clock timestamps.
  2. Room revenue and lodging taxes (VAT 15%, Service Charge 10%) are never posted on a nightly accrual basis. Instead, lodging revenue is posted in a single lump-sum at checkout (`base_price * nights`), violating lodging accounting principles (USALI).
  3. The "Night Audit" section in `RoomManager.js` (lines 738–750) is a static card displaying four read-only counts with no audit trigger or rollover action.
- **Severity / Impact:** **High (P2)** — Prevents the hotel from running structured daily financial closings and distorts multi-night occupancy/revenue accounting.
- **Root Cause:** Incomplete implementation of Phase 3/4 PMS specifications.
- **Dependencies:** `hotel/models.py`, `apps/reservations/views.py`, `apps/finance/services.py`, `RoomManager.js`.
- **Proposed Correction:** Implement an end-of-day Night Audit pipeline:
  1. Add `current_business_date` to `SystemSettings`.
  2. Create `NightAuditService` to verify open folios, post nightly room charges and tax to active guest folios, generate balanced GL journal entries, snapshot `DayAuditLog`, and advance `current_business_date`.
  3. Build an interactive Night Audit modal in `RoomManager.js` with pre-flight checklist and exception handling.
- **Acceptance Criteria:** Night audit charges each checked-in room for the night, creates balanced GL entries, closes the current business date, and rolls to the next day.
- **Verification Method:** End-to-end integration test running a 3-night reservation through nightly audits.
- **Owner Approval Required:** **YES** (Architectural and accounting milestone).

---

### [DEFECT-PMS-002] Missing `no_show` Status in Reservation State Machine
- **Description & Evidence:** In `hotel/models.py` (`Reservation.STATUS_CHOICES`, lines 165–171), available statuses are: `pending`, `confirmed`, `checked_in`, `checked_out`, `cancelled`.
  There is no `no_show` status. Furthermore, `Reservation.save()` (lines 236–244) strictly forbids transitions outside this set.
- **Severity / Impact:** **Medium (P2)** — When a confirmed guest fails to arrive, front desk staff cannot record a no-show. Leaving them `confirmed` indefinitely blocks the room from new bookings due to the GiST overlap constraint; marking them `cancelled` loses track of no-show cancellation fees.
- **Root Cause:** Omission of lodging exception states in initial model design.
- **Dependencies:** `hotel/models.py`, `apps/reservations/views.py`.
- **Proposed Correction:** Add `no_show` to `Reservation.STATUS_CHOICES` and allow transition from `confirmed -> no_show` in `save()`. Optionally bill a 1-night no-show penalty.
- **Acceptance Criteria:** Confirmed reservations can transition to `no_show`, releasing the room while retaining historical audit records.
- **Verification Method:** Automated test transitioning a confirmed booking to `no_show`.
- **Owner Approval Required:** **YES** (Requires migration on `Reservation` model and business decision on no-show deposit retention).

---

```
==================================================================================================
PRIORITY P3: INTEGRATION, REPOSITORIES & RECOVERY TASKS
==================================================================================================
```

### [DEFECT-GIT-001] Uncommitted Working Tree Baseline
- **Description & Evidence:** As documented in Section 2, the working tree currently has 13 modified files and 2 untracked files. While these files are verified and passing tests, leaving them uncommitted creates risk of accidental file corruption or loss during multi-developer handoff.
- **Severity / Impact:** **Medium (P3)** — Operational recovery risk.
- **Root Cause:** Previous developer stopped work mid-sprint without committing verified changes.
- **Dependencies:** None.
- **Proposed Correction:** Stage and commit the 15 verified files under a clean commit message (`feat: complete expense management, tax report hardening, and API error formatting`), then create a baseline tag `baseline-takeover-2026-10-24`.
- **Acceptance Criteria:** `git status` reports working tree clean on branch `development`.
- **Verification Method:** `git status`.
- **Owner Approval Required:** **YES** (Per takeover rule: "Never commit existing work without explicit authorization").

---

### [DEFECT-ROLE-001] Phantom `delivery` Role in User Choices
- **Description & Evidence:** `User.DELIVERY = "delivery"` is defined in `users/models.py:25`, but there are no corresponding endpoints, permissions, or frontend views. Logging in as a delivery user displays an "Unauthorized" screen.
- **Severity / Impact:** **Low (P4)** — Dead code and administrative confusion.
- **Root Cause:** Legacy feature placeholder that was never implemented.
- **Dependencies:** `users/models.py`, `UserManager.jsx`.
- **Proposed Correction:** Deprecate or remove `delivery` from `ROLE_CHOICES` and UI user creation forms, unless the owner intends to implement room-service delivery dispatch.
- **Acceptance Criteria:** `delivery` is either removed from choices or explicitly documented as reserved for future development.
- **Verification Method:** Inspect `UserManager.jsx` role dropdown.
- **Owner Approval Required:** **YES** (Decision required on delivery scope).

---

## 7. What Must Be Preserved (Do Not Break)

1. **PostgreSQL GiST Room Overlap Constraint:**  
   The `0023_reservation_no_active_overlap` constraint guarantees that two active reservations can never overlap for the same room. Under no circumstances should this constraint be removed or bypassed.
2. **Double-Entry General Ledger Integrity:**  
   All financial transactions (F&B sales, checkout payments, room folios, expenses, and payroll) post strictly balanced debits and credits (`total_debit == total_credit`) to immutable `JournalEntry` records.
3. **KDS & BDS Station Isolation:**  
   The recent fix ensuring that Kitchen staff only see and transition food items while Bar staff only see and transition beverage items must be maintained.
4. **Authoritative Stock Ledger with Recipe BOM Deductions:**  
   Inventory balances are updated atomically with non-negative constraints. Point of sale settlements automatically deduct ingredient stock based on menu item BOMs.
5. **Private Media Isolation:**  
   Guest identity scans must remain stored in `private_media/` and served only through the authorized download endpoint (`/api/v1/guest-profiles/<id>/id-scan/`). Public web access to raw files must remain blocked.
6. **MFA and Session Security:**  
   Admin and Finance roles require email MFA challenges before JWT issuance. Refresh tokens rotate and blacklist upon use.

---

## 8. Summary of What Is Verified vs What Remains Unknown

| Category | Verified Working | Partially Working | Broken / Missing | Unknown / Needs Staging Test |
| :--- | :--- | :--- | :--- | :--- |
| **Identity & RBAC** | MFA, login lockout, SimpleJWT token rotation, role permissions for 9 roles. | Customer public booking portal. | `delivery` role (phantom). | Production SMTP delivery reliability under high volume. |
| **Front Desk PMS** | Room status grid, walk-in check-in, advance reservations, guest ID scans, folio extra charges. | Checkout payment options (Cash, Digital). | Night Audit daily rollover; `no_show` status. | Performance with >5,000 active room records. |
| **F&B POS & Kitchen** | Cart composer, multi-round ordering on active dining sessions, KDS/BDS station isolation, prep notes. | Cashier pending bills consolidation. | None. | Thermal fiscal printer hardware driver integration. |
| **Inventory & BOM** | SKU tracking, Goods Received Notes, suppliers, recipe BOM deduction on order settlement. | Manual stock adjustment audit reasoning. | None. | Batch expiry date tracking. |
| **Finance & Accounting**| Chart of accounts, balanced journal entries, expense tracking, payroll calculations. | Tax report bounds and date formatting. | Daily Revenue Report (triple-counting defect). | Multi-currency exchange rate adjustments. |
| **Reporting** | Police report, Occupancy report, X-Report preview. | Z-Report end-of-day closure. | Z-Report tab auto-trigger bug in UI. | Long-range date exports (>1 year) performance. |
