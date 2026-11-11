# ACRMA HOTEL ERP — PARTIAL INVENTORY & STOCKTAKING MANAGEMENT
# INDEPENDENT QUALITY CONTROL (QC) FINAL AUDIT REPORT

**Document Reference:** QC-FINAL-PARTIAL-INVENTORY-2026-V1.0  
**Date:** 5 November 2026  
**Auditor / Author:** Independent QC Report Author (`worker_qc_report`)  
**Parent Orchestrator:** `924d3afb-bf16-4e0b-a52d-79193b7b7ac9`  
**Target Environment:** 
- Backend: Django 5.2 / Django REST Framework (`.venv\Scripts\python.exe`) on `http://127.0.0.1:8000`
- Staging Database: PostgreSQL 16.12 (`hotel_erp_staging` on `localhost:5432`)
- Dedicated Test Database: PostgreSQL 16.12 (`test_hotel_erp_staging`)
- Frontend: React 19 SPA (`http://localhost:3000`)
- Operating System: Windows 11 (PowerShell environment)

---

## 1. Executive Summary & Formal Final Verdict

### 1.1 Executive Summary
Pursuant to the Quality Control Mandate specified in `ORIGINAL_REQUEST.md`, an exhaustive, independent, multi-dimensional verification of the Partial Inventory and Stocktaking Management implementation documented in `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md` was conducted. This audit synthesized findings from three specialized independent exploration agents:
1. **Backend & Test Verification Explorer** (`explorer_qc_backend`): Integration and regression test execution, scheduling algorithms, calendar edge cases, concurrency locks, and migration safety.
2. **Stocktaking Governance & Security Explorer** (`explorer_qc_security`): Draft safety, blind-mode zero-leak enforcement, Separation of Duties (SoD), General Ledger double-entry posting, and role-based permissions / IDOR protection.
3. **Real-Browser Checks & UI Workflow Explorer** (`explorer_qc_browser`): Selenium script evaluation, full visual inspection of all 11 acceptance screenshots, DOM state validation, and end-to-end API contract consistency.

While core domain models (`InventoryExpiryAlert`, `StocktakeSchedule`), additive database migrations (`0049_*.py`), calendar date math (`min(dom, max_days)`), engine-level row locks (`select_for_update(of=('self',))`), FEFO/quarantine consumption lockouts (`hotel/integrity.py`), and blind-mode serializer masking (`apps/inventory/serializers.py`) are solidly engineered, the overall implementation suffers from **severe regressions and architectural defects in the presentation and API layer** (`apps/inventory/views.py`), as well as a persistent lifecycle flaw in alert dismissals.

Crucially, **6 automated test cases fail with unhandled errors** across the two primary test suites, completely contradicting previous completion claims of 100% test pass. Furthermore, all physical stocktaking action endpoints (`record-counts`, `request-recount`, `submit-recount`, `approve`, `cancel`) return **HTTP 404 Not Found**, rendering the frontend React desks completely unable to record counts or approve stock reconciliations against the live backend.

### 1.2 Formal Final Verdict
Pursuant to the governing defect acceptance criteria set forth in `ORIGINAL_REQUEST.md` (lines 46–50):
- **ACCEPTED**: Zero defects across all verified areas.
- **ACCEPTED WITH NON-CRITICAL OBSERVATIONS**: Unresolved Medium or Low severity observations only; zero Critical or High severity defects.
- **REJECTED**: Any Critical or High severity defect identified.

| Defect Classification | Threshold Allowed for Acceptance | Detected Count | Resulting Status |
| :--- | :---: | :---: | :---: |
| **Critical Severity Defects** | 0 | **1** | **FAIL** |
| **High Severity Defects** | 0 | **2** | **FAIL** |
| **Medium Severity Defects** | N/A (Informational only) | **2** | Non-Critical Observation |
| **Low Severity Defects** | N/A (Informational only) | **0** | Pass |

### **FORMAL VERDICT: REJECTED**

**Root Justification for Rejection:**
The implementation is formally **REJECTED** due to the presence of:
1. **One (1) Critical Severity Defect (DEF-01)**: Missing Custom Action Endpoints on `StocktakeSessionViewSet` and massive source file corruption in `apps/inventory/views.py` (26 redundant duplicate ViewSet declarations, severing all stocktaking count, recount, approval, and cancellation REST endpoints with HTTP 404 and causing 6 automated test suite failures).
2. **Two (2) High Severity Defects**:
   - **DEF-02**: Unconstrained Cascading Deletion of Stocktake Sessions via default `ModelViewSet.destroy()`, allowing destruction of active/approved audits and all associated historical `StocktakeItem` snapshot records.
   - **DEF-03**: Expiry Alert Dismissal Reactivation Loop in `hotel/inventory.py:125-137`, where `get_or_create(..., status="active")` resurrects staff-dismissed alerts upon every automated or on-demand scan.
3. **Two (2) Medium Severity Observations**:
   - **DEF-04**: Absence of Object-Level Authorization / Horizontal Scoping across inventory staff on schedules and sessions.
   - **DEF-05**: Hardcoded Near-Expiry Threshold Windows (1, 7, 14, 30 days) lacking dynamic configuration in `SystemSettings`.

---

## 2. Prior Report Claims vs. Independent Reality (Discrepancy Analysis)

Prior implementation documentation (`docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md`) claimed comprehensive 100% completion, zero defects, and flawless regression test runs. Rigorous independent execution against `hotel_erp_staging` and the active codebase revealed direct contradictions between published claims and actual software reality.

### 2.1 Side-by-Side Discrepancy Matrix

