# Milestone 1 Empirical Challenge & Verification Report (DEF-01, DEF-02, DEF-03)

**Agent:** Challenger M1-1 (Critic / Specialist)  
**State Folder:** `.agents/teamwork/challenger_m1_1/`  
**Milestone:** Milestone 1 — Targeted RBAC Architecture & Frontend Corrections  
**Date:** 2026-11-09  
**Verdict:** **APPROVE**  

---

## 1. Observation

All tests were executed directly in the environment using `.venv\Scripts\python.exe` and `npm test` against the staging database and test suites.

### 1.1 DEF-01: Model Choices, Validation, and Serializers
- **File Checked:** `users/models.py:31-44`
  - Observation: `HOTEL_MANAGER = "hotel_manager"` is defined in `User` class constants and included in `ROLE_CHOICES`: `(HOTEL_MANAGER, "Hotel Manager")`.
- **Model Clean Execution (`u.full_clean()`):**
  - Command:
    ```powershell
    .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); u12 = User.objects.get(id=12); u12.full_clean(); u16 = User.objects.get(id=16); u16.full_clean(); print('OK')"
    ```
  - Output: `OK` (0 validation errors for user 12 `manager_proc2` [role: `hotel_manager`] and user 16 `sec_ops_manager` [role: `hotel_manager`]).
- **UserSerializer Validation:**
  - Valid Role (`hotel_manager`):
    `UserSerializer(data={'username': 'test_hm', 'email': 'test_hm@example.com', 'role': 'hotel_manager'}).is_valid()` returned `True`.
  - Invalid Role (`manager`):
    `UserSerializer(data={'username': 'test_m', 'email': 'test_m@example.com', 'role': 'manager'}).is_valid()` returned `False`.
    Verbatim error: `{'role': [ErrorDetail(string='"manager" is not a valid choice.', code='invalid_choice')]}`.
  - Invalid Role (`attacker`):
    `UserSerializer(data={'username': 'test_a', 'email': 'test_a@example.com', 'role': 'attacker'}).is_valid()` returned `False`.
    Verbatim error: `{'role': [ErrorDetail(string='"attacker" is not a valid choice.', code='invalid_choice')]}`.

---

### 1.2 DEF-02: Hotel Manager API Access & User Administration Restriction
Using DRF `APIClient` authenticated as User 12 (`manager_proc2`, role=`hotel_manager`):
- **GET `/users/dashboard-stats/`:**
  - Status Code: **HTTP 200 OK**
  - Enforced Permission: `IsHotelManagerOrAdmin` (`users/permissions.py:21`)
- **GET `/users/orders/`:**
  - Status Code: **HTTP 200 OK**
  - View: `AdminOrdersView` (`apps/orders/views.py:1497`)
- **GET `/users/reports/operations-timing/`:**
  - Status Code: **HTTP 200 OK**
  - View: `OperationsTimingReportView` (`apps/reporting/views.py:735`)
- **User Administration Isolation:**
  - DRF URL Mapping Inspection:
    `core/urls.py` mounts `users.urls` at `path("api/users/", ...)` and `path("users/", ...)`.
    Inside `apps/identity/urls.py`, `DefaultRouter` registers `r"users"` to `UserViewSet` (`permission_classes = [IsHotelAdmin]`).
  - Calling user administration endpoints as `manager_proc2`:
    - `GET /users/users/` -> **HTTP 403 Forbidden** (`{"detail": "Hotel administrator access is required."}`)
    - `GET /api/users/users/` -> **HTTP 403 Forbidden** (`{"detail": "Hotel administrator access is required."}`)
    - `GET /api/v1/users/` -> **HTTP 403 Forbidden** (`{"detail": "Hotel administrator access is required."}`)
    - `POST /users/users/` (privilege escalation attempt) -> **HTTP 403 Forbidden**
    - `PATCH /users/users/12/` (`is_superuser=True` attempt) -> **HTTP 403 Forbidden**
  - Calling user administration as Admin (`u_admin`):
    - `GET /api/v1/users/` -> **HTTP 200 OK**
    - `GET /users/users/` -> **HTTP 200 OK**
    - `GET /api/users/users/` -> **HTTP 200 OK**
  - Negative Check on Waiter Role:
    - Calling `GET /users/dashboard-stats/` as regular waiter -> **HTTP 403 Forbidden** (`{"detail": "Hotel manager or administrator access is required."}`).

---

