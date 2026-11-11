# ACRMA HOTEL ERP — TARGETED INVENTORY QC REMEDIATION REPORT

**Document Reference:** `ERP-REMED-INVENTORY-QC-2026-V1.0`  
**Prior QC Audit Reference:** `QC-FINAL-PARTIAL-INVENTORY-2026-V1.0`  
**Date:** 5 November 2026  
**Author:** Lead Systems Architect & Main Orchestrator  
**Governing Branch:** `development`  
**Database & Staging Environment:** PostgreSQL 16.12 (`hotel_erp_staging` on `localhost:5432`) | Django 5.2 / DRF (`http://127.0.0.1:8000`) | React 19 SPA (`http://localhost:3000`)

---

## 1. Executive Summary & Defect Reconciliation Scorecard

Pursuant to the Owner Directive **# ACRMA HOTEL ERP — TARGETED INVENTORY QC REMEDIATION**, targeted engineering interventions were executed to resolve all three major defects and two medium observations identified in the Independent QC Report (`QC-FINAL-PARTIAL-INVENTORY-2026-V1.0`).

All 5 defect areas have been remediated, verified with automated unit/integration suites, live HTTP endpoint verification, and real-browser Selenium acceptance tests against `hotel_erp_staging`.

### Remediation Scorecard

| Defect ID | Severity | Description | Pre-Remediation State | Post-Remediation Verified State | Audit Status |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **DEF-01** | **Critical** | Missing StocktakeSession actions & ViewSet duplication | `StocktakeSessionViewSet` lacked custom actions (`record-counts`, `request-recount`, `submit-recount`, `approve`, `cancel`); 26 duplicate declarations in `views.py` (5,914 lines); 6 test failures (`NoReverseMatch`); live UI action forms failed with HTTP 404. | All 5 actions restored with `@action` decorators; `views.py` deduplicated to 1,603 lines of authoritative code (22 unique classes); all URL reverses resolve; live HTTP requests return 200 OK. | **RESOLVED** |
| **DEF-02** | **High** | Cascading audit deletion on `destroy()` | Default `ModelViewSet.destroy()` permitted deletion of in-progress/approved stocktake sessions, cascading to permanently delete child `StocktakeItem` historical audit records. | Overrode `destroy()` on `StocktakeSessionViewSet`: deletion of counted, under-review, or approved sessions is strictly blocked (HTTP 400 Bad Request). Historical audits are permanently immutable. | **RESOLVED** |
| **DEF-03** | **High** | Expiry alert dismissal reactivation loop | `evaluate_inventory_expiry_alerts()` queried `get_or_create(..., status='active')`, resurrecting staff-dismissed alerts as new duplicate active rows on every subsequent scan. | Replaced with query inspecting existing alerts: staff-dismissed alerts remain in `status='dismissed'` across repeated scans; on-hand quantity synced non-destructively; zero active duplicate rows created. | **RESOLVED** |
| **DEF-04** | **Medium** | Missing location-level object permissions | Schedules and stocktake sessions lacked horizontal scoping; any inventory staff could modify schedules across all locations. | Implemented `HasStocktakeLocationPermission` in `users/permissions.py`; checks location custodian, creator, and assigned staff; unauthorized staff attempts return HTTP 403 Forbidden. | **RESOLVED** |
| **DEF-05** | **Medium** | Hardcoded expiry warning thresholds | Near-expiry warning tiers (1, 7, 14, 30 days) were hardcoded constants lacking dynamic configuration. | Added `near_expiry_warning_days` (default 30) to `SystemSettings` in `hotel/models.py`; applied migration `0050`; dynamic window clamping in `evaluate_inventory_expiry_alerts()`. | **RESOLVED** |

---

## 2. Root Cause Analysis & Changes Made

### 2.1 DEF-01: Restoration of Stocktake Actions & ViewSet Cleanup
- **Root Cause:** Splicing operations during earlier feature additions had truncated `StocktakeSessionViewSet` down to its `create` method while appending 26 redundant duplicate declarations of `InventoryExpiryAlertViewSet` and `StocktakeScheduleViewSet`.
- **Changes Made in [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py):**
  1. Restored `@action(detail=True, methods=["post"], url_path="record-counts") def record_counts(self, request, pk=None)`.
  2. Restored `@action(detail=True, methods=["post"], url_path="request-recount") def request_recount(self, request, pk=None)`.
  3. Restored `@action(detail=True, methods=["post"], url_path="submit-recount") def submit_recount(self, request, pk=None)`.
  4. Restored `@action(detail=True, methods=["post"], url_path="approve") def approve(self, request, pk=None)`.
  5. Restored `@action(detail=True, methods=["post"], url_path="cancel") def cancel(self, request, pk=None)`.
  6. Restored full procurement action methods on `PurchaseRequisitionViewSet` (`approve`, `reject`, `convert-to-po`), `PurchaseOrderViewSet` (`receive-grn`), `SupplierInvoiceViewSet` (`match-and-record`, `approve`), `RequestForQuotationViewSet` (`publish`, `close`), and `SupplierQuotationViewSet` (`evaluate`, `award`, `convert-to-po`).
  7. Deduplicated `apps/inventory/views.py`: removed the 26 redundant interleaved blocks, reducing line count from 5,914 to 1,603 lines containing exactly the 22 authoritative ViewSet classes registered in `apps/inventory/urls.py`.