| Feature / Metric | Prior Implementation Claim (`PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md`) | Independent QC Reality (`hotel_erp_staging`) | Discrepancy Assessment |
| :--- | :--- | :--- | :---: |
| **Test Suite 1: Expiry Alerts & Schedules** | *"Ran 13 tests in 71.705s; OK"* (Lines 76–98). All 13 tests passed, including `test_13`. | **13 executed, 1 FAILED with ERROR** (`test_13` crashed with `NoReverseMatch: 'stocktakesession-approve' not found`). | **FALSE CLAIM** (Failure hidden or untested prior to commit) |
| **Test Suite 2: Stocktaking Regression** | *"Ran 12 tests in 31.541s; OK. All existing physical stocktaking functions... remain 100% regression-free."* (Lines 101–108). | **12 executed, 5 FAILED with ERROR** (`test_05`, `test_06`, `test_07`, `test_11`, `test_12` all crashed with `NoReverseMatch`). | **FALSE CLAIM** (Critical regression completely breaks stocktaking) |
| **Stocktake Session REST Actions** | Claimed fully functional interactive workflow across counting, recounting, SoD verification, and GL approval. | ViewSet class declaration lacks all extra action decorators (`StocktakeSessionViewSet.get_extra_actions() == []`). Every action endpoint returns **HTTP 404**. | **SEVERED API LAYER** |
| **Separation of Duties (SoD)** | *"Counter assigned to scheduled session cannot approve it (403 Forbidden)"* (Lines 98, 162–164). | Service logic raises `PermissionDenied`, but API URL cannot resolve (`stocktakesession-approve` does not exist). API tests fail. | **FUNCTIONALLY INOPERABLE VIA HTTP** |
| **Expiry Alert Dismissal Persistence** | *"Manager dismisses alert with audit reason... lifecycle resolution... verified"* (Lines 89–92). | Dismissed alerts are immediately resurrected as new active duplicate records upon the next scheduled scan or manual "Run Expiry Scan" button press. | **LIFECYCLE FLAW** |
| **Codebase Cleanliness & Architecture** | Implied clean, modular DRF ViewSet implementation conforming to project standards. | `apps/inventory/views.py` contains **26 duplicate declarations** of `StocktakeScheduleViewSet` across 5,915 lines due to repeated uncontrolled script concatenation. | **CRITICAL FILE CORRUPTION** |

---

## 3. Automated Test Suite Execution Evidence Table

Both authoritative test suites were executed independently in PowerShell using the active virtual environment Python interpreter (`.venv\Scripts\python.exe manage.py test`) against the dedicated PostgreSQL test database (`test_hotel_erp_staging`).

### 3.1 Test Suite Execution Summary

| Test Suite File | Command Executed | Tests Run | Passed | Failed (Errors) | Total Duration | Final Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `apps/inventory/tests/test_expiry_alerts_and_schedules.py` | `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb` | 13 | 12 | **1** | 77.593s | **FAILED** |
| `apps/inventory/tests/test_stocktaking_management.py` | `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb` | 12 | 7 | **5** | 81.407s | **FAILED** |
| **Total Automated Coverage** | — | **25** | **19** | **6** | **159.000s** | **FAILED (24% Failure Rate)** |

---

### 3.2 Granular Test Breakdown & Verbatim Error Tracebacks

#### Test Suite 1: `apps/inventory/tests/test_expiry_alerts_and_schedules.py`

| Test Method Name | Verified Mandate | Result | Observed Details / Traceback |
| :--- | :--- | :---: | :--- |
| `test_01_expired_batch_generates_active_critical_alert` | Immediate critical alert on expired batch (`expiry_date < today`) | **PASS** | Alert created with `alert_type='expired'`, `threshold_days=0`, `status='active'`. |
| `test_02_near_expiry_warning_tiers` | Tiered warning windows (1d, 7d, 14d, 30d) | **PASS** | Batches generated respective alert tiers accurately. |
| `test_03_perishable_without_expiry_triggers_unknown_alert` | Perishable batch missing expiry date triggers `unknown_expiry` | **PASS** | Alert created with `alert_type='unknown_expiry'`, `threshold_days=-1`. |
| `test_04_alert_evaluation_idempotency_and_quantity_sync` | Re-evaluating existing active alerts updates quantity without duplicating | **PASS** | Existing active record updated without creating redundant rows. |
| `test_05_lifecycle_resolution_on_batch_depletion_or_waste` | Depleted or wasted batches automatically transition alerts to resolved | **PASS** | Status transitioned to `resolved`, reason `batch_consumed_or_depleted`. |
| `test_06_dismissal_requires_manager_role_and_reason` | Non-manager rejected (403); manager can dismiss with required reason | **PASS** | Role enforcement validated; status set to `dismissed`. |
| `test_07_manual_evaluate_api_endpoint` | `POST /api/v1/inventory/expiry-alerts/evaluate/` returns counts | **PASS** | Returns HTTP 200 with `{created, updated, resolved, active_total}`. |
| `test_08_create_schedule_api_and_next_run_calculation` | API sets cadence and calculates next run time in UTC+3 | **PASS** | Daily, weekly, monthly math validated; timezone handled properly. |
| `test_09_due_schedule_execution_creates_draft_session_without_gl` | Due schedule generates draft session; zero GL entries or stock changes | **PASS** | Session created in `draft` mode; GL journals unchanged. |
| `test_10_period_idempotency_prevents_duplicate_runs` | Re-running scheduler in same period skips redundant generation | **PASS** | Status marked `skipped`, reason `already_executed_for_period`. |
| `test_11_downtime_recovery_single_catchup_session` | Scheduler recovering from downtime creates exactly 1 catch-up session | **PASS** | Catch-up created, `next_run_at` advanced to future window. |
| `test_12_schedule_management_actions` | Pause, activate, trigger-now, upcoming endpoints | **PASS** | Schedule state transitions operate properly. |
| `test_13_segregation_of_duties_preserved_for_scheduled_session` | Assigned counter cannot approve session | **ERROR** | **CRASHED DURING URL REVERSE** (See Traceback below). |

