# Acrma Hotel ERP — Architecture, Test Suites & Cross-Phase Dependency Mapping Report

**Report ID:** EXP-3-ARCH-TEST-DEP-SURVEY  
**Audit Date:** 2026-11-03  
**Auditor:** Explorer 3 (Architecture, Test Suites & Cross-Phase Dependency Mapping)  
**Deliverable Path:** `.agents/teamwork/explorer_survey_3/handoff.md`  
**Governing Directive:** `.agents/teamwork/ORIGINAL_REQUEST.md` & `DISPATCH.md`  

---

## Executive Summary

This investigation provides an authoritative technical survey of the Acrma Hotel ERP architecture, test runner infrastructure, and cross-phase dependency topology to govern remaining development phases (Phase 2.1 Audit, Phase 2.2 Procurement Operational Frontend, Phase 2.3 Procurement Integration & Browser Acceptance, Phase 3 Physical Stocktaking, and Phase 4 Final Integration & Release Readiness).

Key conclusions:
1. **Architecture & Code Layout:** The system is structured as a Django 5.2.17 / DRF 3.18.2 modular monolith (PostgreSQL 16) with a modern React 19 single-page application. Core models reside in `hotel/models.py` and `users/models.py`, while domain business logic, serializers, views, and test suites are cleanly divided across `apps/` (`inventory`, `finance`, `orders`, `reservations`, `rooms`, `identity`, `reporting`, `audit`).
2. **Phase 2.1 Backend Readiness:** The Phase 2.1 backend implementation for RFQ, Supplier Quotation, and Split-Award PO Conversion is fully coded in `hotel/procurement.py` (1,386 lines), registered in `apps/inventory/views.py`, and backed by Migration `0047_rfq_and_supplier_quotation_workflow.py`. All 10 automated unit tests pass in 0.85s.
3. **Phase 2.2 & Phase 3 Frontend Status:** The frontend (`hotel-frontend/src/pages/InventoryDashboard.js`) currently has 10 tabs covering legacy inventory, but **zero operational UI** for Requisitions, RFQs, Quotations, Split-Award POs, 3-Way Invoice Matching, or Stocktake Sessions. This strictly honors the non-negotiable phase gate: Phase 2.2 has not begun prior to Phase 2.1 owner acceptance.
4. **Execution Topology:** A strict serial critical path separates phase gates (Owner Sign-Off -> Phase 2.2 -> Phase 2.3 Integration -> Owner Authorization -> Phase 3 -> Phase 4 Release Gate), while allowing high-throughput parallel execution across Backend (Agent A), Frontend (Agent B), QA (Agent C), Security/Accounting (Agent D), and Architecture (Agent E) within each phase.

---

## 1. Observation

### 1.1 Technical Architecture & Code Layout

Direct inspection of configuration files, settings modules, and application directories confirms the following architecture:

#### Backend Stack & Directory Structure
- **Framework & Core Libraries:**
  - Python runtime (executed via virtual environment `.venv\Scripts\python.exe`)
  - `Django==5.2.17`
  - `djangorestframework==3.18.2`
  - `djangorestframework-simplejwt==5.5.1` (with `rest_framework_simplejwt.token_blacklist`)
  - `django-unfold==0.61.0` (modern Tailwind-based admin UI)
  - `psycopg2-binary==2.9.10`
  - `dj-database-url==3.0.1`
  - `gunicorn==23.0.0`
  - `Pillow==13.0.0`
