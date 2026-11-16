# AUDIT SPECIFICATION REPORT: RBAC ARCHITECTURE CORRECTIONS

**Audit Reference:** AUDIT-RBAC-ARCHITECTURE-2026-V1.0  
**Target Specification:** Acrma Hotel ERP Role, Permission, and Frontend Corrections  
**Author:** Audit Specification Miner (`survey_spec_miner`)  
**Date:** 2026-11-09  
**Branch:** `development` (Commit: `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`)  
**Deliverable Path:** `.agents/teamwork/survey_spec_miner/handoff.md`  

---

## 1. Observation

Direct empirical evidence gathered through read-only inspection of source code, database tables, and runtime probing:

### 1.1 DEF-01: Formalization of `hotel_manager` Role
* **Source Files:**
  * `users/models.py:22-44`: `User.ROLE_CHOICES` contains 11 choices (`admin`, `reception`, `waiter`, `cashier`, `kitchen`, `bar`, `inventory`, `delivery`, `housekeeping`, `finance`, `customer`). `HOTEL_MANAGER = "hotel_manager"` is absent from class constants and `ROLE_CHOICES`.
  * `users/admin.py:43-57`: `CustomUserAdmin.display_role` lacks label mappings for `hotel_manager` and `housekeeping`.
  * `apps/identity/serializers.py:38-89`: `UserSerializer` inherits `choices` validation from `User.role`.
* **Database State:**
  * Active staging database contains 2 active users with `role = "hotel_manager"`:
    * ID 12: `manager_proc2` (`is_active=True`, `is_staff=False`, `is_superuser=False`)
    * ID 16: `sec_ops_manager` (`is_active=True`, `is_staff=False`, `is_superuser=False`)
* **Verbatim Runtime Error (Model Validation):**
  * Command: `.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth import get_user_model; u = get_user_model().objects.get(id=12); u.full_clean()"`
  * Result: `django.core.exceptions.ValidationError: {'role': ["Value 'hotel_manager' is not a valid choice."]}`
* **Verbatim Runtime Error (Serializer Validation):**
  * Command: `.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); import users.serializers; s = users.serializers.UserSerializer(data={'username':'test_hm','email':'test_hm@example.com','role':'hotel_manager'}); print(s.is_valid(), s.errors)"`
  * Result: `False {'role': [ErrorDetail(string='"hotel_manager" is not a valid choice.', code='invalid_choice')]}`

### 1.2 DEF-02: Frontend Routing & Operational Dashboard for `hotel_manager`
* **Source Files:**
  * `hotel-frontend/src/App.js:588-610`: `switch (role)` explicitly maps `'admin'`, `'finance'`, `'waiter'`, `'cashier'`, `'kitchen'`, `'bar'`, `'reception'`, `'inventory'`, `'customer'`, and `'housekeeping'`. `hotel_manager` is completely omitted and falls into `default:`, returning `<div style={{ padding: '50px', textAlign: 'center' }}><h1>Unauthorized</h1><button onClick={handleLogout}>Back to Login</button></div>`.
  * `hotel-frontend/src/Sidebar.js:98-104, 207-209`: Sidebar includes an `ADMIN` section with `users` (`UserManager.jsx`) and `settings` (`SystemSettingsManager.js`).
  * `apps/orders/views.py:40-42`: `DashboardStatsView` enforces `permission_classes = [IsHotelAdmin]`.
  * `users/permissions.py:6-18`: `IsHotelAdmin` requires `(user.is_superuser or user.role == "admin")`.
* **Verbatim Runtime Error (Backend API Lockout):**
  * Command: `.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from rest_framework.test import APIClient; from django.contrib.auth import get_user_model; u = get_user_model().objects.get(id=12); client = APIClient(); client.force_authenticate(user=u); res = client.get('/users/dashboard-stats/'); print(res.status_code, res.data)"`
  * Result: `403 {'error': {'code': 'permission_denied', 'message': 'Hotel administrator access is required.', 'details': {'detail': ErrorDetail(string='Hotel administrator access is required.', code='permission_denied')}}}`