**Verbatim Traceback for `test_13` Failure:**
```text
======================================================================
ERROR: test_13_segregation_of_duties_preserved_for_scheduled_session 
(apps.inventory.tests.test_expiry_alerts_and_schedules.ExpiryAlertsAndStocktakeSchedulesTestCase.test_13_segregation_of_duties_preserved_for_scheduled_session)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\apps\inventory\tests\test_expiry_alerts_and_schedules.py", line 480, in test_13_segregation_of_duties_preserved_for_scheduled_session
    approve_url = reverse("stocktakesession-approve", args=[session.id])
  File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\base.py", line 98, in reverse
    resolved_url = resolver._reverse_with_prefix(view, prefix, *args, **kwargs)
  File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\resolvers.py", line 831, in _reverse_with_prefix
    raise NoReverseMatch(msg)
django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found. 'stocktakesession-approve' is not a valid view function or pattern name.

FAILED (errors=1)
```

---

#### Test Suite 2: `apps/inventory/tests/test_stocktaking_management.py`

| Test Method Name | Verified Mandate | Result | Observed Details / Traceback |
| :--- | :--- | :---: | :--- |
| `test_01_create_stocktake_session_snapshots_inventory` | Session creation snapshots item balances in location | **PASS** | Snapshot created accurately. |
| `test_02_partial_inventory_filtering_by_category` | Scoping session to category filters snapshot items | **PASS** | Only items matching category included. |
| `test_03_blind_counting_mode_masks_expected_quantities` | Blind mode masks theoretical stock for non-superusers | **PASS** | Serializer masks expected stock. |
| `test_04_visible_counting_mode_displays_expected_quantities` | Visible mode exposes theoretical stock to counters | **PASS** | Values present in serializer output. |
| `test_05_mode_locking_on_first_count_submission` | Counting mode locked upon first count entry | **ERROR** | **CRASHED**: `NoReverseMatch: Reverse for 'stocktakesession-record-counts' not found.` (`line 263`) |
| `test_06_recount_workflow_flagging_and_resubmission` | Supervisor requests recount; counter resubmits | **ERROR** | **CRASHED**: `NoReverseMatch: Reverse for 'stocktakesession-request-recount' not found.` (`line 303`) |
| `test_07_separation_of_duties_prevents_self_approval` | Counter cannot approve own session | **ERROR** | **CRASHED**: `NoReverseMatch: Reverse for 'stocktakesession-approve' not found.` (`line 365`) |
| `test_08_superuser_emergency_override_requires_justification` | Superuser self-approval requires >=15 char reason | **PASS** | Service layer logic validates justification string length and logs audit event. |
| `test_09_balanced_gl_posting_on_variance_approval` | Variance approval posts balanced debits/credits to Accounts 5020 & 1300 | **PASS** | Service layer unit invocation verifies double-entry balance. |
| `test_10_approval_is_strictly_idempotent` | Re-approving session prevents duplicate stock changes/GL entries | **PASS** | Service layer idempotency key prevents duplication. |
| `test_11_session_cancellation_leaves_balances_intact` | Session cancellation releases lock without modifying balances | **ERROR** | **CRASHED**: `NoReverseMatch: Reverse for 'stocktakesession-cancel' not found.` (`line 541`) |
| `test_12_non_manager_cannot_create_or_approve_sessions` | Waiter/cashier cannot create or approve sessions | **ERROR** | **CRASHED**: `NoReverseMatch: Reverse for 'stocktakesession-approve' not found.` (`line 574`) |

**Summary of Errors in Test Suite 2:**
Out of 12 tests, all 5 tests that attempt to interact with the `StocktakeSession` REST API endpoints (`record-counts`, `request-recount`, `approve`, `cancel`) crash immediately with `django.urls.exceptions.NoReverseMatch`.

---

## 4. All 8 Capability Areas Independent Audit Matrix & Detailed Findings

### 4.1 Master Capability Audit Matrix

| Area | Capability Domain | Key Evaluated Source Files | Independent Status | Defect ID & Severity |
| :---: | :--- | :--- | :---: | :---: |
| **Area 1** | Expiry-Alert Lifecycle | `hotel/models.py:1181-1226`<br>`hotel/inventory.py:46-173`<br>`apps/inventory/views.py:3196-3246` | **FAIL** | **DEF-03** (High) |
| **Area 2** | Backend POS/KDS Stock Lockout (Expired / Quarantine) | `hotel/integrity.py:482-580`<br>`apps/orders/services.py:360-395` | **PASS** | None |
| **Area 3** | Near-Expiry Thresholds & Unknown-Expiry Handling | `hotel/inventory.py:105-121`<br>`hotel/integrity.py:445-446` | **PASS WITH OBSERVATION** | **DEF-05** (Medium) |
| **Area 4** | Scheduling Cadence & Calendar Clamps (29/30/31) | `hotel/stocktaking.py:571-628` | **PASS** | None |
| **Area 5** | Concurrency, Locks, Downtime Recovery, Timezones | `hotel/stocktaking.py:630-740`<br>`hotel/management/commands/run_inventory_scheduler.py` | **PASS** | None |
| **Area 6** | Stocktaking Draft Safety, Blind-Mode, SoD, GL Posting | `apps/inventory/views.py:3163-3195`<br>`hotel/stocktaking.py:46-522`<br>`apps/inventory/serializers.py:920-1028` | **FAIL** | **DEF-01** (Critical)<br>**DEF-02** (High) |
| **Area 7** | API Permissions, IDOR Protection, FE/BE Consistency | `users/permissions.py:74-128`<br>`hotel-frontend/src/pages/stocktaking/` | **FAIL** | **DEF-01** (Critical)<br>**DEF-03** (High)<br>**DEF-04** (Medium) |
| **Area 8** | Migration Safety & Codebase Regressions | `hotel/migrations/0049_*.py`<br>`apps/inventory/views.py` | **FAIL** | **DEF-01** (Critical) |

---

### 4.2 Detailed Findings by Capability Area