- **Application Modules (`INSTALLED_APPS` in `core/settings.py:67-81`):**
  - Core Django: `unfold`, `django.contrib.admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`
  - Third-party: `rest_framework`, `rest_framework_simplejwt`, `rest_framework_simplejwt.token_blacklist`, `corsheaders`
  - Domain Apps: `users`, `hotel`
  - Modular Domain Packages (`apps/` directory, routed through `users/urls.py:7-17`):
    - `apps.identity` (`apps/identity/`): Authentication, MFA, OTP challenges, token versioning, lockout.
    - `apps.rooms` (`apps/rooms/`): Room status, housekeeping tasks, lost and found, room categories.
    - `apps.reservations` (`apps/reservations/`): Front office booking, stay lifecycle, check-in/out, no-show status.
    - `apps.orders` (`apps/orders/`): Restaurant/Bar POS, DiningSession multi-round ordering, KDS station isolation.
    - `apps.payments` (`apps/payments/`): Chapa HMAC verification, webhook idempotency, transaction references.
    - `apps.inventory` (`apps/inventory/`): SKU catalog, locations, batches, transfers, waste, recipe BOMs, procurement, stocktaking.
    - `apps.finance` (`apps/finance/`): Double-entry General Ledger, Chart of Accounts, payroll PAYE, expense management.
    - `apps.reporting` (`apps/reporting/`): GL-backed Daily Revenue Report, Police report, Occupancy, Z-Report.
    - `apps.audit` (`apps/audit/`): Immutable `AuditEvent` logging with actor attribution and correlation IDs.
- **Database & Environment Architecture:**
  - Database Engine: PostgreSQL 16
  - Production / Cloud Connection: Supports Neon.tech connection strings (`DATABASE_URL`) with enforced SSL (`sslmode=require`), PgBouncer connection pooling awareness (`-pooler`), connection health checks, and query timeouts (`statement_timeout=30000ms`, `lock_timeout=5000ms`).
  - Fallback / Local Connection: Standard PostgreSQL parameters (`DB_NAME=hotel_erp_db`, `DB_USER=postgres`, `DB_HOST=localhost`, `DB_PORT=5432`).
  - Environment Loading: `python-dotenv` loads from `.env`. Fail-closed validation triggers when `DJANGO_ENV=production`, checking minimum secret entropy (32+ chars, >=16 unique symbols, >=3.2 bits/char) and forbidding insecure defaults.

#### Frontend Stack & Directory Structure
- **Framework & Runtime (`hotel-frontend/package.json`):**
  - `react`: `^19.2.4`
  - `react-dom`: `^19.2.4`
  - `react-router-dom`: `^7.14.0`
  - `react-scripts`: `5.0.1` (Webpack 5 underneath)
  - `axios`: `^1.14.0` (Centralized HTTP client with JWT interceptors)
  - `framer-motion`: `^12.38.0` (Animations)
  - `lucide-react`: `^1.7.0` (Icons)
  - `qrcode.react`: `^4.2.0`
  - `react-to-print`: `^3.3.0` (Thermal receipt and folio printing)
- **Directory Layout:**
  - `hotel-frontend/src/App.js`: Top-level application shell, header, user profile, and master tab routing.
  - `hotel-frontend/src/Sidebar.js`: Section-grouped navigation (`OVERVIEW`, `OPERATIONS`, `FINANCE`, `REPORTS`, `ADMIN`) with role-based and module-flag visibility filters.
  - `hotel-frontend/src/apiClient.js`: Unified Axios client handling Bearer token injection, recursive error envelope parsing (`apiErrorMessage`), and session expiration dispatch.
  - `hotel-frontend/src/pages/`: Modular page views including `OrdersManager.js`, `RoomManager.js`, `FinanceDashboard.js`, `InventoryDashboard.js`, `ReportsCenter.js`, `CashierDashboard.js`, `KitchenDashboard.js`, `BarDashboard.js`, `WaiterDashboard.js`, `HousekeepingManager.js`, `UserManager.jsx`.

---

### 1.2 Test Suite Architecture & Infrastructure

Inspection of `.github/workflows/ci.yml`, `core/settings_test.py`, `core/test_runner.py`, and test packages across the codebase reveals:

