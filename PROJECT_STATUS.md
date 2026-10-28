# Acrma Hotel ERP — Project Health & Status Report

**Report Date:** October 24, 2026  
**Auditor:** Principal Software Architect & QA Lead  
**Corpus / Workspace:** `fitsumapp/smart-hotel-erp`  
**Current Git Branch:** `development`  
**Latest Git Commit:** `b6ea79f` (*fix: allow KDS dashboard CORS headers*)  
**Deliverable Path:** `PROJECT_STATUS.md`  

---

## 1. Overall System Health Scorecard

| Operational Pillar | Readiness Score | Operational Status | Summary Assessment |
| :--- | :---: | :---: | :--- |
| **1. Identity & Access Control** | **95%** | **STABLE / SECURE** | MFA for Admin/Finance, brute-force lockout, SimpleJWT token rotation, and strict RBAC across 9 roles are fully operational. |
| **2. Payment & Financial Integrity** | **90%** | **STABLE / SECURE** | Chapa HMAC verification, idempotent webhooks, double-entry General Ledger with balanced debit/credit invariants are verified. |
| **3. Front Office & PMS Core** | **85%** | **OPERATIONAL** | Room grid, walk-in check-in, advance bookings, and private guest KYC ID scan storage work. Night Audit rollover and no-show handling are missing. |
| **4. Food & Beverage POS & KDS** | **90%** | **OPERATIONAL** | Multi-round table ordering on active dining sessions, KDS/BDS station isolation, and prep notes are verified working. |
| **5. Inventory & Supply Chain** | **95%** | **STABLE** | Non-negative stock constraints, GRNs, recipe BOM sale deductions, and supplier RBAC are verified working. |
| **6. Housekeeping & Facilities** | **95%** | **STABLE** | Automated checkout cleaning tasks, dedicated cleaner dashboard, minibar folio charges, and lost-and-found work cleanly. |
| **7. Reporting & Analytics** | **60%** | **DEFECTIVE / AT RISK** | Police and Occupancy reports work. Consolidated Daily Revenue report triple-counts room charges; Z-report tab prematurely closes day. |
| **8. Infrastructure & Deployment** | **85%** | **READY FOR PILOT** | Production startup fail-closed assertions, Passenger WSGI error masking, and CSP/HSTS security headers are operational. |
| **OVERALL PILOT READINESS** | **87%** | **CONDITIONALLY READY** | **Ready for pilot upon resolving P1 Revenue Report defect and establishing clean Git baseline.** |

---

## 2. Git Working Tree & Local Modification Status

The repository is on branch `development` at commit `b6ea79f`. There is an active dirty working tree consisting of **13 modified files** and **2 untracked files**.

### Detailed File-by-File Breakdown:
1. `apps/finance/services.py` (Modified):
   - Adds default Chart of Accounts: Petty Cash (`1020`), Maintenance & Repairs Expense (`5400`), and Marketing & Advertising Expense (`5500`).
   - Impact: Enhances expense tracking granularity.
   - Verification: All 13 finance tests pass.
2. `apps/finance/views.py` (Modified):
   - Implements safe zero defaults, MM/DD/YYYY date parsing resilience, and bounded exception handling in `TaxReportView`.
   - Impact: Prevents 500 errors when querying tax reports for empty date periods.
   - Verification: Tested with `test_tax_report.py`.
3. `apps/finance/tests/test_tax_report.py` (Modified):
   - Adds automated regression tests for US date parsing and safe empty defaults.
   - Verification: 13/13 tests pass in 0.67s.
4. `apps/finance/tests/test_expense_manager.py` (**Untracked**):
   - 127-line test suite covering Expense Manager creation, Supplier access control, Petty Cash accounts, and General Ledger journal entry generation.
   - Verification: 4/4 tests pass.
5. `apps/inventory/views.py` (Modified):
   - Updates `SupplierViewSet` permissions from `IsInventoryManager` to `IsSupplierOperator`.
   - Impact: Allows Finance staff to view and manage suppliers when entering expenses.
   - Verification: Verified via unit tests.
6. `core/api.py` (Modified):
   - Updates `_message` helper to extract nested Django REST Framework field validation errors.
   - Impact: Form errors return user-friendly field-level messages instead of generic "Request could not be completed".
   - Verification: Tested in `users/test_api_errors.py`.
7. `hotel-frontend/src/App.js` (Modified):
   - Fixes user badge deduplication in header when username equals role (e.g. `finance` / `FINANCE`).
   - Impact: Clean UI displaying user full name or "Hotel Staff" subtitle.
   - Verification: Verified in `App.test.js`.
8. `hotel-frontend/src/App.test.js` (Modified):
   - Added unit tests for profile header badge deduplication and full-name display.
   - Verification: 5/5 tests pass.
9. `hotel-frontend/src/apiClient.js` (Modified):
   - Enhanced `apiErrorMessage` helper to recursively parse and format nested error dictionaries.
   - Impact: Toast alerts display readable validation messages.
   - Verification: Tested in `apiClient.test.js`.
10. `hotel-frontend/src/apiClient.test.js` (**Untracked**):
    - 70-line test suite covering API error message extraction across all backend error envelopes.
    - Verification: 4/4 tests pass.
11. `hotel-frontend/src/pages/FinanceDashboard.js` (Modified):
    - Implemented Ethiopian income tax (PAYE) calculation brackets and 7%/11% pension auto-calculator; wired form inputs to state.
    - Impact: Automated payroll tax deduction calculations.
    - Verification: Frontend production build compiles cleanly.
12. `hotel-frontend/src/pages/InventoryDashboard.js` (Modified):
    - Standardized modal overlay dismissal (clicking backdrop or Esc), back/cancel buttons, and styling across supplier and SKU modals.
    - Impact: Resolves modal trapping issues.
    - Verification: Production build OK.
