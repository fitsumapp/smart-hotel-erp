# Project: Acrma Hotel ERP RBAC Architecture Corrections

## Architecture
- **Backend Architecture**: Django 5.x / Django Rest Framework, PostgreSQL 16.12 (`hotel_erp_staging`).
  - `users/`: Core `User` model, custom authentication, role definitions (`User.ROLE_CHOICES`), admin registrations, and global permission classes (`users/permissions.py`).
  - `apps/identity/`: Serializers (`UserSerializer`), token generation (`get_tokens_for_user`), login services, and viewsets.
  - `apps/orders/`: Dining workflows, order lifecycle, table bill requests, cashier cash handovers, and supervisory approval endpoints.
  - `apps/inventory/`: Stock location management, stock transfers, stocktaking sessions, procurement (requisitions, RFQs, quotations, POs, GRNs, invoice matching).
  - `apps/reporting/`: Operational timing reports, kitchen/bar performance metrics.
  - `hotel/`: Core domain models (`Supplier`, `SupplierQuotation`, `StocktakeSession`, `StockLocation`), FEFO/FIFO batch allocation engine (`hotel/integrity.py`), and stocktaking business logic (`hotel/stocktaking.py`).
- **Frontend Architecture**: React 19 Single Page Application (`hotel-frontend/`).
  - `App.js`: Role-based top-level routing, auth verification, and layout dispatch.
  - `Sidebar.js`: Navigation menu groups (Operations, Front Office, Finance, Reports, Admin) with role-based visibility filtering (`isItemVisible`).
  - `DashboardLayout.js`: Operational workspace rendering overview cards, tab switching, and integrating sub-centers.
  - `StocktakeCenter.jsx`: Physical count recording, variance reporting, recount, blind count entry, and approval actions.
  - `ProcurementCenter.jsx`: Complete 6-desk procurement workflow (Requisitions, RFQs, Vendor Bids, Awards, Receiving/GRN, 3-Way Invoice Matching).
- **Security & Authorization Model**:
  - Single-hotel global stock permissions: `admin`, superuser, `hotel_manager`, and `inventory` staff hold global property-wide stock access.
  - Departmental staff (`kitchen`, `bar`, `waiter`, `cashier`) restricted strictly to their designated operational areas; no general warehouse or stocktaking access.
  - Removal of default-allow fallback for unassigned locations (`custodian IS NULL`).
  - Strict Separation of Duties (SoD): Count submitters cannot approve stocktakes (`counted_by != approved_by`).
  - Immutability of historical stock transactions and approved stocktaking audits.

---

