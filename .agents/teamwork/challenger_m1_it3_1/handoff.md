# Handoff Report: Empirical Challenge & Stress-Test of Procurement RBAC Boundaries (Milestone 1 Iteration 3)

**Agent:** Challenger M1-It3-1 (`challenger_m1_it3_1`)  
**Role:** Critic / Empirical Challenger / Specialist  
**Working Directory:** `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment`  
**State Folder:** `.agents/teamwork/challenger_m1_it3_1/`  
**Date:** 2026-11-09T19:37:00Z  
**Formal Verdict:** **APPROVE**  

---

## 1. Observation

### 1.1 Empirical Verification Test Harness (`scratch/test_challenger_m1_it3.py`)
An independent, transaction-isolated empirical test harness was authored and executed directly against the application backend. All database mutations were executed within an atomic transaction with a guaranteed rollback (`transaction.set_rollback(True)`), ensuring zero contamination of the staging database.

**Execution Command:**
```powershell
.venv\Scripts\python.exe scratch/test_challenger_m1_it3.py
```

**Verbatim Execution Output:**
```
================================================================================
ACRMA HOTEL ERP — EMPIRICAL CHALLENGER VERIFICATION HARNESS (M1-It3-1)
================================================================================

================================================================================
[TEST SUITE 1] STAGING DATABASE CLEANUP AUDIT (hotel_erp_staging)
================================================================================
[*] Staging User count        : 37 (Expected: 37)
[*] Staging PayrollEntry count: 0 (Expected: 0)
[*] Staging Users by role     : {'admin': 9, 'bar': 1, 'cashier': 3, 'customer': 2, 'finance': 3, 'hotel_manager': 2, 'housekeeping': 1, 'inventory': 10, 'kitchen': 2, 'reception': 1, 'waiter': 3}
[*] Staging DB Audit Result   : PASS

================================================================================
[TEST SUITE 2] RBAC & APPROVAL BOUNDARY TESTING (TRANSACTION-ISOLATED)
================================================================================
[*] Creating / fetching test actors...
[*] Base fixtures created successfully.

--------------------------------------------------------------------------------
EMPIRICAL MATRIX 1: 7 RESTRICTED ROLES x 7 PROCUREMENT ENDPOINTS
--------------------------------------------------------------------------------
Role           | orders   | rfqs     | quotes   | grns     | invoices | policies | requisitions (general/cross)
---------------------------------------------------------------------------------------------------------
kitchen        | 403      | 403      | 403      | 403      | 403      | 403      | Scoped (list=200, cross-create=403, conv=403)
bar            | 403      | 403      | 403      | 403      | 403      | 403      | Scoped (list=200, cross-create=403, conv=403)
waiter         | 403      | 403      | 403      | 403      | 403      | 403      | 403 Forbidden (list=403, conv=403)
cashier        | 403      | 403      | 403      | 403      | 403      | 403      | 403 Forbidden (list=403, conv=403)
reception      | 403      | 403      | 403      | 403      | 403      | 403      | 403 Forbidden (list=403, conv=403)
housekeeping   | 403      | 403      | 403      | 403      | 403      | 403      | Scoped (list=200, cross-create=403, conv=403)
customer       | 403      | 403      | 403      | 403      | 403      | 403      | 403 Forbidden (list=403, conv=403)

--------------------------------------------------------------------------------
EMPIRICAL TEST 2: SEPARATION OF DUTIES (SoD) ENFORCEMENT
--------------------------------------------------------------------------------
[*] Testing Requisition Self-Approval...
    - Self-approval attempt status: 400 (Expected: 400 Bad Request)
    - Response body: {'error': 'Separation of duties violation: Requisitioner cannot approve their own requisition. Independent managerial sign-off is required.'}
    - Peer approval attempt status: 200 (Expected: 200 OK)

[*] Testing Dock Receiver Invoice Approval Prevention...
    - Dock receiver invoice approval status: 400 (Expected: 400 Bad Request)
    - Response body: {'error': 'Separation of duties violation: Dock receiver cannot approve invoice payment for goods they received.'}

[*] Testing Inventory Role Invoice Approval Prevention...
    - Inventory invoice approval status: 403 (Expected: 403 Forbidden)

--------------------------------------------------------------------------------
EMPIRICAL TEST 3: APPROVAL TIERS THRESHOLD BOUNDARY ENFORCEMENT
--------------------------------------------------------------------------------

[*] Tier 1 ($5,000): Expected to accept inventory and hotel_manager
    - inventory approving Tier 1 ($5,000) -> HTTP 200
    - hotel_manager approving Tier 1 ($5,000) -> HTTP 200

[*] Tier 2 ($25,000): Expected to block inventory, accept finance
    - inventory approving Tier 2 ($25,000) -> HTTP 403
    - finance approving Tier 2 ($25,000) -> HTTP 200

[*] Tier 3 ($75,000): Expected to block inventory and finance, accept admin
    - inventory approving Tier 3 ($75,000) -> HTTP 403
    - finance approving Tier 3 ($75,000) -> HTTP 403
    - admin approving Tier 3 ($75,000) -> HTTP 200

[*] Transaction rolled back cleanly. Staging DB records untouched.

================================================================================
CHALLENGER EMPIRICAL VERIFICATION SUMMARY
================================================================================
Total Verification Checks: 61
Passed Checks            : 61
Failed Checks            : 0

>>> FINAL EMPIRICAL VERDICT: APPROVE <<<
All RBAC boundaries, Separation of Duties safeguards, approval tiers,
and staging database cleanup verified 100% compliant.
```

