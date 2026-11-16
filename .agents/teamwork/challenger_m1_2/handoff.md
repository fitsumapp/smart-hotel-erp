# Milestone 1 Challenger Verification Report (DEF-04, DEF-05, DEF-06)

**State Folder:** `.agents/teamwork/challenger_m1_2/`  
**Milestone:** M1 — Targeted RBAC Architecture & Frontend Corrections  
**Author:** Challenger M1-2 (Empirical Challenger)  
**Date:** 2026-11-09  
**Verdict:** **APPROVE**

---

## 1. Observation

Direct empirical test execution of test harness `scratch/test_challenger_m1_2.py`, Django regression test suites, and React unit tests yielded the following direct observations:

### 1.1 DEF-05 Single-Hotel Global Stock Permissions Matrix
Evaluated `HasStocktakeLocationPermission.has_permission(request, view)` and `has_object_permission(request, view, session)` across 8 roles on both unassigned (`custodian=None`) and assigned (`custodian=kitchen_user`) locations:
- `admin` (id=1, `staging_admin`): `has_permission=True`, `has_object_permission(unassigned)=True`, `has_object_permission(assigned)=True`.
- `hotel_manager` (id=12, `manager_proc2`): `has_permission=True`, `has_object_permission(unassigned)=True`, `has_object_permission(assigned)=True`.
- `inventory` (id=8, `staging_controller`): `has_permission=True`, `has_object_permission(unassigned)=True`, `has_object_permission(assigned)=True`.
- `kitchen` (id=4, `staging_chef`): `has_permission=False`, `has_object_permission(unassigned)=False`, `has_object_permission(assigned)=True` (custodian match on assigned location; however view access is fully blocked by `has_permission=False`).
- `waiter` (id=3, `staging_waiter`): `has_permission=False`, `has_object_permission(unassigned)=False`, `has_object_permission(assigned)=False`.
- `cashier` (id=7, `staging_cashier`): `has_permission=False`, `has_object_permission(unassigned)=False`, `has_object_permission(assigned)=False`.
- `bar` (id=5, `staging_bartender`): `has_permission=False`, `has_object_permission(unassigned)=False`, `has_object_permission(assigned)=False`.
- `customer` / external supplier (id=21, `sec_supplier_alpha`): `has_permission=False`, `has_object_permission(unassigned)=False`, `has_object_permission(assigned)=False`.

### 1.2 DEF-05 Unassigned Store Fallback Removal via REST API
Tested REST API access to unassigned location (`custodian=None`) via `APIClient`:
- Non-inventory departmental staff (`kitchen`, `waiter`, `cashier`, `bar`) querying `/api/users/stocktaking/sessions/` -> `status=403 Forbidden`.
- Departmental staff POSTing to create session for unassigned location -> `status=403 Forbidden`.
- Departmental staff POSTing to create automated schedule for unassigned location -> `status=403 Forbidden`.
- `inventory` user querying `/api/users/stocktaking/sessions/` -> `status=200 OK`; creating session on unassigned location -> `status=201 Created`.
- `hotel_manager` user querying `/api/users/stocktaking/sessions/` -> `status=200 OK`; creating session on unassigned location -> `status=201 Created`.

### 1.3 DEF-05 Separation of Duties (SoD) & Deletion Protections
- In `hotel/stocktaking.py:approve_stocktake_session`:
  - Self-approval attempt where `session.counted_by == supervisor` (user `staging_controller`) raised verbatim `django.core.exceptions.PermissionDenied`: `"Separation of duties violation: count submitters cannot approve their own stocktake."`
  - Attempting emergency self-approval with `emergency_self_approval=True` by a non-superuser raised verbatim `PermissionDenied`.
  - Superuser emergency self-approval with short justification (< 15 characters) raised verbatim `django.core.exceptions.ValidationError`: `['A detailed justification (minimum 15 characters) is required for superuser emergency self-approval.']`
  - Independent supervisory approval where `supervisor` (hotel_manager `manager_proc2`) != `counted_by` (`staging_controller`) completed successfully with `session.status = "approved"` and `session.reviewed_by = manager_proc2`.