## Feature Inventory
Every feature identified during the Survey phase is enumerated below with its assigned milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `User.ROLE_CHOICES` Formalization | Add `HOTEL_MANAGER = "hotel_manager"` to model constants and choices; preserve existing database rows without renaming or deleting accounts | M1 | DEF-01, Survey Spec Miner |
| 2 | Model Clean & Serializer Validation | Ensure `u.full_clean()` and `UserSerializer` validate `role="hotel_manager"` cleanly | M1 | DEF-01, Survey Spec Miner |
| 3 | Admin Role Display & Badging | Add badge styling and display mapping for `hotel_manager` and `housekeeping` in `CustomUserAdmin` | M1 | DEF-01, Survey Backend Explorer |
| 4 | Hotel Manager Frontend Routing | Update `App.js` `switch (role)` to route `hotel_manager` to `DashboardLayout` without Unauthorized / blank screens | M1 | DEF-02, Survey Frontend Explorer |
| 5 | Operational Dashboard Scope | Ensure `DashboardLayout` displays operational overview for `hotel_manager` while hiding technical admin controls (`users`, `settings`) in `Sidebar.js` | M1 | DEF-02, Survey Frontend Explorer |
| 6 | Operational Dashboard Stats API | Authorize `hotel_manager` on `DashboardStatsView` (`/users/dashboard-stats/`) | M1 | DEF-02, Survey Spec Miner |
| 7 | Operational Orders API | Authorize `hotel_manager` on `AdminOrdersView` (`/users/orders/`) | M1 | DEF-02, Survey Backend Explorer |
| 8 | Order Served Supervision | Authorize `hotel_manager` across `MarkOrderServedView`, `MarkOrderItemServedView`, `BulkMarkOrderItemsServedView` | M1 | DEF-03, Survey Backend Explorer |
| 9 | Dining Bill Request Supervision | Authorize `hotel_manager` on `RequestBillView` | M1 | DEF-03, Survey Backend Explorer |
| 10 | Cash Handover Supervision | Authorize `hotel_manager` on `RecordCashHandoverView` | M1 | DEF-03, Survey Backend Explorer |
| 11 | Operations Timing Report Access | Authorize `hotel_manager` on `OperationsTimingReportView` | M1 | DEF-03, Survey Spec Miner |
| 12 | Dining Permission Class Extension | Extend `IsWaiterOrAdmin` to recognize `hotel_manager` | M1 | DEF-03, Survey Spec Miner |
| 13 | Order Test Fixture Normalization | Update `apps/orders/tests/test_bill_request_handover.py` fixtures from `"manager"` to `"hotel_manager"` | M1 | DEF-03, Survey Backend Explorer |
| 14 | Inventory Role `DashboardLayout` Routing | Route `role === 'inventory'` to `DashboardLayout` in `App.js` with initial tab `'inventory'` | M1 | DEF-04, Survey Frontend Explorer |
| 15 | Inventory Navigation Scoping | Configure `Sidebar.js` to expose inventory, stocktaking, procurement (all 6 sub-desks), and inventory reports for `inventory` role without granting `admin` | M1 | DEF-04, Survey Frontend Explorer |
| 16 | Single-Hotel Global Stock Permissions | Grant global stock location and stocktake session access to `admin`, superuser, `hotel_manager`, and `inventory` staff | M1 | DEF-05, Survey Spec Miner |
| 17 | Unassigned Location Fallback Removal | Remove `custodian IS NULL` default-allow check in `apps/inventory/views.py` and `users/permissions.py` | M1 | DEF-05, Survey Backend Explorer |
| 18 | Stocktake Separation of Duties (SoD) | Enforce `counted_by != approved_by` in `hotel/stocktaking.py` and prevent count self-approval | M1 | DEF-05, Survey Spec Miner |
| 19 | Audit History Immutability Protection | Prevent deletion of counted, under-review, or approved stocktaking sessions in `StocktakeSessionViewSet.destroy` | M1 | DEF-05, Survey Spec Miner |
| 20 | Stock Reversal Permissions | Authorize `hotel_manager` on `StockTransactionViewSet.reverse` and `InventoryWasteRecordViewSet.reverse` alongside `admin` and `inventory` | M1 | DEF-05, Survey Backend Explorer |
| 21 | Supplier Identity Architecture Review | Review vendor authentication (`role = "customer"`), verify master `Supplier` foreign keys, confirm quotation submissions via internal desk, document findings | M1 | DEF-06, Survey Spec Miner |
| 22 | Automated Regression Suite Execution | Execute regression suites across identity, inventory, orders, workflows, and integrity against test DB; reconcile test counts without double-counting | M2 | R4, Survey Backend Explorer |
| 23 | Real-Browser Acceptance Across 9 Roles | Execute Selenium acceptance tests for Admin, Hotel Manager, Inventory, Kitchen, Bar, Waiter, Cashier, Reception, Housekeeping; capture screenshots | M3 | R5, Survey Frontend Explorer |
| 24 | Final RBAC Correction Report | Author comprehensive report `docs/FINAL_RBAC_CORRECTION_REPORT.md` covering all 11 required sections | M4 | R6, ORIGINAL_REQUEST.md |

---