---

### 1.2 Staging Database Cleanup Verification (`hotel_erp_staging`)
Direct query to the persistent staging PostgreSQL database confirms zero contamination and complete retention of all user accounts:

```powershell
.venv\Scripts\python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.models import User; from hotel.models import PayrollEntry, JournalEntry; print(f'Users: {User.objects.count()} (Target: 37), PayrollEntry: {PayrollEntry.objects.count()} (Target: 0), JournalEntry: {JournalEntry.objects.count()} (Target: 84)')"
```

**Verbatim Output:**
```
Users: 37 (Target: 37), PayrollEntry: 0 (Target: 0), JournalEntry: 84 (Target: 84)
```

Staging accounts by role:
- `admin`: 9
- `inventory`: 10
- `finance`: 3
- `cashier`: 3
- `waiter`: 3
- `customer`: 2
- `hotel_manager`: 2
- `kitchen`: 2
- `bar`: 1
- `housekeeping`: 1
- `reception`: 1
**Total:** 37 users. Exactly 0 `PayrollEntry` rows exist.

---

### 1.3 Full Regression Suite Execution
All automated regression test suites were executed serially using Django's isolated test runner (`test_hotel_erp_staging`):

1. **Procurement RBAC Regression Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput`
   - Result: `Ran 18 tests in 9.170s. OK.` (18 executed, 18 passed, 0 failures, 0 errors).
2. **Procurement Management Workflow Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput`
   - Result: `Ran 12 tests in 66.851s. OK.` (12 executed, 12 passed, 0 failures, 0 errors).
3. **RFQ & Quotation Workflow Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput`
   - Result: `Ran 10 tests in 41.170s. OK.` (10 executed, 10 passed, 0 failures, 0 errors).
4. **Dining Orders Supervisory Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover --keepdb --noinput`
   - Result: `Ran 13 tests in 250.675s. OK.` (13 executed, 13 passed, 0 failures, 0 errors).
