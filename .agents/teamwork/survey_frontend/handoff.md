# Handoff Report: Frontend Navigation, Route Guards, and Selenium Acceptance Architecture (DEF-02, DEF-04, R5)

## 1. Observation

### 1.1 DEF-02: Hotel Manager Frontend Lockout and Operational Dashboard
- **File**: `hotel-frontend/src/App.js` (lines 583–611)
  - `renderDashboard()` extracts the authenticated user and executes a role switch:
    ```javascript
    const role = user.role?.toLowerCase().trim();
    switch (role) {
      case 'admin':
      case 'finance':
        return <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab} userData={user} handleLogout={handleLogout} />;
      case 'waiter':
        return <WaiterDashboard userData={user} handleLogout={handleLogout} />;
      case 'cashier':
        return <CashierDashboard userData={user} handleLogout={handleLogout} />;
      case 'kitchen':
        return <KitchenDashboard userData={user} handleLogout={handleLogout} />;
      case 'bar':
        return <BarDashboard userData={user} handleLogout={handleLogout} />;
      case 'reception':
        return <ReceptionDashboard userData={user} handleLogout={handleLogout} />;
      case 'inventory':
        return <InventoryDashboard userData={user} handleLogout={handleLogout} />;
      case 'customer':
        return <CustomerDashboard userData={user} handleLogout={handleLogout} />;
      case 'housekeeping':
        return <HousekeepingDashboard userData={user} handleLogout={handleLogout} />;
      default:
        return <div style={{ padding: '50px', textAlign: 'center' }}><h1>Unauthorized</h1><button onClick={handleLogout}>Back to Login</button></div>;
    }
    ```
  - Observation: `hotel_manager` is completely missing from `switch (role)`. Any user with `role: "hotel_manager"` falls into `default:` and receives an "Unauthorized" blank screen with a "Back to Login" button.
- **File**: `hotel-frontend/src/UserManager.jsx` (lines 175–211)
  - In `getAvailableRoles()`, available roles are populated conditionally (`['Admin', 'Cashier', 'Waiter', 'Kitchen', 'Bar', 'Reception', 'Housekeeping', 'Finance', 'Inventory']`). `'Hotel Manager'` is omitted entirely.
- **File**: `hotel-frontend/src/Sidebar.js` (lines 98–103, 190–209)
  - The `ADMIN` group contains items `{ id: 'users', title: 'Users' }` and `{ id: 'settings', title: 'Settings' }`.
  - `isItemVisible` checks:
    ```javascript
    if (userRole === 'finance' && !['dashboard', 'finance', 'inventory', 'procurement', 'all_reports'].includes(item.id)) return false;
    return true;
    ```
  - Observation: There is no role filter for `hotel_manager`. If `hotel_manager` is given `DashboardLayout` without filtering `Sidebar.js`, they would see `users` and `settings`.
- **Backend Permissions Guarding Technical Controls**:
  - `apps/orders/views.py` (line 1085):
    ```python
    if request.user.role != "admin" and not request.user.is_superuser:
        return Response({"error": "Only admins can modify system settings."}, status=403)
    ```
  - `apps/identity/views.py` (lines 134–136): `UserViewSet` enforces `permission_classes = [IsHotelAdmin]`, where `IsHotelAdmin` requires `(user.is_superuser or user.role == "admin")`.
  - Observation: The backend explicitly restricts system settings and user management to `admin` / superusers.

---

### 1.2 DEF-04: Inventory Role Frontend Disconnect
- **File**: `hotel-frontend/src/App.js` (lines 602–603, 508–516)
  - Routing in `App.js`:
    ```javascript
    case 'inventory':
      return <InventoryDashboard userData={user} handleLogout={handleLogout} />;
    ```
  - Inside `DashboardLayout` (lines 508–516):
    ```javascript
    {activeTab === 'inventory'            && <InventoryDashboard userData={userData} handleLogout={handleLogout} onNavigate={setActiveTab} />}
    {activeTab === 'stocktaking'          && <StocktakeCenter userData={userData} />}
    {activeTab === 'procurement'          && <ProcurementCenter userData={userData} />}
    {activeTab.startsWith('procurement_') && (
      <ProcurementCenter
        userData={userData}
        initialSection={activeTab.replace('procurement_', '')}
      />
    )}
    ```