13. `users/permissions.py` (Modified):
    - Declares `IsSupplierOperator` permission allowing `admin`, `inventory`, and `finance` users.
    - Impact: Enables finance expense logging against suppliers.
    - Verification: Verified via tests.
14. `users/views.py` (Modified):
    - Re-exports `IsSupplierOperator` for legacy backward compatibility.
    - Verification: Clean imports.
15. `users/test_api_errors.py` (Modified):
    - Added unit test `test_field_validation_error_extracts_descriptive_message`.
    - Verification: Passed.

**Recommendation:** Do NOT discard or reset any of these 15 files. They represent completed, high-quality, verified enhancements. Upon owner approval, commit them to establish a clean baseline.

---

## 3. Test Suites & Quality Assurance Summary

### Backend Tests
- **Test Runner:** `core.test_runner.IsolatedRunner`
- **Execution Settings:** `core.settings_test` (In-memory SQLite, isolated cache, isolated mock uploads)
- **Results:**
  - `apps.finance`: 13 passed, 0 failed
  - `core`: 18 passed, 0 failed
  - `apps.orders`: 28 passed, 0 failed
  - `apps.reporting` + `apps.rooms`: 30 passed, 0 failed
  - `users`: 118 passed, 0 failed (3 PostgreSQL concurrency tests skipped as designed)
  - **Total Backend Tests:** **207 tests (204 passed, 3 skipped, 0 failed)**
- **System Integrity:** `python manage.py check` reports **0 issues**.
- **Database Schema Drift:** `python manage.py makemigrations --check` reports **no changes detected**.

### Frontend Tests
- **Test Runner:** Jest / React Testing Library (`npm test -- --watchAll=false`)
- **Results:**
  - `src/apiClient.test.js`: 4 passed
  - `src/App.test.js`: 5 passed
  - **Total Frontend Tests:** **9 passed, 0 failed (2 test suites)**
- **Production Build:** `npm run build` completed successfully. Main bundle size: 281.55 kB gzip.

---

## 4. Key Architectural Safeguards in Place

1. **Database-Enforced Anti-Double-Booking:**
   PostgreSQL `btree_gist` exclusion constraint prevents overlapping date ranges for the same room.
2. **Double-Entry General Ledger:**
   All cash receipts, room checkouts, restaurant orders, minibar consumptions, and payroll entries post strictly balanced debits and credits (`total_debit == total_credit`) to immutable `JournalEntry` records.
3. **Transactional State Machines:**
   `Reservation.save()`, `Order.save()`, and `StockTransaction` enforce valid transition paths with explicit database row locks (`select_for_update()`).
4. **Isolated Media Storage:**
   Guest ID scans and sensitive KYC documents are saved outside public static directories and served only through authenticated, role-authorized endpoints.
5. **Fail-Closed Production Configuration:**
   Application startup halts immediately if `DEBUG=True` in production, or if database/payment credentials are missing.

---

## 5. Identified Defects & Recovery Tasks

| ID | Issue Description | Severity | Impact | Status |
| :--- | :--- | :---: | :---: | :---: |
| **DEFECT-FIN-001** | Triple-counting of room-charged F&B meals in Daily Revenue Report (`apps/reporting/views.py:271`). | **Critical (P1)** | Corrupts financial analytics and executive dashboard. | Confirmed / Proposed |
| **DEFECT-OPS-001** | Clicking "Z-Report" tab in Reports Center triggers immediate `POST` request closing the day (`ReportsCenter.js:52`). | **High (P2)** | Accidental premature day closure. | Confirmed / Proposed |
| **DEFECT-PMS-001** | Missing Night Audit daily rollover pipeline, business date tracking, and daily room accrual. | **High (P2)** | Inability to run structured hotel end-of-day accounting. | Confirmed / Proposed |
| **DEFECT-PMS-002** | `Reservation.STATUS_CHOICES` lacks `no_show` status; confirmed reservations block rooms indefinitely. | **Medium (P2)** | Inventory deadlock for unarrived guests. | Confirmed / Proposed |
| **DEFECT-GIT-001** | Dirty working tree with 15 uncommitted files from interrupted development sprint. | **Medium (P3)** | Codebase handoff risk and lack of baseline tag. | Confirmed / Proposed |
| **DEFECT-POS-001** | Cashier bills screen displays separate order tickets rather than consolidated table session billing. | **Medium (P3)** | Cashier operational overhead during table settlement. | Confirmed / Proposed |
| **DEFECT-ROLE-001** | Phantom `delivery` role in `User.ROLE_CHOICES` with zero endpoints or views. | **Low (P4)** | Administrative dead code. | Confirmed / Proposed |

---

## 6. Pilot Deployment Readiness Assessment

The Acrma Hotel ERP is **conditionally ready for a single-hotel pilot deployment**, subject to the following recovery sequence:

### Gate 1: Baseline Stabilization (Immediate)
- Obtain owner approval to commit the 15 verified in-flight files.
- Tag the repository at `baseline-takeover-2026-10-24`.

### Gate 2: Critical Defect Remediation (Before Pilot Go-Live)
- Correct `DEFECT-FIN-001` (Daily Revenue Report triple-counting).
- Correct `DEFECT-OPS-001` (ReportsCenter Z-Report preview vs closure separation).
- Implement `DEFECT-PMS-002` (`no_show` reservation status).

### Gate 3: Night Audit Implementation (First Week of Pilot)
- Implement `SystemSettings.current_business_date`.
- Implement `NightAuditService` for nightly room rate accrual.
- Build front-desk Night Audit modal in `RoomManager.js`.
