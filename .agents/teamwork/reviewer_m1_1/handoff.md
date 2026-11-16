# Milestone 1 Independent Review & Adversarial Audit Report

**Reviewer:** Reviewer M1-1 (Archetype: Reviewer & Adversarial Critic)  
**State Folder:** `.agents/teamwork/reviewer_m1_1/`  
**Target Milestone:** Milestone 1 — Targeted RBAC Architecture & Frontend Corrections (DEF-01 through DEF-06)  
**Subject Under Review:** Implementation by Worker M1 (`.agents/teamwork/worker_m1/handoff.md`)  
**Date:** 2026-11-09  
**Verdict:** **APPROVE**

---

## 1. Observation

Direct empirical evidence was gathered across backend models, migrations, views, permissions, frontend React components, and test runners:

### DEF-01: Authoritative Role Formalization & Validation
- **`users/models.py:19, 33`**:
  `HOTEL_MANAGER = "hotel_manager"` added to model constants and `ROLE_CHOICES` includes `(HOTEL_MANAGER, "Hotel Manager")`.
- **`users/admin.py:47, 56`**:
  Badge mappings updated with `User.HOTEL_MANAGER: "primary"` and `User.HOUSEKEEPING: "info"`.
- **`users/migrations/0009_alter_user_role.py`**:
  Applied migration 0009 cleanly (`showmigrations users` confirms `[X] 0009_alter_user_role`).
- **`u.full_clean()` validation**:
  Direct execution of `u.full_clean()` on existing staging users:
  - User 12 (`manager_proc2`): Validated cleanly with role `hotel_manager`.
  - User 16 (`sec_ops_manager`): Validated cleanly with role `hotel_manager`.
- **`UserSerializer` validation**:
  `UserSerializer(data={'username':'hm_test','email':'hm_test@example.com','role':'hotel_manager'})` validated with `is_valid() == True` and zero validation errors.

### DEF-02: Hotel Manager Operational Dashboard & Admin Privilege Isolation
- **`hotel-frontend/src/App.js:612`**:
  `case 'hotel_manager':` routes directly to `<DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />`.
- **`hotel-frontend/src/App.js:514-518`**:
  Header displays `"Hotel Operations Overview"` when `userData?.role === 'hotel_manager'`.
- **`hotel-frontend/src/Sidebar.js:213`**:
  `if (userRole === 'hotel_manager' && ['users', 'settings'].includes(item.id)) return false;`
  Because the `ADMIN` group only contains `users` and `settings`, the entire `ADMIN` navigation menu is hidden for hotel managers.
- **`hotel-frontend/src/App.js:424-426, 542-543`**:
  Defensive route guards reset `activeTab` to `'dashboard'` if a hotel manager attempts to access `'users'` or `'settings'`. `<UserManager />` and `<SystemSettingsManager />` will not render for `hotel_manager`.
- **`apps/orders/views.py:40-41` (`DashboardStatsView`)**:
  `permission_classes = [IsHotelManagerOrAdmin]` authorizes `hotel_manager` alongside `admin` and superusers.
- **`apps/orders/views.py:1497` (`AdminOrdersView`)**:
  `if request.user.role not in ["admin", "finance", "hotel_manager"] and not request.user.is_superuser:` allows hotel managers to query the operational orders queue.
- **Technical Isolation Verification**:
  - `GET /users/users/` with `hotel_manager` authentication returned **`HTTP 403 Forbidden`** (`authorization_denied`).
  - `POST /users/settings/` with `hotel_manager` authentication returned **`HTTP 403 Forbidden`** (`Only admins can modify system settings.`).

### DEF-03: Dining & Operational Supervisor Checks Normalization
- In `apps/orders/views.py`:
  - Line 418 (`MarkOrderServedView`): `is_supervisor = request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser`
  - Line 503 (`MarkOrderItemServedView`): `is_supervisor = request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser`
  - Line 581 (`BulkMarkOrderItemsServedView`): `is_supervisor = request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser`
  - Line 665 (`RequestBillView`): `if request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser:`
  - Line 802 (`RecordCashHandoverView`): `if request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser:`
- In `apps/reporting/views.py:735` (`OperationsTimingReportView`):
  Authorized roles include `"hotel_manager"`, allowing kitchen/bar performance timing reports to load.