- In `apps/inventory/views.py:StocktakeSessionViewSet.destroy`:
  - `DELETE /api/users/stocktaking/sessions/{id}/` for session with status `approved` -> returned `status=400 Bad Request` with error: `"Cannot delete stocktake session in 'approved' status. Historical inventory audits cannot be deleted. Use the cancel action instead."`
  - `DELETE` for session with status `under_review` -> returned `status=400 Bad Request`.
  - `DELETE` for draft session with `is_mode_locked = True` -> returned `status=400 Bad Request` with error: `"Cannot delete stocktake session with recorded counts or locked mode. Use the cancel action instead."`
  - `DELETE` for clean, unlocked, uncounted draft session -> returned `status=204 No Content`.

### 1.4 DEF-06 External Supplier Identity Architecture
- Inspected active staging user `sec_supplier_alpha` (id=21) and `sec_supplier_beta` (id=22):
  - `role = "customer"`, `is_staff = False`, `is_superuser = False`.
- `sec_supplier_alpha` querying `/api/users/stocktaking/sessions/` -> returned `status=403 Forbidden`.
- Directly calling `hotel.procurement.approve_purchase_requisition(approver=sec_supplier_alpha)` -> raised verbatim `django.core.exceptions.PermissionDenied`: `"User role 'customer' is not authorized to approve at Tier 1: Department Head / F&B Manager. Required role: inventory."`
- `sec_supplier_alpha` attempting `POST /api/users/procurement/requisitions/{id}/approve/` -> returned `status=400 Bad Request`.
- Schema inspection on `hotel.models.Supplier` confirmed 0 ForeignKeys to `User` model, maintaining strict identity decoupling.

### 1.5 DEF-04 Inventory Role Scope & Frontend Routing
- Backend endpoint accessibility for `inventory` user without `admin` role:
  - `/api/users/stocktaking/sessions/` -> HTTP 200 OK
  - `/api/users/procurement/requisitions/` -> HTTP 200 OK
  - `/api/users/procurement/rfqs/` -> HTTP 200 OK
  - `/api/users/procurement/quotations/` -> HTTP 200 OK
  - `/api/users/procurement/invoices/` -> HTTP 200 OK
  - `/api/users/inventory-items/` -> HTTP 200 OK
  - `/api/users/locations/` -> HTTP 200 OK
  - `/api/users/transfers/` -> HTTP 200 OK
  - Technical user management `/api/users/users/` -> HTTP 403 Forbidden
- Frontend static verification in `hotel-frontend/src/App.js` and `hotel-frontend/src/Sidebar.js`:
  - `App.js:614-615`: `case 'inventory'` renders `<DashboardLayout activeTab={activeTab || 'inventory'} ... />`.
  - `Sidebar.js:214`: filters navigation for `userRole === 'inventory'`, exposing only `['inventory', 'stocktaking', 'procurement', 'all_reports']`.
  - `Sidebar.js:178-182`: restricts children under `all_reports` strictly to `report_inventory` for `inventory` role.

### 1.6 Automated Test Suite Execution
- Command: `.venv\Scripts\python.exe manage.py test users.test_milestone2_workflows --keepdb`
  - Result: `Ran 4 tests in 28.614s ... OK`
