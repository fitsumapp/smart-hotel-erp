# Independent Backend & Test Verification Handoff Report (Areas 1, 2, 3, 4, 5, 8)

**Document Reference:** QC-BACKEND-PARTIAL-INVENTORY-2026-V1.0  
**Date:** 2026-11-05  
**Author:** Backend & Test Verification Explorer (`explorer_qc_backend`)  
**Target Environment:** Django 5.2 backend (`.venv\Scripts\python.exe`), PostgreSQL 16.12 (`hotel_erp_staging` on `localhost:5432`), React 19 SPA (`http://localhost:3000`)  
**Overall Verdict for Evaluated Backend Scope:** **REJECTED** (Due to Critical Severity regressions in `apps/inventory/views.py` breaking all stocktaking session count/recount/approval/cancellation endpoints and causing automated test failures)

---

## 1. Observation

### 1.1 Automated Test Execution Results Against `hotel_erp_staging`
Both automated test suites required by the verification mandate were executed independently using the active virtual environment Python interpreter (`.venv\Scripts\python.exe manage.py test`):

#### Test Suite 1: `apps/inventory/tests/test_expiry_alerts_and_schedules.py`
- **Command Executed:** `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules -v 2`
- **Test Summary:** 13 tests executed in 32.123s.
- **Pass/Fail Counts:** 12 passed, **1 failed with ERROR**.
- **Failure Details:**
  ```text
  ERROR: test_13_segregation_of_duties_preserved_for_scheduled_session (apps.inventory.tests.test_expiry_alerts_and_schedules.ExpiryAlertsAndStocktakeSchedulesTestCase.test_13_segregation_of_duties_preserved_for_scheduled_session)
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
- **Discrepancy with Implementation Report:** Prior document `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md` (lines 76-98) claimed:
  `Ran 13 tests in 71.705s; OK` and marked `test_13` as PASS. Independent verification confirms this claim is **FALSE**.

#### Test Suite 2: `apps/inventory/tests/test_stocktaking_management.py`
- **Command Executed:** `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management -v 2`
- **Test Summary:** 12 tests executed in 85.583s.
- **Pass/Fail Counts:** 7 passed, **5 failed with ERROR**.
- **Failures Details:**
  - `test_05_mode_locking_on_first_count_submission`:
    `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-record-counts' not found.` (`test_stocktaking_management.py:263`)
  - `test_06_recount_workflow_flagging_and_resubmission`:
    `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-request-recount' not found.` (`test_stocktaking_management.py:303`)
  - `test_07_separation_of_duties_prevents_self_approval`:
    `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found.` (`test_stocktaking_management.py:365`)
  - `test_11_session_cancellation_leaves_balances_intact`:
    `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-cancel' not found.` (`test_stocktaking_management.py:541`)
  - `test_12_non_manager_cannot_create_or_approve_sessions`:
    `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found.` (`test_stocktaking_management.py:574`)
- **Discrepancy with Implementation Report:** `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md` (lines 101-107) claimed:
  `Ran 12 tests in 31.541s; OK`. Independent verification confirms this claim is **FALSE**.

---

### 1.2 Capability Areas Independent Evaluation Summary Table

| Area | Capability Mandate | Observed Code / Config Location | Independent Status | Defect Severity |
| :--- | :--- | :--- | :---: | :---: |
| **Area 1** | Expiry-Alert Lifecycle | `hotel/models.py:1181-1226`<br>`hotel/inventory.py:46-173`<br>`apps/inventory/views.py:3196-3246` | **FAIL** | **High** |
| **Area 2** | Backend POS/KDS Stock Lockout (Expired / Quarantine) | `hotel/integrity.py:482-580`<br>`apps/orders/services.py:360-395` | **PASS** | None |
| **Area 3** | Near-Expiry Thresholds & Unknown-Expiry Handling | `hotel/inventory.py:105-121`<br>`hotel/integrity.py:445-446` | **PASS WITH OBSERVATION** | **Medium** |
| **Area 4** | Scheduling Cadence & Calendar Clamps (29/30/31) | `hotel/stocktaking.py:571-628` (`compute_next_run`) | **PASS** | None |
| **Area 5** | Concurrency, Locks, Downtime Recovery, Timezones | `hotel/stocktaking.py:630-740`<br>`hotel/management/commands/run_inventory_scheduler.py` | **PASS** | None |
| **Area 8** | Migration Safety & Regression Check | `hotel/migrations/0049_*.py`<br>`apps/inventory/views.py` | **FAIL** | **Critical** |