#### Test Infrastructure & Configuration
- **Backend Test Runner:** Custom runner `core.test_runner.IsolatedRunner` extending Django's `DiscoverRunner`.
  - Configured in `core/settings_test.py:29`: `TEST_RUNNER = "core.test_runner.IsolatedRunner"`.
  - In-Memory Database: Uses SQLite in-memory `:memory:` for high test velocity and clean state isolation between runs.
  - Hash Acceleration: Overrides `PASSWORD_HASHERS` with `MD5PasswordHasher` (`core/settings_test.py:24-26`).
  - Storage & Media Isolation: `IsolatedRunner.setup_test_environment()` provisions temporary directories (`hotel-tests-*`) for `MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT`, tearing them down automatically.
  - Cache Isolation: `IsolatedResult.startTest()` flushes `hotel_api_cache` before non-SimpleTestCase tests to prevent counter leakage across rate-limiting tests.
- **Frontend Test Runner:** Jest with `@testing-library/react` (`^16.3.2`), `@testing-library/jest-dom` (`^6.9.1`), and `@testing-library/user-event` (`^13.5.0`).
  - Configured in `hotel-frontend/package.json:47-53` with custom `moduleNameMapper` for React Router v7 compatibility.
  - Invoked via: `npm test -- --watchAll=false`.

#### Test Suite Catalog & Verified Invocation Results
All test suites were executed read-only without inspecting test assertions to deduce business logic (satisfying the integrity constraint):

| Test Suite Target | Scope / Purpose | Command Invocations | Observed Result |
| :--- | :--- | :--- | :---: |
| **Django System Check** | Deploy and configuration sanity | `.venv\Scripts\python.exe manage.py check --settings=core.settings_test` | **0 issues** (1 silenced) |
| **Migration Drift Check** | Schema drift and model sync | `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | **No changes detected** |
| **Phase 2.1 RFQ & Quotations** | RFQ creation, bidding, multi-award, PO conversion | `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --settings=core.settings_test` | **10 passed** (0.846s) |
| **Procurement 3-Way Match** | Requisitions, PO, GRN receiving, GRNI, invoice matching | `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --settings=core.settings_test` | **12 passed** (0.783s) |
| **Dual-Mode Stocktaking** | Blind/visible modes, mode locking, recount, GL posting | `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --settings=core.settings_test` | **12 passed** (0.726s) |
| **Frontend Unit Suites** | `apiClient.test.js`, `ReportsCenter.test.js`, `App.test.js` | `Set-Location hotel-frontend; npm test -- --watchAll=false` | **19 passed** (3 suites, 61.3s) |
| **Full Baseline Backend Suite** | Full backend test suite across all modules | `.venv\Scripts\python.exe manage.py test --settings=core.settings_test` | **207 passed** (3 skipped PostgreSQL-only) |

---

## 2. Logic Chain

### 2.1 Cross-Phase Dependency Graph & Remaining Roadmap

The project requirements specify four remaining phases:
- **Phase 2.2:** Procurement Operational Frontend
- **Phase 2.3:** Procurement Integration and Browser Acceptance
- **Phase 3:** Physical Stocktaking
- **Phase 4:** Final Integration and Release Readiness

The following dependency graph models the progression and gating prerequisites:

```
[Phase 2.1 Backend Implementation] (COMPLETED IN CODE)
       │
       ▼
[GATE 1: Owner Acceptance & Baseline Audit of Phase 2.1] ◄── STRICT NON-NEGOTIABLE GATE
       │
       ├────────────────────────────────────────┐
       ▼                                        ▼
