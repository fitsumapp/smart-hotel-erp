# Milestone 1 Adversarial Review Report: RBAC Architecture Corrections

**State Folder:** `.agents/teamwork/reviewer_m1_2/`  
**Milestone:** Milestone 1 — Targeted RBAC Architecture & Frontend Corrections (DEF-01 through DEF-06)  
**Author:** reviewer_m1_2 (Adversarial Reviewer & Critic)  
**Date:** 2026-11-09  
**Verdict:** **REQUEST_CHANGES**

---

## Review & Challenge Summary

An adversarial examination of Milestone 1 changes was conducted across the 6 defect specifications (DEF-01 through DEF-06). Automated tests were executed independently, and empirical penetration probes were executed against all modified models, serializers, permissions, and viewsets.

While DEF-01, DEF-02, DEF-04, and DEF-05 exhibit strong security posture and robust defensive controls, a **CRITICAL PERMISSION LEAK** was discovered under **DEF-03**:
Worker M1 expanded `users.permissions.IsFinanceStaff` to include `"hotel_manager"`. Because `PayrollEntryViewSet` relies solely on `IsFinanceStaff` without secondary method-level role guards, an operational `hotel_manager` account can create payroll records and trigger automated double-entry postings directly into the General Ledger (`_post_payroll_gl` -> `post_journal_entry`). This breaches the fundamental architectural separation between operational supervisory authority and financial ledger authority mandated by `ORIGINAL_REQUEST.md` and `PROJECT.md`.

In addition, a **MAJOR ARCHITECTURAL DEFECT** was uncovered: a circular import hazard between `apps.identity.serializers` and `users.serializers` that causes fatal `ImportError` exceptions when importing `UserSerializer` directly from its defining module.

---

## 1. Observation

1. **Automated Test Suite Execution:**
   - Ran `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows --keepdb`.
   - Result: `Ran 17 tests in 107.064s ... OK`. 0 failures, 0 errors.

2. **DEF-01 Probing (`users/models.py`, `apps/identity/serializers.py`, `0009_alter_user_role.py`):**
   - Testing arbitrary strings (`"manager"`, `"HOTEL_MANAGER"`, `"hotel_manager "`, `""`, `None`) on `UserSerializer` resulted in `is_valid() == False` with DRF `code='invalid_choice'`.
   - Model-level `u.full_clean()` rejected invalid roles with `ValidationError: {'role': ["Value '...' is not a valid choice."]}`.
   - Postgres schema inspection revealed column `users_user.role` is `character varying(20)`. The string `"hotel_manager"` is 13 characters. Reversing migration `0009` to `0008` causes no database-level data truncation, but causes Django model validation to fail on existing accounts with `role="hotel_manager"`.
   - Direct import probe: Executing `.venv\Scripts\python.exe -c "from apps.identity.serializers import UserSerializer"` resulted in:
     `ImportError: cannot import name 'PublicRegistrationSerializer' from partially initialized module 'apps.identity.serializers' (most likely due to a circular import) (apps\identity\serializers.py)`
     Root cause: `apps/identity/serializers.py:2` executes `from users.serializers import *`, while `users/serializers.py:87` executes `from apps.identity.serializers import PublicRegistrationSerializer, UserSerializer`.

3. **DEF-02 Probing (Isolation of Technical Controls from `hotel_manager`):**
   - Direct API calls authenticated as `hotel_manager` (User ID 12):
     - `GET /api/users/users/` -> `403 Forbidden`
     - `POST /api/users/users/` -> `403 Forbidden`
     - `DELETE /users/users/12/` -> `403 Forbidden`
     - `POST /users/settings/` -> `403 Forbidden` (`{'error': 'Only admins can modify system settings.'}`)
   - In `hotel-frontend/src/App.js` lines 422-426, `useEffect` detects `role === 'hotel_manager'` and resets `activeTab` to `'dashboard'` if set to `'users'` or `'settings'`.
   - In `hotel-frontend/src/Sidebar.js:213`, `['users', 'settings']` are filtered out for `hotel_manager`.

