# ACRMA HOTEL ERP — USER ROLE & PERMISSION ARCHITECTURE AUDIT
**Audit Reference:** `AUDIT-RBAC-ARCHITECTURE-2026-V1.0`  
**Date of Audit:** 8 November 2026  
**Environment:** Active Staging (`hotel_erp_staging` on PostgreSQL 16.12, Django 5.2 / DRF, React 19 SPA)  
**Branch:** `development` (Commit: `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`)  
**Audit Scope:** Read-Only Source Code, Database, and API Permission Architecture Audit  

---

## 1. Executive Summary

This read-only audit inspects the complete user role, permission, and access-control structure of the Acrma Hotel ERP. The objective is to establish the authoritative ground truth of the system's role architecture before finalizing stock access policies.

### Core Architectural Findings:
1. **Single-Field Role Model:** Authorization is driven entirely by a single character string on the custom User model (`User.role`), supplemented by `User.is_superuser`.
2. **Zero Django Groups/Permissions:** Django's built-in `auth.Group` and `auth.Permission` tables are completely unused ($0$ groups, $0$ user-permission rows). All RBAC logic is implemented via custom DRF `BasePermission` classes and procedural inline view checks.
3. **Implicit Departmental Mapping:** There is no `Department` table or model. A user's departmental affiliation is implicitly inferred from their `role` (e.g., `kitchen`, `bar`, `housekeeping`).
4. **Physical Location Assignment:** Physical location access is managed via a single nullable foreign key on the location model: `StockLocation.custodian` (`ForeignKey(User, null=True, blank=True, related_name="managed_stock_locations")`).
5. **Major Role Definition Gaps & Conflicts:**
   - Role `'hotel_manager'` exists in the active staging database and is enforced in backend permissions, but is **missing from `User.ROLE_CHOICES`** and **causes an "Unauthorized" screen in the React frontend**.
   - Role `'manager'` is checked in `apps/orders/views.py`, creating a naming conflict with `'hotel_manager'`.
   - The single role `'inventory'` is heavily overloaded, conflating storekeepers, procurement officers, purchasing managers, and physical stocktaking counters.

---

## 2. Complete Role-Permission Matrix