[Phase 2.2A: Requisitions & RFQ UI]    [Phase 2.2B: Quotation & Award UI]
       │                                        │
       └───────────────────┬────────────────────┘
                           ▼
              [Phase 2.2C: PO, GRN & 3-Way Match UI]
                           │
                           ▼
              [Phase 2.2 Frontend Build Gate]
                           │
                           ▼
              [GATE 2: Independent QC Inspection of Phase 2.2]
                           │
                           ▼
              [Phase 2.3: Procurement Integration & Browser Acceptance]
                           │
                           ▼
              [GATE 3: Owner Acceptance of Phase 2.3 / Procurement Milestone]
                           │
                           ▼
              [GATE 4: Owner Authorization to Start Phase 3] ◄── STRICT GATE
                           │
                           ▼
              [Phase 3: Dual-Mode Physical Stocktaking (Frontend & Workflow)]
                           │
                           ▼
              [GATE 5: Independent QC Inspection of Phase 3]
                           │
                           ▼
              [GATE 6: Owner Authorization to Start Phase 4] ◄── STRICT GATE
                           │
                           ▼
              [Phase 4: Final Integration, Release Readiness & Night Audit]
                           │
                           ▼
              [FINAL RELEASE GATE: Owner Production Sign-Off]
```

---

### 2.2 Serialized Critical Path vs. Safe Parallel Execution

To maximize engineering throughput without risking architectural divergence or boundary violations, tasks are categorized into **Strictly Serialized Phases** and **Safe Concurrent Workstreams**:

#### Strictly Serialized Critical Path (Gates requiring completion and approval before advancing):
1. **Serial Gate 1 (Phase 2.1 Acceptance Gate):**
   - *Constraint:* Zero Phase 2.2 feature code may be written until the repository state, working tree modifications, and Phase 2.1 evidence are audited and accepted by the Owner.
   - *Rationale:* Modifying frontend UI on unaccepted API contracts risks rework and violates R3.
2. **Serial Gate 2 (Phase 2.2 -> Phase 2.3 Transition):**
   - *Constraint:* End-to-end browser acceptance testing and cross-module integration cannot execute until Phase 2.2 frontend views compile cleanly and are wired to backend endpoints.
3. **Serial Gate 3 (Phase 2.3 -> Phase 3 Transition):**
   - *Constraint:* Physical Stocktaking implementation requires explicit Owner authorization after formal sign-off on Phase 2.3.
4. **Serial Gate 4 (Phase 3 -> Phase 4 Transition):**
   - *Constraint:* Release readiness and final Night Audit integration require completion and QC sign-off of Physical Stocktaking.

#### Safe Concurrent Execution Tracks (Parallel tracks within active phases):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 2.2 PARALLEL EXECUTION TOPOLOGY                           │
├────────────────────┬───────────────────────────────────┬───────────────────────────────┤
│ Track / Agent      │ Workstream Scope                  │ Dependencies & Interlocks     │
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track B-1**      │ Requisitions & Approval Tier UI   │ Consumes `/procurement/reqs/` │
│ (Agent B - Front)  │ • Requisition creation form       │ and `/procurement/policies/`. │
│                    │ • Line item spec builder          │ No dependency on RFQ UI.      │
│                    │ • Managerial approval tier badges │                               │
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track B-2**      │ RFQ & Supplier Bidding UI         │ Consumes `/procurement/rfqs/`.│
│ (Agent B - Front)  │ • RFQ creation from approved reqs │ Can run in parallel with B-1. │
│                    │ • Invited vs public bidding toggle│                               │
│                    │ • Deadline countdown & closure UI │                               │
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track B-3**      │ Supplier Quotation & Awarding UI  │ Consumes `/quotations/` and   │
│ (Agent B - Front)  │ • Quotation submission portal     │ `/quotations/award/`.         │
│                    │ • Landed cost ETB calculator      │ Can run in parallel with B-2. │
│                    │ • Split-award selection matrix    │                               │
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track B-4**      │ GRN Desk & 3-Way Match UI         │ Consumes `/procurement/grns/` │
│ (Agent B - Front)  │ • Perishable expiry date input    │ and `/procurement/invoices/`. │
│                    │ • PO vs GRN vs Invoice comparison │ Dependent on B-3 for PO link. │
│                    │ • GRNI accrual / PPV preview      │                               │
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track A**        │ API Contract & Serializer Support │ Validates query params, nested│
│ (Agent A - Back)   │ • Pagination & filtering tuning   │ payload validation, and CORS. │
│                    │ • Mock test vectors for frontend  │ Runs in parallel with Track B.│
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track D**        │ Accounting & Security Audit       │ Validates Dr 1300 / Cr 2010   │
│ (Agent D - Sec/Acc)│ • Double-entry GL invariant check │ and Dr 2010 / Cr 2000 / Cr 5040│
│                    │ • Dependency audit (`pip-audit`)  │ Runs in parallel with Track B.│
├────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ **Track C**        │ QA Test Plan & Acceptance Design  │ Prepares browser test vectors,│
│ (Agent C - QA)     │ • E2E test plan for Phase 2.3     │ Playwright/Cypress scenarios, │
│                    │ • Edge case matrix (split awards) │ and mock datasets in parallel.│
└────────────────────┴───────────────────────────────────┴───────────────────────────────┘
```

