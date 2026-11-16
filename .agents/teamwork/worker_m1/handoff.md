# Milestone 1 Handoff Report: Targeted RBAC Architecture & Frontend Corrections

**State Folder:** `.agents/teamwork/worker_m1/`  
**Milestone:** M1 — Targeted RBAC Architecture & Frontend Corrections (DEF-01 through DEF-06)  
**Author:** worker_m1 (RBAC and Frontend Implementation Worker)  
**Date:** 2026-11-09  

---

## 1. Observation

Prior to this work, empirical inspection identified six core RBAC and architectural discrepancies:

1. **DEF-01 (`users/models.py`, `users/admin.py`):**
   - In `users/models.py:30-42`, `User.ROLE_CHOICES` lacked `HOTEL_MANAGER = "hotel_manager"`.
   - Running `u.full_clean()` on existing staging users (ID 12: `manager_proc2`, ID 16: `sec_ops_manager`) resulted in:
     `django.core.exceptions.ValidationError: {'role': ["Value 'hotel_manager' is not a valid choice."]}`
   - `users/admin.py:43-57` omitted badge color mapping for `hotel_manager` and `housekeeping`.

2. **DEF-02 (`hotel-frontend/src/App.js`, `hotel-frontend/src/Sidebar.js`, `hotel-frontend/src/UserManager.jsx`, `apps/orders/views.py`):**
   - In `hotel-frontend/src/App.js:588-610`, `switch (role)` omitted `case 'hotel_manager':`, causing hotel managers to fall through to `default:` and render an unauthorized blank screen: `<h1>Unauthorized</h1>`.
   - In `hotel-frontend/src/Sidebar.js:207`, technical superuser administration controls (`users` and `settings`) were exposed to non-superuser manager accounts unless specifically filtered.
   - In `apps/orders/views.py:40`, `DashboardStatsView` enforced `permission_classes = [IsHotelAdmin]`, returning HTTP 403 Forbidden to hotel manager users.
   - In `apps/orders/views.py:1497`, `AdminOrdersView` restricted order browsing to `["admin", "finance"]`, blocking hotel managers.
   - In `hotel-frontend/src/UserManager.jsx:175-211`, `getAvailableRoles()` omitted `'Hotel Manager'`.

3. **DEF-03 (`apps/orders/views.py`, `apps/reporting/views.py`, `users/permissions.py`, `apps/orders/tests/test_bill_request_handover.py`):**
   - `apps/orders/views.py` contained procedural role checks expecting string `"manager"` instead of authoritative `"hotel_manager"`:
     - Line 418 (`MarkOrderServedView`)
     - Line 503 (`MarkOrderItemServedView`)
     - Line 581 (`BulkMarkOrderItemsServedView`)
     - Line 665 (`RequestBillView`)
     - Line 802 (`RecordCashHandoverView`)
   - `apps/reporting/views.py:735` (`OperationsTimingReportView.get`) checked `request.user.role in ["admin", "manager", "kitchen", "bar", "finance"]`, returning HTTP 403 Forbidden to hotel managers.
   - `users/permissions.py:135` (`IsWaiterOrAdmin`) checked `user.role in {"admin", "waiter"}`, returning `False` for hotel managers attempting dining floor supervisory actions.
   - `apps/orders/tests/test_bill_request_handover.py:24` created a test user with non-existent `role="manager"`.

4. **DEF-04 (`hotel-frontend/src/App.js`, `hotel-frontend/src/Sidebar.js`):**
   - In `hotel-frontend/src/App.js:602`, `case 'inventory':` routed directly to isolated `<InventoryDashboard />` without `DashboardLayout` or `Sidebar.js`.
   - As observed in `InventoryDashboard.js`, there were 0 links or components for `StocktakeCenter` or `ProcurementCenter`. Physical stocktaking and all 6 procurement sub-desks existed solely within `DashboardLayout`, which was inaccessible to `inventory` staff unless given `admin`.

5. **DEF-05 (`users/permissions.py`, `apps/inventory/views.py`):**
   - In `users/permissions.py:243` (`HasStocktakeLocationPermission.has_object_permission`), line 243 had:
     `if location and location.custodian is None: return True`
   - In `apps/inventory/views.py:1282, 1502` (`StocktakeSessionViewSet.get_queryset` and `StocktakeScheduleViewSet.get_queryset`), queries included `| Q(location__custodian__isnull=True)`.
   - In `apps/inventory/views.py:175, 522` (`StockTransactionViewSet.reverse` and `InventoryWasteRecordViewSet.reverse`), reversal was restricted to `("admin", "inventory")`, excluding `hotel_manager`.