### 1.3 DEF-03: Dining Supervisor Views & Waiter Isolation
Empirical tests executed against active orders via DRF `APIClient`:
1. **`MarkOrderItemServedView` (`/users/orders/items/<id>/mark-served/`):**
   - Unassigned Waiter B attempting to serve Waiter A's item:
     - Status: **HTTP 403 Forbidden**
     - Verbatim message: `{"error": "You are not authorized to mark items served for another waiter's order."}`
   - Kitchen User attempting to serve item:
     - Status: **HTTP 403 Forbidden** (blocked by `IsWaiterOrAdmin` permission class)
   - Hotel Manager (User 12) serving item:
     - Status: **HTTP 200 OK**
     - Verbatim message: `{"message": "Item marked as served.", "item_id": 61, "order_id": 42, "order_status": "served"}`
2. **`MarkOrderServedView` (`/users/orders/<id>/mark-served/`):**
   - Waiter B attempting to serve Waiter A's entire order:
     - Status: **HTTP 403 Forbidden**
     - Verbatim message: `{"error": "You are not authorized to mark another waiter's order as served."}`
   - Hotel Manager (User 12) serving entire order:
     - Status: **HTTP 200 OK**
     - Verbatim message: `{"message": "Order marked as served!"}`
3. **`RequestBillView` (`/users/orders/<id>/request-bill/`):**
   - Waiter B attempting to request bill for Waiter A's order:
     - Status: **HTTP 403 Forbidden**
     - Verbatim message: `{"error": "You are not authorized to request a bill for another waiter's order."}`
   - Hotel Manager (User 12) requesting bill:
     - Status: **HTTP 200 OK**
     - Verbatim message: `{"message": "Bill request sent successfully!", "order_id": 42, "status": "bill_requested", "bill_prepared": false}`
4. **`RecordCashHandoverView` (`/users/orders/<id>/cash-handover/`):**
   - Waiter B attempting to record cash handover for Waiter A's order:
     - Status: **HTTP 403 Forbidden**
     - Verbatim message: `{"error": "You are not authorized to collect cash for another waiter's order."}`
   - Hotel Manager (User 12) recording cash handover:
     - Status: **HTTP 201 Created**
     - Verbatim message: `{"message": "Cash collection of ETB 115.0 recorded. Please hand over the collected cash to the cashier.", "handover_id": ..., "amount": 115.0, "tip_amount": 0.0, "status": "pending_handover"}`

---