---

### 2.3 Agent Responsibilities & Task Ownership Matrix

To prevent role overlap and ensure accountability across the multi-agent team, tasks and approval gates are assigned as follows:

| Agent Role | Primary Responsibilities | Phase Ownership & Key Artifacts | Strict Prohibitions |
| :--- | :--- | :--- | :--- |
| **Agent A**<br>(Backend Engineering) | • Maintain Django ORM models, serializers, services, viewsets, and database migrations.<br>• Provide backend optimizations (N+1 queries, indexing, pagination).<br>• Enforce transactional locking (`select_for_update`) and idempotency keys. | • `hotel/procurement.py`<br>• `hotel/stocktaking.py`<br>• `apps/inventory/views.py`<br>• `hotel/migrations/` | • Never modify code to make failing tests pass artificially.<br>• Never execute destructive SQL or alter production DB. |
| **Agent B**<br>(Frontend Engineering) | • Implement modular, responsive UI components in React 19.<br>• Build Procurement dashboards (Requisitions, RFQs, Quotes, Split Awards, GRN, 3-Way Match).<br>• Build Physical Stocktaking count and recount interfaces.<br>• Wire forms to `apiClient.js` with comprehensive error envelopes. | • `hotel-frontend/src/pages/procurement/`<br>• `hotel-frontend/src/pages/stocktaking/`<br>• `hotel-frontend/src/Sidebar.js`<br>• `hotel-frontend/src/App.js` | • Never commit build artifacts or bypass lint/test gates.<br>• Never implement unaccepted phase features. |
| **Agent C**<br>(QA and Test Engineering) | • Execute and audit automated test suites (Django and Jest).<br>• Design and execute cross-module integration tests and browser acceptance tests.<br>• Verify regression safety across all 207+ backend and 19+ frontend tests. | • `apps/inventory/tests/`<br>• `hotel-frontend/src/*.test.js`<br>• Test execution evidence logs | • **Never read test assertions to deduce expected business logic prior to implementation** (Integrity rule).<br>• Never modify implementation code. |
| **Agent D**<br>(Security and Accounting) | • Verify double-entry GL balance invariants (`total_debit == total_credit`).<br>• Validate GRNI interim accrual (Account 2010) and PPV variance accounts (Account 5040).<br>• Enforce Separation of Duties (`counted_by != approved_by`, requisitioner != approver).<br>• Run vulnerability scans (`pip-audit`, `detect-secrets`). | • Financial reconciliation reports<br>• Security runbooks (`docs/PAYMENT_OPERATIONS.md`, `docs/IDENTITY_SECURITY.md`) | • Never approve unverified financial entries.<br>• Never activate live payment credentials in dev. |
| **Agent E**<br>(Independent Architecture Reviewer) | • Perform architectural reviews of domain boundaries and modular monolith structure.<br>• Verify compliance with ADR-001 through ADR-008 and procurement/stocktaking ADRs.<br>• Inspect concurrency safeguards, row locking, and API versioning. | • Architecture review logs<br>• Technical debt and refactoring recommendations | • Never authorize shortcuts that violate modular monolith boundaries or fail-closed principles. |
| **Independent QC Agent** | • Independent, neutral quality inspection of actual changed files, tests, and evidence against engineering standards.<br>• Issue binding formal decision: `PASS`, `PASS WITH NON-CRITICAL OBSERVATIONS`, or `FAIL`. | • Formal QC Verification Report for each phase gate | • Never accept implementation without independent verification.<br>• Must remain strictly objective and independent of implementing agents. |
| **Main Orchestrator**<br>(Technical Lead) | • Overall technical leadership, task dispatch, and agent coordination.<br>• Maintain master execution tracker at `docs/MASTER_EXECUTION_TRACKER.md`.<br>• Serve as the exclusive interface to the repository Owner for phase sign-off. | • `docs/MASTER_EXECUTION_TRACKER.md`<br>• Formal coordination reports | • Never mark incomplete workflows as complete.<br>• Never advance phases without Owner and QC sign-offs. |

