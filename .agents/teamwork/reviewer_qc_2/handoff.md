# ADVERSARIAL QC REVIEW REPORT (reviewer_qc_2)

**Document Reference:** QC-REVIEW-2026-V1.0  
**Date:** 5 November 2026  
**Auditor / Reviewer:** Adversarial QC Reviewer (`reviewer_qc_2`)  
**Parent Orchestrator:** `924d3afb-bf16-4e0b-a52d-79193b7b7ac9`  
**Target QC Deliverable Reviewed:** `docs/PARTIAL_INVENTORY_INDEPENDENT_QC_REPORT.md`  
**Final Review Verdict:** **APPROVE**

---

## 1. Observation

Direct, independent observations executed in PowerShell against the staging environment (`hotel_erp_staging` / `test_hotel_erp_staging` on PostgreSQL 16.12, Python interpreter `.venv\Scripts\python.exe`):

### 1.1 Automated Test Execution & Verbatim Error Reproduction
1. **Expiry Alerts & Schedules Test Suite (`apps/inventory/tests/test_expiry_alerts_and_schedules.py`):**
   - Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb`
   - Output: `Ran 13 tests in 68.211s. FAILED (errors=1)`
   - Verbatim Error Traceback:
     ```text
     ======================================================================
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
     ```

2. **Stocktaking Management Regression Suite (`apps/inventory/tests/test_stocktaking_management.py`):**
   - Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb`
   - Output: `Ran 12 tests in 136.199s. FAILED (errors=5)`
   - Verbatim Errors:
     - `test_05_mode_locking_on_first_count_submission`: Line 263, `NoReverseMatch: Reverse for 'stocktakesession-record-counts' not found.`
     - `test_06_recount_workflow_flagging_and_resubmission`: Line 303, `NoReverseMatch: Reverse for 'stocktakesession-request-recount' not found.`
     - `test_07_separation_of_duties_prevents_self_approval`: Line 365, `NoReverseMatch: Reverse for 'stocktakesession-approve' not found.`
     - `test_11_session_cancellation_leaves_balances_intact`: Line 541, `NoReverseMatch: Reverse for 'stocktakesession-cancel' not found.`
     - `test_12_non_manager_cannot_create_or_approve_sessions`: Line 574, `NoReverseMatch: Reverse for 'stocktakesession-approve' not found.`

### 1.2 ViewSet Routes and Codebase Structure Inspection
- Command: `.venv\Scripts\python.exe manage.py shell -c "import users.serializers; from apps.inventory.views import StocktakeSessionViewSet; print('Extra actions on StocktakeSessionViewSet:', [a.__name__ for a in StocktakeSessionViewSet.get_extra_actions()])"`
  - Output: `Extra actions on StocktakeSessionViewSet: []`
- Inspection of `apps/inventory/views.py:3163-3195`:
  - `StocktakeSessionViewSet` defines only `create()`. Methods `record_counts`, `request_recount`, `submit_recount`, `approve`, and `cancel` are completely absent.
  - `destroy()` is not overridden, inheriting default `ModelViewSet.destroy()`.
- Count of `class StocktakeScheduleViewSet` in `apps/inventory/views.py`:
  - Command: `Get-Content "apps/inventory/views.py" | Select-String "class StocktakeScheduleViewSet" | Measure-Object`
  - Output: `Count: 26` (confirmed exactly 26 redundant declarations across 5,915 lines).
- Inspection of `hotel/models.py:2387-2390`:
  - `StocktakeItem.session = models.ForeignKey(StocktakeSession, on_delete=models.CASCADE, related_name="items")`.
- Inspection of `hotel/inventory.py:125-137`:
  - Alert lookup uses `get_or_create(batch=batch, alert_type=alert_type, status="active", defaults={...})`.
- Screenshot Artifacts Inspection in `docs/screenshots/partial_inventory/`:
  - Verified all 11 files exist. Exact file sizes directly match the QC report table (e.g. `01_inventory_dashboard_landing.png` = 208,094 bytes; `02_batches_and_expiry_tab.png` = 272,960 bytes; `11_generated_scheduled_session_in_table.png` = 225,810 bytes).
- Git Repository State & Operational Guardrails:
  - Command: `git status`
  - Output: Working tree state intact; zero lines of application code or migrations were added or modified by the QC audit. Untracked file added is strictly `docs/PARTIAL_INVENTORY_INDEPENDENT_QC_REPORT.md` and metadata under `.agents/`.
- Staging Database Verification:
  - Active Alerts Count = 4 (`InventoryExpiryAlert.objects.filter(status='active').count()`)
  - Active Schedules Count = 1 (`StocktakeSchedule.objects.filter(is_active=True).count()`)
  - Matches browser test state (`05_alert_dismissed_state.png` and `09_schedule_created_table.png`). Staging DB is uncorrupted.

---

## 2. Logic Chain