### 1.3 DEF-03: Supervisor Checks Across Dining and Order Workflows
* **Source Files:**
  * `apps/orders/views.py`:
    * Line 418 (`MarkOrderServedView`): `is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser`
    * Line 503 (`MarkOrderItemServedView`): `is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser`
    * Line 581 (`BulkMarkOrderItemsServedView`): `is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser`
    * Line 665 (`RequestBillView`): `if request.user.role in ["admin", "manager"] or request.user.is_superuser:`
    * Line 802 (`RecordCashHandoverView`): `if request.user.role in ["admin", "manager"] or request.user.is_superuser:`
  * `apps/reporting/views.py`:
    * Line 735 (`OperationsTimingReportView`): `if not (request.user.is_superuser or request.user.role in ["admin", "manager", "kitchen", "bar", "finance"]):`
  * `users/permissions.py:131-136`: `IsWaiterOrAdmin` checks `(user.is_superuser or user.role in {"admin", "waiter"})`.
* **Verbatim Runtime Error (Permission Layer Rejection):**
  * Command: `.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.permissions import IsWaiterOrAdmin; from django.contrib.auth import get_user_model; u = get_user_model().objects.get(id=12); from rest_framework.test import APIRequestFactory; req = APIRequestFactory().post('/dummy'); req.user = u; print(IsWaiterOrAdmin().has_permission(req, None))"`
  * Result: `False`
  * Command for Operations Timing Report: `.venv\Scripts\python.exe -c "... client.force_authenticate(user=u); res = client.get('/users/reports/operations-timing/'); print(res.status_code, res.data)"`
  * Result: `403 {'error': 'Access denied.'}`

### 1.4 DEF-04: Frontend Routing & Navigation Disconnect for `inventory` Role
* **Source Files:**
  * `hotel-frontend/src/App.js:602-603`: Role `inventory` routes directly to `<InventoryDashboard userData={user} handleLogout={handleLogout} />`.
  * `hotel-frontend/src/pages/InventoryDashboard.js:3500-3522`: Tabs only expose `['actions', 'batches', 'categories', 'items', 'ledger', 'overview', 'recipes', 'reports', 'suppliers', 'waste']`.
  * `hotel-frontend/src/App.js:509-516`: `StocktakeCenter` and `ProcurementCenter` are ONLY rendered inside `DashboardLayout`, which is restricted to `admin` and `finance`.
  * `hotel-frontend/src/Sidebar.js:54-69`: Sidebar contains `inventory`, `stocktaking`, and `procurement` (requisitions, rfqs, vendor bids, awards, receiving, 3-way matching), but `Sidebar` is never rendered for `inventory` users.

### 1.5 DEF-05: Single-Hotel Global Stock Permissions, SoD & Invalidation Protections
* **Source Files:**
  * `users/permissions.py:200-246`: `HasStocktakeLocationPermission.has_object_permission` allows `{"admin", "hotel_manager"}` and superuser globally, but restricts `inventory` staff to `location.custodian == user` or assigned schedules, falling back to line 243: `if location and location.custodian is None: return True`.
  * `apps/inventory/views.py:1274-1283, 1496-1504`: `StocktakeSessionViewSet` and `StocktakeScheduleViewSet` filter querysets with `Q(location__custodian=user) | ... | Q(location__custodian__isnull=True)`.
  * `apps/inventory/views.py:543-546`: `StockLocationViewSet` uses `IsInventoryManager` (`{"admin", "inventory", "hotel_manager"}`).
  * `hotel/stocktaking.py:414-435`: SoD enforcement blocks self-approval (`session.counted_by and supervisor.username == session.counted_by.username` raises `PermissionDenied`). Superuser emergency override requires explicit flag and 15+ char justification, logging an immutable `AuditEvent`.
  * `apps/inventory/views.py:1450-1480`: `StocktakeSessionViewSet.destroy()` blocks deletion of any counted, under-review, approved, or cancelled sessions with `HTTP 400 Bad Request`.
  * `hotel/integrity.py:530-585`: FEFO allocation enforces `expiry_date >= today` and orders by `expiry_date`, `received_date`, `id`. FIFO orders non-perishables by `received_date`, `id`.

### 1.6 DEF-06: External Supplier Identity Architecture Review
* **Database State:**
  * Users `sec_supplier_alpha` (ID 21) and `sec_supplier_beta` (ID 22) are assigned `role = "customer"`, `is_staff=False`, `is_superuser=False`.