4. **DEF-03 Probing (Cash Handover vs Financial Accounting Privileges):**
   - In `apps/orders/views.py`:
     - `RecordCashHandoverView` permits `hotel_manager` to record cash collected by waiters.
     - `ConfirmCashHandoverView` enforces `permission_classes = [IsCashierOrAdmin]`. Authenticated hotel managers are blocked from confirming cash handovers or settling cashier registers.
   - In `users/permissions.py:86`, `IsFinanceStaff` was modified:
     ```python
     class IsFinanceStaff(BasePermission):
         message = "Finance or hotel administrator access is required."
         def has_permission(self, request, view):
             user = request.user
             return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or getattr(user, "role", "") in {"admin", "finance", "hotel_manager"}))
     ```
   - In `apps/finance/views.py:388`, `PayrollEntryViewSet` enforces `permission_classes = [IsFinanceStaff]`.
   - Empirical exploit test: User 12 (`role="hotel_manager"`) executed:
     `POST /users/finance/payroll/` with draft payroll data -> HTTP 201 Created (`{'id': 1, 'employee_name': 'Test Emp', 'status': 'draft', ...}`).
   - When executed with `status="paid"`, `PayrollEntryViewSet.perform_create` calls `self._post_payroll_gl(entry)`, invoking `apps.finance.services.post_journal_entry` to write financial double-entry records to General Ledger accounts.

5. **DEF-04 Probing (Inventory Role Boundary Enforcement):**
   - In `hotel-frontend/src/App.js` lines 427-432, `useEffect` detects `role === 'inventory'` and strictly locks `activeTab` to `['inventory', 'stocktaking', 'procurement', 'report_inventory']` or tabs beginning with `procurement_`. Attempts to navigate to finance, cashier, F&B, rooms, users, or settings are immediately reverted to `'inventory'`.
   - Direct API calls authenticated as `inventory`:
     - `GET /users/finance/journal-entries/` -> `403 Forbidden`
     - `POST /users/finance/accounts/` -> `403 Forbidden`
     - `POST /users/orders/1/confirm-handover/` -> `403 Forbidden`
     - `GET /users/users/` -> `403 Forbidden`
     - `POST /users/settings/` -> `403 Forbidden`

6. **DEF-05 Probing (Unassigned Stock Locations & Stocktake SoD):**
   - Stock location created with `custodian = None`.
   - `HasStocktakeLocationPermission`:
     - Waiter: `has_permission == False`, `has_object_permission == False`.
     - Kitchen: `has_permission == False`, `has_object_permission == False`.
     - Hotel Manager: `has_permission == True`, `has_object_permission == True`.
     - Inventory: `has_permission == True`, `has_object_permission == True`.
   - Direct API calls to `POST /users/stocktaking/sessions/` for unassigned location:
     - Waiter -> `403 Forbidden`
     - Kitchen -> `403 Forbidden`
   - Separation of Duties (SoD) test:
     - Session created and counted by User 12 (`hotel_manager`).
     - Self-approval attempt: `approve_stocktake_session(session_id=sess.id, supervisor=u12)` -> raised `PermissionDenied: "Separation of duties violation: count submitters cannot approve their own stocktake."`
     - Attempt with `emergency_self_approval=True` by User 12 -> raised `PermissionDenied` (only superusers can invoke emergency override).
     - Approval by separate administrator (`staging_admin`) -> Succeeded (`status: "approved"`).
     - Attempted deletion of approved session: `DELETE /users/stocktaking/sessions/{sess.id}/` -> HTTP 400 Bad Request: `{"error": "Cannot delete stocktake session in 'approved' status. Historical inventory audits cannot be deleted. Use the cancel action instead."}`.

---

## 2. Logic Chain