---

### 1.3 Detailed Observations by Area

#### Area 1: Expiry-Alert Lifecycle
1. **Model & Schema (`hotel/models.py:1181-1226`):**
   `InventoryExpiryAlert` is properly structured with `batch`, `item`, `location`, `alert_type`, `threshold_days`, `batch_number`, `expiry_date`, `current_quantity`, `status` (`active`, `resolved`, `dismissed`), `resolved_at`, and `resolution_reason`. Indexes `exp_alert_status_type_idx` and `exp_alert_batch_type_idx` are created in PostgreSQL staging.
2. **Evaluation & Duplicate Prevention (`hotel/inventory.py:125-153`):**
   `evaluate_inventory_expiry_alerts()` uses `InventoryExpiryAlert.objects.get_or_create(batch=batch, alert_type=alert_type, status="active", defaults=...)`.
   Existing active alerts have their `current_quantity` and `location` updated dynamically without creating duplicate active records.
3. **Automated Lifecycle Resolution (`hotel/inventory.py:73-88`):**
   Batches with `current_quantity <= Decimal("0.00")` or status in `("depleted", "recalled")` automatically have active alerts transitioned to `status="resolved"` with `resolution_reason="batch_consumed_or_depleted"`.
   Batches with `unknown_expiry` that later have `expiry_date` populated and status set to `active` transition to `status="resolved"` with `resolution_reason="expiry_date_verified"`.
4. **Staff Dismissal (`apps/inventory/views.py:3235-3246`):**
   `POST /api/v1/inventory/expiry-alerts/{id}/dismiss/` requires `IsBatchOperator` / `inventory_manager` permission; sets `status="dismissed"`, records `resolved_at`, and stores the user justification.
5. **Observed Defect / Reactivation Behavior (Severity: High):**
   When an alert is `dismissed` by staff, the record receives `status="dismissed"`. On the next scheduler run, `evaluate_inventory_expiry_alerts()` executes `get_or_create(..., status="active")`. Because no active alert exists, it creates a new active alert for the same batch, effectively undoing staff dismissal unless the batch is wasted or consumed.
6. **Live Staging Database Status:**
   Querying `hotel_erp_staging` shows 5 alerts:
   - ID 1: `BAT-EXPIRED-TEST-001` (`expired`, active, 10.0000 qty)
   - ID 2: `LEGACY-INITIAL-SEC-BEEF-01` (`unknown_expiry`, active, 100.0000 qty)
   - ID 3: `BATCH-EXP-STAGE-01` (`expired`, active, 25.0000 qty)
   - ID 4: `BATCH-NEAR-STAGE-07` (`near_expiry_7`, active, 40.0000 qty)
   - ID 5: `BATCH-UNK-STAGE-99` (`unknown_expiry`, dismissed, resolution reason: *"Authorized by Food Safety Officer: inspected packaging for immediate bakery use."*)

#### Area 2: Backend Enforcement Preventing Expired & Quarantined Batches from POS/KDS Consumption
1. **Manual Batch Consumption Lockout (`hotel/integrity.py:493-509`):**
   For non-waste transactions (`sale_deduction`, `issuance`, `loss`), if `manual_batch.expiry_date < today`, the system raises `ValidationError: Batch '{manual_batch.batch_number}' has expired ({manual_batch.expiry_date}) and cannot be used for {transaction_type}. Expired stock must be routed to waste.`
   If `manual_batch.status == "unverified_quarantine"`, it raises `ValidationError: Batch ... is in unverified quarantine and cannot be used for {transaction_type} until physically verified.`
   If `manual_batch.status in ("recalled", "depleted")`, consumption is rejected.
2. **Authoritative FEFO Batch Allocation Lockout (`hotel/integrity.py:533-570`):**
   Non-waste deductions filter `candidate_qs.filter(status="active")`.
   For perishable items (`item.is_perishable == True`), allocation strictly filters `expiry_date__isnull=False, expiry_date__gte=today`, ordering by `expiry_date, received_date, id`. This completely excludes expired batches and batches with NULL/unknown expiry dates.
   For non-perishable items, `candidate_qs.exclude(expiry_date__lt=today)` excludes expired stock.
3. **POS/KDS Kitchen/Bar Deduction Path (`apps/orders/services.py:375-385`):**
   Order lifecycle completion invokes `record_stock_change(item_id=ingredient.pk, transaction_type="sale_deduction", location=target_location, ...)`. This directly triggers the above FEFO logic and guarantees that neither kitchen nor POS can consume expired or quarantined batches.