#### Area 1: Expiry-Alert Lifecycle
- **Schema & Indexes (`hotel/models.py:1181-1226`):**
  The `InventoryExpiryAlert` model is well-designed. It captures foreign keys to `batch`, `item`, and `location`, stores alert type (`expired`, `near_expiry_1`, `near_expiry_7`, `near_expiry_14`, `near_expiry_30`, `unknown_expiry`), threshold days, batch snapshot numbers, and full resolution audit metadata (`status`, `resolution_reason`, `resolved_at`, `resolved_by`). Composite B-tree indexes `exp_alert_status_type_idx` and `exp_alert_batch_type_idx` exist in PostgreSQL 16 `hotel_erp_staging`.
- **Dynamic Quantity Synchronization (`hotel/inventory.py:140-153`):**
  When evaluated against existing active alerts, `evaluate_inventory_expiry_alerts()` updates `current_quantity` and `location` in-place without generating redundant rows.
- **Automated Lifecycle Resolution (`hotel/inventory.py:73-88`):**
  Batches reaching `current_quantity <= 0.00` or status in `('depleted', 'recalled')` automatically transition active alerts to `status='resolved'` with `resolution_reason='batch_consumed_or_depleted'`. Batches with unknown expiry that later receive a verified expiry date transition to `resolved` with `resolution_reason='expiry_date_verified'`.
- **High Severity Defect — Dismissal Reactivation Loop (DEF-03):**
  In `hotel/inventory.py:125-137`:
  ```python
  alert, created = InventoryExpiryAlert.objects.get_or_create(
      batch=batch,
      alert_type=alert_type,
      status="active",
      defaults={...}
  )
  ```
  When an alert is acknowledged and dismissed by staff via `POST /api/v1/inventory/expiry-alerts/{id}/dismiss/`, its status is updated to `"dismissed"`. However, during the subsequent background scheduler cycle or when a manager clicks "⚡ Run Expiry Scan", `get_or_create` searches for an alert with `status="active"`. Because the dismissed record is no longer active, the query creates a **new duplicate active alert** for the still-expired batch. This completely invalidates staff acknowledgment and creates an infinite alert recreation loop.

---

#### Area 2: Backend POS/KDS Stock Lockout for Expired & Quarantine Batches
- **Authoritative FEFO Allocation Lockout (`hotel/integrity.py:533-570`):**
  The central stock transaction engine (`record_stock_change`) strictly filters candidate batches during non-waste inventory consumption (`sale_deduction`, `issuance`, `transfer`):
  - Filters `candidate_qs.filter(status="active")`.
  - For perishable items (`item.is_perishable == True`), allocation enforces `expiry_date__isnull=False, expiry_date__gte=today`, ordered by `expiry_date, received_date, id`. This completely excludes expired batches and batches with unverified/NULL expiry dates from automated allocation.
  - For non-perishable items, `candidate_qs.exclude(expiry_date__lt=today)` prevents consumption of expired stock.
- **Manual Batch Selection Validation (`hotel/integrity.py:493-509`):**
  If an operator attempts to manually select an expired batch for consumption, the system throws:
  `ValidationError: Batch '{batch_number}' has expired ({expiry_date}) and cannot be used for {transaction_type}. Expired stock must be routed to waste.`
  If a batch has `status == "unverified_quarantine"`, the system raises:
  `ValidationError: Batch ... is in unverified quarantine and cannot be used for {transaction_type} until physically verified.`
- **POS / Kitchen Display System (KDS) Integration (`apps/orders/services.py:375-385`):**
  When dining room guests order menu items or kitchen orders are fulfilled, deduction calls `record_stock_change(item_id=..., transaction_type="sale_deduction", location=...)`. This directly routes through the FEFO engine, guaranteeing that expired or quarantined inventory is never served to hotel guests.
- **Status:** **PASS** (Zero defects detected; fully verified in staging).

---

#### Area 3: Near-Expiry Thresholds and Unknown-Expiry Handling
- **Warning Windows (`hotel/inventory.py:105-117`):**
  Active batches are properly bucketed into tiered warning windows based on `days_until_exp = (batch.expiry_date - today).days`:
  - `expired`: `days_until_exp < 0`
  - `near_expiry_1`: `days_until_exp <= 1`
  - `near_expiry_7`: `days_until_exp <= 7`
  - `near_expiry_14`: `days_until_exp <= 14`
  - `near_expiry_30`: `days_until_exp <= 30`
- **Unknown Expiry Detection (`hotel/inventory.py:120-121`):**
  Batches where `expiry_date is None` generate an `unknown_expiry` alert (threshold = -1) if `item.is_perishable or batch.is_legacy or batch.status == "unverified_quarantine"`.
- **Default Shelf Life Fallback (`hotel/integrity.py:445-446`):**
  When stock is received without an explicit expiry date, if `item.is_perishable and item.shelf_life_days > 0`, the system automatically populates `expiry_date = today + timedelta(days=item.shelf_life_days)`.
- **Medium Severity Defect — Hardcoded Thresholds (DEF-05):**
  While warning windows function correctly in code, the threshold days (1, 7, 14, 30) are hardcoded directly into Python code and model choices. There is no dynamic configuration model in `SystemSettings` to allow hotel administrators to adjust warning horizons per storage location (e.g., Deep Freeze vs. Banquet Kitchen) or per perishable category.
- **Status:** **PASS WITH OBSERVATION** (Medium Defect DEF-05).

---

#### Area 4: Daily, Weekly, and Monthly Scheduling & Month-End Clamps (29/30/31)
- **Timezone-Aware Next Run Calculation (`hotel/stocktaking.py:571-628`):**
  All calculations explicitly utilize the hotel property timezone (`Africa/Addis_Ababa`, UTC+3).
  - **Daily:** Schedules calculate `candidate = base_dt.date() + scheduled_time`; if candidate is past, it cleanly rolls over to `base_dt.date() + 1 day`.
  - **Weekly:** Schedules calculate day-of-week delta `(target_dow - base_dt.weekday()) % 7`; advances 7 days if scheduled time for today has already elapsed.
  - **Monthly Month-End Calendar Clamping:**
    ```python
    max_days = calendar.monthrange(year, month)[1]
    dom = min(target_dom, max_days)
    ```
    This mathematical clamp ensures that schedules configured for the 29th, 30th, or 31st do not crash or skip short months:
    - 31st scheduled for February (non-leap year) clamps safely to February 28.
    - 31st scheduled for February (leap year) clamps safely to February 29.
    - 31st scheduled for April, June, September, November clamps safely to day 30.
    - Year rollover from December to January correctly increments calendar year and resets month to 1.