* **Source Architecture:**
  * `hotel/models.py:884-905`: `Supplier` is an independent master entity (`name`, `phone`, `email`, `tin_number`). It does NOT have a foreign key to `User`.
  * `hotel/models.py:1762-1875`: `SupplierQuotation` references `Supplier` via `ForeignKey(Supplier, on_delete=models.PROTECT)`.
  * `apps/inventory/views.py:1117-1185`: `SupplierQuotationViewSet` has `permission_classes = [IsAuthenticated]`. Internal procurement officers (`proc_officer`, `inventory` role) create and record supplier quotations on behalf of vendors via `QuotationDesk.jsx`.
  * `hotel-frontend/src/pages/CustomerDashboard.jsx:1-120`: The customer dashboard is strictly a Public Booking Engine for guests. There is NO vendor bidding interface in `CustomerDashboard.jsx`.

---

## 2. Logic Chain

1. **DEF-01 Resolution Chain:**
   * Observation 1.1 shows `User.full_clean()` and `UserSerializer.is_valid()` fail because `hotel_manager` is omitted from `User.ROLE_CHOICES`.
   * Staging DB already contains 2 active accounts with `role="hotel_manager"`.
   * Adding `HOTEL_MANAGER = "hotel_manager"` and `(HOTEL_MANAGER, "Hotel Manager")` to `User.ROLE_CHOICES` in `users/models.py`, updating `CustomUserAdmin.display_role` in `users/admin.py`, and generating a non-destructive Django migration (`0009_alter_user_role.py`) fully validates existing accounts without renaming or deleting any user.

2. **DEF-02 Resolution Chain:**
   * Observation 1.2 shows that `hotel_manager` hits `Unauthorized` in React because `App.js` lacks `case 'hotel_manager':`.
   * Even when routed to `DashboardLayout`, `DashboardContent` requests `/users/dashboard-stats/`, which fails with HTTP 403 Forbidden because `DashboardStatsView` uses `IsHotelAdmin`.
   * Updating `App.js` to render `DashboardLayout` for `hotel_manager`, updating `Sidebar.js` to show operational modules while hiding technical admin controls (`users`, `settings`), and permitting `hotel_manager` on `DashboardStatsView` completely resolves the lockout while maintaining least privilege.

3. **DEF-03 Resolution Chain:**
   * Observation 1.3 shows that supervisor checks in `apps/orders/views.py` (lines 418, 503, 581, 665, 802) and `apps/reporting/views.py` (line 735) check `["admin", "manager"]`.
   * Furthermore, DRF blocks `hotel_manager` at the permission layer because `IsWaiterOrAdmin` only allows `{"admin", "waiter"}`.
   * Replacing `"manager"` with `"hotel_manager"` across all 6 views AND updating `IsWaiterOrAdmin` to recognize `hotel_manager` restores proper operational supervision across dining, bills, handovers, and kitchen/bar timing reports.

4. **DEF-04 Resolution Chain:**
   * Observation 1.4 shows that `inventory` staff are locked into `InventoryDashboard.js`, which does not import or render `StocktakeCenter` or `ProcurementCenter`.
   * `DashboardLayout` and `Sidebar.js` already have full component integrations for stocktaking and procurement.
   * Updating `App.js` to route `role === 'inventory'` to `DashboardLayout` (defaulting `activeTab` to `'inventory'`) and configuring `Sidebar.js` to display inventory, stocktaking, procurement, and inventory reports (while hiding front office, F&B, finance, users, and settings) gives inventory users full operational access without granting them `admin`.

5. **DEF-05 Resolution Chain:**
   * In a single-hotel ERP, inventory staff manage property-wide inventory across all storage rooms.
   * Currently, `inventory` staff are restricted by location custodian filters, falling back to `custodian IS NULL`. This fallback created a vulnerability where unauthorized staff could access unassigned stores.
   * Extending global stocktaking permissions to `{"admin", "hotel_manager", "inventory"}` and eliminating the `custodian IS NULL` fallback ensures single-hotel global access for authorized roles, while completely locking out departmental roles (`kitchen`, `bar`, `waiter`, `cashier`).
   * SoD (counted_by != approved_by), session deletion protection, and FIFO/FEFO batch allocation are confirmed intact and must remain strictly enforced.

6. **DEF-06 Resolution Chain:**
   * Observation 1.6 shows external supplier accounts (`sec_supplier_alpha`, `sec_supplier_beta`) are assigned `customer` role, and quotations reference `Supplier` master rows rather than user accounts.
   * The ERP has no external supplier login portal; bids are recorded by internal procurement staff.
   * Introducing a `supplier` role is unnecessary, adds architectural complexity, and risks regressions.
   * The safest resolution is to retain `customer` role for existing supplier users, maintain master `Supplier` record linking, and document the architecture in Section 9 of the final report.