#### Area 3: Near-Expiry Thresholds and Unknown-Expiry Handling
1. **Tiered Warning Windows (`hotel/inventory.py:105-117`):**
   The system categorizes batches with positive stock into:
   - `expired`: `days_until_exp < 0` (threshold = 0)
   - `near_expiry_1`: `days_until_exp <= 1` (threshold = 1)
   - `near_expiry_7`: `days_until_exp <= 7` (threshold = 7)
   - `near_expiry_14`: `days_until_exp <= 14` (threshold = 14)
   - `near_expiry_30`: `days_until_exp <= 30` (threshold = 30)
2. **Unknown Expiry Handling (`hotel/inventory.py:120-121`):**
   Batches where `expiry_date` is `None` trigger an `unknown_expiry` alert (threshold = -1) if `item.is_perishable or batch.is_legacy or batch.status == "unverified_quarantine"`.
3. **Default Shelf Life Fallback (`hotel/integrity.py:445-446`):**
   When stock is received without an explicit expiry date, if `item.is_perishable and item.shelf_life_days > 0`, the system automatically sets `expiry_date = today + timedelta(days=item.shelf_life_days)`.
4. **Observed Defect / Hardcoded Thresholds (Severity: Medium):**
   While tiered windows (1, 7, 14, 30 days) operate correctly, the threshold days are hardcoded into Python logic and model choices. There is no configurable settings model or dynamic threshold override per category/location in `SystemSettings`.

#### Area 4: Daily, Weekly, and Monthly Scheduling & Calendar Edge Cases (29/30/31)
1. **Next Run Calculation (`hotel/stocktaking.py:571-628`):**
   - **Daily:** Combines `base_dt.date()` and `scheduled_time` in `Africa/Addis_Ababa` (UTC+3); advances 1 day if candidate <= base_dt.
   - **Weekly:** Computes `(target_dow - base_dt.weekday()) % 7`; advances 7 days if candidate <= base_dt.
   - **Monthly Month-End Clamping:**
     `max_days = calendar.monthrange(year, month)[1]`
     `dom = min(target_dom, max_days)`
     This clamps configured days (29, 30, 31) to the actual maximum days of the target month:
     - 31st in February (non-leap year) -> clamped to Feb 28.
     - 31st in February (leap year) -> clamped to Feb 29.
     - 31st in April/June/September/November -> clamped to day 30.
     - Rollover from December to January: `if month == 12: year += 1; month = 1` properly advances the calendar year.
2. **Independent Verification:** Tested in `test_08_create_schedule_api_and_next_run_calculation` (PASS).

#### Area 5: Concurrency, Crashes, Retries, Downtime Recovery, Timezones
1. **Engine-Level Distributed Row Locking (`hotel/stocktaking.py:650`):**
   `StocktakeSchedule.objects.select_for_update(of=("self",)).filter(is_active=True, next_run_at__lte=current_time)` inside `@transaction.atomic` prevents concurrent worker processes or celery/cron instances from generating duplicate sessions.
2. **Period Idempotency (`hotel/stocktaking.py:664-682`):**
   `StocktakeSession.objects.filter(schedule=sched, scheduled_date=target_date).first()`. If a session was already generated for that period, the schedule advances `next_run_at`, marks `last_run_status = "skipped"`, and logs `reason = "already_executed_for_period"`.
3. **Downtime Catch-Up Recovery (`hotel/stocktaking.py:676, 706`):**
   If the background scheduler service was offline across multiple scheduled periods, execution resumes, creates exactly 1 catch-up session for the earliest missed target date, and computes the next run from `current_time`. This prevents session floods.
4. **Timezone Boundary Integrity:**
   All schedule evaluations explicitly use `zoneinfo.ZoneInfo("Africa/Addis_Ababa")` (UTC+3). Database records store UTC timestamps (`2026-11-06 03:00:00 UTC` for local `06:00:00` Addis Ababa time).
5. **Daemon & CLI Management Command:**
   `python manage.py run_inventory_scheduler` supports one-shot and `--daemon --interval <sec>` modes. Tested in `test_09`, `test_10`, `test_11`, `test_12` (all PASS).

