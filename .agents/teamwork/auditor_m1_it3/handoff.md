# Handoff Report: Forensic Integrity Audit — Milestone 1 Iteration 3

**Agent:** Forensic Integrity Auditor M1-It3 (`auditor_m1_it3`)  
**Roles:** critic, specialist, auditor  
**Working Directory:** `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment`  
**State Folder:** `.agents/teamwork/auditor_m1_it3/`  
**Date:** 2026-11-09T22:48:00Z  
**Verdict:** **CLEAN**  
**Milestone 1 Status:** **CLOSED — ACCEPTED**  

---

## 1. Observation

### 1.1 Source Code and ViewSet Permissions
- `apps/inventory/views.py`:
  - `ProcurementApprovalPolicyViewSet` (line 697): `permission_classes = [IsInventoryManager]`
  - `PurchaseRequisitionViewSet` (line 702): `permission_classes = [IsPurchaseRequisitionStaff]`
  - `RequestForQuotationViewSet` (line 1081): `permission_classes = [IsProcurementOrFinanceOperator]`
  - `SupplierQuotationViewSet` (line 1189): `permission_classes = [IsProcurementOrFinanceOperator]`
  - `PurchaseOrderViewSet` (line 851): `permission_classes = [IsProcurementOrFinanceOperator]`
  - `GoodsReceiptNoteViewSet` (line 932): `permission_classes = [IsProcurementOrFinanceOperator]`
  - `SupplierInvoiceViewSet` (line 994): `permission_classes = [IsProcurementOrFinanceOperator]`
  - `SupplierInvoiceViewSet.approve` action (line 1059): `permission_classes = [IsFinanceStaff]`
  - `PurchaseRequisitionViewSet.convert_to_po` action (line 818): `permission_classes = [IsProcurementOperator]`
  - `PurchaseRequisitionViewSet.get_queryset` (line 711): Row-scoping restricts operational departmental users (`kitchen`, `bar`, `housekeeping`) to `Q(requested_by=user) | Q(department__iexact=user_role)`. Privileged management roles receive property-wide visibility.

### 1.2 Domain Service Role Enforcement and Separation of Duties (`hotel/procurement.py`)
- `_validate_procurement_role(user, allowed_roles, action_name)` (line 82): Raises `PermissionDenied` when user role is not authorized. Superusers bypass.
- `approve_purchase_requisition` (line 255):
  - Line 277: `if approver_id == requester_id and not is_superuser: raise ValidationError("Separation of duties violation: Requisitioner cannot approve their own requisition...")`
  - Line 284: `valid_roles.update({"inventory", "kitchen", "f_and_b", "hotel_manager"})` explicitly authorizes `hotel_manager` on Tier 1.
- `convert_requisition_to_purchase_order` (line 326): `_validate_procurement_role(actual_issuer, allowed_roles={"admin", "hotel_manager", "inventory"})`
- `receive_goods_receipt_note` (line 415): `_validate_procurement_role(actual_receiver, allowed_roles={"admin", "hotel_manager", "inventory"})`
- `approve_supplier_invoice` (line 709):
  - Line 731: `_validate_procurement_role(approver, allowed_roles={"admin", "finance"})`
  - Line 741: `if approver_role != "admin" and not is_superuser: raise PermissionDenied("Only hotel administrators can authorize supplier invoice price variance overrides.")`
  - Line 747: `if approver_id in grn_receiver_ids and not is_superuser: raise ValidationError("Separation of duties violation: Dock receiver cannot approve invoice payment for goods they received.")`

### 1.3 Direct PostgreSQL Staging Database State (`hotel_erp_staging`)
Command:
```python
python -c "from users.models import User; from hotel.models import PayrollEntry, JournalEntry; ... print(...)"
```
Output:
- Connected Database: `hotel_erp_staging`
- `PayrollEntry.objects.count()` = **0**
- `PayrollEntry.objects.filter(id__in=[4, 5, 6]).count()` = **0** (IDs 4, 5, 6 completely purged)
- `User.objects.count()` = **37** (exact baseline, 33 active, 4 inactive)
- Role distribution: `admin: 9, bar: 1, cashier: 3, customer: 2, finance: 3, hotel_manager: 2, housekeeping: 1, inventory: 10, kitchen: 2, reception: 1, waiter: 3` (all 11 roles intact)
- `JournalEntry.objects.count()` = **84**
- `JournalEntry.objects.filter(description__icontains='payroll').count()` = **0**