6. **DEF-06 (`hotel/models.py`, `hotel/procurement.py`):**
   - Active staging database inspection confirmed external supplier accounts `sec_supplier_alpha` (ID 21) and `sec_supplier_beta` (ID 22) hold `role = "customer"`.
   - Master entity `hotel.models.Supplier` holds independent business data and has no Foreign Key to `User`.
   - `hotel.models.SupplierQuotation` references `Supplier` (`models.ForeignKey(Supplier, on_delete=models.PROTECT)`).

---

## 2. Logic Chain

1. **DEF-01 Resolution:**
   - Adding `HOTEL_MANAGER = "hotel_manager"` to constants and `ROLE_CHOICES` in `users/models.py` enables DRF `UserSerializer` and Django model validation to recognize the role.
   - Adding `User.HOTEL_MANAGER: "primary"` and `User.HOUSEKEEPING: "info"` to `CustomUserAdmin.display_role` restores proper admin badge presentation.
   - Generating `users/migrations/0009_alter_user_role.py` and applying it to the database updates Django migration state without modifying the underlying Postgres `varchar(20)` column type or affecting existing user rows.
   - Running `u.full_clean()` on user 12 and user 16 confirmed 0 validation errors.

2. **DEF-02 Resolution:**
   - In `hotel-frontend/src/App.js`, adding `case 'hotel_manager':` to `switch (role)` directs hotel managers into `<DashboardLayout />`.
   - In `DashboardLayout`, setting the page title to `'Hotel Operations Overview'` when `user.role === 'hotel_manager'` provides clear operational context.
   - Filtering out `users` and `settings` in `Sidebar.js` for `hotel_manager` suppresses technical administrative items, causing the entire `ADMIN` navigation section to hide cleanly.
   - Creating `IsHotelManagerOrAdmin` in `users/permissions.py` and assigning it to `DashboardStatsView` in `apps/orders/views.py`, while extending `AdminOrdersView` to allow `["admin", "finance", "hotel_manager"]`, grants hotel managers full operational access to dashboard statistics and order queues while keeping user administration locked to superusers/admins.
   - In `hotel-frontend/src/UserManager.jsx`, adding `'Hotel Manager'` to `getAvailableRoles()`, normalizing submission values, and styling badges allows admins to manage hotel managers properly.

3. **DEF-03 Resolution:**
   - Replacing `"manager"` with `"hotel_manager"` in `MarkOrderServedView`, `MarkOrderItemServedView`, `BulkMarkOrderItemsServedView`, `RequestBillView`, and `RecordCashHandoverView` inside `apps/orders/views.py` restores supervisory authority for serving food, requesting bills, and recording cash handover.
   - Updating `apps/reporting/views.py:735` to allow `"hotel_manager"` permits the hotel manager to inspect kitchen and bar service timing metrics.
   - Extending `IsWaiterOrAdmin` in `users/permissions.py` to `{"admin", "hotel_manager", "waiter"}` ensures DRF permission checks pass.
   - Updating `apps/orders/tests/test_bill_request_handover.py` replaces `role="manager"` with `User.HOTEL_MANAGER` and adds assertions confirming the hotel manager can supervisory request bills.

4. **DEF-04 Resolution:**
   - In `hotel-frontend/src/App.js`, routing `case 'inventory':` to `<DashboardLayout activeTab={activeTab || 'inventory'} ... />` embeds inventory staff into the layout containing `StocktakeCenter` and `ProcurementCenter`.
   - In `Sidebar.js`, restricting items visible to `inventory` staff strictly to `['inventory', 'stocktaking', 'procurement', 'all_reports']` (with only child `report_inventory`) ensures inventory users can access inventory control, physical stocktaking, and all 6 procurement desks (requisitions, rfqs, vendor bids, awards, receiving, 3-way matching), while hiding front office, F&B, finance, users, and settings.

5. **DEF-05 Resolution:**
   - Under single-hotel global stock permissions, inventory staff manage stock hotel-wide across all locations.
   - In `users/permissions.py:226`, `HasStocktakeLocationPermission.has_object_permission` was updated to grant property-wide global access to `{"admin", "hotel_manager", "inventory"}` and superusers.
   - In `users/permissions.py:243`, the fallback `if location and location.custodian is None: return True` was removed. Departmental staff (`kitchen`, `bar`, `waiter`, `cashier`) fail `has_permission` immediately (returning HTTP 403 Forbidden).
   - In `apps/inventory/views.py:1275, 1496`, `StocktakeSessionViewSet.get_queryset` and `StocktakeScheduleViewSet.get_queryset` were updated to grant global queryset access to `{"admin", "hotel_manager", "inventory"}` and superusers, removing `| Q(location__custodian__isnull=True)`.
   - In `apps/inventory/views.py:175, 522`, `StockTransactionViewSet.reverse` and `InventoryWasteRecordViewSet.reverse` were updated to authorize `hotel_manager` alongside `admin` and `inventory`.