## Code Layout
- Backend Models & Enums: `users/models.py`, `hotel/models.py`, `apps/inventory/models.py`
- Backend Permissions: `users/permissions.py`, `apps/identity/permissions.py`
- Backend Views & Endpoints: `apps/orders/views.py`, `apps/reporting/views.py`, `apps/inventory/views.py`, `apps/identity/views.py`
- Backend Admin: `users/admin.py`, `hotel/admin.py`
- Frontend Routing: `hotel-frontend/src/App.js`
- Frontend Navigation: `hotel-frontend/src/Sidebar.js`, `hotel-frontend/src/UserManager.jsx`
- Frontend Dashboards: `hotel-frontend/src/components/layout/DashboardLayout.js`, `hotel-frontend/src/pages/InventoryDashboard.js`
- Test Suites: `apps/inventory/tests/`, `apps/orders/tests/`, `apps/identity/tests/`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`
- Verification Scripts & Harnesses: `scratch/test_browser_*.py`, `scratch/audit_roles.py`, `scratch/roles_acceptance_suite.py`
- Screenshots Directory: `docs/screenshots/roles_acceptance/`
- Deliverable: `docs/FINAL_RBAC_CORRECTION_REPORT.md`

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Targeted RBAC Architecture & Frontend Corrections | DEF-01 through DEF-06: `hotel_manager` formalization, frontend `App.js` and `Sidebar.js` routing for `hotel_manager` and `inventory`, supervisor checks normalization, global stock permissions & removal of `custodian IS NULL`, supplier identity verification | None | DONE (Forensic Integrity Audit CLEAN / CLOSED per docs/M1_ITERATION3_FORENSIC_CLOSURE_REPORT.md) |
| M2 | Automated Regression Suite Execution | R4: Run regression suites for identity, orders, inventory, workflows, integrity; reconcile test counts without double-counting | M1 | DONE (499/499 automated tests PASS — 480 backend + 19 frontend; reconciled master table) |
| M3 | Real-Browser Acceptance Verification | R5: Execute real-browser Selenium test suite across all 9 roles, verify dashboards, navigation, restrictions, capture screenshots | M1, M2 | DONE (9 roles + 2 workflows verified; full screenshots in `docs/screenshots/roles_acceptance/`) |
| M4 | Final Deliverable & Integrity Verification Gate | R6: Author `docs/FINAL_RBAC_CORRECTION_REPORT.md` (all 11 sections), complete independent reviews and forensic audit | M1, M2, M3 | DONE (Deliverable authored in `docs/FINAL_RBAC_CORRECTION_REPORT.md`; Independent Review sign-off APPROVED) |

---

## Interface Contracts

### 1. `users/models.py` ↔ DRF Serializers & Django Admin
- `HOTEL_MANAGER = "hotel_manager"` added to `User` model constants.
- `ROLE_CHOICES` includes `(HOTEL_MANAGER, "Hotel Manager")`.
- Existing database accounts (`id=12`, `id=16`) validate via `u.full_clean()` with 0 validation errors.
- Serializers (`UserSerializer`) accept `role: "hotel_manager"` in incoming payloads.
- Django Admin `CustomUserAdmin.display_role` displays badge `'Hotel Manager'`.

### 2. Frontend `App.js` / `Sidebar.js` ↔ `hotel_manager`
- `App.js` `switch (role)`: Case `'hotel_manager'` routes to `<DashboardLayout ... />`.
- `DashboardLayout`: Displays `"Hotel Operations Overview"` title when `role === 'hotel_manager'`.
- `Sidebar.js`:
  - `isItemVisible`: If `userRole === 'hotel_manager'`, hide items `['users', 'settings']`.
  - Exposes: `dashboard`, `orders`, `menus`, `categories`, `tables`, `rooms`, `inventory`, `stocktaking`, `procurement`, `finance`, `all_reports`.
- Backend `/users/dashboard-stats/` and `/users/orders/`: Allow `hotel_manager` without HTTP 403 Forbidden.

### 3. Frontend `App.js` / `Sidebar.js` ↔ `inventory` Role
- `App.js` `switch (role)`: Case `'inventory'` routes to `<DashboardLayout ... initialTab="inventory" />`.
- `Sidebar.js`:
  - `isItemVisible`: If `userRole === 'inventory'`, expose only `['inventory', 'stocktaking', 'procurement', 'all_reports']`.
  - For `all_reports`, expose only child `report_inventory`.
  - Hide Front Office, F&B (orders/menus/tables), Rooms, Finance, Users, Settings.
- Provides immediate access to Inventory Dashboard, Stocktake Center, Procurement Center (all 6 sub-desks: requisitions, rfqs, vendor bids, awards, receiving, 3-way matching), expiry alerts, batch quarantine, and stock transfers.

### 4. Stocktaking Authorization & SoD Contracts
- `HasStocktakeLocationPermission`:
  - Superuser, `admin`, `hotel_manager`, and `inventory` granted global access.
  - Departmental staff (`kitchen`, `bar`, `waiter`, `cashier`) denied general stocktake access.
  - `location.custodian is None` fallback removed.
- `approve_stocktake_session`:
  - Disallows self-approval: `session.counted_by == supervisor` raises `PermissionDenied`.
  - Approved sessions and historical transactions cannot be deleted (`destroy()` returns HTTP 400 / HTTP 405).