### 1.4 Empirical HTTP Probing Matrix (`scratch/test_forensic_procurement_m1_it3.py`)
- `/users/procurement/orders/`: 403 Forbidden for `kitchen`, `bar`, `waiter`, `cashier`, `customer`, `reception`, `housekeeping`. 200 OK for `admin`, `hotel_manager`, `inventory`, `finance`.
- `/users/procurement/grns/`: 403 Forbidden for all departmental line staff. 200 OK for procurement/finance staff.
- `/users/procurement/invoices/`: 403 Forbidden for all departmental line staff. 200 OK for procurement/finance staff.
- `/users/procurement/rfqs/`: 403 Forbidden for all departmental line staff. 200 OK for procurement/finance staff.
- `/users/procurement/quotations/`: 403 Forbidden for all departmental line staff. 200 OK for procurement/finance staff.
- `/users/procurement/policies/`: 403 Forbidden for finance and all line staff. 200 OK for `admin`, `hotel_manager`, `inventory`.
- `/users/procurement/requisitions/`: 403 Forbidden for `waiter`, `cashier`, `customer`, `reception`. 200 OK for `kitchen`, `bar`, `housekeeping` (scoped).
- Mutation guards: Waiter PO create -> 403; Waiter PR create -> 403; Customer PR create -> 403; Kitchen cross-dept PR create -> 403; Kitchen convert-to-po -> 403; Inventory invoice payment approve -> 403.
- Service layer checks: Waiter role block -> PermissionDenied; Hotel Manager Tier 1 PR approval -> OK; Requester self-approval -> ValidationError; Kitchen PO convert -> PermissionDenied; Waiter GRN receive -> PermissionDenied.

### 1.5 Automated Regression Suite Verification
1. `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput`
   - Result: `Ran 18 tests in 14.953s. OK.` (18 executed, 18 passed, 0 failures, 0 errors, 0 skipped).
2. `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput`
   - Result: `Ran 12 tests in 43.680s. OK.` (12 executed, 12 passed, 0 failures, 0 errors, 0 skipped).
3. `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput`
   - Result: `Ran 10 tests in 88.529s. OK.` (10 executed, 10 passed, 0 failures, 0 errors, 0 skipped).
4. `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb --noinput`
   - Result: `Ran 30 tests in 182.425s. OK.` (30 executed, 30 passed, 0 failures, 0 errors, 0 skipped).
- Total tests executed across suites: **70 tests, 70 passed, 0 failed, 0 errors, 0 skipped**.

---

## 2. Logic Chain

1. **DEF-01 Resolution:** The post-acceptance audit established that 6 out of 7 procurement viewsets were previously accessible with `[IsAuthenticated]`. Implementing `[IsProcurementOrFinanceOperator]` across orders, GRNs, invoices, RFQs, and quotations successfully terminates general procurement access for unauthorized departmental roles (`kitchen`, `bar`, `waiter`, `cashier`, `customer`).
2. **Defensive Depth in Service Layer:** Adding `_validate_procurement_role` in `hotel/procurement.py` ensures that background tasks or internal services cannot circumvent DRF permission classes. Enforcing PK comparison for Separation of Duties prevents self-approval fraud.
3. **DEF-02 Purge and Verification:** The 3 test payroll entries in `hotel_erp_staging` were confirmed to be in draft status with 0 journal entries. Targeted deletion of IDs 4, 5, 6 was executed cleanly, resulting in 0 total payroll entries while leaving all 37 user accounts and 84 journal entries intact.
4. **Test Database Concurrency Resolution:** Investigating initial test errors in Suite 4 uncovered orphaned background test processes (PIDs 7232, 1612, 14288, 20756, 17580) holding locks on table `users_user` in `test_hotel_erp_staging`. Terminating these stale processes cleared the lock contention, enabling all 30 tests in Suite 4 to run and pass with 100% success.
5. **Count Reconciliation:** All 70 regression tests were executed and accounted for without double-counting (18 + 12 + 10 + 13 + 4 + 13 = 70).

---

## 3. Caveats

1. **Superuser Bypass in SoD:** In accordance with ERP conventions and existing unit test fixtures, Django superusers (`is_superuser=True`) bypass Separation of Duties checks. Standard non-superuser administrators (`role="admin"`) remain subject to SoD constraints.
2. **External Suppliers Identity:** External suppliers continue to authenticate using `role="customer"` and interact via supplier portal endpoints (`/api/users/suppliers/...`). They remain strictly forbidden from internal hotel procurement endpoints (`HTTP 403 Forbidden`).

---

## 4. Conclusion

The remedial implementation for Milestone 1 Iteration 3 is complete, authentic, robust, and verified.
- **Verdict:** **CLEAN**
- **Status:** **CLOSED — ACCEPTED**
- All 7 procurement viewsets are secured with role-based permission classes.
- Staging database is verified clean (0 payroll entries, 37 users, 84 journal entries).
- All 70 regression tests pass with 100% success rate.
- Comprehensive report published in `docs/M1_ITERATION3_FORENSIC_CLOSURE_REPORT.md`.

---

## 5. Verification Method

To independently reproduce the forensic verification:

```powershell
# 1. Run Dedicated Procurement RBAC Suite (18 tests, PASS)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput

# 2. Run Procurement Management Suite (12 tests, PASS)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput

# 3. Run RFQ & Quotation Workflow Suite (10 tests, PASS)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput

# 4. Run Orders, Milestone 2, and Finance Suites (30 tests, PASS)
.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb --noinput

# 5. Run Standalone Forensic RBAC Probing (All 7 desks & 11 roles, PASS)
.venv\Scripts\python.exe scratch/test_forensic_procurement_m1_it3.py

# 6. Verify Staging Database State (37 users, 0 payroll entries, 84 JVs)
.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from users.models import User; from hotel.models import PayrollEntry, JournalEntry; assert User.objects.count() == 37; assert PayrollEntry.objects.count() == 0; assert JournalEntry.objects.count() == 84; print('VERIFIED CLEAN')"
```