| Role Identifier | Formally in `ROLE_CHOICES`? | Active Users in Staging | Primary Responsibilities | View Access | Create Access | Edit / Update Access | Approval Authorities | Deletion Rights | Stock & Stocktake Access | Geographic Access Scope |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`superuser`** (`is_superuser=True`) | Built-in flag | 7 users | System administrator, technical owner, emergency break-glass operator. | Global access across all modules, ledgers, audit logs, and settings. | Any entity across any module. | Any entity across any module. | All approvals. *(Subject only to SoD: cannot approve own stock count)*. | Unrestricted (except immutable audit logs). | Global access to all stores, batches, sessions, and schedules. | **Global** |
| **`admin`** | Yes | 9 users | General Manager, Hotel Owner, Operations Director, Executive Management. | All dashboards, reports, ledgers, stores, rooms, users, settings. | All business entities, users, rooms, categories, items, batches. | Full operational editing across all modules. | Waste records, stocktakes (with SoD), Tier 3 procurement ($>\$50\text{k}$), refunds. | Draft stocktakes, unposted records, users, rooms. | Global access to all physical stores, sessions, and schedules. | **Global** |
| **`hotel_manager`** | **NO** *(Missing from choices)* | 2 users | Operations Manager, General Manager Delegate. | Global operational dashboards, inventory, procurement, finance ledgers. | Requisitions, RFQs, POs, Stocktake sessions & schedules. | Operational data across inventory, procurement, and finance. | Stocktakes (with SoD), procurement requisitions. | Draft stocktakes, draft orders. | Global access across all physical stock locations in backend API. *(Blocked in UI)*. | **Global (API)** / **Inaccessible (UI)** |
| **`finance`** | Yes | 3 users | Financial Controller, Accountant, Cash Auditor, CFO. | General ledger, trial balance, P&L, cashier shifts, invoices, reports. | Journal entries, supplier invoices (match & record), expense records. | Chart of accounts, draft invoices, fiscal settings. | Tier 2 procurement ($\$10\text{k} - \$50\text{k}$), supplier invoices, cash handovers. | Draft journals, draft invoices. | Read access to valuation ledgers. Subject to location scoping for physical stocktake. | **Global (Finance)** / **Scoped (Stocktake)** |
| **`inventory`** | Yes | 10 users | Storekeeper, Material Manager, Buyer, Stocktake Counter, Custodian. | Inventory items, categories, batch balances, expiry alerts, transfers. | Stock transactions, purchase requisitions, RFQs, GRNs, transfers, counts. | Draft requisitions, count entries on assigned stocktake sessions. | Tier 1 procurement ($0 - \$10\text{k}$). *Cannot approve waste or own counts*. | Draft uncounted stocktakes. *Cannot delete posted transactions*. | Access to assigned store(s) as custodian, plus unassigned stores (`custodian IS NULL`). | **Location-Specific** (+ unassigned stores) |
| **`kitchen`** | Yes | 2 users | Head Chef, Line Cook, Kitchen Pantry Supervisor. | Kitchen display queue (KDS), food item balances, recipe BOMs. | Food purchase requisitions, recipe preparation start events. | Update kitchen order item status (`received` $\rightarrow$ `started` $\rightarrow$ `ready`). | None. | None. | Can view batch shelf life (`IsBatchOperator`). *Cannot access stocktakes*. | **Department-Specific** (Kitchen Station) |
| **`bar`** | Yes | 1 users | Head Bartender, Bar Operator, Beverage Pourer. | Bar display queue (BDS), beverage orders. | Beverage purchase requisitions, drink preparation start events. | Update bar order item status (`received` $\rightarrow$ `started` $\rightarrow$ `ready`). | None. | None. | Blocked from batch management and stocktake sessions (403 Forbidden). | **Department-Specific** (Bar Station) |
| **`waiter`** | Yes | 3 users | Dining Room Server, Food Runner, Table Attendant. | Active dining sessions, restaurant tables, menu catalog, own orders. | Dining sessions, food/beverage orders, cash handover requests. | Add items to dining session, mark own items as `served`, request bill. | None. | Cannot cancel orders once preparation starts. | Zero stock or warehouse access (403 Forbidden). | **User-Scoped** (Own assigned orders) |
| **`cashier`** | Yes | 3 users | Restaurant Cashier, POS Settlement Operator, Front Cashier. | Pending bills, completed bills, daily sales, dining session receipts. | Payment receipts, bill prints, shift closing records. | Prepare bills (`bill_prepared_at`), settle dining sessions. | Confirm waiter cash handovers. | None. | Zero stock or warehouse access (403 Forbidden). | **Shift / POS Desk-Specific** |
| **`reception`** | Yes | 1 users | Front Desk Agent, Receptionist, Night Auditor. | Room rack, reservation catalog, guest profiles, front desk folios. | Reservations, check-in records, folio charges, checkout payments. | Update room front-desk status (`clean`, `occupied`, `out_of_order`), guests. | Guest check-in, checkout billing settlement. | None. | Can view minibar catalog for guest billing. *Cannot manage warehouse*. | **Property-Wide Front Desk** |
| **`housekeeping`** | Yes | 1 users | Room Attendant, Housekeeping Inspector, Minibar Restocker. | Room cleaning status, housekeeping tasks, lost and found registry. | Lost and found logs, room inspection records, minibar consumption. | Housekeeping task status (`pending` $\rightarrow$ `in_progress` $\rightarrow$ `completed`). | Room cleanliness inspection (`inspected`). | None. | Can record minibar consumption (auto-deducts from `MINIBAR-PANTRY`). | **Housekeeping & Minibar** |
| **`customer`** | Yes | 2 users | Hotel Guest, Self-Service Portal User, **External Supplier**. | Public room catalog, own booking confirmation, own folio invoice. | Online reservation, self-service check-in, RFQ supplier quotation bids. | Own guest profile. | None. | None. | Zero inventory or warehouse access (403 Forbidden). | **Public / Token-Scoped** |
| **`delivery`** | Yes *(Deprecated)* | 0 users | Deprecated phantom role (ADR-006). | None. | None. | None. | None. | None. | None. | None |

---

## 3. StockLocation, StocktakeSession & StocktakeSchedule Access Rules