---

### 2.4 Financial Integrity & Accounting Logic Invariants

Every remaining phase involves financial movements and inventory balance adjustments that must adhere to double-entry bookkeeping rules:

1. **Procurement GRN Interim Receiving (Phase 2.1 & 2.2):**
   - Upon physical receipt of goods at `STORE-MAIN`, the system issues a Goods Receipt Note and posts:
     - **Debit:** Account `1300` (Inventory Asset) for goods valuation.
     - **Credit:** Account `2010` (Goods Received Not Invoiced - GRNI) for interim liability.
   - Verified in `hotel/procurement.py:601-634`.
2. **3-Way Matching & Final Invoice Settlement (Phase 2.1 & 2.2):**
   - When the supplier invoice arrives, quantities and prices are matched against the PO and GRN. Upon approval:
     - **Debit:** Account `2010` (GRNI) to clear interim liability.
     - **Debit / Credit:** Account `5040` (Purchase Price Variance - PPV) for any tolerated variance between PO unit price and invoice unit price.
     - **Credit:** Account `2000` (Accounts Payable) for the final supplier liability.
   - Enforces invariant: `total_debit == total_credit`.
3. **Physical Stocktaking Discrepancy Adjustment (Phase 3):**
   - Discrepancies between physical count and theoretical system balance post balanced adjustments:
     - *Deficit (Physical < Theoretical):*
       - **Debit:** Account `5020` (Inventory Variance / Loss Expense).
       - **Credit:** Account `1300` (Inventory Asset).
     - *Surplus (Physical > Theoretical):*
       - **Debit:** Account `1300` (Inventory Asset).
       - **Credit:** Account `5020` (Inventory Variance / Loss Expense).
   - Enforces invariant: Handled atomically via `record_stock_change()` inside `hotel/stocktaking.py:382-422`.

---

## 3. Caveats & Architectural Bottlenecks

1. **SQLite In-Memory Test Runner vs. PostgreSQL Production:**
   - *Observation:* The automated test runner (`core.test_runner.IsolatedRunner`) executes against an in-memory SQLite database (`:memory:`).
   - *Risk:* PostgreSQL-specific exclusion constraints (such as `btree_gist` anti-double-booking constraints in Migration `0023`) and true multi-connection row-locking behavior (`select_for_update()`) are skipped or no-oped during SQLite runs.
   - *Recommendation:* Prior to final Phase 4 release, a dedicated test run against a staging PostgreSQL 16 database must be executed to validate concurrency constraints under real multi-threaded connections.
2. **Monolithic Frontend Component Sizing:**
   - *Observation:* `hotel-frontend/src/pages/InventoryDashboard.js` already spans 4,446 lines (247 KB), and `RoomManager.js` spans 88 KB.
   - *Risk:* Implementing all Procurement views (Requisitions, RFQs, Quotes, Awards, POs, GRN, 3-Way Match) directly within `InventoryDashboard.js` will degrade maintainability, create massive Git diffs, and increase merge conflict risks.
   - *Recommendation:* Agent B must implement Procurement as modular sub-components under a dedicated directory: `hotel-frontend/src/pages/procurement/` (`RequisitionManager.jsx`, `RfqManager.jsx`, `QuotationBidding.jsx`, `AwardMatrix.jsx`, `GrnDesk.jsx`, `InvoiceMatching.jsx`), importing them into the master inventory or sidebar router.
