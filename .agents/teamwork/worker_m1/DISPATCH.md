## 2026-11-09T06:55:09Z
You are the RBAC and Frontend Implementation Worker for Milestone 1 of Acrma Hotel ERP RBAC Architecture Corrections.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md` before starting work.
Also read PROJECT.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md`.
Read Explorer findings in:
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_spec_miner\handoff.md`
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_backend\handoff.md`
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_frontend\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Ownership (You own these files exclusively):
- `users/models.py`
- `users/admin.py`
- `users/permissions.py`
- `apps/orders/views.py`
- `apps/reporting/views.py`
- `apps/inventory/views.py`
- `apps/orders/tests/test_bill_request_handover.py`
- `hotel-frontend/src/App.js`
- `hotel-frontend/src/Sidebar.js`
- `hotel-frontend/src/UserManager.jsx`

Detailed Task Specifications:
1. DEF-01: Formalize `hotel_manager` in `User.ROLE_CHOICES` (`users/models.py`). Add `HOTEL_MANAGER = "hotel_manager"` to constants and choices. Update `CustomUserAdmin.display_role` (`users/admin.py`) with badge color mapping for `hotel_manager` and `housekeeping`. Verify model validation `u.full_clean()` passes for existing users (`id=12`, `id=16`). If a migration is needed, generate `users/migrations/0009_alter_user_role.py` (or makemigrations users) ensuring zero data loss and preserving existing database accounts.
2. DEF-02: Configure frontend routing and navigation for `hotel_manager`:
   - In `hotel-frontend/src/App.js`: In `switch (role)`, add `case 'hotel_manager':` to route to `<DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />`. Ensure overview title handles `hotel_manager` cleanly. Guard `users` and `settings` tabs.
   - In `hotel-frontend/src/Sidebar.js`: In `isItemVisible`, if `userRole === 'hotel_manager'`, hide items `['users', 'settings']`. Ensure operational modules (dashboard, orders, menus, categories, tables, rooms, inventory, stocktaking, procurement, finance, all_reports) are visible.
   - In `hotel-frontend/src/UserManager.jsx`: Add `'Hotel Manager'` to available roles in `getAvailableRoles()`.
   - In backend `apps/orders/views.py`: Update `DashboardStatsView` (`/users/dashboard-stats/`) and `AdminOrdersView` (`/users/orders/`) to permit `hotel_manager`.
3. DEF-03: Normalize supervisor authorization checks:
   - In `apps/orders/views.py`: Replace procedural `request.user.role in ["admin", "manager"]` with authoritative check recognizing `hotel_manager` (`request.user.role in ["admin", "hotel_manager"] or request.user.is_superuser`) in:
     - `MarkOrderServedView` (line 418)
     - `MarkOrderItemServedView` (line 503)
     - `BulkMarkOrderItemsServedView` (line 581)
     - `RequestBillView` (line 665)
     - `RecordCashHandoverView` (line 802)
   - In `apps/reporting/views.py`: In `OperationsTimingReportView.get` (line 735), replace `"manager"` with `"hotel_manager"`.
   - In `users/permissions.py`: In `IsWaiterOrAdmin.has_permission`, include `hotel_manager` (`user.role in {"admin", "hotel_manager", "waiter"}`).
   - In `apps/orders/tests/test_bill_request_handover.py`: Update test user creation from `role="manager"` to `role="hotel_manager"`.
4. DEF-04: Configure frontend routing and navigation for `inventory` users:
   - In `hotel-frontend/src/App.js`: Route `case 'inventory':` to `<DashboardLayout activeTab={activeTab || 'inventory'} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />`.
   - In `hotel-frontend/src/Sidebar.js`: In `isItemVisible`, if `userRole === 'inventory'`, expose only `['inventory', 'stocktaking', 'procurement', 'all_reports']` (and for `all_reports` only child `report_inventory`). Hide Front Office, F&B (orders/menus/tables), Rooms, Finance, Users, Settings.
   - This provides full frontend access to Inventory Dashboard, Stocktake Center, Procurement Center (all 6 sub-desks: requisitions, rfqs, vendor bids, awards, receiving, 3-way matching), expiry alerts, transfers, PRs, RFQs, POs, GRNs, invoice matching without granting `admin`.
5. DEF-05: Single-hotel global stock permissions and removal of unassigned store fallback:
   - In `users/permissions.py`: In `HasStocktakeLocationPermission.has_object_permission`, grant global access to `{"admin", "hotel_manager", "inventory"}` and superuser; remove `if location and location.custodian is None: return True` fallback. Ensure departmental staff (`kitchen`, `bar`, `waiter`, `cashier`) receive no general warehouse or stocktaking access.
   - In `apps/inventory/views.py`: In `StocktakeSessionViewSet.get_queryset` and `StocktakeScheduleViewSet.get_queryset`, grant global access to `{"admin", "hotel_manager", "inventory"}` and superuser, and remove `| Q(location__custodian__isnull=True)` fallback for non-authorized roles.
   - In `apps/inventory/views.py`: In `StockTransactionViewSet.reverse` and `InventoryWasteRecordViewSet.reverse`, authorize `hotel_manager` alongside `admin` and `inventory`.
   - Preserve stocktake workflows (draft/count/recount/approval/cancellation), blind mode, separation of duties (`counted_by != approved_by` in `hotel/stocktaking.py`), audit history deletion protections (`destroy()` returns HTTP 400), and FEFO/FIFO engine.
6. DEF-06: Confirm supplier accounts retain `role = "customer"` and master `Supplier` linkage is preserved.