### 3.1 StockLocation Access Architecture
- **ViewSet:** [`StockLocationViewSet`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/apps/inventory/views.py#L68)
- **Permission Class:** [`IsInventoryManager`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/users/permissions.py#L76) (`admin`, `inventory`, `hotel_manager`, superuser).
- **Rule:** Read and write access to physical store master records is global among all inventory managers and administrators. Location custodianship is established by populating `StockLocation.custodian`.

### 3.2 StocktakeSchedule Access Architecture
- **ViewSet:** [`StocktakeScheduleViewSet`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/apps/inventory/views.py#L1482)
- **Permission Class:** [`HasStocktakeLocationPermission`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/users/permissions.py#L201).
- **Listing & Retrieval:**
  - Administrators (`admin`, `hotel_manager`, superuser) see all schedules across all locations.
  - Inventory staff (`inventory`) only see schedules where:
    1. They are the custodian of the store (`location__custodian == user`), OR
    2. They are the designated schedule staff (`assigned_staff == user`), OR
    3. They created the schedule (`created_by == user`), OR
    4. The store has no custodian assigned (`location__custodian__isnull = True`).
- **Creation & Modification:** Staff cannot create or modify schedules for a store managed by another custodian (returns `HTTP 403 Forbidden`).

### 3.3 StocktakeSession Access Architecture
- **ViewSet:** [`StocktakeSessionViewSet`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/apps/inventory/views.py#L1259)
- **Permission Class:** [`HasStocktakeLocationPermission`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/users/permissions.py#L201).
- **Listing & Retrieval:**
  - Administrators (`admin`, `hotel_manager`, superuser) retain global visibility across all sessions.
  - Inventory staff only see sessions where:
    1. `location.custodian == user`, OR
    2. `session.created_by == user`, OR
    3. `session.counted_by == user`, OR
    4. `session.schedule.assigned_staff == user`, OR
    5. `location.custodian IS NULL`.
- **Custom Detail Actions:** All 5 custom actions (`record_counts`, `request_recount`, `submit_recount`, `approve`, `cancel`) execute `self.get_object()`, enforcing the location-scoped queryset. Unauthorized attempts by staff belonging to other stores return `HTTP 404 Not Found`.
- **Separation of Duties (SoD):** The staff member recorded in `counted_by` cannot approve the session (`approve` returns `HTTP 403 Forbidden`). Only a distinct supervisor or administrator can approve variance.
- **Audit Preservation:** Once a session enters `counted`, `under_review`, `approved`, or `cancelled` status, deletion is strictly prohibited (`DELETE` returns `HTTP 400 Bad Request`). Only uncounted, unlocked `draft` sessions can be deleted.

---

## 4. User Assignment Mechanisms

### 4.1 Department Assignment
- **Mechanism:** Completely implicit via `User.role`.
- **Architecture:** There is no foreign key or many-to-many relationship linking users to a `Department` entity. Setting `user.role = "kitchen"` is the sole mechanism that establishes a user's departmental identity.

### 4.2 Location Assignment
- **Primary Mechanism:** `StockLocation.custodian` (`ForeignKey(User, null=True, blank=True, related_name="managed_stock_locations")`).
  - A user can be custodian of multiple locations (e.g., `user.managed_stock_locations.all()`).
  - Each `StockLocation` can have at most one primary custodian.
- **Secondary / Task Mechanisms:**
  - `StocktakeSchedule.assigned_staff`: Grants a staff member access to counts generated by that recurring schedule.
  - `StocktakeSession.counted_by`: Associates the physical counter with the specific audit session.

### 4.3 Procurement Approval Tier Assignment
- **Mechanism:** Configured in [`ProcurementApprovalPolicy`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/hotel/models.py#L425) and [`ProcurementApprovalTier`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/hotel/models.py#L440):
  - **Tier 1 ($0 - \$10,000):** Assigned to `required_role = "inventory"` (Department Head / Storekeeper).
  - **Tier 2 ($\$10,000.01 - \$50,000):** Assigned to `required_role = "finance"` (Finance Controller).
  - **Tier 3 ($>\$50,000):** Assigned to `required_role = "admin"` (General Manager / Owner).

---

## 5. Architectural Deficiencies, Conflicts & Redundancies

### 5.1 DEFECT-01: Undefined Role in Model Choices (`hotel_manager`)
- **Location:** [`users/models.py`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/users/models.py#L22)
- **Finding:** `User.ROLE_CHOICES` lists 11 roles, omitting `hotel_manager`. However, two active staging users (`manager_proc2` ID 12, `sec_ops_manager` ID 16) hold `role = "hotel_manager"`.
- **Impact:** While backend permissions (`users/permissions.py`) and inventory views (`apps/inventory/views.py`) explicitly recognize `hotel_manager`, attempting to validate or save user records via Django ModelForms or serializers that enforce `choices` will raise a validation error.

### 5.2 DEFECT-02: Frontend Lockout for Hotel Manager Role
- **Location:** [`hotel-frontend/src/App.js`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/hotel-frontend/src/App.js#L588)
- **Finding:** `App.js` executes a `switch (role)` to render role-specific dashboards. It includes `'admin'`, `'finance'`, `'waiter'`, `'cashier'`, `'kitchen'`, `'bar'`, `'reception'`, `'inventory'`, `'customer'`, and `'housekeeping'`. It does NOT include `'hotel_manager'`.
- **Impact:** Any user logging in with `role: "hotel_manager"` falls into `default:` and is shown a blank screen with **"Unauthorized"**. A General Manager with this role cannot use the web application!

### 5.3 DEFECT-03: Supervisor Naming Conflict (`"manager"` vs `"hotel_manager"`)
- **Location:** [`apps/orders/views.py`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/apps/orders/views.py#L418)
- **Finding:** In `apps/orders/views.py` (lines 418, 503, 581, 665, 802), supervisory overrides check:
  ```python
  is_supervisor = request.user.role in ["admin", "manager"] or request.user.is_superuser
  ```
- **Impact:** The code checks for the string `"manager"`, whereas the rest of the codebase (and the database) uses `"hotel_manager"`. Consequently, a `hotel_manager` has zero supervisory authority in the restaurant and dining room modules.

### 5.4 DEFECT-04: Frontend Disconnect for Inventory Role
- **Location:** [`hotel-frontend/src/App.js`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/hotel-frontend/src/App.js#L602), [`hotel-frontend/src/Sidebar.js`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/hotel-frontend/src/Sidebar.js#L207)
- **Finding:** When a user with `role = "inventory"` logs in, `App.js` routes them to `InventoryDashboard.js`.
  - `InventoryDashboard.js` does NOT include components for `StocktakeCenter` or `ProcurementCenter`.
  - `StocktakeCenter` and `ProcurementCenter` exist only inside `DashboardLayout`, which is only rendered for `role = "admin"` and `role = "finance"`.
- **Impact:** Inventory staff cannot access physical stocktaking or procurement in the UI unless granted the `admin` layout role.

### 5.5 DEFECT-05: Overloaded Role (`inventory`)
- **Finding:** The role string `"inventory"` is forced to represent five distinct organizational functions:
  1. Floor stock counter (data entry)
  2. Physical storekeeper (stock issuance & GRN receipt)
  3. Warehouse custodian (location accountability)
  4. Procurement buyer (RFQ creation & supplier negotiation)
  5. Department approving manager (Tier 1 procurement authorization)
- **Impact:** Segregation of duties cannot be enforced by role; the system is forced to rely on single object foreign keys (`counted_by`, `custodian`) to prevent unauthorized actions.

### 5.6 DEFECT-06: Supplier Misclassification as `customer`
- **Finding:** External suppliers (e.g., `sec_supplier_alpha`, `sec_supplier_beta`) are assigned `role = "customer"`. There is no dedicated `supplier` role in `User.ROLE_CHOICES`.

### 5.7 DEFECT-07: Default-Allow on Unassigned Stores (`custodian IS NULL`)
- **Location:** [`users/permissions.py`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/users/permissions.py#L242), [`apps/inventory/views.py`](file:///d:/workspace/ongoing%20projects/Acrma hotel mangment/Acrma hotel mangment/apps/inventory/views.py#L1282)
- **Finding:** If a location has no assigned custodian (`custodian = None`), the permission check falls back to allowing **all** authenticated inventory staff full visibility and operational access.
- **Impact:** In the active staging database, `STORE-MAIN`, `KITCHEN-MAIN`, `BAR-MAIN`, and `MINIBAR-PANTRY` have `custodian = None`. As a result, Store A staff can view and count stock in the Bar and Kitchen.

---

## 6. Recommendations for Policy Finalization

Before finalizing the hotel's stock access and security policies, the following structural resolutions are recommended:

1. **Formalize Management Roles:**
   - Add `HOTEL_MANAGER = "hotel_manager"` to `User.ROLE_CHOICES`.
   - Update `hotel-frontend/src/App.js` to render `DashboardLayout` for `hotel_manager`.
   - Normalize `apps/orders/views.py` from `["admin", "manager"]` to `["admin", "hotel_manager"]`.
2. **Expose Stocktaking & Procurement to Inventory Staff:**
   - Update `App.js` so that `inventory` staff can render `StocktakeCenter` and `ProcurementCenter`, or embed them as tabs within `InventoryDashboard.js`.
3. **Transition Unassigned Stores to Default-Deny:**
   - Require unassigned stores (`custodian IS NULL`) to be managed strictly by `admin` or `hotel_manager`, or require every active store to have an assigned custodian before stocktaking can occur.
4. **Decouple Procurement from Storekeeping:**
   - For post-pilot enhancement, introduce distinct roles for `storekeeper` and `procurement_officer` to eliminate role overloading.