3. **PowerShell CLI Syntax & Virtualenv Execution:**
   - *Observation:* Chained commands using `&&` fail in Windows PowerShell (PowerShell requires `;` or separate commands). Furthermore, invoking system `python` fails with `ModuleNotFoundError: No module named 'django'`.
   - *Actionable Requirement:* All commands and agent scripts must explicitly target `.venv\Scripts\python.exe` and use PowerShell-compatible syntax.
4. **Working Tree Modification Volume:**
   - *Observation:* The working tree currently contains 37 modified files and 26 untracked files with Git HEAD at baseline `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`.
   - *Risk:* A developer running `git checkout .`, `git reset --hard`, or `git clean -fd` would wipe out months of verified engineering work across Expense Management, Tax Hardening, Batch Tracking, Procurement, and Stocktaking.
   - *Non-Negotiable Policy:* Never reset repository, never discard user changes. Stage and preserve in-flight work.

---

## 4. Conclusion

1. **Phase 2.1 Backend Implementation is Complete and Verified:**
   - All backend models, migrations (`0045`, `0047`), business logic (`hotel/procurement.py`), and DRF viewsets (`apps/inventory/views.py`) are fully implemented and passing all 22 focused procurement tests (`test_rfq_quotation_workflow` 10/10, `test_procurement_management` 12/12).
   - **Recommendation:** Formally recommend Phase 2.1 for Owner Acceptance, subject to staging and preserving the working tree files.
2. **Phase 2.2 is Ready for Implementation Upon Owner Sign-Off:**
   - The backend API endpoints are stable and operational.
   - Once Owner approval is granted, Agent B can immediately begin building the Procurement UI in parallel sub-tracks.
3. **Master Execution Tracker Input:**
   - The phase definitions, dependencies, agent ownership matrix, and serialized approval gates detailed in Section 2 provide the authoritative blueprint for `docs/MASTER_EXECUTION_TRACKER.md`.

---

## 5. Verification Method

To independently verify all findings and claims in this report, execute the following commands in sequence from the project root using PowerShell:

### 1. Django Configuration & Deployment Check
```powershell
.venv\Scripts\python.exe manage.py check --settings=core.settings_test
```
*Expected Result:* `System check identified no issues (1 silenced).`

### 2. Database Schema Drift Verification
```powershell
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```
*Expected Result:* `No changes detected`

### 3. Phase 2.1 Backend RFQ & Quotation Test Suite
```powershell
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --settings=core.settings_test
```
*Expected Result:* `Ran 10 tests in ~0.8s ... OK`

### 4. Procurement 3-Way Match & Requisition Test Suite
```powershell
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --settings=core.settings_test
```
*Expected Result:* `Ran 12 tests in ~0.8s ... OK`

### 5. Dual-Mode Physical Stocktaking Test Suite
```powershell
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --settings=core.settings_test
```
*Expected Result:* `Ran 12 tests in ~0.8s ... OK`

### 6. Frontend Unit Test Suite
```powershell
Set-Location hotel-frontend; npm test -- --watchAll=false
```
*Expected Result:* `Test Suites: 3 passed, 3 total; Tests: 19 passed, 19 total`

### 7. Frontend Production Compilation Check
```powershell
Set-Location hotel-frontend; npm run build
```
*Expected Result:* `Compiled successfully.` File sizes after gzip: `301.39 kB` (`build/static/js/main.ce8c58e7.js`), `3.84 kB` (`build/static/css/main.c6610b91.css`). Verified deployable in `hotel-frontend/build/`.