- **Status:** **PASS** (Zero defects detected; fully verified by unit test `test_08`).

---

#### Area 5: Concurrency, Crashes, Retries, Downtime Recovery, Timezone Boundaries
- **Distributed PostgreSQL Row Locking (`hotel/stocktaking.py:650`):**
  Inside `@transaction.atomic`, due schedules are queried using:
  `StocktakeSchedule.objects.select_for_update(of=("self",)).filter(is_active=True, next_run_at__lte=current_time)`
  This prevents race conditions when multiple Celery workers, cron jobs, or management commands trigger concurrently.
- **Period Idempotency Safeguards (`hotel/stocktaking.py:664-682`):**
  Before generating a session, the scheduler queries:
  `StocktakeSession.objects.filter(schedule=sched, scheduled_date=target_date).first()`
  If a session already exists for that period, the schedule advances `next_run_at`, records `last_run_status = "skipped"`, and logs `reason = "already_executed_for_period"`, preventing duplicate sessions.
- **Downtime Catch-Up Recovery (`hotel/stocktaking.py:676, 706`):**
  If the background scheduler daemon was offline across multiple scheduled run intervals, upon restart it creates exactly **one** catch-up session for the earliest missed target date and advances `next_run_at` relative to `current_time`. This completely prevents schedule flooding after server restarts.
- **Management CLI Command (`hotel/management/commands/run_inventory_scheduler.py`):**
  Supports both one-shot execution and continuous daemon polling (`--daemon --interval <sec>`).
- **Status:** **PASS** (Zero defects detected; verified in tests `test_09`, `test_10`, `test_11`, `test_12`).

---

#### Area 6: Stocktaking Draft Safety, Blind-Mode Protection, Separation of Duties, Approval-Based GL Posting
- **Critical Severity Defect — Missing Action Endpoints on ViewSet (DEF-01):**
  In `apps/inventory/views.py:3163-3195`, `StocktakeSessionViewSet` defines only `create()`. Due to copy-paste corruption during development, the `@action` methods:
  - `record_counts` (`POST /api/v1/stocktaking/sessions/{id}/record-counts/`)
  - `request_recount` (`POST /api/v1/stocktaking/sessions/{id}/request-recount/`)
  - `submit_recount` (`POST /api/v1/stocktaking/sessions/{id}/submit-recount/`)
  - `approve` (`POST /api/v1/stocktaking/sessions/{id}/approve/`)
  - `cancel` (`POST /api/v1/stocktaking/sessions/{id}/cancel/`)
  were misplaced inside intermediate declarations of `StocktakeScheduleViewSet` and subsequently deleted. Calling `StocktakeSessionViewSet.get_extra_actions()` returns `[]`. Every stocktake action returns **HTTP 404 Not Found**, and all automated tests attempting to resolve these URLs fail.
- **High Severity Defect — Unconstrained Cascading Deletion (DEF-02):**
  `StocktakeSessionViewSet` inherits from `ModelViewSet` and does not override `destroy()`. In `hotel/models.py:2387-2390`, `StocktakeItem` defines `on_delete=models.CASCADE`. An inventory manager can issue `DELETE /api/v1/stocktaking/sessions/{id}/` against sessions in `in_progress` or even `approved` status, silently and permanently destroying audit records and historical count snapshots.
- **Blind-Mode Zero-Leak Security (`apps/inventory/serializers.py:920-1028`):**
  In `StocktakeItemSerializer.to_representation()` and `StocktakeSessionSerializer.to_representation()`, when `counting_mode == "blind"` and status is in `("draft", "in_progress")` and `not is_admin`, the fields `theoretical_quantity`, `variance_quantity`, `variance_value`, `total_theoretical_value`, and `total_variance_value` are set to `None`. Network inspection confirms theoretical stock is completely omitted from JSON payloads sent to non-administrative counters. (Frontend renders `<Lock /> Hidden`). **Status: PASS**.
- **Separation of Duties (SoD) Enforcement (`hotel/stocktaking.py:413-436`):**
  At the service layer, `approve_stocktake_session()` checks:
  `if session.counted_by and supervisor.username == session.counted_by.username:`
  Raises `PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")`. Superuser emergency overrides require `>= 15` characters justification and create an immutable `AuditEvent`. However, because the API route `stocktakesession-approve` is missing, SoD cannot be exercised via HTTP. **Status: Service PASS / API FAIL**.
- **Approval-Based GL Posting (`hotel/stocktaking.py:488-522`, `hotel/accounting.py:20-70`):**
  Automated scheduling, draft creation, and count recording **never** touch the General Ledger. GL posting occurs strictly upon supervisor approval:
  - Deficits (Shrinkage): Debit Account `5020` (Inventory Stocktake Variance Expense), Credit Account `1300` (Inventory Asset).
  - Surpluses: Debit Account `1300` (Inventory Asset), Credit Account `5020` (Variance Expense).
  - Enforces `total_debit == total_credit` balance. Unique idempotency keys prevent duplicate ledger entries. However, triggering approval via HTTP fails with 404. **Status: Service PASS / API FAIL**.

---

#### Area 7: API Permissions, IDOR Protection, Frontend/Backend Consistency
- **Role-Based API Permissions (`users/permissions.py:74-128`, `apps/inventory/views.py`):**
  Endpoints enforce strict permissions:
  - `StocktakeSessionViewSet`: `[IsInventoryManager]`
  - `StocktakeScheduleViewSet`: `[IsInventoryManager]`
  - `InventoryExpiryAlertViewSet`: `[IsBatchOperator]`
  Unauthenticated calls return HTTP 401; unauthorized roles (waiter, cashier, customer) receive HTTP 403. **Status: PASS**.