#### Area 8: Migration Safety and Code Regression
1. **Migration File Review (`hotel/migrations/0049_inventory_expiry_alerts_and_stocktake_schedules.py`):**
   - The migration is 100% additive: creates `InventoryExpiryAlert`, `StocktakeSchedule`, and adds nullable FK `schedule` and nullable DateField `scheduled_date` to `StocktakeSession`.
   - Staging data integrity is preserved; no fields or tables were dropped or altered destructively.
2. **CRITICAL DEFECT — File Corruption in `apps/inventory/views.py` (Severity: Critical):**
   - Direct inspection of `apps/inventory/views.py` revealed that the file was repeatedly concatenated/overwritten, growing to 5,915 lines with **26 duplicate class declarations** of `StocktakeScheduleViewSet`.
   - In lines 3163-3195, `StocktakeSessionViewSet` only defines `create()`.
   - The custom action endpoints belonging to `StocktakeSessionViewSet`:
     - `record_counts` (line 3365)
     - `request_recount` (line 3557)
     - `submit_recount` (line 3748)
     - `approve` (line 3945)
     - `cancel` (line 4139)
     were mistakenly pasted inside definitions of `StocktakeScheduleViewSet`.
   - The final definition of `StocktakeScheduleViewSet` (line 5801) omitted these actions.
   - **Impact:**
     1. Django URL router cannot resolve any of the following reverse names:
        - `stocktakesession-record-counts`
        - `stocktakesession-request-recount`
        - `stocktakesession-approve`
        - `stocktakesession-cancel`
     2. Automated tests fail with 5 errors in `test_stocktaking_management.py` and 1 error in `test_expiry_alerts_and_schedules.py`.
     3. The React 19 frontend physical stocktaking desk (`StocktakeCountDesk.jsx:72`, `StocktakeVarianceDesk.jsx:65, 110, 142`) makes HTTP calls to:
        - `POST /api/v1/stocktaking/sessions/${session.id}/record-counts/`
        - `POST /api/v1/stocktaking/sessions/${session.id}/request-recount/`
        - `POST /api/v1/stocktaking/sessions/${session.id}/approve/`
        - `POST /api/v1/stocktaking/sessions/${session.id}/cancel/`
        All of these requests encounter **404 Not Found** in the active backend environment.

---

## 2. Logic Chain

1. **Premise 1:** The quality control audit requires independent execution of test suites against `hotel_erp_staging` without relying on prior completion reports.
   - *Observation Reference:* Executed `.venv\Scripts\python.exe manage.py test` on `apps.inventory.tests.test_expiry_alerts_and_schedules` and `apps.inventory.tests.test_stocktaking_management`.
   - *Inference:* `test_expiry_alerts_and_schedules` failed 1 test (`test_13`), and `test_stocktaking_management` failed 5 tests (`test_05`, `test_06`, `test_07`, `test_11`, `test_12`).

2. **Premise 2:** All 6 test failures stem from the exact same exception: `django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-<action>' not found`.
   - *Observation Reference:* Traced stack traces in `steps/18/output.txt` and `steps/41/output.txt`. Tested URL reverse resolution in Django shell (`task-182`): `stocktakesession-approve`, `stocktakesession-record-counts`, `stocktakesession-request-recount`, and `stocktakesession-cancel` all failed with `NoReverseMatch`.

3. **Premise 3:** ViewSet registration in `apps/inventory/urls.py` binds `StocktakeSessionViewSet` to `stocktaking/sessions` with `basename="stocktakesession"`.
   - *Observation Reference:* `apps/inventory/views.py` lines 3163-3195 defines `StocktakeSessionViewSet` with ONLY `create()`. The custom action methods (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) were accidentally indented inside `StocktakeScheduleViewSet` in middle sections of the file, and then completely omitted in the final `StocktakeScheduleViewSet` at line 5801.

4. **Premise 4:** The frontend application at `hotel-frontend/src/pages/stocktaking/` relies on these exact URL endpoints to record physical counts, submit recounts, approve variances, and cancel sessions.
   - *Observation Reference:* `StocktakeCountDesk.jsx:72`, `StocktakeVarianceDesk.jsx:65, 110, 142`.
   - *Inference:* The live frontend stocktaking workflow cannot perform counting, recounting, approval, or cancellation against the backend API in its current state.