- **File**: `hotel-frontend/src/pages/InventoryDashboard.js` (lines 15, 3500–3521)
  - `InventoryDashboard` receives `({ userData, handleLogout, onNavigate })`.
  - Tab buttons in `InventoryDashboard.js`: `overview`, `batches`, `actions`, `waste`, `recipes`, `ledger`, `items`, `categories`, `suppliers`, `reports`.
  - Search command execution:
    ```
    Term 'stocktake': 0 occurrences in InventoryDashboard.js
    Term 'stocktaking': 0 occurrences in InventoryDashboard.js
    Term 'procurement': 0 occurrences in InventoryDashboard.js
    Term 'schedule': 0 occurrences in InventoryDashboard.js
    ```
  - Observation: `InventoryDashboard.js` is rendered standalone without `Sidebar.js`. It contains ZERO components or links for `StocktakeCenter` or `ProcurementCenter`.
  - Meanwhile, `StocktakeCenter.jsx` (`hotel-frontend/src/pages/stocktaking/StocktakeCenter.jsx`) and `ProcurementCenter.jsx` (`hotel-frontend/src/pages/procurement/ProcurementCenter.jsx`) exist ONLY within `DashboardLayout`.
  - Because `DashboardLayout` was only rendered for `admin` and `finance`, inventory officers are completely locked out of physical stocktaking and procurement in the UI unless granted the `admin` role.

---

### 1.3 R5: Selenium Real-Browser Acceptance Infrastructure
- **Existing Scripts in `scratch/`**:
  - `scratch/qc_browser_reproduction.py`
  - `scratch/test_browser_remediation.py`
  - `scratch/test_browser_remediation_actions.py`
  - `scratch/test_browser_limitations_remediation.py`
  - `scratch/test_browser_partial_features.py`
  - `scratch/diagnose_browser.py`
- **Authentication Method Observed**:
  - Scripts import `get_tokens_for_user(user)` from `apps.identity.services`.
  - Tokens and user metadata are injected directly into browser `localStorage`:
    ```python
    driver.execute_script("""
        localStorage.setItem('access_token', arguments[0]);
        localStorage.setItem('refresh_token', arguments[1]);
        localStorage.setItem('user', JSON.stringify(arguments[2]));
        localStorage.setItem('role', arguments[3]);
    """, tokens["access"], tokens["refresh"], user_payload, user.role)
    driver.get("http://localhost:3000/dashboard")
    ```
  - In `apps/identity/services.py` (lines 118–125): `authenticate_with_lockout` enforces `MAX_LOGIN_ATTEMPTS = 5` with a 15-minute account lockout (`LOCKOUT_TIME = timedelta(minutes=15)`). Injecting JWT into `localStorage` bypasses UI login throttling, MFA prompts, and network latency, ensuring 100% deterministic test execution.
- **Active Staging Database Users Across All 9 Roles**:
  Query command:
  ```python
  User.objects.filter(role=role, is_active=True)
  ```
  Results directly verified in `hotel_erp_staging`:
  | Role | Active Count | Representative Staging Users |
  |---|---|---|
  | **Admin** | 8 | `staging_admin` (ID 1, superuser=True), `sec_hotel_admin` (ID 14), `sec_gen_manager` (ID 15) |
  | **Hotel Manager** | 2 | `manager_proc2` (ID 12, password: `password123`), `sec_ops_manager` (ID 16) |
  | **Inventory** | 8 | `staging_controller` (ID 8), `remed_staff_a` (ID 37), `remed_staff_b` (ID 38), `sec_storekeeper` (ID 19) |
  | **Kitchen** | 2 | `staging_chef` (ID 4), `sec_dept_supervisor` (ID 20) |
  | **Bar** | 1 | `staging_bartender` (ID 5) |
  | **Waiter** | 3 | `staging_waiter` (ID 3), `waiter_p4_browser` (ID 33) |
  | **Cashier** | 3 | `staging_cashier` (ID 7), `cashier_p4_browser` (ID 32) |
  | **Reception** | 1 | `staging_receptionist` (ID 2) |
  | **Housekeeping** | 1 | `staging_housekeeper` (ID 6) |
- **Browser Driver Configuration**:
  - Selenium initialized with Chrome:
    ```python
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1600,1050")
    driver = webdriver.Chrome(options=chrome_opts)
    ```
  - Execution test verified: Chrome started successfully; browser version `156.0.8078.81`.
