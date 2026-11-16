# Backend Architecture Survey & Investigation Report
**Investigation Reference:** `SURVEY-BACKEND-RBAC-2026-V1.0`  
**Date:** 9 November 2026  
**Investigator:** survey_backend (Explorer Subagent)  
**Target Focus:** DEF-01, DEF-03, DEF-05, DEF-06, Automated Test Suites, Git Integrity  

---

## 1. Observation

### 1.1 Git Status & Workspace Integrity
Running `git status` revealed:
- **Modified tracked files (43):**
  - Backend services and views: `apps/finance/services.py`, `apps/inventory/models.py`, `apps/inventory/serializers.py`, `apps/inventory/urls.py`, `apps/inventory/views.py`, `apps/orders/serializers.py`, `apps/orders/services.py`, `apps/orders/urls.py`, `apps/orders/views.py`, `apps/reporting/urls.py`, `apps/reporting/views.py`, `apps/reservations/views.py`, `apps/rooms/urls.py`, `apps/rooms/views.py`, `core/settings.py`, `hotel/admin.py`, `hotel/integrity.py`, `hotel/inventory.py`, `hotel/models.py`, `users/models.py`, `users/permissions.py`, `users/views.py`.
  - Frontend components: `hotel-frontend/src/App.js`, `hotel-frontend/src/AuthPage.jsx`, `hotel-frontend/src/MenuManager.js`, `hotel-frontend/src/RoomManager.js`, `hotel-frontend/src/Sidebar.js`, `hotel-frontend/src/SystemSettingsManager.js`, `hotel-frontend/src/UserManager.jsx`, `hotel-frontend/src/apiClient.js`, `hotel-frontend/src/apiClient.test.js`, `hotel-frontend/src/apiConfig.js`, `hotel-frontend/src/pages/BarDashboard.js`, `hotel-frontend/src/pages/CashierDashboard.js`, `hotel-frontend/src/pages/InventoryDashboard.js`, `hotel-frontend/src/pages/KitchenDashboard.js`, `hotel-frontend/src/pages/OrdersManager.js`, `hotel-frontend/src/pages/ReportsCenter.js`, `hotel-frontend/src/pages/WaiterDashboard.js`.
  - Tests: `apps/inventory/tests/test_waste_management.py`, `apps/orders/tests/test_dining_sessions.py`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`.
- **Untracked files (53):** Included `users/migrations/0008_alter_user_role.py`, `hotel/migrations/0039_...` through `0050_...`, `hotel/procurement.py`, `hotel/stocktaking.py`, `hotel/transfers.py`, scratch audit scripts, and prior phase reports.
- **Integrity Result:** Zero reset, zero checkout, zero deletions, and zero commits performed during investigation.

### 1.2 DEF-01: User Model, Choices, Serializers, and Staging Database
1. **Model Choices in `users/models.py:30-42`:**
   ```python
   ROLE_CHOICES = [
       (ADMIN, "Admin"),
       (RECEPTION, "Reception"),
       (WAITER, "Waiter"),
       (CASHIER, "Cashier"),
       (KITCHEN, "Kitchen"),
       (BAR, "Bar"),
       (INVENTORY, "Inventory"),
       (DELIVERY, "Delivery (Deprecated)"),
       (HOUSEKEEPING, "Housekeeping"),
       (FINANCE, "Finance"),
       (CUSTOMER, "Customer"),
   ]
   ```
   `HOTEL_MANAGER = "hotel_manager"` is absent from `ROLE_CHOICES`.
2. **Staging Database Verification:**
   Query executed against `hotel_erp_staging` (PostgreSQL 16.12):
   - Total users: **37**
   - Role breakdown: `inventory`: 10, `admin`: 9, `cashier`: 3, `finance`: 3, `waiter`: 3, `kitchen`: 2, `hotel_manager`: 2, `customer`: 2, `bar`: 1, `housekeeping`: 1, `reception`: 1.
   - Specific `hotel_manager` accounts verified:
     - User ID 12: `manager_proc2` (`is_active=True`, `is_staff=False`, `is_superuser=False`)
     - User ID 16: `sec_ops_manager` (`is_active=True`, `is_staff=False`, `is_superuser=False`)
3. **Serializers & Admin Registration:**
   - `apps/identity/serializers.py:UserSerializer` (re-exported by `users/serializers.py:87`) uses `model = User` with field `"role"`. ModelSerializer enforces choices validation against `User.role.choices`.
   - `users/admin.py:43-57`: `CustomUserAdmin.display_role` label dictionary maps colors for 10 roles, omitting `hotel_manager` and `housekeeping`.

### 1.3 DEF-03: Inconsistent Supervisor Authorization Checks
1. **Procedural `["admin", "manager"]` checks in `apps/orders/views.py`:**
   - Line 418 (`MarkOrderServedView`):
     ```python
     is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser
     ```
   - Line 503 (`MarkOrderItemServedView`):
     ```python
     is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser
     ```
   - Line 581 (`BulkMarkOrderItemsServedView`):
     ```python
     is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser
     ```
   - Line 665 (`RequestBillView`):
     ```python
     if request.user.role in ["admin", "manager"] or request.user.is_superuser:
     ```
   - Line 802 (`RecordCashHandoverView`):
     ```python
     if request.user.role in ["admin", "manager"] or request.user.is_superuser:
     ```
2. **Procedural checks in `apps/reporting/views.py`:**
   - Line 735 (`OperationsTimingReportView.get`):
     ```python
     if not (request.user.is_superuser or request.user.role in ["admin", "manager", "kitchen", "bar", "finance"]):
     ```
3. **Procedural checks blocking Hotel Manager from Operational POS Views:**
   - `apps/orders/views.py:1497` (`AdminOrdersView` backing `/users/orders/`):
     ```python
     if request.user.role not in ["admin", "finance"] and not request.user.is_superuser:
         return Response({"error": "Forbidden: Admin or Finance role required."}, status=status.HTTP_403_FORBIDDEN)
     ```
   - `apps/orders/views.py:41` (`DashboardStatsView` backing `/users/dashboard-stats/`):
     Guarded by `permission_classes = [IsHotelAdmin]`, where `IsHotelAdmin` in `users/permissions.py:17` checks `(user.is_superuser or user.role == "admin")`.
   - `apps/orders/views.py:210` (`UpdateOrderStatusView`):
     Guarded by `permission_classes = [IsKitchenBarOrAdmin]`, which restricts to `admin`, `kitchen`, and `bar`.
4. **Test Suite Reference in `apps/orders/tests/test_bill_request_handover.py`:**
   - Lines 21-24: Creates test user `manager-btest` with `role="manager"`.
   - Line 153: `def test_admin_and_manager_supervisory_access(self):`

### 1.4 DEF-05: Inventory Scoping, Stocktake SoD, and Audit Protections
1. **Unassigned Store Fallback (`custodian IS NULL`):**
   - `apps/inventory/views.py:1275-1283` (`StocktakeSessionViewSet.get_queryset`):
     ```python
     if user and user.is_authenticated and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
         qs = qs.filter(
             Q(location__custodian=user)
             | Q(created_by=user)
             | Q(counted_by=user)
             | Q(schedule__assigned_staff=user)
             | Q(location__custodian__isnull=True)
         ).distinct()
     ```
   - `apps/inventory/views.py:1308-1315` (`StocktakeSessionViewSet.create`):
     ```python
     if user and not (user.is_superuser or getattr(user, "role", "") in {"admin", "hotel_manager"}):
         try:
             loc = StockLocation.objects.get(pk=location_id)
             if loc.custodian_id and loc.custodian_id != user.id:
                 return Response({"error": "You do not have permission to initiate stocktaking for this location."}, status=403)
     ```
     If `loc.custodian_id is None`, the check passes for any user with access.
   - `users/permissions.py:242-244` (`HasStocktakeLocationPermission.has_object_permission`):
     ```python
     # If location has no specific custodian assigned, general inventory staff are permitted
     if location and location.custodian is None:
         return True
     ```
2. **Separation of Duties (SoD) Protection:**
   - `hotel/stocktaking.py:414-435` (`approve_stocktake_session`):
     ```python
     if session.counted_by and supervisor.username == session.counted_by.username:
         if not (supervisor.is_superuser and emergency_self_approval):
             raise PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")
     ```
     Requires `emergency_self_approval=True` and justification $\ge 15$ characters, writing an immutable `AuditEvent`.
3. **Audit History Immutability:**
   - `apps/inventory/views.py:1449-1480` (`StocktakeSessionViewSet.destroy`):
     Strictly forbids deletion if session status is not `"draft"`, if `is_mode_locked` is true, if `counted_by` is set, or if item count entries exist. Returns `HTTP 400 Bad Request`.
   - `apps/inventory/views.py:170-171` (`StockTransactionViewSet.destroy`):
     Returns `HTTP 405 Method Not Allowed`: `{"error": "Stock history is immutable; reverse it instead."}`.
   - Reversal endpoints (`StockTransactionViewSet.reverse` line 175 and `InventoryWasteRecordViewSet.reverse` line 522) currently check `request.user.role not in ("admin", "inventory") and not request.user.is_superuser`, omitting `hotel_manager`.

### 1.5 DEF-06: External Supplier Authentication & Quotations
1. **Model Architecture:**
   - `Supplier` (`hotel/models.py:884-905`): Master vendor record (name, contact_person, phone, email, tin_number, supplied_categories). Has **no** foreign key to `User`.
   - `SupplierQuotation` (`hotel/models.py:1762-1889`): Tracks vendor quotations. References `supplier = ForeignKey(Supplier)` and `created_by = ForeignKey(User)`.
2. **User Classification:**
   - In staging DB, external supplier accounts `sec_supplier_alpha` (ID 21) and `sec_supplier_beta` (ID 22) hold `role = "customer"`.
   - `apps/identity/serializers.py:31` and `apps/identity/services.py:93`: Public user registration defaults `user.role = User.CUSTOMER`.
3. **Endpoint Access:**
   - `RequestForQuotationViewSet` (`apps/inventory/views.py:1021`) and `SupplierQuotationViewSet` (`apps/inventory/views.py:1117`) specify `permission_classes = [IsAuthenticated]`.
   - In `hotel/procurement.py:959` (`submit_supplier_quotation`), any authenticated user submitting on behalf of a supplier must provide a valid `supplier_id`. If the RFQ is restricted (`is_public_bidding=False`), it validates `rfq.invited_suppliers.filter(pk=supplier.id).exists()`.

### 1.6 Automated Test Suite Execution & Runner Findings
1. **Test Runner Architecture:**
   - **SQLite In-Memory Runner (`core.settings_test`):**
     - Invoked via `--settings=core.settings_test`.
     - Uses `DATABASES['default']['NAME'] = ':memory:'` and `core.test_runner.IsolatedRunner`.
     - Fast execution ($<3$ seconds for 11 workflow tests, 25 seconds for 160 inventory tests).
     - **Limitation:** In-memory SQLite does not support multi-threaded concurrent write connections; concurrent idempotency tests (`test_06` and `test_07` in `test_inventory_integrity.py`) raise `django.db.utils.OperationalError: database table is locked`.
   - **PostgreSQL Test Runner (`core.settings`):**
     - Invoked via `manage.py test <suite> --keepdb` (or `--noinput`).
     - Targets the dedicated PostgreSQL test database `test_hotel_erp_staging`.
     - Real PostgreSQL row-level locks and concurrent threads succeed completely (26/26 passed in `test_inventory_integrity.py`).
2. **Reconciled Test Results:**
   | Suite | Runner / DB | Discovered | Executed | Passed | Failed | Skipped | Errored | Time |
   |---|---|---|---|---|---|---|---|---|
   | `apps.identity.tests.test_auth_reliability` | SQLite (`settings_test`) | 5 | 5 | 5 | 0 | 0 | 0 | 1.37s |
   | `apps.orders.tests` (all 4 files) | PostgreSQL (`--keepdb`) | 64 | 64 | 64 | 0 | 0 | 0 | 494.40s |
   | `users.test_milestone2_workflows` + `users.test_phase3_integrity` | SQLite (`settings_test`) | 11 | 11 | 9 | 0 | 2 | 0 | 2.56s |
   | `apps.inventory.tests.test_rfq_quotation_workflow` | PostgreSQL (`--keepdb`) | 10 | 10 | 10 | 0 | 0 | 0 | 46.47s |
   | `apps.inventory.tests.test_inventory_integrity` | PostgreSQL (`--keepdb`) | 26 | 26 | 26 | 0 | 0 | 0 | 154.59s |
   | `apps.inventory.tests.test_stock_transfers` | PostgreSQL (`--keepdb`) | 11 | 11 | 9 | 2 | 0 | 0 | 50.38s |

---

## 2. Logic Chain

1. **Premise 1 (DEF-01):** The database already contains two active production/staging users with `role = "hotel_manager"`. However, `users/models.py` defines `ROLE_CHOICES` without `"hotel_manager"`. Any ModelForm or DRF serializer that validates `choices` on `User.role` will reject these existing accounts or prevent creating/updating them.
   - *Direct Support:* Observations 1.2.1 and 1.2.2.
2. **Premise 2 (DEF-03):** Supervisory permissions in dining sessions, order serving, bill requests, and cashier handovers in `apps/orders/views.py` verify `request.user.role in ["admin", "manager"]`. Because the system role is `"hotel_manager"` and not `"manager"`, a Hotel Manager is stripped of supervisory authority on all dining floors.
   - *Direct Support:* Observations 1.3.1 and 1.3.4.
3. **Premise 3 (Operational Exclusion):** In addition to the string mismatch, operational management endpoints such as `DashboardStatsView` (`apps/orders/views.py:41`) and `AdminOrdersView` (`apps/orders/views.py:1497`) restrict access to `IsHotelAdmin` or `["admin", "finance"]`. This inadvertently locks the `hotel_manager` out from viewing orders and dashboard metrics in the single-hotel ERP.
   - *Direct Support:* Observation 1.3.3.
4. **Premise 4 (DEF-05):** In `apps/inventory/views.py:1282, 1502` and `users/permissions.py:243`, the query filtering includes `| Q(location__custodian__isnull=True)`. In the staging database, multiple department stores (e.g. `STORE-MAIN`, `KITCHEN-MAIN`, `BAR-MAIN`) have `custodian = None`. Under the single-hotel global stock policy, `admin`, superuser, `hotel_manager`, and `inventory` staff must have global warehouse management access across all stores, while departmental users (`kitchen`, `bar`, `waiter`, `cashier`) must have zero general stocktake or warehouse access.
   - *Direct Support:* Observation 1.4.1.
5. **Premise 5 (DEF-06):** External vendors authenticate with `role = "customer"` because no separate `supplier` role exists in `ROLE_CHOICES`. The `Supplier` entity holds business data, while `SupplierQuotation` tracks bids submitted by the authenticated user (`created_by`). Altering existing supplier accounts or introducing new database roles is unnecessary and risky within the single-hotel RBAC policy; preserving `customer` for portal authentication is the safest approach.
   - *Direct Support:* Observation 1.5.1 and 1.5.2.
6. **Premise 6 (Test Reliability):** SQLite in-memory runner (`core.settings_test`) is suitable for rapid unit and serializer testing, but multi-threaded concurrency tests require PostgreSQL (`--keepdb`).
   - *Direct Support:* Observations 1.6.1 and 1.6.2.

---

## 3. Caveats

- **Caveat 1:** In `apps/inventory/tests/test_stock_transfers.py`, 2 failures occurred (`test_10` and `test_11`) because `StockTransferViewSet` in `apps/inventory/views.py` lacks the custom `@action` decorators for `dispatch` and `receive`, and does not override `destroy` to return 405. This is an existing pre-milestone state in `apps/inventory/views.py`.
- **Caveat 2:** Only read-only investigation was conducted. No database modifications or code edits were applied.
- **Caveat 3:** Browser acceptance was not executed during this backend survey turn; it will be conducted by the verification suite.

---

## 4. Conclusion

1. **DEF-01 Resolution Path:** Add `HOTEL_MANAGER = "hotel_manager"` to `User.ROLE_CHOICES` in `users/models.py`. Update `CustomUserAdmin.display_role` in `users/admin.py` to include `hotel_manager` and `housekeeping` badge labels. Generate/apply Django migration to update model choices while preserving all existing database rows.
2. **DEF-03 Resolution Path:** Replace procedural `["admin", "manager"]` checks with authoritative checks recognizing `hotel_manager`:
   - `apps/orders/views.py`: Lines 418, 503, 581, 665, 802.
   - `apps/orders/views.py:1497`: Extend `AdminOrdersView` to allow `["admin", "finance", "hotel_manager"]`.
   - `apps/orders/views.py:41`: Extend `DashboardStatsView` permission to allow `hotel_manager`.
   - `apps/reporting/views.py:735`: Replace `"manager"` with `"hotel_manager"`.
   - `apps/orders/tests/test_bill_request_handover.py`: Update test fixtures from `"manager"` to `"hotel_manager"`.
3. **DEF-05 Resolution Path:** Update `users/permissions.py` and `apps/inventory/views.py` to enforce single-hotel global stock permissions:
   - Allow `admin`, `superuser`, `hotel_manager`, and `inventory` roles global access across all stock locations.
   - Remove the default-allow fallback on unassigned locations for departmental staff (`kitchen`, `bar`, `waiter`, `cashier`), ensuring they receive 403 Forbidden for warehouse and stocktaking actions.
   - Add `hotel_manager` to transaction and waste reversal endpoints in `apps/inventory/views.py:175, 522`.
4. **DEF-06 Resolution Path:** Retain existing `role = "customer"` classification for external supplier accounts (`sec_supplier_alpha`, `sec_supplier_beta`). Rely on `IsAuthenticated` and restricted RFQ invited suppliers filtering (`rfq.invited_suppliers`) to protect procurement bidding.

---

## 5. Verification Method

To independently verify the observations and findings in this report:

1. **Inspect User Model & Staging Database:**
   ```powershell
   .\.venv\Scripts\python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.models import User; from collections import Counter; print(Counter(User.objects.values_list('role', flat=True)))"
   ```
   *Expected:* 37 users, including 2 with `role='hotel_manager'` and 2 with `role='customer'`.

2. **Verify Procedural Supervisor Checks:**
   ```powershell
   git grep -n "\[\"admin\", \"manager\"\]" apps/
   git grep -n "role in \[\"admin\", \"manager\"" apps/
   ```
   *Expected:* Matches in `apps/orders/views.py:418, 503, 581, 665, 802` and `apps/reporting/views.py:735`.

3. **Verify Unassigned Location Fallbacks in Inventory:**
   ```powershell
   git grep -n "custodian__isnull=True" apps/inventory/
   ```
   *Expected:* Matches in `apps/inventory/views.py:1282, 1502`.

4. **Execute Automated Test Suites:**
   - Orders Test Suite:
     ```powershell
     .\.venv\Scripts\python manage.py test apps.orders.tests --keepdb
     ```
     *Expected:* 64 tests ran, OK (0 failures).
   - Fast Unit & Workflow Suites:
     ```powershell
     .\.venv\Scripts\python manage.py test apps.identity.tests.test_auth_reliability users.test_milestone2_workflows users.test_phase3_integrity --settings=core.settings_test
     ```
     *Expected:* 16 tests ran, OK (0 failures, 2 skipped).
   - PostgreSQL Concurrency Integrity Suite:
     ```powershell
     .\.venv\Scripts\python manage.py test apps.inventory.tests.test_inventory_integrity --keepdb
     ```
     *Expected:* 26 tests ran, OK (0 failures).