5. **Premise 5:** Expiry enforcement (Area 2), scheduling logic (Area 4), and concurrency/locking/downtime recovery (Area 5) are functionally solid and mathematically verified in `hotel/integrity.py` and `hotel/stocktaking.py`.
   - *Observation Reference:* `hotel/integrity.py:482-580` FEFO and quarantine filtering prevents non-waste consumption; `compute_next_run()` properly clamps month-ends (min(31, max_days)); `select_for_update(of=("self",))` enforces row locks.
   - *Inference:* The core business logic in `hotel/` models and services is properly implemented, but the API presentation layer in `apps/inventory/views.py` is critically broken.

---

## 3. Caveats

1. **Zero-Code-Modification Constraint:** Pursuant to strict QC operational guardrails, no application code was altered. The viewset methods were not moved back into `StocktakeSessionViewSet` during this investigation turn. A remediation patch must be applied by the designated implementation worker.
2. **Prior False Reporting:** Prior completion reports (`docs/PARTIAL_INVENTORY_COMPLETION_REPORT.md` and `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md`) recorded pass results that do not match the actual codebase state. The orchestrator must not accept these reports as proof of completion.
3. **Production Database Scope:** All tests and inspections were conducted against `test_hotel_erp_staging` and the active staging database `hotel_erp_staging`. Production databases were not touched.

---

## 4. Conclusion & Defect Log

### Overall Verdict: **REJECTED**
Per the acceptance criteria:
- **ACCEPTED:** Zero defects.
- **ACCEPTED WITH NON-CRITICAL OBSERVATIONS:** Medium or Low severity observations only.
- **REJECTED:** Any Critical or High severity defect identified.

Because **Defect D-01 is Critical Severity** (breaking core API routing and causing 6 automated test failures) and **Defect D-02 is High Severity** (dismissal reactivation), the backend verification verdict is **REJECTED**.

### Defect Inventory

| Defect ID | Severity | Component | File & Lines | Description & Impact |
| :--- | :---: | :--- | :--- | :--- |
| **DEF-BACKEND-01** | **Critical** | Views & URL Routing | `apps/inventory/views.py:3163-5915` | **StocktakeSessionViewSet Missing Custom Actions & Corrupted Viewset Declarations**: File contains 26 redundant `StocktakeScheduleViewSet` definitions. `StocktakeSessionViewSet` is missing `record_counts`, `request_recount`, `submit_recount`, `approve`, and `cancel`. Causes 6 test failures (`NoReverseMatch`) and 404 errors on live frontend count/approval desks. |
| **DEF-BACKEND-02** | **High** | Alert Lifecycle | `hotel/inventory.py:125-137` | **Dismissed Alerts Reactivated on Subsequent Scans**: `evaluate_inventory_expiry_alerts()` uses `get_or_create(..., status="active")`. If staff dismisses an alert for a still-expired batch, the next scan finds no active alert and creates a new active alert, invalidating staff dismissal. |
| **DEF-BACKEND-03** | **Medium** | Configurable Thresholds | `hotel/inventory.py:105-117` | **Hardcoded Near-Expiry Thresholds**: Alert threshold windows (1, 7, 14, 30 days) are hardcoded into Python logic and model choices rather than dynamic settings stored in `SystemSettings`. |

---

## 5. Verification Method (Independent Reproduction)

To independently verify all findings and test results:

1. **Verify Automated Integration Test Failures:**
   ```powershell
   # In workspace root:
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules -v 2
   # Expected result: FAILED (errors=1) at test_13 with NoReverseMatch for 'stocktakesession-approve'
   ```
2. **Verify Stocktaking Regression Test Failures:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management -v 2
   # Expected result: FAILED (errors=5) at test_05, test_06, test_07, test_11, test_12 with NoReverseMatch
   ```
3. **Verify URL Resolution Discrepancy Directly via Python Shell:**
   ```powershell
   .venv\Scripts\python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.urls import reverse; [print(name, reverse(name, args=[1])) for name in ['stocktakesession-approve', 'stocktakesession-record-counts', 'stocktakesession-cancel']]"
   # Expected result: django.urls.exceptions.NoReverseMatch
   ```
4. **Verify PostgreSQL 16 Staging Database Tables:**
   ```powershell
   .venv\Scripts\python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from hotel.models import InventoryExpiryAlert, StocktakeSchedule; print('Active Alerts:', InventoryExpiryAlert.objects.filter(status='active').count()); print('Active Schedules:', StocktakeSchedule.objects.filter(is_active=True).count())"
   ```
5. **Verify FEFO Lockout Logic in Source:**
   Inspect `hotel/integrity.py` lines 493-509 and 533-570 to verify that `status="active"` and `expiry_date >= today` are strictly enforced for non-waste stock transactions.