### 1.4 Automated Regression Test Suite Executions
- **Suite 1: `apps.orders.tests.test_bill_request_handover`**
  - Command: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover --keepdb`
  - Output: `Ran 13 tests in 109.016s ... OK` (13 passed, 0 failed, 0 errors).
- **Suite 2: `users.test_milestone2_workflows`**
  - Command: `.venv\Scripts\python.exe manage.py test users.test_milestone2_workflows --keepdb`
  - Output: `Ran 4 tests in 45.031s ... OK` (4 passed, 0 failed, 0 errors).
- **Suite 3: `hotel-frontend/src/apiClient.test.js`**
  - Command: `npm test -- --watchAll=false src/apiClient.test.js`
  - Output: `Test Suites: 1 passed, 1 total; Tests: 12 passed, 12 total` (12 passed, 0 failed).
- **Suite 4: Standalone Empirical Challenge Suite (`scratch/test_challenge_m1.py`)**
  - Command: `.venv\Scripts\python.exe scratch\test_challenge_m1.py`
  - Output: `ALL EMPIRICAL CHALLENGE CHECKS & STRESS TESTS PASSED!` (15 checks verified).

---

## 2. Logic Chain

1. **DEF-01 Resolution Verified:**
   - Observations 1.1 confirm `User.ROLE_CHOICES` includes `("hotel_manager", "Hotel Manager")`.
   - Calling `u.full_clean()` on user 12 and user 16 proves existing staging database accounts are compliant with Django validation without errors.
   - Serializer tests show `UserSerializer` validates `hotel_manager` payloads while rejecting legacy strings (`manager`) and unlisted roles (`attacker`), ensuring data integrity at the API boundary.

2. **DEF-02 Resolution Verified:**
   - Observations 1.2 demonstrate that `hotel_manager` (user 12) successfully accesses operational statistics (`/users/dashboard-stats/`), order management queues (`/users/orders/`), and timing metrics (`/users/reports/operations-timing/`) with HTTP 200.
   - Concurrently, user administration remains strictly guarded under `IsHotelAdmin`: user 12 is blocked with HTTP 403 from listing users (`/api/users/users/`, `/users/users/`, `/api/v1/users/`), creating new accounts (`POST`), or escalating permissions (`PATCH`).
   - Regular staff (e.g., waiters) are blocked from manager dashboard statistics (HTTP 403), proving granular least-privilege scoping.

3. **DEF-03 Resolution Verified:**
   - Observations 1.3 show that `hotel_manager` acts as a dining floor supervisor across all 4 dining workflow endpoints (`MarkOrderItemServedView`, `MarkOrderServedView`, `RequestBillView`, `RecordCashHandoverView`), overriding specific waiter assignments.
   - Waiter isolation is intact: an unassigned waiter attempting to perform supervisory actions or tamper with another waiter's order is blocked with HTTP 403.
   - Non-dining staff (e.g., kitchen users) are denied dining floor actions by `IsWaiterOrAdmin` with HTTP 403.

4. **Adversarial Edge Cases Verified:**
   - State machine guards in `hotel/models.py` and `apps/orders/views.py` prevent invalid transitions:
     - Orders with unready/pending items cannot be marked served (HTTP 400).
     - Non-served orders cannot have bills requested (HTTP 400).
     - Paid orders cannot accept cash handovers (HTTP 400).
   - Under single-hotel stocktaking permissions (DEF-05), `hotel_manager` possesses global property-wide stock access, whereas departmental staff (`waiter`) attempting to access unassigned locations (`custodian IS NULL`) are rejected (`has_permission == False`).

---

## 3. Caveats

1. **Routing Path Distinction:** In DRF, `path("api/users/", include("users.urls"))` renders the `DefaultRouter` root index at `/api/users/` (HTTP 200 schema list). The user administration viewset itself is at `/api/users/users/`, `/users/users/`, and `/api/v1/users/`, where `hotel_manager` is strictly forbidden (HTTP 403).
2. **Circular Import Initialization:** Standalone test scripts importing `users.views` or `apps.orders.views` must import `users.urls` first to initialize the legacy compatibility facade before accessing view classes.

---

## 4. Conclusion

The implementation of Milestone 1 (DEF-01, DEF-02, DEF-03) meets all specification requirements and security constraints. No regressions, permission leaks, or unauthorized bypasses were discovered during empirical testing.

**VERDICT: APPROVE**

---

## 5. Verification Method

To independently reproduce and verify this assessment:

1. **Execute Empirical Challenge & Adversarial Stress Suite:**
   ```powershell
   .venv\Scripts\python.exe scratch\test_challenge_m1.py
   ```
   *Expected Output:*
   ```
   === DEF-01: Model & Serializer Verification ===
   [PASS] User.ROLE_CHOICES contains ('hotel_manager', 'Hotel Manager')
   [PASS] User 12 (manager_proc2) role=hotel_manager passed full_clean()
   [PASS] User 16 (sec_ops_manager) role=hotel_manager passed full_clean()
   [PASS] UserSerializer valid with role='hotel_manager'
   [PASS] UserSerializer rejected invalid role='manager'
   [PASS] UserSerializer rejected invalid role='attacker'

   === DEF-02: Hotel Manager API Access & User Administration Block ===
   GET /users/dashboard-stats/ -> HTTP 200
   GET /users/orders/ -> HTTP 200
   GET /users/reports/operations-timing/ -> HTTP 200
   GET /users/users/ (UserViewSet) -> HTTP 403
   GET /api/users/users/ (UserViewSet) -> HTTP 403
   GET /api/v1/users/ (UserViewSet) -> HTTP 403
   Waiter GET /users/dashboard-stats/ -> HTTP 403

   === DEF-03: Dining Supervisor Views & Waiter Isolation ===
   Waiter B mark-item-served for Waiter A's order -> HTTP 403
   Kitchen user mark-item-served -> HTTP 403
   Hotel Manager mark-item-served -> HTTP 200
   Waiter B mark-order-served for Waiter A's order -> HTTP 403
   Hotel Manager mark-order-served -> HTTP 200
   Waiter B request-bill for Waiter A's order -> HTTP 403
   Hotel Manager request-bill -> HTTP 200
   Waiter B cash-handover for Waiter A's order -> HTTP 403
   Hotel Manager cash-handover -> HTTP 201

   === ADVERSARIAL STRESS TESTING: Edge Cases & Boundary Conditions ===
   ...
   ALL EMPIRICAL CHALLENGE CHECKS & STRESS TESTS PASSED!
   ```

2. **Execute Dining Bill & Handover Django Test Suite:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover --keepdb
   ```
   *Expected Output:* `Ran 13 tests ... OK`

3. **Execute Frontend Test Suite:**
   ```powershell
   cd hotel-frontend; npm test -- --watchAll=false src/apiClient.test.js
   ```
   *Expected Output:* `Test Suites: 1 passed, 1 total; Tests: 12 passed, 12 total`