### 2.2 DEF-02: Stocktake Audit Trail Deletion Safeguard
- **Root Cause:** Standard DRF `ModelViewSet` exposes `destroy()` which executes SQL `DELETE`, triggering PostgreSQL `ON DELETE CASCADE` on `hotel_stocktakeitem`.
- **Changes Made in [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1435):**
  - Overrode `destroy(self, request, *args, **kwargs)`:
    - If `instance.status != "draft"`, returns HTTP 400 Bad Request with `"Historical inventory audits cannot be deleted. Use the cancel action instead."`
    - If `instance.is_mode_locked or instance.counted_by is not None or instance.items.filter(counted_quantity__isnull=False).exists()`, returns HTTP 400 Bad Request blocking deletion.
    - Only uncounted, unlocked draft sessions can be deleted.

### 2.3 DEF-03: Expiry Alert Dismissal Lifecycle & Reactivation Fix
- **Root Cause:** `evaluate_inventory_expiry_alerts()` queried `get_or_create(..., status="active")`. Once staff dismissed an alert (setting `status="dismissed"`), the subsequent scan found no `status="active"` record and spawned a duplicate active alert.
- **Changes Made in [`hotel/inventory.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel/inventory.py#L125-L165):**
  - Scans for any existing alert for `(batch, alert_type)` regardless of status.
  - If `existing_alert.status == "dismissed"`, preserves the dismissed status without recreation; synchronizes `current_quantity` and `location` non-destructively.
  - If `existing_alert.status == "active"`, updates quantity and location idempotently.
  - If `existing_alert.status == "resolved"`, spawns a new active alert only if positive stock is re-introduced.
  - Corrected `Notification` bulk creation to use schema field `user_id_ref=u.id`.

### 2.4 DEF-04: Location-Based Object Permissions
- **Root Cause:** `IsInventoryManager` only verified global role membership (`user.role in {"admin", "inventory"}`) without verifying location custodian assignment.
- **Changes Made in [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L201):**
  - Implemented `HasStocktakeLocationPermission(BasePermission)`:
    - `has_permission`: Verifies user is active staff (`admin`, `inventory`, `hotel_manager`).
    - `has_object_permission`: Allows read-only access for SAFE_METHODS; allows full access for administrators; for inventory staff, enforces that `user == obj.location.custodian`, `user == obj.created_by`, `user == obj.assigned_staff`, or `obj.location.custodian is None`.
  - Applied `HasStocktakeLocationPermission` to `StocktakeSessionViewSet` and `StocktakeScheduleViewSet`.

### 2.5 DEF-05: Configurable Expiry Warning Windows
- **Root Cause:** Surveillance tiers were hardcoded constants.
- **Changes Made in [`hotel/models.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel/models.py#L670):**
  - Added `near_expiry_warning_days = models.PositiveIntegerField(default=30, help_text="Configurable surveillance window in days before batch expiry to trigger near-expiry warnings.")` to `SystemSettings`.
  - Generated and applied migration `0050_systemsettings_near_expiry_warning_days.py` against `hotel_erp_staging`.
  - In `evaluate_inventory_expiry_alerts()`, reads `sys_settings.near_expiry_warning_days` to dynamically clamp active warning tiers.

---

## 3. Database Migration Records

Migration `0050_systemsettings_near_expiry_warning_days` was generated and applied to `hotel_erp_staging`:

```text
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, hotel, sessions, token_blacklist, users
Running migrations:
  Applying hotel.0050_systemsettings_near_expiry_warning_days... OK
  Applying users.0008_alter_user_role... OK
```

- Verified in PostgreSQL 16 staging table `hotel_systemsettings`: column `near_expiry_warning_days` added as `integer DEFAULT 30 NOT NULL`.

---

## 4. Test Verification Scorecard & Results

### 4.1 Automated Backend Test Execution (PostgreSQL 16 `hotel_erp_staging`)

| Test Suite | File Path | Tests Run | Passed | Failures | Errors | Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Expiry Alerts & Schedules** | [`apps/inventory/tests/test_expiry_alerts_and_schedules.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_expiry_alerts_and_schedules.py) | 13 | 13 | 0 | 0 | **100% PASS** |
| **Stocktaking Management** | [`apps/inventory/tests/test_stocktaking_management.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_stocktaking_management.py) | 12 | 12 | 0 | 0 | **100% PASS** |
| **Procurement Management** | [`apps/inventory/tests/test_procurement_management.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_procurement_management.py) | 12 | 12 | 0 | 0 | **100% PASS** |
| **RFQ & Quotation Workflow** | [`apps/inventory/tests/test_rfq_quotation_workflow.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_rfq_quotation_workflow.py) | 10 | 10 | 0 | 0 | **100% PASS** |
| **Remediation Specifics Suite** | `scratch/verify_remediation_specifics.py` | 4 | 4 | 0 | 0 | **100% PASS** |
| **Live HTTP Endpoints Suite** | `scratch/test_live_http_endpoints.py` | 8 | 8 | 0 | 0 | **100% PASS** |
| **TOTAL AUTOMATED VERIFICATION** | — | **59** | **59** | **0** | **0** | **100% PASS** |

### 4.2 Remediation Specifics Verification Details
- **Check 1 (DEF-02 Audit Deletion Protection):** Attempting `DELETE /users/stocktaking/sessions/<id>/` on a counted/under-review session returned `HTTP 400 Bad Request` with `"Historical inventory audits cannot be deleted"`. Snapshot items remained intact in database.
- **Check 2 (DEF-03 Dismissal Persistence):** Active alert dismissed via API (`status='dismissed'`). Evaluated `evaluate_inventory_expiry_alerts()` 3 consecutive times: `created=0, updated=0` across all 3 scans. Active duplicates count = 0.
- **Check 3 (DEF-04 Location Permissions):** Unauthorized staff member attempting to pause a schedule at a different store returned `HTTP 403 Forbidden`. Assigned custodian returned `HTTP 200 OK`. Administrator returned `HTTP 200 OK`.
- **Check 4 (DEF-05 Configurable Warning Thresholds):** Configured `near_expiry_warning_days=14`: batch expiring in 25 days generated 0 alerts. Configured `near_expiry_warning_days=30`: batch expiring in 25 days generated near-expiry alert.

---

## 5. Live HTTP Lifecycle Execution Evidence

Direct execution against the running Django backend (`http://127.0.0.1:8000`) via `scratch/test_live_http_endpoints.py`:

```text
1. Creating draft session via live API...
   Created Session #STK-20261105-466EE4 (ID 10) - Status: 201
2. Submitting physical count via /record-counts/ as counter...
   Record counts HTTP status: 200, new session status: under_review
3. Counter attempting SoD self-approval via /approve/...
   Counter self-approval HTTP status: 403 (Expected 403 Forbidden)
4. Supervisor requesting recount via /request-recount/...
   Request recount HTTP status: 200, new status: recount_required
5. Counter submitting recount via /submit-recount/...
   Submit recount HTTP status: 200, new status: under_review
6. Admin approving session via /approve/...
   Approval HTTP status: 200, status: approved, journal_entry_number: JV-4E7C93BF
7. Attempting DELETE on approved session via /sessions/{id}/...
   DELETE approved session HTTP status: 400 (Expected 400 Bad Request)
8. Creating second session to test /cancel/ endpoint...
   Cancel session HTTP status: 200, status: cancelled

ALL LIVE HTTP ENDPOINT VERIFICATIONS PASSED 100%!
```

---

## 6. Real-Browser Acceptance Verification Results

Automated browser acceptance suite (`scratch/test_browser_remediation_actions.py`) was executed using **Selenium WebDriver (Headless Google Chrome)** against the live React 19 application (`http://localhost:3000`) and Django backend (`http://127.0.0.1:8000`):

- **10 Visual Screenshots Captured** in `docs/screenshots/remediation/`:
  1. `01_dashboard_authenticated.png` — Authenticated dashboard landing.
  2. `02_stocktake_center_sessions.png` — Physical Stocktaking Center sessions list.
  3. `03_count_desk_loaded.png` — Interactive Count Desk loaded with blind-mode zero-leak masking.
  4. `04_counts_entered.png` — Physical count quantities entered into input grid.
  5. `05_count_submitted_transition.png` — Count form submitted to `/record-counts/` (HTTP 200); session transitioned to `under_review`.
  6. `06_variance_desk_view.png` — Variance Comparative Desk displaying discrepancy analysis.
  7. `07_approval_modal.png` — Review & Approve modal showing SoD enforcement and automated GL double-entry impact.
  8. `08_approval_success.png` — Approved stocktake; posted to General Ledger and closed.
  9. `09_batches_and_expiry_tab.png` — Batches & Expiry surveillance desk.
  10. `10_expiry_scan_verified.png` — On-demand expiry scan verified without resurrecting dismissed alerts.

---

## 7. Mandatory Safeguards & Data Integrity Confirmation

1. **Non-Destructive Operation**: Zero existing stocktaking records or audit history were deleted during remediation.
2. **Repository Integrity**: Zero lines of application code were reset or cleaned; no `git clean`, `git reset`, `git commit`, or `git push` was executed.
3. **Staging Environment Confinement**: All work, tests, and database migrations were executed strictly against `hotel_erp_staging` (PostgreSQL 16.12 on localhost:5432). Production remains untouched and undeployed.

---

## 8. Conclusion

All 3 major defects (**DEF-01**, **DEF-02**, **DEF-03**) and both medium observations (**DEF-04**, **DEF-05**) identified in the Independent QC Report have been resolved. The implementation has been verified with 59 passing tests, live HTTP validation, and real-browser acceptance. Ready for final QC audit and formal acceptance.

