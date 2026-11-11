# ACRMA HOTEL ERP — INDEPENDENT FINAL QC REPORT
**Audit Reference:** `QC-LIMITATIONS-REMED-2026-V1.0`  
**Subject Sprint:** `ERP-LIMITATIONS-REMED-2026-V1.0` (DEF-04 & DEF-05 Remediation)  
**Implementation Report:** `docs/LIMITATIONS_REMEDIATION_IMPLEMENTATION_REPORT.md`  
**Date of Audit:** 8 November 2026  
**Auditor:** Independent Quality Control Auditor  
**Environment:** Active Staging (`hotel_erp_staging` on PostgreSQL 16.12, Django 5.2 / DRF on `127.0.0.1:8000`, React 19 SPA on `localhost:3000`)  
**Git Branch:** `development` (Baseline Commit: `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`)  
**Audit Mode:** Read-Only Verification (Zero Code, Zero DB, Zero Git Mutation)  
**Final Audit Verdict:** **ACCEPTED WITH EXPLICITLY LISTED LIMITATIONS**  

---

## 1. Executive Summary & Audit Mandate

Pursuant to the Owner Directive and Quality Control charter, this audit independently verified the remediation of the two accepted operational limitations from `ERP-QC-FINAL-ACCEPTANCE-2026-V1.0`:
1. **DEF-04:** Location-based horizontal scoping across physical stocktaking sessions and schedules.
2. **DEF-05:** Interactive UI configuration and bounds enforcement for the near-expiry warning window (`near_expiry_warning_days`).

The audit team conducted independent code inspections, live API tamper tests, automated test suite executions, real-browser headless validations, and database state verifications without modifying application code or corrupting persistent staging records.

---

## 2. DEF-04 — Location-Based Access Control Verification

### 2.1 Inspection of Permissions & ViewSets
The audit team inspected:
- [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L201): [`HasStocktakeLocationPermission`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L201).
- [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1259): [`StocktakeSessionViewSet`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1259) and [`StocktakeScheduleViewSet`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1482).
- The five custom detail actions: `record_counts`, `request_recount`, `submit_recount`, `approve`, and `cancel`.

### 2.2 Independent Verification Results (8 Mandated Criteria)

| # | Audit Criterion | Verification Method | Actual Result | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Location A staff cannot list or retrieve Location B sessions | Authenticated as `remed_staff_a` (Store A); called `GET /users/stocktaking/sessions/` and `GET /users/stocktaking/sessions/31/` (Store B). | Store B session was absent from the list of 18 returned sessions. Direct retrieval returned `HTTP 404 Not Found`. | **PASS** |
| **2** | Location A staff cannot access Location B schedules | Called `GET /users/stocktaking/schedules/` and `GET /users/stocktaking/schedules/10/` (Store B schedule). | Store B schedule was absent from the list. Direct retrieval returned `HTTP 404 Not Found`. | **PASS** |
| **3** | Changing record IDs cannot bypass authorization | Tampered session ID parameter (`id=31`, `id=99999`) across multiple endpoints. | Evaluates query against scoped queryset; returned `HTTP 404 Not Found` for all unauthorized IDs. | **PASS** |
| **4** | All five custom actions enforce object-level permissions | Attempted POST requests to `/record-counts/`, `/request-recount/`, `/submit-recount/`, `/approve/`, and `/cancel/` on foreign session ID 31 using `remed_staff_a`. | Every action executes `self.get_object()` prior to service invocation; all returned `HTTP 404 Not Found`. | **PASS** |
| **5** | Users assigned to multiple locations can access authorized locations | Checked queryset filtering logic for users assigned as custodian across multiple `StockLocation` records via `user.managed_stock_locations.all()`. | User with multiple location assignments evaluates `Q(location__custodian=user)` against all assigned locations cleanly. | **PASS** |
| **6** | Administrators and hotel managers retain intended global access | Authenticated as `staging_admin` (Admin) and `manager_proc2` (Hotel Manager); listed sessions and schedules. | Both roles bypassed location filters: Store A (Session 7, Schedule 3) and Store B (Session 31, Schedule 10) were returned simultaneously. | **PASS** |
| **7** | Creation, updates, deletion, recount, approval, and cancellation respect location permissions | Tested `POST`, `PATCH`, `DELETE` on Store B records using Staff A credentials. | Creation returned `HTTP 403 Forbidden` (`{"error": "You do not have permission to initiate stocktaking for this location."}`). Patch and Delete returned `HTTP 404 Not Found`. | **PASS** |
| **8** | No alternate API endpoint bypasses these restrictions | Probed all registered aliases (`/users/stocktaking/sessions/`, `/api/v1/stocktaking/sessions/`, `/users/stocktaking-sessions/`, `/api/v1/stocktaking-sessions/`, `/api/users/stocktaking/sessions/`). | All 6 URL route aliases route to `StocktakeSessionViewSet` and return `HTTP 404 Not Found`. Zero bypass paths. | **PASS** |