- In `users/permissions.py:150` (`IsWaiterOrAdmin`):
  Permission check explicitly permits `getattr(user, "role", "") in {"admin", "hotel_manager", "waiter"}`.
- In `apps/orders/tests/test_bill_request_handover.py:24, 164-168`:
  Manager fixture updated to `role=User.HOTEL_MANAGER`, verified supervisory bill requests return `HTTP 200 OK` and transition order status to `"bill_requested"`.

### DEF-04: Inventory User Frontend Navigation & Sub-Desk Access
- **`hotel-frontend/src/App.js:614-615`**:
  `case 'inventory':` routes to `<DashboardLayout activeTab={activeTab || 'inventory'} ... />`.
- **`hotel-frontend/src/App.js:525-533`**:
  Renders `InventoryDashboard`, `StocktakeCenter`, and `ProcurementCenter` (supporting all 6 sub-desks via `procurement_<section>`).
- **`hotel-frontend/src/Sidebar.js:178-182, 214`**:
  `inventory` users are strictly restricted to `['inventory', 'stocktaking', 'procurement', 'all_reports']`.
  Under `procurement`, all 6 child desks (`requisitions`, `rfqs`, `quotations`, `awards`, `receiving`, `invoices`) are visible.
  Under `all_reports`, only `report_inventory` is visible. Front office, F&B, finance, users, and settings are hidden.

### DEF-05: Single-Hotel Global Stock Permissions, Unassigned Fallback Removal, SoD & Immutability
- **`users/permissions.py:224-255` (`HasStocktakeLocationPermission`)**:
  - `has_permission`: Strictly permits `user.is_superuser or getattr(user, "role", "") in {"admin", "inventory", "hotel_manager"}`.
  - `has_object_permission`: Grants global property-wide access to `{"admin", "hotel_manager", "inventory"}`.
  - Dangerous fallback `if location and location.custodian is None: return True` has been completely eliminated.
- **`apps/inventory/views.py:1275, 1495`**:
  Querysets for `StocktakeSessionViewSet` and `StocktakeScheduleViewSet` grant global access to `{"admin", "hotel_manager", "inventory"}` and superusers, while removing `| Q(location__custodian__isnull=True)`.
- **`apps/inventory/views.py:175, 522`**:
  `StockTransactionViewSet.reverse` and `InventoryWasteRecordViewSet.reverse` authorize `hotel_manager` alongside `admin` and `inventory`.
- **Separation of Duties (SoD)**:
  `hotel/stocktaking.py:414-416` enforces `session.counted_by != supervisor`. Attempting self-approval raises `PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")`.
- **Immutability Protection**:
  `StocktakeSessionViewSet.destroy` blocks deletion of non-draft sessions with `HTTP 400 Bad Request`. `StockTransactionViewSet.destroy` and `InventoryWasteRecordViewSet.destroy` return `HTTP 405 Method Not Allowed`.

### DEF-06: External Supplier Architecture Preservation
- Direct DB query confirmed external supplier accounts `sec_supplier_alpha` (ID 21) and `sec_supplier_beta` (ID 22) retain `role = "customer"`.
- Master `Supplier` records remain independent entities, and `SupplierQuotation` models reference `Supplier` without bloating `User.ROLE_CHOICES`.

### Test Suite Execution
- **Automated Django Test Command**:
  `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows --keepdb`
  - Output: `Ran 17 tests in 209.070s - OK`
  - Total discovered: 17, Executed: 17, Passed: 17, Failed: 0, Errors: 0, Skipped: 0.
- **Automated Frontend Unit Tests**:
  `npm --prefix hotel-frontend test -- --watchAll=false src/apiClient.test.js`
  - Output: `Test Suites: 1 passed, 1 total; Tests: 12 passed, 12 total`

---

## 2. Logic Chain

