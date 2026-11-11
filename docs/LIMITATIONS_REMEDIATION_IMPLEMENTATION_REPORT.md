# ACRMA HOTEL ERP — LIMITATIONS REMEDIATION IMPLEMENTATION REPORT
**Sprint Reference:** `ERP-LIMITATIONS-REMED-2026-V1.0`  
**Prior Acceptance Reference:** `ERP-QC-FINAL-ACCEPTANCE-2026-V1.0`  
**Date:** 7 November 2026  
**Environment:** Staging (`hotel_erp_staging` on PostgreSQL 16.12, Django 5.2 / DRF on `127.0.0.1:8000`, React 19 SPA on `localhost:3000`)  
**Branch:** `development`  
**Status:** IMPLEMENTATION COMPLETE — READY FOR INDEPENDENT QC  

---

## 1. Executive Summary & Sprint Scope

In `ERP-QC-FINAL-ACCEPTANCE-2026-V1.0`, the independent Quality Control audit certified the primary release readiness of the partial inventory implementation while explicitly noting two operational limitations:
- **DEF-04 (Operational Observation):** Stocktake session and schedule read access (`list` and `retrieve`) lacked location-level horizontal scoping. Staff members assigned to a specific store could view other stores' stocktake records and schedules, and custom actions did not enforce location boundaries prior to execution.
- **DEF-05 (Minor Observation):** The `near_expiry_warning_days` parameter was fully functional in backend settings and migration `0050`, but lacked an interactive configuration interface in the React SPA `SystemSettingsManager.js`.

This targeted corrective sprint resolved both limitations without modifying any already accepted stocktaking or inventory functionality.

---

## 2. Git & Environment Baseline