- **IDOR Protection & Queryset Scoping (`hotel/models.py`, `apps/inventory/views.py`):**
  The ERP is an on-premise single-property hotel ERP; no multi-tenant isolation is required. However, there is no horizontal staff scoping (**DEF-04**): any inventory user can pause, edit, or delete schedules created by other managers, and any counter can submit counts on sessions assigned to another counter. **Status: PASS WITH OBSERVATION (Medium Defect DEF-04)**.
- **Frontend / Backend Consistency:**
  - **Severe Disconnect (Critical Defect DEF-01)**: React 19 action desks (`StocktakeCountDesk.jsx`, `StocktakeVarianceDesk.jsx`) call `POST .../record-counts/`, `.../submit-recount/`, `.../request-recount/`, `.../approve/`, and `.../cancel/`. All return **HTTP 404 Not Found**.
  - **Dismissal Loop (High Defect DEF-03)**: Dismissing alerts in `InventoryDashboard.js` updates the UI, but the next background or manual scan recreates active alerts. **Status: FAIL**.

---

#### Area 8: Migration Safety & Codebase Regression
- **Migration Safety (`hotel/migrations/0049_inventory_expiry_alerts_and_stocktake_schedules.py`):**
  Migration `0049` is 100% additive:
  - Creates table `hotel_inventoryexpiryalert` with status/type composite indexes.
  - Creates table `hotel_stocktakeschedule`.
  - Adds nullable FK `schedule` and indexed DateField `scheduled_date` to `StocktakeSession`.
  - Zero columns, tables, or constraints were dropped or altered destructively. Staging data in `hotel_erp_staging` is fully preserved. **Status: PASS**.
- **Severe Codebase Regression in `apps/inventory/views.py` (DEF-01):**
  Inspection of `apps/inventory/views.py` revealed that the file expanded to 5,915 lines containing **26 duplicate class declarations** of `StocktakeScheduleViewSet`. The original action methods for `StocktakeSessionViewSet` were detached and lost. This regression broke 6 automated tests and disabled the entire stocktaking action workflow. **Status: FAIL**.

---

## 5. Real-Browser Checks & UI Visual Audit

### 5.1 Acceptance Script Analysis (`scratch/test_browser_partial_features.py`)
The browser acceptance script was authored in conversation scratch space and placed at `scratch/test_browser_partial_features.py` (363 lines).
- **Run History Audit:**
  - **Task-3600:** Initially failed at Step 7 with `selenium.common.exceptions.TimeoutException` waiting for `#tab-stocktake-schedules`.
  - **Task-3635:** Resolved wait conditions using `EC.presence_of_element_located` and `safe_click()`. Completed all 13 steps and captured 11 screenshots into `docs/screenshots/partial_inventory/`.
- **QC Execution Guardrail:** Direct rerun of the browser script during QC review was blocked by user command permission policy (`permission check failed for unsandboxed .venv\Scripts\python.exe -u scratch/test_browser_partial_features.py`). In strict compliance with operational guardrails, no attempt to circumvent this denial was made. Verification was completed by independently auditing the captured visual artifacts, DOM source code, network endpoints, and database state.

---

### 5.2 Visual Screenshot Evidence Table (`docs/screenshots/partial_inventory/`)

All 11 screenshots generated during the browser acceptance run were inspected in detail:

| Screenshot File | File Size | UI Workflow Phase | Directly Observed DOM Elements & Visual State | Evaluation Status |
| :--- | :---: | :--- | :--- | :---: |
| `01_inventory_dashboard_landing.png` | 208,094 B | Authentication & Admin Landing | Authenticated as `Admin_p2_browser` (role: ADMIN). Sidebar displays "Inventory Control" and "Physical Stocktaking". KPI cards: Today's Revenue, Occupancy Rate (50%), Low Stock Alerts (1). | **PASS** |
| `02_batches_and_expiry_tab.png` | 272,960 B | Batches & Expiry Tab | Red warning pill badge on "Batches & Expiry" tab. Top summary: Active Lots: 24, Near-Expiry: 1, Expired: 2. Critical Food Safety Notice banner: "2 Expired Batch(es) Locked... strictly prohibited from guest service". Surveillance Feed KPI: Active Alerts: 5, Expired: 2, Near-Expiry: 1, Unknown: 2, Resolved: 0. "⚡ Run Expiry Scan" button present. | **PASS** |
| `03_expiry_scan_completed.png` | 248,360 B | On-Demand Expiry Scan | Green alert banner: "✓ Expiry scan complete: 5 active alerts (0 new, 0 resolved)." Alert table renders: Purple badge "Perishable Stock - Unknown Expiry" (`BATCH-UNK-STAGE-99`, 18.00 kg); Amber badge "Expiring Within 7 Days" (`BATCH-NEAR-STAGE-07`, 40.00 l, 5d remaining); Red badge "Expired Stock" (`BATCH-EXP-STAGE-01`, 25.00 l, Expired 2d ago). Actions: [Route Waste], [Dismiss], [Locate]. | **PASS** |
| `04_dismiss_alert_modal.png` | 230,376 B | Dismiss Alert Modal | Modal opened for `Prime Beef Tenderloin (ITM-MEAT-BEEF)`, batch `BATCH-UNK-STAGE-99`. Required text input: "REASON FOR DISMISSAL / ACKNOWLEDGMENT *", placeholder "e.g. Inspected and approved for immediate use in today's banquet menu." [Confirm Dismissal] button. | **PASS** |
| `05_alert_dismissed_state.png` | 238,147 B | Post-Dismissal Feed Update | Active Alerts KPI card decremented from 5 to 4. Unknown Perishable decremented from 2 to 1. Resolved / Dismissed incremented from 0 to 1. Filter pill `Active (4)` active. Row `BATCH-UNK-STAGE-99` removed from active filter view. | **PASS** |
| `06_stocktake_center_sessions.png` | 210,012 B | Stocktake Center Navigation | Stocktake Center loads. Desk switcher: "Count Sessions & History (3)" vs "Recurring Schedules & Automation (0)". KPI cards: Active In-Progress: 1, Pending Review: 0, Recounts Required: 1, Approved & Closed: 1. Cumulative Net Variance: +ETB 885.00. Table lists manual stocktake sessions. | **PASS** |
| `07_stocktake_schedules_desk.png` | 168,556 B | Schedules Desk Empty State | Desk switcher switches to "Recurring Schedules & Automation (0)". Button changes to "+ New Recurring Schedule". Empty state: "No Automated Stocktaking Schedules Configured". KPI cards: Active: 0, Daily: 0, Weekly & Monthly: 0, Overdue: 0. | **PASS** |
| `08_create_schedule_modal.png` | 167,579 B | Create Schedule Modal | Modal: "Configure Recurring Stocktake Schedule". Fields: Schedule Name, Recurrence Cadence (Daily), Execution Time (06:00 AM), Storage Location (Main Bar Station), Category Filter, Designated Counter (Unassigned), Protocol cards (Blind Count Zero-Leak selected vs Visible Count). Governance safeguard banner rendered. | **PASS** |
| `09_schedule_created_table.png` | 182,422 B | Schedule Creation Success | Green toast banner: "✓ Automated stocktake schedule created successfully." Tab counter: "Recurring Schedules & Automation 1". Row rendered: "Daily Nightly Central Store Audit", Cadence: Daily at 06:00:00, Location: Main Bar Station, Protocol: Blind, Next Scheduled: 11/6/26, 6:00 AM, Status: Active. Row actions: [▶ Run Now], [⏸ Pause], [🗑 Delete]. | **PASS** |
| `10_schedule_triggered_notification.png` | 188,823 B | "Run Now" Manual Trigger | Green toast banner: "✓ Execution complete for 'Daily Nightly Central Store Audit'. Draft Stocktake Session #STK-20261105-43B597 has been snapshot and is ready for count submission." Last Run status updated to "11/5/26, 1:47 PM SUCCESS". Count Sessions tab badge incremented to 4. | **PASS** |
| `11_generated_scheduled_session_in_table.png` | 225,810 B | Spawned Scheduled Session | Switched to Count Sessions tab. New session `#STK-20261105-43B597` rendered at top with purple badge "⏰ Auto: Scheduled". Location: Main Bar Station, Mode: Blind, Status: In Progress (Draft), Theoretical Val: ETB 1,565.00, Variance Val: ETB 0.00. Actions: [Count], [Details]. | **PASS** |

### 5.3 UI / Browser Audit Summary
The visual rendering, modal interactions, layout responsiveness, and schedule management controls are professionally designed and rendered without visual glitches. However, the interactive completion of the stocktake workflow (entering counts and approving variances) is blocked because the action endpoints fail with HTTP 404 in the live backend, and alert dismissals are reverted upon subsequent scans.

---

## 6. Master Defect Register

The following register documents all defects and architectural discrepancies identified during this independent quality control audit:

| Defect ID | Severity | Capability Area | Source File & Lines | Defect Title & Observed Behavior | Real-World & Systemic Impact | Recommended Remediation |
| :---: | :---: | :---: | :--- | :--- | :--- | :--- |
| **DEF-01** | **Critical** | Areas 6, 7, 8 | `apps/inventory/views.py:3163-5915` | **Missing Custom Actions on `StocktakeSessionViewSet` & 26 Duplicate ViewSet Declarations**<br>`StocktakeSessionViewSet` defines only `create()`. Methods `record_counts`, `request_recount`, `submit_recount`, `approve`, and `cancel` were accidentally indented inside `StocktakeScheduleViewSet` and subsequently deleted during repetitive file concatenations. Class `StocktakeScheduleViewSet` is declared 26 redundant times. | 1. URL resolver throws `NoReverseMatch` on 6 automated tests.<br>2. React desks receive HTTP 404 on count submissions, recounts, approvals, and cancellations.<br>3. Stocktaking workflow cannot be completed through the API. | Restore `@action` methods (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) inside `StocktakeSessionViewSet`. Clean up `apps/inventory/views.py` by removing all 26 duplicate class declarations of `StocktakeScheduleViewSet`. |
| **DEF-02** | **High** | Area 6 | `apps/inventory/views.py:3163-3195`<br>`hotel/models.py:2387-2390` | **Unconstrained Cascading Deletion of Stocktake Sessions**<br>`StocktakeSessionViewSet` inherits default `destroy()` from `ModelViewSet` without lifecycle checks. Model `StocktakeItem` specifies `on_delete=models.CASCADE`. | Any authenticated inventory manager can execute `DELETE /api/v1/stocktaking/sessions/<id>/` on sessions in `in_progress`, `under_review`, or `approved` status, permanently deleting historical count snapshots and financial audit trails. | Override `destroy()` in `StocktakeSessionViewSet` to raise `HTTP 405 Method Not Allowed` or permit deletion strictly for uncounted `draft` sessions. Protect `StocktakeItem` with `on_delete=models.PROTECT`. |
| **DEF-03** | **High** | Areas 1, 7 | `hotel/inventory.py:125-137` | **Expiry Alert Dismissal Reactivation Loop**<br>`evaluate_inventory_expiry_alerts()` uses `get_or_create(batch=batch, alert_type=alert_type, status="active", ...)`. When staff dismisses an alert, its status becomes `"dismissed"`. | On the next background scheduler run or manual scan, the query finds no active alert and creates a new active duplicate alert for the still-expired batch, undoing staff dismissal. | Update `get_or_create` logic to query existing alerts by `(batch, alert_type)` regardless of status. If an alert exists with `status="dismissed"`, retain its dismissed state unless batch quantity or expiry date has changed. |
| **DEF-04** | **Medium** | Area 7 | `apps/inventory/views.py:5801-5825`<br>`hotel/stocktaking.py:149-249` | **Missing Object-Level Authorization on Schedules and Sessions (Horizontal IDOR)**<br>`StocktakeScheduleViewSet.get_queryset()` returns `all()` without checking creator ownership. `record_counts()` does not verify whether `request.user == session.schedule.assigned_staff`. | Any staff member with inventory permissions can pause, trigger, modify, or delete schedules created by other managers, and any counter can submit counts for another staff member's assigned audit. | Implement object-level permissions (`check_object_permissions`) or restrict schedule mutations to schedule creators / administrators. Validate `request.user == assigned_staff` in count submission. |
| **DEF-05** | **Medium** | Area 3 | `hotel/inventory.py:105-117` | **Hardcoded Near-Expiry Threshold Windows**<br>Threshold windows (1, 7, 14, 30 days) are hardcoded into Python logic and model choice enums without runtime configurability. | Hotel administrators cannot tailor warning horizons to specific storage locations (e.g. Freezers vs Dry Stores) or specific perishable categories (e.g. Dairy vs Spirits). | Move alert threshold configurations to database-backed settings (e.g., `SystemSettings` or a dedicated `InventoryAlertConfig` model). |