---

## 3. Caveats

1. **Uncommitted Work Tree:** `git status` shows 44 modified files and numerous untracked files from prior milestones. All changes must be strictly additive and must preserve existing code. No resets, cleanups, or commits are permitted.
2. **Database Test Concurrency:** When executing Django tests via `manage.py test`, the flag `--keepdb` must be passed to prevent interactive prompts regarding the existing test database `test_hotel_erp_staging`.
3. **Single-Hotel Operational Scope:** Single-hotel global stock permissions apply property-wide. Physical store segregation between kitchen, bar, and general warehouse is managed operationally via locations, but inventory managers hold global oversight.

---

## 4. Conclusion

All 6 defect specifications (DEF-01 through DEF-06) and the final report structure have been thoroughly investigated, empirically verified, and formally mapped:
1. **DEF-01:** Formalize `HOTEL_MANAGER = "hotel_manager"` in `User.ROLE_CHOICES`, update `CustomUserAdmin`, generate `0009_alter_user_role.py`, preserve existing accounts.
2. **DEF-02:** Add `case 'hotel_manager':` in `App.js`, filter out technical controls in `Sidebar.js`, allow `hotel_manager` on `DashboardStatsView`.
3. **DEF-03:** Replace `["admin", "manager"]` with `["admin", "hotel_manager"]` across `apps/orders/views.py` (5 locations) and `apps/reporting/views.py` (1 location), update `IsWaiterOrAdmin` in `users/permissions.py`, update `apps/orders/tests/test_bill_request_handover.py`.
4. **DEF-04:** Route `inventory` users through `DashboardLayout` in `App.js`, set initial tab to `'inventory'`, filter `Sidebar.js` to expose inventory, stocktaking, procurement, and inventory reports without granting `admin`.
5. **DEF-05:** Grant `inventory` global stocktaking access alongside `admin` and `hotel_manager` in `HasStocktakeLocationPermission` and viewsets; delete `custodian IS NULL` fallback; maintain SoD, deletion protection, and FIFO/FEFO engines.
6. **DEF-06:** Keep `customer` role for existing supplier accounts, maintain master `Supplier` foreign keys, document findings without adding redundant roles.
7. **Deliverable:** Produce `docs/FINAL_RBAC_CORRECTION_REPORT.md` satisfying all 11 required sections.

---

## 5. Verification Method

To independently verify these specifications:
```powershell
# 1. Verify User model full_clean() & serializer validation
.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth import get_user_model; u = get_user_model().objects.get(id=12); u.full_clean(); print('User 12 clean OK')"

# 2. Verify DashboardStatsView authorization for hotel_manager
.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from rest_framework.test import APIClient; from django.contrib.auth import get_user_model; client = APIClient(); client.force_authenticate(user=get_user_model().objects.get(id=12)); res = client.get('/users/dashboard-stats/'); assert res.status_code == 200, res.status_code; print('Stats OK')"

# 3. Verify dining supervisor permissions for hotel_manager
.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.permissions import IsWaiterOrAdmin; from django.contrib.auth import get_user_model; from rest_framework.test import APIRequestFactory; req = APIRequestFactory().post('/'); req.user = get_user_model().objects.get(id=12); assert IsWaiterOrAdmin().has_permission(req, None); print('IsWaiterOrAdmin OK')"

# 4. Verify automated regression test suite
.venv\Scripts\python.exe manage.py test apps.identity.tests apps.inventory.tests apps.orders.tests users.test_milestone2_workflows users.test_phase3_integrity --keepdb

# 5. Verify real-browser Selenium acceptance for all 9 roles
.venv\Scripts\python.exe scratch\qc_browser_reproduction.py
```

---