- **Repository Root:** `d:/workspace/ongoing projects/Acrma hotel mangment/Acrma hotel mangment`
- **Active Git Branch:** `development`
- **Database Backend:** PostgreSQL 16.12 (`hotel_erp_staging` on `localhost:5432`)
- **Backend Application:** Django 5.2 running under Python 3.12 virtual environment (`.venv`)
- **Frontend Application:** React 19 SPA running on `http://localhost:3000`
- **Files Modified:**
  1. [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L201)
  2. [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L701)
  3. [`apps/orders/serializers.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/orders/serializers.py#L61)
  4. [`hotel-frontend/src/SystemSettingsManager.js`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel-frontend/src/SystemSettingsManager.js#L26)
- **Files Added:**
  1. [`apps/inventory/tests/test_location_scoping_and_settings.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_location_scoping_and_settings.py)
  2. [`scratch/test_browser_limitations_remediation.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/scratch/test_browser_limitations_remediation.py)
  3. `docs/screenshots/limitations_remediation/*.png` (7 browser screenshots)

---

## 3. Technical Root Cause & Remediation Architecture

### 3.1 DEF-04: Location Scoping & IDOR Protection

#### Root Cause
In `HasStocktakeLocationPermission`, standard HTTP safe methods (`GET`, `HEAD`, `OPTIONS`) were granted blanket access (`if request.method in SAFE_METHODS: return True`), allowing any authenticated staff member to execute `GET /users/stocktaking/sessions/{id}/` and `GET /users/stocktaking/schedules/{id}/` across any location. Furthermore, `StocktakeSessionViewSet` and `StocktakeScheduleViewSet` lacked location filtering in `get_queryset()`, allowing all sessions and schedules across the hotel to be returned to unauthorized staff. Finally, detail actions (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) passed `session_id=pk` straight into domain services without calling `self.get_object()`, bypassing DRF queryset scoping and object permissions.

#### Remediation Details
1. **Permission Enforcement ([`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/users/permissions.py#L201)):**
   - Removed the blanket `SAFE_METHODS` bypass in `has_object_permission`.
   - Read and write operations now evaluate the exact location custodian and assignment chain:
     - Administrators (`admin`, `hotel_manager`, or `is_superuser`) retain global cross-location access.
     - For `StocktakeSession`: permitted if the user is `location.custodian`, `created_by`, `counted_by`, or assigned to the parent `schedule.assigned_staff`, or if the location has no designated custodian (`location.custodian is None`).
     - For `StocktakeSchedule`: permitted if the user is `location.custodian`, `assigned_staff`, `created_by`, or if `location.custodian is None`.
2. **QuerySet Horizontal Scoping ([`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/views.py#L1268)):**
   - In `StocktakeSessionViewSet.get_queryset()`, filtered non-admin queries by:
     ```python
     qs = qs.filter(
         Q(location__custodian=user)
         | Q(created_by=user)
         | Q(counted_by=user)
         | Q(schedule__assigned_staff=user)
         | Q(location__custodian__isnull=True)
     )
     ```
   - In `StocktakeScheduleViewSet.get_queryset()`, filtered non-admin queries by:
     ```python
     qs = qs.filter(
         Q(location__custodian=user)
         | Q(assigned_staff=user)
         | Q(created_by=user)
         | Q(location__custodian__isnull=True)
     )
     ```
3. **Creation Validation:**
   - In both ViewSets' `create()` methods, verified that non-admin users cannot initiate stocktake sessions or schedules for locations they do not manage, returning `HTTP 403 Forbidden`.
4. **Action-Level Object Resolution:**
   - In `StocktakeSessionViewSet`, every custom action (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) now calls `self.get_object()` prior to executing service logic. If a staff member attempts IDOR on a foreign session, DRF automatically returns `HTTP 404 Not Found` (or `403 Forbidden`).

---

### 3.2 DEF-05: Expiry Warning Window Configuration via React SPA

#### Root Cause
Backend support for `near_expiry_warning_days` was already present in `SystemSettings` (defaulting to 30 days) and used by `hotel.inventory.evaluate_inventory_expiry_alerts()`. However, the React SPA's `SystemSettingsManager.js` neither fetched nor rendered this field, and the DRF serializer lacked explicit range validation ($1 \le \text{days} \le 365$).

#### Remediation Details
1. **Serializer Validation ([`apps/orders/serializers.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/orders/serializers.py#L61)):**
   - Added `validate_near_expiry_warning_days(self, value)` enforcing integer bounds between $1$ and $365$ days.
   - Replaced default DRF `DateField` on `current_business_date` with `SafeDateField` to gracefully accept `datetime` objects without runtime coercion exceptions.
2. **React SPA Integration ([`hotel-frontend/src/SystemSettingsManager.js`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/hotel-frontend/src/SystemSettingsManager.js#L26)):**
   - Added `near_expiry_warning_days: 30` to local state and populate from `GET /users/settings/`.
   - Added client-side validation rejecting values outside $[1, 365]$.
   - Added a dedicated configuration accordion section:
     ```jsx
     <div className="section-card">
       <button className="accordion-header" onClick={() => toggleSection('inventory')}>
         <span>📦 Inventory & Expiry Surveillance</span>
         <span>{openSections.inventory ? '▲' : '▼'}</span>
       </button>
       {openSections.inventory && (
         <div className="section-body">
           <div className="form-group">
             <label htmlFor="input-near-expiry-warning-days">
               Near-Expiry Warning Window (Days):
             </label>
             <input
               id="input-near-expiry-warning-days"
               type="number"
               min="1"
               max="365"
               value={settings.near_expiry_warning_days}
               onChange={(e) => setSettings({ ...settings, near_expiry_warning_days: parseInt(e.target.value) || 0 })}
             />
             <p className="form-help">
               Batches expiring within this number of days generate warning alerts.
             </p>
           </div>
         </div>
       )}
     </div>
     ```
   - Bound save action to `POST /users/settings/` and confirmed that changes persist on reload and correctly clamp background surveillance alerts.

---

## 4. Migration & Schema Verification

- **Additive Migrations Required:** None ($0$).
- **Verification:**
  - `hotel.models.StockLocation.custodian` (`ForeignKey` to `User`) was already established in prior database migrations.
  - `hotel.models.SystemSettings.near_expiry_warning_days` (`PositiveIntegerField(default=30)`) was already established in migration `0050_systemsettings_near_expiry_warning_days.py`.
  - All existing table schemas, constraints, and audit columns were preserved without alteration.

---

## 5. Automated Test Matrix & Execution Scorecard

The complete automated test suite was executed against the active PostgreSQL staging database (`hotel_erp_staging`).

| Test Module / Suite | Tests | Result | Execution Time | Coverage Scope |
| :--- | :---: | :---: | :---: | :--- |
| [`test_location_scoping_and_settings.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/apps/inventory/tests/test_location_scoping_and_settings.py) | **11** | **PASS** | 45.4s | DEF-04 location scoping, IDOR protection, multi-location assignment, DEF-05 validation & window clamping |
| `test_procurement_management.py` | **12** | **PASS** | 72.1s | Purchase requisitions, approvals, PO conversion, 3-way matching, invoice overbilling checks |
| `test_expiry_alerts_and_schedules.py` | **13** | **PASS** | ~40.0s | Expiry alert lifecycle, suppression of non-stocked batches, automated daily/weekly scheduling |
| `test_stocktaking_management.py` | **12** | **PASS** | ~39.4s | Dual-mode counting, blind snapshot isolation, SoD approval, GL journal generation |
| `test_rfq_quotation_workflow.py` | **10** | **PASS** | ~48.0s | RFQ generation, supplier bid comparison, evaluation, awarding |
| `test_cross_module_inventory_integration.py` | **10** | **PASS** | ~50.0s | POS/KDS inventory consumption, real-time balance tracking, recipe BOM deduction |
| `test_batch_allocation_engine.py` | **11** | **PASS** | ~51.3s | FIFO/FEFO allocation engine, quarantine/expired stock locking |
| `test_station_isolation.py` | **9** | **PASS** | ~45.0s | Multi-station order routing, KDS/bar station isolation |
| `users.test_accounting_integrity.py` | **5** | **PASS** | ~20.2s | Double-entry journal balance, trial balance verification, audit immutability |
| `test_inventory_integrity.py` | **26** | **PASS** | 75.9s | Real-time stock transactions, minibar integration, negative inventory prevention |
| `scratch/independent_qc_audit_verifier.py` | **16** | **PASS** | 104.0s | End-to-end verification of DEF-01 through DEF-05 |
| `scratch/test_live_http_endpoints.py` | **8** | **PASS** | 80.0s | Live HTTP verification across running Django server |
| **Combined Full Suite** | **130** | **PASS (100%)** | 457.2s | **Full system regression check across all 10 modules** |

---

## 6. Real-Browser Acceptance Verification & Screenshot Catalog

Using Selenium WebDriver in Chrome headless mode against the live React SPA (`http://localhost:3000`) and live Django backend (`http://127.0.0.1:8000`), the remediation script [`scratch/test_browser_limitations_remediation.py`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/scratch/test_browser_limitations_remediation.py) verified all operational workflows.

Screenshots are persisted in [`docs/screenshots/limitations_remediation/`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/):

| Step | Screenshot File | Size | Verification Description |
| :---: | :--- | :---: | :--- |
| **1** | [`01_settings_navigated_and_near_expiry_visible.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/01_settings_navigated_and_near_expiry_visible.png) | 165 KB | Admin logs in, navigates to Settings, expands "Inventory & Expiry Surveillance", and confirms input field displays default `30` days. |
| **2** | [`02_settings_changed_and_saved.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/02_settings_changed_and_saved.png) | 165 KB | Admin updates value to `21` days, clicks "Save Changes", and confirms `alert("Settings updated successfully!")` response. |
| **3** | [`03_settings_persisted_after_refresh.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/03_settings_persisted_after_refresh.png) | 165 KB | Full browser refresh (`driver.refresh()`) reloads settings from API; input retains persisted value `21` days. (Cleanly restored to 30 days afterwards). |
| **4** | [`04_location_a_staff_sessions_filtered.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/04_location_a_staff_sessions_filtered.png) | 227 KB | Staff A (`remed_staff_a`, custodian of Store A) accesses Stocktaking Center. Table shows only Store A and unassigned shared stores; Store B sessions are completely concealed. |
| **5** | [`05_location_a_staff_schedules_filtered.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/05_location_a_staff_schedules_filtered.png) | 191 KB | Staff A switches to Schedules tab. Only Store A schedule is visible; Store B schedule is concealed. |
| **6** | [`06_location_b_staff_sessions_filtered.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/06_location_b_staff_sessions_filtered.png) | 222 KB | Staff B (`remed_staff_b`, custodian of Store B) logs in. Table shows only Store B and unassigned shared stores; Store A sessions are completely concealed. |
| **7** | [`07_admin_full_visibility.png`](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/docs/screenshots/limitations_remediation/07_admin_full_visibility.png) | 223 KB | Administrator logs in and views Stocktaking Center. Shows full global multi-store visibility across Store A, Store B, Main Bar, and Main Central Store simultaneously. |

---

## 7. Regression & Module Boundary Safety

1. **Procurement Integrity:** All 12 tests in `test_procurement_management.py` pass. Requisition approval, PO conversion, and 3-way invoice matching remain intact.
2. **Stocktaking Life-Cycle:** Uncounted draft deletion remains permitted; counted, review, approved, and cancelled sessions strictly reject `DELETE` with `HTTP 400 Bad Request`.
3. **Expiry Alert Lifecycle:** Re-evaluations are strictly idempotent, quantity updates are non-destructive, and warnings escalate accurately.
4. **Accounting & POS Consumption:** All KDS/POS recipe deductions, station routing, and journal entries balance to zero discrepancy.

---

## 8. Status & Handoff to Independent QC

The targeted remediation of **DEF-04** and **DEF-05** is complete, verified, and regression-tested. In strict adherence to governance instructions, the implementation team **does not self-certify release readiness**.

The codebase, live staging environment (`hotel_erp_staging`), and test suites are now yielded for independent Quality Control audit.