---

## 7. Reproduction & Verification Playbook

To allow the orchestrator, QA engineers, and remediation workers to independently reproduce and verify all findings, execute the following commands in the workspace environment:

### Step 1: Reproduce Automated Test Failures
Run both test suites using the staging Python interpreter in PowerShell:

```powershell
# 1. Reproduce failure in apps/inventory/tests/test_expiry_alerts_and_schedules.py (test_13 NoReverseMatch)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb -v 2

# Expected Result: FAILED (errors=1) at test_13_segregation_of_duties_preserved_for_scheduled_session:
# django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found.

# 2. Reproduce 5 failures in apps/inventory/tests/test_stocktaking_management.py
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb -v 2

# Expected Result: FAILED (errors=5) at test_05, test_06, test_07, test_11, test_12:
# django.urls.exceptions.NoReverseMatch for 'stocktakesession-record-counts', 'stocktakesession-request-recount', 'stocktakesession-approve', 'stocktakesession-cancel'.
```

### Step 2: Verify Missing Extra Actions via Python Shell
Inspect the extra action routes registered on `StocktakeSessionViewSet`:

```powershell
.venv\Scripts\python.exe manage.py shell -c "import users.serializers; from apps.inventory.views import StocktakeSessionViewSet; print('Extra actions on StocktakeSessionViewSet:', [a.__name__ for a in StocktakeSessionViewSet.get_extra_actions()])"

# Expected Output: Extra actions on StocktakeSessionViewSet: []
# (Demonstrates that record_counts, request_recount, submit_recount, approve, and cancel are completely missing).
```

### Step 3: Verify HTTP 404 on Live Action Endpoint
Attempt an HTTP call to the count recording endpoint on the local server:

```powershell
.venv\Scripts\python.exe -c "import urllib.request, urllib.error; req = urllib.request.Request('http://127.0.0.1:8000/api/v1/stocktaking/sessions/1/record-counts/', data=b'{}', headers={'Content-Type': 'application/json'}); urllib.request.urlopen(req)"

# Expected Output: urllib.error.HTTPError: HTTP Error 404: Not Found
```

### Step 4: Verify 26 Duplicate ViewSet Declarations in Source
Verify the corruption and redundant class declarations in `apps/inventory/views.py`:

```powershell
Get-Content "apps/inventory/views.py" | Select-String "class StocktakeScheduleViewSet" | Measure-Object

# Expected Output: Count: 26
```

### Step 5: Verify Active Staging Database Alerts and Schedules
Inspect existing records in `hotel_erp_staging`:

```powershell
.venv\Scripts\python.exe manage.py shell -c "from hotel.models import InventoryExpiryAlert, StocktakeSchedule; print('Active Alerts Count:', InventoryExpiryAlert.objects.filter(status='active').count()); print('Active Schedules Count:', StocktakeSchedule.objects.filter(is_active=True).count())"
```

---

## 8. Remediation Roadmap for Acceptance

To achieve formal **ACCEPTED** status, an implementation worker must execute the following remediation plan:

1. **Fix DEF-01 (Critical - Views & Routing)**:
   - Clean up `apps/inventory/views.py` by removing all duplicate declarations of `StocktakeScheduleViewSet`.
   - Restore the missing action methods (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) inside `StocktakeSessionViewSet` with proper `@action(detail=True, methods=['post'], url_path=...)` decorators and permission classes.
   - Re-run both test suites to achieve **25 / 25 tests passing (100% OK)**.
2. **Fix DEF-02 (High - Deletion Safety)**:
   - Override `destroy()` in `StocktakeSessionViewSet` to prevent deletion of in-progress or approved stocktakes (`raise MethodNotAllowed` or `ValidationError`).
   - Alter `StocktakeItem.session` foreign key to `on_delete=models.PROTECT` or block deletion if items exist.
3. **Fix DEF-03 (High - Dismissal Persistence)**:
   - In `hotel/inventory.py:125-137`, refactor `get_or_create` to check for any existing alert for the batch and alert type. If an alert has `status='dismissed'`, do not resurrect it unless the batch's expiry date or quantity changes significantly.
4. **Address DEF-04 & DEF-05 (Medium Observations)**:
   - Add object-level authorization on schedule management and counter validation on count submissions.
   - Abstract near-expiry thresholds into configurable settings in a subsequent release.

---

**Report Certification:**
This report represents an authentic, independent, and evidence-backed evaluation of the ACRMA Hotel ERP Partial Inventory and Stocktaking implementation. No application source code or database migrations were modified during this audit, and all evidence is reproducible directly from the repository and database state.