6. **DEF-06 Resolution:**
   - Supplier accounts `sec_supplier_alpha` and `sec_supplier_beta` remain classified with `role = "customer"`.
   - Model linkage from `SupplierQuotation` to `hotel.Supplier` is preserved without modifying schema or inflating role enums.

---

## 3. Caveats

1. **Pre-existing Work Tree:** The working tree contained numerous uncommitted files from previous phases. All Milestone 1 edits were strictly additive, surgical, and confined to the specified files of write ownership.
2. **Single-Hotel Operational Scope:** Single-hotel global stocktaking permissions grant property-wide access to all locations for inventory and hotel manager staff. Separation of stores for departmental operations is handled procedurally via stock locations.
3. **Database Test Concurrency:** Automated test execution on PostgreSQL was run with `--keepdb` against `test_hotel_erp_staging` to prevent interactive prompts.

---

## 4. Conclusion

Milestone 1 is complete. All 6 defect specifications (DEF-01 through DEF-06) have been implemented and verified:
- `hotel_manager` is formally established in models, choices, serializers, and Django Admin.
- `hotel_manager` and `inventory` routing and navigation in `App.js`, `Sidebar.js`, and `UserManager.jsx` are configured with appropriate role scoping and technical control guards.
- Dining and reporting supervisor checks authorize `hotel_manager`.
- Single-hotel global stocktaking permissions are active and the unassigned location security bypass is completely eliminated.
- External supplier identity architecture is verified stable with `role = "customer"`.
- Automated test suites ran with 100% pass rates (17/17 Django tests + 12/12 React unit tests).

---

## 5. Verification Method

To independently verify Milestone 1 implementation:

1. **Verify Model Validation on Hotel Manager Accounts:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); u12 = User.objects.get(id=12); u12.full_clean(); u16 = User.objects.get(id=16); u16.full_clean(); print('Users 12 & 16 full_clean OK')"
   ```
   *Expected Output:* `Users 12 & 16 full_clean OK`

2. **Verify Serializer Validation:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.serializers import UserSerializer; s = UserSerializer(data={'username':'hm_test','email':'hm_test@example.com','role':'hotel_manager'}); assert s.is_valid(), s.errors; print('Serializer valid OK')"
   ```
   *Expected Output:* `Serializer valid OK`

3. **Verify DashboardStatsView & AdminOrdersView for Hotel Manager:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from rest_framework.test import APIClient; from django.contrib.auth import get_user_model; u = get_user_model().objects.get(id=12); client = APIClient(); client.force_authenticate(user=u); r1 = client.get('/users/dashboard-stats/'); assert r1.status_code == 200, r1.status_code; r2 = client.get('/users/orders/'); assert r2.status_code == 200, r2.status_code; r3 = client.get('/users/reports/operations-timing/'); assert r3.status_code == 200, r3.status_code; print('All Hotel Manager API endpoints return HTTP 200 OK')"
   ```
   *Expected Output:* `All Hotel Manager API endpoints return HTTP 200 OK`

4. **Verify Single-Hotel Stocktaking Permissions:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.permissions import HasStocktakeLocationPermission; from django.contrib.auth import get_user_model; from rest_framework.test import APIRequestFactory; from hotel.models import StockLocation, StocktakeSession; User = get_user_model(); perm = HasStocktakeLocationPermission(); req = APIRequestFactory().get('/'); loc = StockLocation.objects.first(); session = StocktakeSession.objects.first() or StocktakeSession(location=loc); req.user = User.objects.get(id=12); assert perm.has_permission(req, None) and perm.has_object_permission(req, None, session); req.user = User.objects.filter(role='inventory').first(); assert perm.has_permission(req, None) and perm.has_object_permission(req, None, session); req.user = User.objects.filter(role='waiter').first(); assert not perm.has_permission(req, None); print('Stocktake permissions verified OK')"
   ```
   *Expected Output:* `Stocktake permissions verified OK`

5. **Execute Automated Verification Test Suites:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows --keepdb
   ```
   *Expected Output:* `Ran 17 tests ... OK`

6. **Execute Frontend Test Suite:**
   ```powershell
   cd hotel-frontend; npm test -- --watchAll=false src/apiClient.test.js
   ```
   *Expected Output:* `Test Suites: 1 passed, 1 total; Tests: 12 passed, 12 total`