1. **Verification of Test Reproducibility:**
   - The prior completion report (`docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md`) claimed 100% test pass (13/13 and 12/12).
   - Independent test execution directly verified that 6 automated tests crash with `django.urls.exceptions.NoReverseMatch`.
   - The verbatim error tracebacks recorded in the QC deliverable match the runtime execution outputs line-for-line.
   - Therefore, the test failure findings are genuine, reproducible, and completely substantiated.

2. **Validation of Defect Classifications:**
   - **DEF-01 (Critical Severity):** The lack of `@action` decorators for `record_counts`, `request_recount`, `submit_recount`, `approve`, and `cancel` on `StocktakeSessionViewSet` causes all physical count, recount, and approval REST endpoints to return HTTP 404. This severs the frontend React desks from backend services and breaks 6 automated tests. In an ERP system, a missing API surface for a core business function is unequivocally a **Critical Severity** defect.
   - **DEF-02 (High Severity):** Inheriting default `ModelViewSet.destroy()` without lifecycle gating combined with `on_delete=models.CASCADE` on `StocktakeItem` permits an authorized user to issue `DELETE /api/v1/stocktaking/sessions/<id>/` against `in_progress` or `approved` audits, permanently destroying financial reconciliation snapshots and audit trails. This is a severe audit-trail vulnerability, validly classified as **High Severity**.
   - **DEF-03 (High Severity):** Filtering strictly for `status="active"` inside `get_or_create` in `hotel/inventory.py:125-137` causes any alert that was acknowledged and dismissed by staff (`status="dismissed"`) to be resurrected as a new active alert on the very next background scheduler cycle or manual scan. This creates an infinite notification and alert loop, defeating the core requirement for staff acknowledgment persistence. Validly classified as **High Severity**.
   - **DEF-04 & DEF-05 (Medium Severity):** Lack of horizontal staff-scoping on schedules and hardcoded near-expiry windows without dynamic `SystemSettings` configuration are accurately calibrated as Medium severity observations.

3. **Strict Adherence of Final Verdict:**
   - `ORIGINAL_REQUEST.md` mandates:
     - `ACCEPTED`: Zero defects across all verified areas.
     - `ACCEPTED WITH NON-CRITICAL OBSERVATIONS`: Unresolved Medium or Low severity observations only; zero Critical or High severity defects.
     - `REJECTED`: Any Critical or High severity defect identified.
   - Because the audit identified 1 Critical defect and 2 High defects, the only compliant verdict under the governing rules is **REJECTED**.
   - The QC deliverable correctly rendered **REJECTED**.

4. **Integrity and Operational Guardrails:**
   - No hardcoded test passes or fabricated results were present in the QC deliverable.
   - The QC team maintained zero modifications to application source code or migrations.
   - Git working tree state was preserved, and staging database records remain uncorrupted.

---

## 3. Caveats

- **Browser Script Rerun:** Re-running `scratch/test_browser_partial_features.py` during review was blocked by host sandbox security constraints (`permission check failed for unsandboxed python.exe`), as was appropriately disclosed in the QC report itself. Visual verification was established through direct inspection of the 11 captured acceptance screenshots in `docs/screenshots/partial_inventory/`, comparing DOM states, file sizes, and database counts.
- **Remediation Scope:** In strict accordance with the review mandate, no remediation code or bug fixes were applied during this review.

---

## 4. Conclusion

The QC deliverable `docs/PARTIAL_INVENTORY_INDEPENDENT_QC_REPORT.md` is an authentic, highly thorough, and mathematically substantiated assessment of the partial inventory implementation. It properly dismantles false claims made in previous implementation reports, proves the existence of 6 reproducible test failures, correctly classifies DEF-01 as Critical and DEF-02/DEF-03 as High, and issues the mandatory verdict of **REJECTED**.

**Explicit Review Verdict: APPROVE**

---

## 5. Verification Method

To independently verify this review:
1. Run `apps.inventory.tests.test_expiry_alerts_and_schedules`:
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb
   ```
   *Expected:* FAILED (errors=1) at `test_13`.
2. Run `apps.inventory.tests.test_stocktaking_management`:
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb
   ```
   *Expected:* FAILED (errors=5) at `test_05`, `test_06`, `test_07`, `test_11`, `test_12`.
3. Check extra actions on `StocktakeSessionViewSet`:
   ```powershell
   .venv\Scripts\python.exe manage.py shell -c "import users.serializers; from apps.inventory.views import StocktakeSessionViewSet; print([a.__name__ for a in StocktakeSessionViewSet.get_extra_actions()])"
   ```
   *Expected:* `[]`
4. Measure duplicate class count in `apps/inventory/views.py`:
   ```powershell
   Get-Content "apps/inventory/views.py" | Select-String "class StocktakeScheduleViewSet" | Measure-Object
   ```
   *Expected:* `Count: 26`