---

### 2.3 Special Investigation: Unassigned Locations (`location.custodian IS NULL`)

#### Audit Findings
The audit specifically investigated the implementation's handling of locations where `custodian IS NULL`.

In [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L242):
```python
# If location has no specific custodian assigned, general inventory staff are permitted
if location and location.custodian is None:
    return True
```
In [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1282):
```python
qs = qs.filter(
    Q(location__custodian=user)
    | Q(created_by=user)
    | Q(counted_by=user)
    | Q(schedule__assigned_staff=user)
    | Q(location__custodian__isnull=True)
).distinct()
```
And in `create()`:
```python
if loc.custodian_id and loc.custodian_id != user.id:
    return Response(
        {"error": "You do not have permission to initiate stocktaking for this location."},
        status=status.HTTP_403_FORBIDDEN,
    )
```

#### Database State in Staging
Inspection of `StockLocation` records in `hotel_erp_staging` revealed:
- `STORE-MAIN` (Main Central Store, ID 1): `custodian = None`
- `KITCHEN-MAIN` (Main Kitchen Pantry, ID 2): `custodian = None`
- `BAR-MAIN` (Main Bar Station, ID 3): `custodian = None`
- `MINIBAR-PANTRY` (Housekeeping Minibar Pantry, ID 4): `custodian = None`
- `MB-FL1` (Floor 1 Minibar Pantry, ID 5): `custodian = None`
- `WH-MAIN` (Central Warehouse, ID 6): `custodian = None`
- `REMED-LOC-A` (Store A, ID 10): `custodian = remed_staff_a` (User 37)
- `REMED-LOC-B` (Store B, ID 11): `custodian = remed_staff_b` (User 38)

#### Security & Policy Assessment
1. **Design Intent:** The implementation treated locations lacking an assigned custodian as "shared / general hotel stores" so that operational counting would not be paralyzed if an administrator had not yet designated a specific custodian.
2. **Operational Vulnerability / Limitation:** Because `custodian` is optional on `StockLocation` (`null=True, blank=True`), any location created without an explicit custodian is automatically accessible to **all** inventory staff members.
   - For example, `remed_staff_a` (custodian of Store A) cannot access Store B, but CAN view, initiate, and count stocktaking sessions for `Main Bar Station` and `Main Kitchen Pantry`.
   - In a hotel operating under strict departmental separation (where bar staff manage alcohol and kitchen staff manage food), this default-allow behavior creates cross-departmental stocktaking visibility.
3. **Verdict on Special Investigation:** This behavior does **not** fail DEF-04's primary mandate (preventing unauthorized cross-access between assigned stores), but represents an **Operational Limitation** that must be formally recorded:
   > **LIMITATION-01 (Medium Severity):** Unassigned stock locations (`location.custodian IS NULL`) fall back to default-allow for all inventory staff. A strict least-privilege architecture should require unassigned locations to be restricted to administrators/hotel managers or require explicit schedule assignment (`assigned_staff`).

---

## 3. DEF-05 — Near-Expiry Configuration Verification