- **Screenshot Storage**:
  - Existing screenshots: `docs/screenshots/limitations_remediation/`, `docs/screenshots/remediation/`, `docs/screenshots/partial_inventory/`, `docs/screenshots_p23/`, `docs/screenshots_p3/`, `docs/screenshots_p4/`.
  - Target destination for 9-role acceptance: `docs/screenshots/roles_acceptance/`.

---

### 1.4 Environment and Services
- **Backend Service**:
  - Port: 8000 (`http://127.0.0.1:8000`)
  - Server start command: `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload`
  - Database: PostgreSQL on port 5432 (`hotel_erp_staging`) via `.env`.
- **Frontend Service**:
  - Port: 3000 (`http://localhost:3000`)
  - Working directory: `hotel-frontend/`
  - Server start command: `npm start` with environment variable `BROWSER=none` and `PORT=3000`
  - `hotel-frontend/src/apiConfig.js` resolves API base to `http://localhost:8000/api` when served from port 3000.

---

## 2. Logic Chain

1. **DEF-02 Root Cause & Resolution**:
   - *Observation*: `hotel-frontend/src/App.js` line 588 handles `admin`, `finance`, `waiter`, `cashier`, `kitchen`, `bar`, `reception`, `inventory`, `customer`, `housekeeping`. `hotel_manager` is omitted, causing `default:` unauthorized lockout.
   - *Logic*: Routing `hotel_manager` to `DashboardLayout` will grant access to operational modules (`dashboard`, `orders`, `menus`, `categories`, `tables`, `rooms`, `inventory`, `stocktaking`, `procurement`, `finance`, `reports`).
   - *Separation of Superuser Controls*: In `hotel-frontend/src/Sidebar.js`, the `ADMIN` menu group includes `users` and `settings`. Both backend endpoints (`apps/orders/views.py` line 1085 for settings, `apps/identity/views.py` line 136 for users) restrict access to `admin` / superuser. By adding `if (userRole === 'hotel_manager' && ['users', 'settings'].includes(item.id)) return false;` in `isItemVisible`, technical superuser controls are cleanly hidden from `hotel_manager`, while all operational management features remain accessible.

2. **DEF-04 Root Cause & Resolution**:
   - *Observation*: `App.js` line 603 renders `InventoryDashboard` directly for `role === 'inventory'`, bypassing `DashboardLayout` and `Sidebar`. `InventoryDashboard.js` contains 0 links to `StocktakeCenter` or `ProcurementCenter`.
   - *Logic*: In `Sidebar.js`, `stocktaking` and `procurement` are already defined under `OPERATIONS` with `pkg: 'inventory'`.
   - *Resolution*: Route `inventory` through `DashboardLayout` in `App.js`. In `Sidebar.js`, restrict visible items for `userRole === 'inventory'` to `inventory`, `stocktaking`, `procurement`, and `all_reports` (with only `report_inventory` child visible). Set the initial active tab to `'inventory'`. This gives inventory users complete access to Inventory Dashboard, Stocktake Center, Procurement Center (all 6 sub-desks), expiry alerts, batch quarantine, and stock transfers, without granting `admin` permissions or access to non-inventory modules.

3. **R5 Execution Architecture**:
   - *Observation*: All 9 roles have active test users in `hotel_erp_staging`. Chrome `156.0.8078.81` initializes cleanly with `--headless=new`. Token injection via `get_tokens_for_user(user)` reliably sets `access_token`, `refresh_token`, and `user` in `localStorage`, avoiding login brute-force lockouts.
   - *Logic*: A unified Selenium acceptance test suite can iterate through all 9 roles, authenticate each role via token injection, navigate to their designated landing dashboard, verify presence of role-specific UI elements, verify absence/inaccessibility of restricted modules, capture high-resolution screenshots to `docs/screenshots/roles_acceptance/`, and assert zero fatal console errors (`driver.get_log('browser')`).

---

## 3. Caveats

1. **Read-Only Scope**: This investigation did not modify any frontend or backend files. The proposed code adjustments are specified precisely for implementation agents.
2. **Database State**: Staging database `hotel_erp_staging` contains existing users with `pbkdf2_sha256$1000000$` hashes. User passwords should not be mass-reset to avoid disturbing existing accounts. Token injection via `get_tokens_for_user` is the safest, most reliable method for browser acceptance.
3. **Port Availability**: Prior to running Selenium browser verification, background tasks or external terminals must start the Django backend on port 8000 and the React dev server on port 3000.