## 6. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | RBAC Model | `User.ROLE_CHOICES` Formalization (DEF-01) | Add `HOTEL_MANAGER = "hotel_manager"` to model constants and choices | Valid role string `"hotel_manager"` | Serialized user with `role: "hotel_manager"` | `ValidationError: Value 'hotel_manager' is not a valid choice` when absent | `users/models.py:30-44`, DB inspection |
| 2 | Admin UI | `CustomUserAdmin.display_role` (DEF-01) | Add badge styling for `hotel_manager` and `housekeeping` | User object in Django Admin | Badge label in list display | Defaults to unstyled label | `users/admin.py:43-57` |
| 3 | Frontend Routing | `hotel_manager` Dashboard Routing (DEF-02) | Route `hotel_manager` to `DashboardLayout` in React SPA | Authenticated user session (`role: "hotel_manager"`) | Full operational dashboard with KPI cards | Blank screen with "Unauthorized" header | `hotel-frontend/src/App.js:588` |
| 4 | Frontend Navigation | Operational Sidebar Scoping (DEF-02) | Expose operational sections while hiding technical controls (`users`, `settings`) | `userRole === 'hotel_manager'` | Overview, Operations, Finance, Reports | Technical controls exposed to non-superuser | `hotel-frontend/src/Sidebar.js:207` |
| 5 | Backend API | Operational Dashboard Stats Authorization (DEF-02) | Permit `hotel_manager` on `DashboardStatsView` | GET `/users/dashboard-stats/` with Bearer token | KPI aggregate JSON (POS, rooms, inventory, finance) | `HTTP 403 Forbidden` (`IsHotelAdmin` block) | `apps/orders/views.py:40` |
| 6 | Dining RBAC | Mark Order Served Supervision (DEF-03) | Authorize `hotel_manager` to mark any order as served | POST `/users/orders/<id>/mark-served/` | `{"message": "Order marked as served!"}` | `HTTP 403 Forbidden` (non-supervisor block) | `apps/orders/views.py:418` |
| 7 | Dining RBAC | Mark Order Item Served Supervision (DEF-03) | Authorize `hotel_manager` to mark item served | POST `/users/orders/items/<id>/mark-served/` | `{"message": "Item marked as served."}` | `HTTP 403 Forbidden` | `apps/orders/views.py:503` |
| 8 | Dining RBAC | Bulk Mark Served Supervision (DEF-03) | Authorize `hotel_manager` to bulk serve items | POST `/users/orders/items/bulk-mark-served/` | `{"served_item_ids": [...]}` | `HTTP 403 Forbidden` | `apps/orders/views.py:581` |
| 9 | Dining RBAC | Request Bill Supervision (DEF-03) | Authorize `hotel_manager` to request bill | POST `/users/orders/<id>/request-bill/` | `{"message": "Bill requested successfully"}` | `HTTP 403 Forbidden` | `apps/orders/views.py:665` |
| 10 | Dining RBAC | Record Cash Handover Supervision (DEF-03) | Authorize `hotel_manager` to initiate cash handover | POST `/users/orders/<id>/record-cash-handover/` | `{"message": "Cash handover recorded"}` | `HTTP 403 Forbidden` | `apps/orders/views.py:802` |
| 11 | Reporting RBAC | Operations Timing Report Access (DEF-03) | Authorize `hotel_manager` to view KDS/BDS service timings | GET `/users/reports/operations-timing/` | Service timing metrics and trends | `HTTP 403 Forbidden` (`{"error": "Access denied."}`) | `apps/reporting/views.py:735` |
| 12 | Permission Class | `IsWaiterOrAdmin` Supervisor Expansion (DEF-03) | Include `hotel_manager` in allowed roles for waiter supervisor views | Authenticated DRF Request | Boolean permission grant | `HTTP 403 Forbidden` | `users/permissions.py:131` |
| 13 | Frontend Routing | Inventory Role `DashboardLayout` Routing (DEF-04) | Route `inventory` staff to `DashboardLayout` with `'inventory'` active tab | User session with `role: "inventory"` | Integrated layout with Sidebar and tabs | Directly renders isolated `InventoryDashboard.js` | `hotel-frontend/src/App.js:602` |
| 14 | Frontend Navigation | Inventory Sidebar Navigation (DEF-04) | Show Inventory Control, Stocktake Center, Procurement, and Reports in Sidebar | `userRole === 'inventory'` | Navigation items for inventory modules | Modules inaccessible in UI without admin role | `hotel-frontend/src/Sidebar.js:207` |
| 15 | Stocktaking RBAC | Single-Hotel Global Stock Access (DEF-05) | Grant `admin`, superuser, `hotel_manager`, and `inventory` access to all stores | Stocktaking API requests across all location IDs | Unrestricted session/schedule querysets | `HTTP 404 / 403` for non-custodians | `users/permissions.py:226`, `apps/inventory/views.py:1275` |
| 16 | Stocktaking Security | Unassigned Store Fallback Removal (DEF-05) | Eliminate `custodian IS NULL` default-allow check | Request on unassigned location from departmental user | `HTTP 403 Forbidden` | Cross-store count tampering allowed | `users/permissions.py:243`, `apps/inventory/views.py:1282` |
| 17 | Stocktaking SoD | Separation of Duties Count Approval (DEF-05) | Prevent count submitter (`counted_by`) from approving session | POST `/users/stocktaking/sessions/<id>/approve/` | Status transitions to `approved` + GL post | `PermissionDenied: Separation of duties violation` | `hotel/stocktaking.py:414` |
| 18 | Audit Protection | Historical Audit Deletion Safeguard (DEF-05) | Block hard deletion on counted/approved sessions | DELETE `/users/stocktaking/sessions/<id>/` | Session deleted (drafts only) | `HTTP 400 Bad Request: Historical inventory audits cannot be deleted` | `apps/inventory/views.py:1450` |
| 19 | Inventory Integrity | FEFO & FIFO Batch Allocation Engine (DEF-05) | Perishable stock issued by earliest expiry; non-perishable by received date | Order fulfillment / transfer dispatch | Batches decremented by FEFO/FIFO order | `ValidationError: Insufficient valid stock` | `hotel/integrity.py:530` |
| 20 | Identity Arch | External Supplier Identity Handling (DEF-06) | Maintain `customer` role and link quotes directly to `Supplier` master | Vendor RFQ bid recording | Saved `SupplierQuotation` linked to `Supplier` | N/A (Existing flow verified safe) | `hotel/models.py:884`, `hotel/procurement.py:959` |