1. **Integrity & Legitimacy Verification:**
   - Source inspection confirms that test fixtures and test logic in `apps/orders/tests/test_bill_request_handover.py` and `users/test_milestone2_workflows.py` are genuine and un-fabricated.
   - Model validation and serializer validation execute standard Django/DRF pipelines with zero dummy mocks.
   - Therefore, there are NO integrity violations or cheating patterns.

2. **Analysis of DEF-03 Permission Leak:**
   - `ORIGINAL_REQUEST.md` (R1 & R2) and `PROJECT.md` mandate:
     *"Distinguish operational supervisor authority from financial approval authority and technical/security admin"* and *"avoiding unintended financial/technical permissions."*
   - Adding `"hotel_manager"` to `IsFinanceStaff` in `users/permissions.py:86` was intended to support operational reporting or procurement views, but `IsFinanceStaff` is the primary guard for the entire `apps.finance` API.
   - While `JournalEntryViewSet`, `AccountViewSet`, and `ExpenseTransactionViewSet` include defensive method-level role checks, `PayrollEntryViewSet` relies exclusively on `IsFinanceStaff`.
   - Consequently, any user with `role="hotel_manager"` is permitted to create payroll entries and trigger General Ledger journal postings.
   - This represents an over-permissive privilege escalation violating the core principle of least privilege and Separation of Duties between operational management and financial accounting.

3. **Analysis of Serializer Circular Import:**
   - In `apps/identity/serializers.py`, line 2 imports `*` from `users.serializers`.
   - In `users/serializers.py`, line 87 imports `PublicRegistrationSerializer, UserSerializer` from `apps.identity.serializers`.
   - This circular import succeeds only if `users.serializers` happens to be evaluated first. Any module or test importing `apps.identity.serializers` first crashes immediately.
   - This fragility must be resolved before proceeding to Milestone 2 automated regression runs.

---

## 3. Caveats

1. Real-browser Selenium acceptance tests across all 9 roles were not run during this code-level adversarial review; they are explicitly slated for Milestone 3.
2. In `hotel/procurement.py:approve_supplier_invoice`, the underlying service function relies on the caller view for authentication and role validation, but `SupplierInvoiceViewSet` currently uses `permission_classes = [IsAuthenticated]`. While supplier invoices undergo 3-way matching, invoice approval permissions should be audited in Milestone 2.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Worker M1 must address two findings:
1. **Critical (DEF-03):** Revert `users/permissions.py:86` (`IsFinanceStaff`) so that `hotel_manager` is NOT granted finance staff permissions. Operational endpoints requiring manager access must use specific operational permission classes (`IsHotelManagerOrAdmin` or `IsProcurementOrFinanceOperator`).
2. **Major:** Remove the circular import dependency between `apps/identity/serializers.py` and `users/serializers.py`.

---

## 5. Verification Method

To reproduce and verify the critical finding and the circular import:

1. **Reproduce DEF-03 Financial Permission Leak:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from rest_framework.test import APIClient; from django.contrib.auth import get_user_model; User = get_user_model(); u12 = User.objects.get(id=12); client = APIClient(); client.force_authenticate(user=u12); r = client.post('/users/finance/payroll/', {'employee_name': 'Leak Test', 'department': 'kitchen', 'role_title': 'Cook', 'basic_salary': '1000.00', 'gross_pay': '1000.00', 'net_pay': '900.00', 'pay_period_start': '2026-11-01', 'pay_period_end': '2026-11-30', 'status': 'draft'}, format='json'); print('Status:', r.status_code); from hotel.models import PayrollEntry; PayrollEntry.objects.filter(employee_name='Leak Test').delete()"
   ```
   *Expected Output after fix:* `Status: 403` (Currently outputs `Status: 201`).

2. **Reproduce Circular Import:**
   ```powershell
   .venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from apps.identity.serializers import UserSerializer; print(UserSerializer)"
   ```
   *Current Output:* `ImportError: cannot import name 'PublicRegistrationSerializer' from partially initialized module 'apps.identity.serializers'`
   *Expected Output after fix:* `<class 'apps.identity.serializers.UserSerializer'>`