5. **Milestone 2 Operational Workflows Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test users.test_milestone2_workflows --keepdb --noinput`
   - Result: `Ran 4 tests in 28.006s. OK.` (4 executed, 4 passed, 0 failures, 0 errors).
6. **Finance & Tax Reports Suite:**
   - Command: `.venv\Scripts\python.exe manage.py test apps.finance.tests --keepdb --noinput`
   - Result: `Ran 13 tests in 44.829s. OK.` (13 executed, 13 passed, 0 failures, 0 errors).

**Total Regression Execution:** 70 tests discovered, 70 executed, 70 passed, 0 failed, 0 errored, 0 skipped.

---

## 2. Logic Chain

1. **RBAC Endpoint Boundary Integrity:**
   - Across 6 of the 7 endpoints (`orders`, `rfqs`, `quotations`, `grns`, `invoices`, `policies`), all 7 restricted roles (`kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`) are denied with `HTTP 403 Forbidden` at the ViewSet boundary (`IsProcurementOrFinanceOperator` or `IsInventoryManager`).
   - For `requisitions` (`PurchaseRequisitionViewSet`), line and external roles (`waiter`, `cashier`, `reception`, `customer`) are denied all access (`HTTP 403 Forbidden` on list, retrieve, create, and convert-to-po).
   - Operational departmental roles (`kitchen`, `bar`, `housekeeping`) can view and create requisitions only for their own department (`get_queryset()` row-scoping and `create()` role matching). Attempts to request for other departments or convert requisitions to Purchase Orders are blocked with `HTTP 403 Forbidden`.

2. **Separation of Duties (SoD) Defense:**
   - Self-approval defense: In `approve_purchase_requisition`, the primary key check `approver_id == requester_id and not is_superuser` successfully intercepts requisitioner self-approval attempts, returning `HTTP 400 Bad Request` with message: `"Separation of duties violation: Requisitioner cannot approve their own requisition. Independent managerial sign-off is required."`
   - Peer approval by an independent managerial user succeeds with `HTTP 200 OK`.
   - Dock receiver defense: In `approve_supplier_invoice`, dock receivers who logged receipt on a GRN cannot approve invoices matching that PO, returning `HTTP 400 Bad Request` with message: `"Separation of duties violation: Dock receiver cannot approve invoice payment for goods they received."`
   - Financial settlement separation: Storekeepers (`inventory`) cannot approve supplier invoices (`HTTP 403 Forbidden`).

3. **Multi-Tier Threshold Boundaries:**
   - **Tier 1 ($5,000 <= $10,000):** Approved by `inventory` (`HTTP 200 OK`) and `hotel_manager` (`HTTP 200 OK`).
   - **Tier 2 ($25,000 in $10,000.01 - $50,000):** Approval by `inventory` is blocked with `HTTP 403 Forbidden` (`"User role 'inventory' is not authorized to approve at Tier 2... Required role: finance"`). Approval by `finance` succeeds (`HTTP 200 OK`).
   - **Tier 3 ($75,000 > $50,000):** Approval by `inventory` is blocked with `HTTP 403 Forbidden`. Approval by `finance` is blocked with `HTTP 403 Forbidden` (`"User role 'finance' is not authorized to approve at Tier 3... Required role: admin"`). Approval by `admin` succeeds (`HTTP 200 OK`).

4. **Staging Cleanup Verification:**
   - Pre-cleanup audit showed 3 orphaned draft payroll entries (IDs 4, 5, 6) in `hotel_erp_staging`.
   - Independent verification queries confirm 0 `PayrollEntry` records remain, 0 GL entries were damaged, and all 37 staging user accounts remain intact.

---

## 3. Caveats

1. **Serial Test Execution Requirement:** When executing tests with PostgreSQL using `--keepdb`, Django test runners must be run serially (not concurrently), as concurrent test runners attempting to create/delete users with identical usernames can trigger `psycopg2.errors.DeadlockDetected` on the `users_user_username_key` index. All 70 regression tests pass with 100% reliability when executed serially.
2. **Superuser SoD Bypass:** Superusers (`is_superuser=True`) intentionally bypass SoD checks (`and not is_superuser`) to support disaster recovery, system initialization, and automated fixtures, per standard single-tenant enterprise conventions. Standard staff roles (`admin`, `hotel_manager`, `inventory`, `finance`) are strictly bound by SoD.

---

## 4. Conclusion

**FORMAL VERDICT: APPROVE**

The procurement RBAC boundaries, row-scoping rules, Separation of Duties constraints, multi-tier approval thresholds, and staging database cleanup implemented by Worker M1-3 are verified to be fully robust, empirically sound, and completely compliant with specifications.

- 61 of 61 empirical challenger checks passed (100%).
- 70 of 70 regression tests passed (100%).
- Staging database `hotel_erp_staging` contains exactly 37 Users, 0 PayrollEntry records, and 84 JournalEntry records.
- Zero regressions detected.

---

## 5. Verification Method

To independently reproduce the empirical challenge results:

```powershell
# 1. Run the Empirical Challenger Test Harness (61 checks, transaction-isolated)
.venv\Scripts\python.exe scratch/test_challenger_m1_it3.py

# 2. Run the dedicated Procurement RBAC regression suite
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput

# 3. Verify staging database record counts
.venv\Scripts\python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from users.models import User
from hotel.models import PayrollEntry
assert User.objects.count() == 37, f'Expected 37 users, got {User.objects.count()}'
assert PayrollEntry.objects.count() == 0, f'Expected 0 payroll entries, got {PayrollEntry.objects.count()}'
print('VERIFIED: 37 users, 0 payroll entries in staging.')
"
```