---

## 7. Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | User Model Validation | `User.objects.get(id=12).full_clean()` | Fails with `django.core.exceptions.ValidationError: {'role': ["Value 'hotel_manager' is not a valid choice."]}`. |
| 2 | UserSerializer Validation | `UserSerializer(data={"username": "hm_test", "role": "hotel_manager"})` | Fails with `{'role': [ErrorDetail(string='"hotel_manager" is not a valid choice.', code='invalid_choice')]}`. |
| 3 | Frontend Login Guard | Login as `manager_proc2` (`role: "hotel_manager"`) | Frontend `App.js` executes `switch (role)`: misses case and renders `<h1>Unauthorized</h1>`. |
| 4 | Operational Stats API | `GET /users/dashboard-stats/` as `manager_proc2` | Fails with `HTTP 403 Forbidden`: `{"error": {"code": "permission_denied", "message": "Hotel administrator access is required."}}`. |
| 5 | Dining Waiter Supervisor | `IsWaiterOrAdmin().has_permission(req, None)` as `manager_proc2` | Returns `False`; blocks `hotel_manager` from `MarkOrderServedView`, `RequestBillView`, and `RecordCashHandoverView`. |
| 6 | Operations Timing Report | `GET /users/reports/operations-timing/` as `manager_proc2` | Fails with `HTTP 403 Forbidden`: `{"error": "Access denied."}` due to check against `["admin", "manager", ...]`. |
| 7 | Inventory UI Routing | Login as `staging_controller` (`role: "inventory"`) | Renders `InventoryDashboard.js` directly; completely lacks links or tabs for `StocktakeCenter` or `ProcurementCenter`. |
| 8 | Stocktake SoD Violation | Counter `remed_staff_a` calls `approve` on session counted by `remed_staff_a` | Fails with `HTTP 403 Forbidden`: `Separation of duties violation: count submitters cannot approve their own stocktake.`. |
| 9 | Emergency Superuser SoD | Superuser attempts self-approval without 15+ char justification | Fails with `HTTP 400 Bad Request`: `A detailed justification (minimum 15 characters) is required for superuser emergency self-approval.`. |
| 10 | Stocktake Audit Deletion | `DELETE /users/stocktaking/sessions/<id>/` on session in `counted` status | Fails with `HTTP 400 Bad Request`: `Cannot delete stocktake session in 'counted' status. Historical inventory audits cannot be deleted.`. |
| 11 | Departmental Stocktake Access | `staging_chef` (`role: "kitchen"`) calls `GET /users/stocktaking/sessions/` | Fails with `HTTP 403 Forbidden` via `HasStocktakeLocationPermission`. |
| 12 | Expired Batch Allocation | Perishable item transfer with expired batch balance | FEFO engine excludes expired batch (`expiry_date >= today`) and raises `ValidationError: Insufficient valid stock`. |

---