1. **Evidence of Correctness**:
   - Step 1: Formalizing `HOTEL_MANAGER = "hotel_manager"` in `users/models.py` and applying migration 0009 resolved the `ValidationError` on `u.full_clean()` for users 12 and 16.
   - Step 2: Routing `hotel_manager` and `inventory` to `DashboardLayout` in `App.js` resolved the blank/unauthorized screen.
   - Step 3: Filtering `users` and `settings` in `Sidebar.js` and adding route guards in `App.js` ensured that `hotel_manager` and `inventory` cannot view or access technical administration screens.
   - Step 4: Normalizing procedural `"manager"` checks to authoritative `"hotel_manager"` across the 5 order views, `IsWaiterOrAdmin`, and reporting restored supervisory authority.
   - Step 5: Removing `location.custodian is None` from `HasStocktakeLocationPermission` and `apps/inventory/views.py` closed the departmental privilege escalation vulnerability.

2. **Adversarial Stress Testing & Counter-Examples**:
   - *Attack 1 (Departmental Bypass on Unassigned Locations)*: Created an unassigned stock location (`custodian = None`). Tested `waiter`, `kitchen`, `bar`, `cashier`, `reception`, and `housekeeping` via `HasStocktakeLocationPermission`. Result: 100% blocked (`has_permission=False`, `has_object_permission=False`).
   - *Attack 2 (Hotel Manager Privilege Escalation)*: Authenticated as `hotel_manager` and attempted to query `/users/users/` and POST to `/users/settings/`. Result: Both returned `HTTP 403 Forbidden`.
   - *Attack 3 (Separation of Duties Bypass)*: Assigned a stocktake count to `hotel_manager` and attempted self-approval via `approve_stocktake_session`. Result: Blocked with `PermissionDenied` ("Separation of duties violation").
   - *Attack 4 (Audit Trail Destructive Deletion)*: Attempted `destroy()` on an active stocktake session. Result: Blocked with `HTTP 400 Bad Request`.

3. **Integrity Audit**:
   - Checked source code diffs for hardcoded returns, mocked test results, facade logic, or unauthorized skips. Zero integrity violations detected.

---

## 3. Caveats

- **Out-of-Order Standalone Script Imports**: Directly importing sub-serializers (e.g. `apps.identity.serializers` or `apps.inventory.serializers`) in a standalone python script without importing `users.serializers` first can trigger circular import warnings due to legacy export re-exports in `users/serializers.py`. This does not affect normal Django runtime execution where app initialization is managed by Django's app registry.
- **Browser Acceptance Verification**: Real-browser Selenium acceptance across all 9 roles and screenshots are scheduled for Milestone 3 per `PROJECT.md`.

---

## 4. Conclusion

The implementation of Milestone 1 (DEF-01 through DEF-06) satisfies all functional requirements, security constraints, and interface contracts specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`. No regressions, authorization loopholes, or integrity violations were observed.

**Verdict**: **APPROVE**

---

## 5. Verification Method

To independently reproduce and verify this review verdict:

1. **Verify Django Validation & Account Integrity**:
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); u12 = User.objects.get(id=12); u12.full_clean(); u16 = User.objects.get(id=16); u16.full_clean(); print('Users 12 & 16 full_clean OK')"
   ```

2. **Execute Automated Django Test Suite**:
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows --keepdb
   ```

3. **Execute Frontend Test Suite**:
   ```powershell
   npm --prefix hotel-frontend test -- --watchAll=false src/apiClient.test.js
   ```

4. **Execute Adversarial Stress Test Suite**:
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); import users.serializers; from django.contrib.auth import get_user_model; from rest_framework.test import APIRequestFactory, APIClient; from django.core.exceptions import PermissionDenied; from hotel.models import StockLocation, StocktakeSession; from users.permissions import HasStocktakeLocationPermission; from hotel.stocktaking import approve_stocktake_session; User = get_user_model(); factory = APIRequestFactory(); perm = HasStocktakeLocationPermission(); req = factory.get('/'); loc, _ = StockLocation.objects.get_or_create(name='Unassigned Test Loc', defaults={'location_type': 'warehouse'}); loc.custodian = None; loc.save(); session = StocktakeSession(location=loc, title='Dummy'); req.user = User.objects.filter(role='waiter').first(); assert not perm.has_permission(req, None); hm = User.objects.filter(role='hotel_manager').first(); client = APIClient(); client.force_authenticate(user=hm); assert client.get('/users/users/').status_code == 403; assert client.post('/users/settings/', {}).status_code == 403; print('Adversarial Stress Test OK')"
   ```