---

## 4. Conclusion

1. **DEF-02 Fix**:
   - In `hotel-frontend/src/App.js`:
     - Add `case 'hotel_manager':` to the `DashboardLayout` branch in `switch (role)`.
     - In `DashboardLayout`, set the overview title dynamically to `"Hotel Operations Overview"` when `userData?.role === 'hotel_manager'`.
     - Guard `activeTab === 'users'` and `activeTab === 'settings'` to redirect to `dashboard` for `hotel_manager`.
   - In `hotel-frontend/src/Sidebar.js`:
     - In `isItemVisible`, hide `users` and `settings` when `userRole === 'hotel_manager'`.
   - In `hotel-frontend/src/UserManager.jsx`:
     - Add `'Hotel Manager'` to `getAvailableRoles()`.
     - Add badge styling for `'hotel_manager'`.

2. **DEF-04 Fix**:
   - In `hotel-frontend/src/App.js`:
     - Add `case 'inventory':` to the `DashboardLayout` branch in `switch (role)`.
     - Set default `activeTab` to `'inventory'` when `parsed.role === 'inventory'` or upon login.
     - In `DashboardLayout`, restrict tab rendering for `inventory` to `['inventory', 'stocktaking', 'procurement', 'report_inventory']` and `procurement_*`.
   - In `hotel-frontend/src/Sidebar.js`:
     - In `isItemVisible`, allow only `['inventory', 'stocktaking', 'procurement', 'all_reports']` when `userRole === 'inventory'`.
     - In `isChildVisible`, allow only `report_inventory` for `all_reports` when `userRole === 'inventory'`.

3. **R5 Real-Browser Acceptance Specification**:
   - **Runner**: Python script using Selenium WebDriver with headless Chrome.
   - **Target Matrix**:
     1. `Admin` (`staging_admin`): Full dashboard, settings, users, all operations.
     2. `Hotel Manager` (`manager_proc2`): Operational dashboard, inventory, procurement, rooms, F&B, finance, reports; verified exclusion of `settings` and `users`.
     3. `Inventory` (`staging_controller` / `remed_staff_a`): Inventory Control, Stocktake Center, Procurement Center (all 6 sub-desks), inventory report; verified exclusion of POS/Rooms/Finance/Admin.
     4. `Kitchen` (`staging_chef`): Kitchen Display System (`KitchenDashboard`).
     5. `Bar` (`staging_bartender`): Bar Display System (`BarDashboard`).
     6. `Waiter` (`staging_waiter`): Order & table service (`WaiterDashboard`).
     7. `Cashier` (`staging_cashier`): POS billing & shift settlement (`CashierDashboard`).
     8. `Reception` (`staging_receptionist`): Front desk console, check-in/out, bookings (`ReceptionDashboard`).
     9. `Housekeeping` (`staging_housekeeper`): Room cleaning & minibar operations (`HousekeepingDashboard`).
   - **Screenshots**: Saved to `docs/screenshots/roles_acceptance/<role>_<screen>.png`.
   - **Console Health**: Validate `driver.get_log('browser')` has 0 `SEVERE` errors.

---

## 5. Verification Method

### 5.1 Independent Code Inspection
- Inspect `hotel-frontend/src/App.js` around line 588 to verify `case 'hotel_manager':` and `case 'inventory':` integration.
- Inspect `hotel-frontend/src/Sidebar.js` around line 207 to verify sidebar visibility filtering for `hotel_manager` and `inventory`.
- Inspect `hotel-frontend/src/UserManager.jsx` around line 175 to verify `Hotel Manager` role inclusion.

### 5.2 Server Startup Commands
1. Start Backend:
   ```powershell
   .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
   ```
2. Start Frontend:
   ```powershell
   Set-Location "hotel-frontend"
   $env:BROWSER="none"
   $env:PORT="3000"
   npm start
   ```

### 5.3 Automated Real-Browser Acceptance Script
Run the Selenium acceptance test script across all 9 roles:
```powershell
.venv\Scripts\python.exe scratch/test_browser_9_roles_acceptance.py
```
Expected output:
- 9 roles successfully authenticated via JWT injection.
- Expected dashboard rendered for each role.
- Navigation to authorized modules verified.
- Access to restricted modules blocked.
- 9+ screenshots generated in `docs/screenshots/roles_acceptance/`.
- 0 fatal JavaScript console errors.