## 8. Report Specifications for `docs/FINAL_RBAC_CORRECTION_REPORT.md`

The deliverable report must encompass all 11 required sections:

### Section 1: Initial State & Baseline Architecture
* Ground truth established from `AUDIT-RBAC-ARCHITECTURE-2026-V1.0`.
* User role distribution: 37 staging users across 11 roles (including 2 orphaned `hotel_manager` accounts and 2 external supplier `customer` accounts).
* Single-field role authorization architecture without Django `auth.Group` tables.

### Section 2: Defect Root Causes & Technical Problem Statements
* Detailed analysis of DEF-01 through DEF-06:
  * DEF-01: Missing `hotel_manager` in `ROLE_CHOICES`.
  * DEF-02: React switch lockout and `DashboardStatsView` `IsHotelAdmin` restriction.
  * DEF-03: `["admin", "manager"]` string mismatch and `IsWaiterOrAdmin` permission barrier.
  * DEF-04: Overlooked `DashboardLayout` for `inventory` role causing stocktaking/procurement UI lockout.
  * DEF-05: Inappropriate multi-property location scoping in single-hotel ERP and dangerous `custodian IS NULL` fallback.
  * DEF-06: Potential supplier role inflation versus safe master `Supplier` record linking.

### Section 3: Files Changed & Code Level Modifications
* Exhaustive list of affected files:
  * Backend: `users/models.py`, `users/admin.py`, `users/permissions.py`, `apps/orders/views.py`, `apps/reporting/views.py`, `apps/orders/tests/test_bill_request_handover.py`, `apps/inventory/views.py`.
  * Frontend: `hotel-frontend/src/App.js`, `hotel-frontend/src/Sidebar.js`.

### Section 4: Database Migrations Audit
* Documentation of `users/migrations/0009_alter_user_role.py`.
* Confirmation that PostgreSQL schema column definitions remain 100% unaltered (metadata update only).
* Non-destructive verification confirming zero changes to existing records.

### Section 5: Final Role-Permission Matrix
* Exhaustive matrix covering all 12 system roles (`superuser`, `admin`, `hotel_manager`, `finance`, `inventory`, `kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`).
* Clear demarcation of permissions across Overview, F&B/POS, Rooms/PMS, Inventory/Stocktake, Procurement, Finance/GL, Reports, and Admin Technical Controls.

### Section 6: Implementation Evidence
* Verbatim code diffs and architectural snippets demonstrating:
  * Model choices and admin badge formalization.
  * Frontend route guards and sidebar conditional visibility.
  * DRF permission classes and supervisor check normalization.
  * Global stock permissions and removal of unassigned fallback.

### Section 7: Reconciled Automated Test Results
* Complete test audit table without double counting:
  * Discovered tests
  * Executed tests
  * Passed tests
  * Failed tests
  * Skipped tests
  * Errored tests
* Suites: `apps/identity/tests/`, `apps/inventory/tests/`, `apps/orders/tests/`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`.

### Section 8: Real-Browser Selenium Acceptance Results with Screenshots
* Acceptance evidence for all 9 specified roles:
  1. Admin (`staging_admin`)
  2. Hotel Manager (`manager_proc2`)
  3. Inventory (`staging_controller`)
  4. Kitchen (`staging_chef`)
  5. Bar (`staging_bartender`)
  6. Waiter (`staging_waiter`)
  7. Cashier (`staging_cashier`)
  8. Reception (`staging_receptionist`)
  9. Housekeeping (`staging_housekeeper`)
* Explicit verification of dashboard loading, authorized module navigation, restricted module blocking, and zero fatal console/network errors.
* Paths to captured PNG screenshots in `docs/screenshots/`.

### Section 9: External Supplier Identity Architecture Review & Security Findings
* Architectural analysis of external supplier identity.
* Rationale for maintaining `customer` role and avoiding role inflation.
* Verification that `SupplierQuotation` linking to `hotel.Supplier` maintains clean isolation.

### Section 10: Limitations & Boundary Conditions
* Explicit documentation of single-hotel ERP boundaries.
* Procedural custodian assignment recommendations.
* Post-pilot recommendations for role specialization (storekeeper vs procurement buyer).

### Section 11: Final Integrity Verification & Git Status Audit
* Verification of `git status` confirming development branch integrity.
* Confirmation that no pre-existing uncommitted modifications were overwritten or deleted.
* Staging database sanity check confirming zero test data leakage into production records.