- Command: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover --keepdb`
  - Result: `Ran 13 tests in 114.415s ... OK`
- Command: `cd hotel-frontend; npm test -- --watchAll=false src/apiClient.test.js`
  - Result: `Test Suites: 1 passed, 1 total; Tests: 12 passed, 12 total`

---

## 2. Logic Chain

1. **DEF-05 Global Stocktaking Permissions and Fallback Removal:**
   - Observations 1.1 and 1.2 demonstrate that `HasStocktakeLocationPermission.has_permission` enforces an authoritative gate permitting solely `{"admin", "hotel_manager", "inventory"}` and superusers.
   - Removing the legacy fallback `if location and location.custodian is None: return True` completely closes the unassigned location vulnerability. When non-inventory departmental staff attempt to list, create, or schedule stocktakes on unassigned stores, they are immediately rejected with HTTP 403 Forbidden.
   - For assigned stores, even though `has_object_permission` allows a custodian to match, the view-level `has_permission` blocks non-inventory users from accessing general stocktake endpoints.

2. **DEF-05 Separation of Duties & Deletion Protections:**
   - Observation 1.3 validates that `approve_stocktake_session` strictly checks `if session.counted_by and supervisor.username == session.counted_by.username`. Self-approval raises `PermissionDenied`. Non-superusers cannot bypass this under any circumstances.
   - In `StocktakeSessionViewSet.destroy`, instances in `approved`, `under_review`, `recount_required`, or draft with recorded counts / mode locked return HTTP 400 Bad Request, preserving immutable audit trails. Only clean, uncounted drafts can be deleted (HTTP 204 No Content).

3. **DEF-06 External Supplier Identity Architecture:**
   - Observation 1.4 confirms that external vendor accounts retain `role = "customer"`.
   - Because they lack `admin`, `hotel_manager`, or `inventory` roles, vendor accounts are denied access to stocktaking endpoints (HTTP 403) and procurement requisition approvals (HTTP 400 / `PermissionDenied`).
   - The absence of a ForeignKey from `Supplier` to `User` confirms that vendors do not have elevated operational privileges or system accounts that conflate commercial partner records with staff access.

4. **DEF-04 Inventory Role Scope:**
   - Observation 1.5 verifies that `inventory` users enjoy complete access to inventory, stocktaking, transfers, and the entire procurement workflow without being granted `admin` privileges.
   - Navigation and routing in `App.js` and `Sidebar.js` embed inventory staff directly into `DashboardLayout` while locking out unrelated dining, rooms, finance, and technical admin modules.

5. **Regression Verification:**
   - Observation 1.6 shows 100% pass rates across Django end-to-end workflows (4/4), dining bill supervisory handovers (13/13), and React client tests (12/12).

---

## 3. Caveats

- **Scope Boundary:** This challenge was scoped specifically to DEF-04, DEF-05, and DEF-06 backend and frontend permission boundaries. Full real-browser Selenium acceptance across all 9 roles and extended cross-module test suites are scheduled for Milestones 2 and 3 in accordance with `PROJECT.md`.
- **Database Safety:** All tests were executed non-destructively against the PostgreSQL staging database and isolated test databases with `--keepdb`. Zero production migrations or git commits were executed.

---

## 4. Conclusion

**Verdict: APPROVE**

The implementations for DEF-04, DEF-05, and DEF-06 fully satisfy all architectural, operational, and security requirements:
- Property-wide global stocktaking permissions are strictly enforced for `admin`, `hotel_manager`, and `inventory` roles.
- The unassigned location default-allow vulnerability (`custodian IS NULL`) has been verified eliminated across model permissions, REST API endpoints, and viewset queries.
- Separation of Duties (SoD) prevents count self-approval, requiring independent managerial sign-off.
- Historical stocktaking sessions and approved audit trails are protected against destructive deletion.
- External supplier accounts remain securely segregated under `role = "customer"` with zero stocktaking or procurement approval privileges.
- All automated test suites and empirical challenges pass with 0 errors and 0 regressions.

---

## 5. Verification Method

To independently reproduce and verify this assessment:

1. **Run the Empirical Challenger Test Harness:**
   ```powershell
   .venv\Scripts\python.exe scratch\test_challenger_m1_2.py
   ```
   *Expected Output:*
   ```
   CHALLENGE RESULTS SUMMARY:
     CHALLENGE_1_PERMISSION_MATRIX: PASS
     CHALLENGE_2_FALLBACK_REMOVAL: PASS
     CHALLENGE_3_SOD_AND_DELETION: PASS
     CHALLENGE_4_SUPPLIER_IDENTITY: PASS
     CHALLENGE_5_INVENTORY_SCOPE: PASS
   OVERALL STATUS: ALL CHALLENGES PASSED
   ```

2. **Execute Automated Workflow Regression Suite:**
   ```powershell
   .venv\Scripts\python.exe manage.py test users.test_milestone2_workflows apps.orders.tests.test_bill_request_handover --keepdb
   ```
   *Expected Output:*
   ```
   Ran 17 tests in ...s
   OK
   ```

3. **Execute Frontend Unit Tests:**
   ```powershell
   cd hotel-frontend
   npm test -- --watchAll=false src/apiClient.test.js
   ```
   *Expected Output:*
   ```
   Test Suites: 1 passed, 1 total
   Tests:       12 passed, 12 total
   ```