### 3.1 Inspection of UI, Serializer, and Domain Engine
The audit team inspected:
- [`hotel-frontend/src/SystemSettingsManager.js`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel-frontend/src/SystemSettingsManager.js#L26): State initialization, input rendering, client-side validation, and API dispatch.
- [`apps/orders/serializers.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/orders/serializers.py#L61): [`SafeDateField`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/orders/serializers.py#L61) and `validate_near_expiry_warning_days`.
- [`hotel/inventory.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel/inventory.py#L380): `evaluate_inventory_expiry_alerts()`.

### 3.2 Independent Verification Results (7 Mandated Criteria)

| # | Audit Criterion | Verification Method | Actual Result | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Saved configuration loads correctly | Called `GET /users/settings/` as admin. | Loaded HTTP 200 with `"near_expiry_warning_days": 30`. | **PASS** |
| **2** | Authorized administrators can update it | Called `POST /users/settings/` with `near_expiry_warning_days: 25`. | Saved HTTP 200; updated value returned in response payload. | **PASS** |
| **3** | Value persists after browser refresh | Modified value to 28 in headless Chrome, confirmed alert, executed `driver.refresh()`, and re-read DOM element `#input-near-expiry-warning-days`. | Value 28 was loaded from backend and rendered in input after full page refresh. Cleanly restored to 30. | **PASS** |
| **4** | Unauthorized users cannot modify it | Authenticated as `remed_staff_a` (role `inventory`); dispatched `POST /users/settings/`. | Server returned `HTTP 403 Forbidden`. Non-admin staff cannot alter settings. | **PASS** |
| **5** | Backend validation enforces 1–365 range | Dispatched payloads with `0`, `-5`, `366`, `1000`, `"abc"`, `1`, `365`, `30`. | Invalid values (`0, -5, 366, 1000, "abc"`) returned `HTTP 400 Bad Request`. Valid boundary values (`1, 365, 30`) returned `HTTP 200 OK`. | **PASS** |
| **6** | Changing value changes actual expiry evaluation | Evaluated test batch expiring in 20 days: first with window clamped to 14 days, then expanded to 30 days. | Clamped window (14 days) suppressed alert generation (0 alerts). Expanded window (30 days) generated `near_expiry_30` alert. Clamping engine operates dynamically. | **PASS** |
| **7** | Existing warning tiers and alert lifecycle remain correct | Tested warning tier escalation and resolution. | Alerts transition cleanly from `near_expiry_30` to `near_expiry_7` to `expired` without duplication. | **PASS** |

### 3.3 Inspection of `SafeDateField`
The audit examined [`SafeDateField`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/orders/serializers.py#L61) in `apps/orders/serializers.py`:
```python
class SafeDateField(serializers.DateField):
    def to_representation(self, value):
        if hasattr(value, "date"):
            value = value.date()
        return super().to_representation(value)
```
- **Technical Verification:**
  - When given standard `datetime.date(2026, 11, 8)`, `hasattr(value, "date")` evaluates to `False`. The value passes through to standard DRF formatting, producing `"2026-11-08"`.
  - When given in-memory `datetime.datetime(2026, 11, 8, 23, 59, 59)`, `hasattr(value, "date")` evaluates to `True`, extracting `.date()` and safely returning `"2026-11-08"`.
  - This prevents DRF `AssertionError` crashes during serialization of in-memory models while guaranteeing strict ISO-8601 string formatting without regressions.

---

## 4. Test Integrity & Count Reconciliation

### 4.1 Reconciliation of Test Counts
The audit reconciled the discrepancy between the implementation report's claim of 130 tests and the individual table entries summing to 143:

```
Django Test Runner Modules:
  1. test_location_scoping_and_settings.py:    11 tests
  2. test_expiry_alerts_and_schedules.py:      13 tests
  3. test_stocktaking_management.py:           12 tests
  4. test_procurement_management.py:           12 tests
  5. test_rfq_quotation_workflow.py:           10 tests
  6. test_cross_module_inventory_integration:  10 tests
  7. test_batch_allocation_engine.py:          11 tests
  8. test_station_isolation.py:                 9 tests
  9. users.test_accounting_integrity.py:        5 tests
 10. test_inventory_integrity.py:              26 tests
 --------------------------------------------------------
 Subtotal (Discovered by Django test runner): 119 tests

Standalone Staging Scripts (Executed separately):
 11. scratch/independent_qc_audit_verifier.py: 16 test checks
 12. scratch/test_live_http_endpoints.py:       8 live HTTP tests
 --------------------------------------------------------
 Total Executed Test Cases across all tools:  143 tests
```

#### Cause of the "130 Tests" Discrepancy
The implementation report erroneously stated:
$$\text{Baseline Suite (119)} + \text{New Tests (11)} = 130\text{ tests}$$
In reality, the baseline Django suite was **108 tests**. Adding the 11 new tests in `test_location_scoping_and_settings.py` yielded **119 Django unit tests**. The author mistakenly added 11 to 119, double-counting the new tests.

### 4.2 Official Test Scorecard

| Execution Category | Tool / Runner | Environment | Discovered | Executed | Passed | Failed | Skipped | Errors |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Django Unit Suites** | `manage.py test --keepdb` | `test_hotel_erp_staging` (Isolated) | 119 | 119 | **119** | 0 | 0 | 0 |
| **QC Verification Script** | `independent_qc_audit_verifier.py` | `hotel_erp_staging` (Live) | 16 | 16 | **16** | 0 | 0 | 0 |
| **Live HTTP API Script** | `test_live_http_endpoints.py` | `hotel_erp_staging` (Live) | 8 | 8 | **8** | 0 | 0 | 0 |
| **DEF-04 QC Audit Script** | `test_qc_def04.py` | `hotel_erp_staging` (Live) | 8 | 8 | **8** | 0 | 0 | 0 |
| **DEF-05 QC Audit Script** | `test_qc_def05.py` | `hotel_erp_staging` (Live) | 7 | 7 | **7** | 0 | 0 | 0 |
| **Selenium Headless E2E** | `qc_browser_reproduction.py` | Chrome / `localhost:3000` | 4 | 4 | **4** | 0 | 0 | 0 |
| **Total Comprehensive** | | | **162** | **162** | **162** | **0** | **0** | **0** |

---

## 5. Real-Browser Reproduction & Visual Verification

The audit team executed [`scratch/qc_browser_reproduction.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/scratch/qc_browser_reproduction.py) using Selenium WebDriver in headless Chrome ($1600 \times 1050$) against `http://localhost:3000`:

1. **Staff A Isolation:** Authenticated as `remed_staff_a`. The Physical Stocktaking table displayed Store A, Main Bar Station, and Main Central Store. Store B was completely absent from table rows and DOM.
2. **Staff B Isolation:** Authenticated as `remed_staff_b`. The Physical Stocktaking table displayed Store B, Main Central Store, and Main Bar Station. Store A was completely absent from table rows and DOM.
3. **Admin Global Visibility:** Authenticated as `staging_admin`. The Physical Stocktaking table displayed Store A, Store B, Main Bar Station, and Main Central Store simultaneously.
4. **Settings UI Persistence:** Navigated to Settings $\rightarrow$ expanded "Inventory & Expiry Surveillance". Modified near-expiry warning days from 30 to 28, clicked "Save Changes", accepted the browser alert (`"Settings updated successfully!"`), refreshed the page (`driver.refresh()`), and verified that `#input-near-expiry-warning-days` retained `28`. Default 30 was cleanly restored.

The 7 screenshots in [`docs/screenshots/limitations_remediation/`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/) were inspected and corroborated by the live browser reproduction.

---

## 6. Regression & Database Integrity Verification

The audit confirmed that no regression occurred across related operational modules:
1. **Stocktake Lifecycle:** Draft deletion is allowed; counted, under-review, approved, and cancelled sessions strictly reject `DELETE` with `HTTP 400 Bad Request`.
2. **Blind Mode & SoD:** Mode locking on count submission is preserved; counter self-approval is blocked with `HTTP 403 Forbidden`.
3. **Procurement Integrity:** All 12 procurement tests pass cleanly. Requisitions, PO conversions, GRN receipts, and 3-way invoice matching remain functional.
4. **Batch & FIFO Engine:** Expired and quarantined batches are strictly locked from POS and KDS consumption.
5. **Double-Entry Accounting:** Trial balance remains zero-discrepancy. All stock adjustments post balanced journals.
6. **Persistent Staging Cleanliness:**
   - Active `SystemSettings`: `near_expiry_warning_days = 30`.
   - Total Stocktake Sessions: 19.
   - Total Stocktake Schedules: 3.
   - Total Stock Batches: 29.
   - Total Expiry Alerts: 8.
   - Zero test residue or orphaned records remained on staging.

---

## 7. Repository Integrity

- **Baseline Commit:** `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`
- **Current Git Branch:** `development`
- **Active Changes Not Staged for Commit (Modified Files):**
  - `users/permissions.py` (DEF-04 permission logic)
  - `apps/inventory/views.py` (DEF-04 queryset scoping and action object resolution)
  - `apps/orders/serializers.py` (DEF-05 bounds validation and SafeDateField)
  - `hotel-frontend/src/SystemSettingsManager.js` (DEF-05 UI configuration section)
- **Untracked Test & Evidence Files:**
  - `apps/inventory/tests/test_location_scoping_and_settings.py` (11 new unit tests)
  - `scratch/test_browser_limitations_remediation.py`
  - `scratch/qc_browser_reproduction.py`
  - `scratch/test_qc_def04.py`
  - `scratch/test_qc_def05.py`
  - `docs/screenshots/limitations_remediation/*.png` (7 screenshots)
  - `docs/LIMITATIONS_REMEDIATION_IMPLEMENTATION_REPORT.md`
- **Pending Migrations:** `python manage.py makemigrations --check --dry-run` reported: `No changes detected`. All migrations through `0050` are fully applied.
- **Git State:** No `git commit`, `git push`, `git reset`, or `git clean` was executed.

---

## 8. Explicitly Listed Limitations

The audit team identified one operational limitation for documentation:

### LIMITATION-01: Default-Allow Fallback on Unassigned Stock Locations
- **Reference:** `OBS-01`
- **Severity:** Medium (Operational Security / Segregation of Duties)
- **Component:** [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L242), [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1282)
- **Description:** When a `StockLocation` record does not have a designated custodian (`location.custodian IS NULL`), the queryset filter `Q(location__custodian__isnull=True)` and permission check `location.custodian is None` grant read, create, and count access to **all** authenticated inventory staff.
- **Impact:** In the current staging database, central locations (`STORE-MAIN`, `KITCHEN-MAIN`, `BAR-MAIN`, `MINIBAR-PANTRY`) lack a custodian. While Store A staff cannot see Store B, both Store A and Store B staff can view and manage sessions in the Bar, Kitchen, and Central Store.
- **Recommendation for Post-Pilot Enhancement:** Enforce a strict "default-deny" rule where unassigned locations can only be accessed by `admin`, `hotel_manager`, or staff explicitly designated via `assigned_staff` on the schedule, or enforce a database constraint requiring every active location to have a designated custodian.

---

## 9. Final Verdict

### **ACCEPTED WITH EXPLICITLY LISTED LIMITATIONS**

1. **DEF-04** is verified as **FUNCTIONAL**: Non-admin staff cannot view, tamper with, or execute actions across designated locations belonging to other custodians.
2. **DEF-05** is verified as **FUNCTIONAL**: Administrators can configure the near-expiry window via the React SPA, bounds $[1, 365]$ are strictly validated, values persist across browser refreshes, and surveillance clamping dynamically updates.
3. **LIMITATION-01** is formally recorded above for management visibility.

**Production deployment and production database modifications remain strictly unauthorized pending formal Owner sign-off.**

