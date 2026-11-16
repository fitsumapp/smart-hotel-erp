# Handoff Report: Procurement RBAC & Staging Remediation Implementation (Milestone 1 Iteration 3)

**Agent:** Worker M1-3 (`worker_m1_it3`)  
**Role:** Implementer / QA / Specialist  
**Working Directory:** `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment`  
**State Folder:** `.agents/teamwork/worker_m1_it3/`  
**Date:** 2026-11-09T19:15:00Z  

---

## 1. Observation

### 1.1 Files Modified and Write Ownership Verification
In strict compliance with the assigned exclusive write ownership, exactly five files were modified or created:
1. `users/permissions.py` (Tracked, updated)
2. `apps/inventory/views.py` (Tracked, updated)
3. `hotel/procurement.py` (Domain service layer, updated)
4. `scratch/cleanup_staging_payroll.py` (Staging cleanup script, created & executed)
5. `apps/inventory/tests/test_procurement_rbac.py` (Dedicated RBAC regression test suite, created)

Zero unauthorized files were created or modified.

### 1.2 Summary of Code Changes

#### 1. `users/permissions.py`:
- Updated `IsSupplierOperator` to include `hotel_manager` in allowed roles alongside `admin`, `inventory`, and `finance`.
- Defined `IsPurchaseRequisitionStaff`:
  - Authorizes: `admin`, `hotel_manager`, `inventory`, `finance`, `kitchen`, `bar`, `housekeeping` (and superusers).
  - Denies: line staff (`waiter`, `cashier`, `reception`) and external customers (`customer`).

#### 2. `apps/inventory/views.py`:
- Updated imports to include `IsProcurementOperator`, `IsProcurementOrFinanceOperator`, `IsPurchaseRequisitionStaff`, `IsSupplierOperator`, and `Q` from `django.db.models`.
- `ProcurementApprovalPolicyViewSet`: Retained `permission_classes = [IsInventoryManager]`.
- `PurchaseOrderViewSet`: Gated viewset with `permission_classes = [IsProcurementOrFinanceOperator]`. Added role checks in `create()` and `update()` restricting mutation strictly to `admin`, `hotel_manager`, and `inventory`. Decorated `receive_grn` action with `permission_classes=[IsProcurementOperator]`.
- `GoodsReceiptNoteViewSet`: Gated viewset with `permission_classes = [IsProcurementOrFinanceOperator]`. Restricted `create()` receiving strictly to `admin`, `hotel_manager`, and `inventory`.
- `SupplierInvoiceViewSet`: Gated viewset with `permission_classes = [IsProcurementOrFinanceOperator]`. Decorated `approve` action with `permission_classes=[IsFinanceStaff]` (SoD enforcement: inventory storekeepers cannot approve Accounts Payable settlement).
- `RequestForQuotationViewSet`: Gated viewset with `permission_classes = [IsProcurementOrFinanceOperator]`. Restricted `create()`, `publish()`, and `close_rfq()` actions to `IsProcurementOperator`.
- `SupplierQuotationViewSet`: Gated viewset with `permission_classes = [IsProcurementOrFinanceOperator]`. Restricted `create()`, `evaluate()`, `award_quotations()`, and `convert_to_po()` actions to `IsProcurementOperator`.
- `PurchaseRequisitionViewSet`: Gated viewset with `permission_classes = [IsPurchaseRequisitionStaff]`. Implemented departmental row-scoping in `get_queryset()` (management/finance have property-wide view; departmental staff only view requisitions where `requested_by=user` or `department=role`). Enforced department validation in `create()` (non-privileged staff cannot request on behalf of other departments). Decorated `convert_to_po` action with `permission_classes=[IsProcurementOperator]`. Caught `PermissionDenied` in `approve()` and custom actions to return `HTTP 403 Forbidden`.

#### 3. `hotel/procurement.py`:
- Introduced defensive role validation helper `_validate_procurement_role(user, allowed_roles, action_name)`. Superusers bypass role checks.
- In `approve_purchase_requisition`: Added `"hotel_manager"` to Tier 1 valid roles (`valid_roles.update({"inventory", "kitchen", "f_and_b", "hotel_manager"})`). Replaced object identity comparison with robust PK equality comparison (`approver_id == requester_id and not is_superuser`) preventing integer/object bypass of Separation of Duties.
- In `convert_requisition_to_purchase_order`: Added `_validate_procurement_role(actual_issuer, {"admin", "hotel_manager", "inventory"})`.
- In `receive_goods_receipt_note`: Added `_validate_procurement_role(actual_receiver, {"admin", "hotel_manager", "inventory"})`.
- In `match_and_record_supplier_invoice`: Added `_validate_procurement_role(actual_user, {"admin", "hotel_manager", "inventory", "finance"})`.
- In `approve_supplier_invoice`:
  - Enforced role check restricting invoice settlement approval strictly to `{"admin", "finance"}`.
  - Enforced Separation of Duties check ensuring the GRN dock receiver cannot approve invoice payment for goods they received (`approver_id in grn_receiver_ids and not is_superuser`).
  - Enforced price variance override safeguard requiring hotel administrator authority (`role == "admin"` or `is_superuser`) when overriding flagged price variances.
- In RFQ / Quotation service functions:
  - Added role validation to `create_request_for_quotation` (`{"admin", "hotel_manager", "inventory"}`).
  - Added role validation to `publish_request_for_quotation` (`{"admin", "hotel_manager", "inventory"}`).
  - Added role validation to `close_request_for_quotation` (`{"admin", "hotel_manager", "inventory"}`).
  - Added role validation to `evaluate_quotation` (`{"admin", "hotel_manager", "inventory", "finance"}`).
  - Added role validation to `evaluate_and_award_quotations` (`{"admin", "hotel_manager", "inventory", "finance"}`).
  - Added role validation to `convert_awarded_quotations_to_purchase_orders` (`{"admin", "hotel_manager", "inventory"}`).

### 1.3 Staging Database Cleanup Execution Output (`scratch/cleanup_staging_payroll.py`)
Execution Command:
`.venv\Scripts\python.exe scratch/cleanup_staging_payroll.py`

Verbatim Output:
```
======================================================================
ACRMA HOTEL ERP — STAGING DATABASE PAYROLL CLEANUP (DEF-02)
======================================================================
[*] Connected Database: hotel_erp_staging
[*] Pre-cleanup User count: 37
[*] Pre-cleanup PayrollEntry count: 3
[*] Pre-cleanup Payroll JournalEntry count: 0
[*] Inspecting target records:
    - ID 4: name='Test', status='draft', salary=1000.00
    - ID 5: name='T', status='draft', salary=100.00
    - ID 6: name='T', status='draft', salary=100.00
[*] Executing targeted atomic deletion for IDs [4, 5, 6]...
[*] Deletion result: 3 record(s) deleted: {'hotel.PayrollEntry': 3}
[*] Post-cleanup target records remaining: 0
[*] Post-cleanup total PayrollEntry count: 0
[*] Post-cleanup User count: 37
======================================================================
SUCCESS: DEF-02 Staging Database Cleanup Completed Cleanly.
All 3 draft test payroll records purged. 0 GL entries affected.
All 37 staging user accounts remain 100% intact.
======================================================================
```

### 1.4 Test Suite Execution Results

#### Test Suite 1: Dedicated Procurement RBAC Regression Suite
Command:
`.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput`
Result:
`Ran 18 tests in 21.355s. OK.` (18 executed, 18 passed, 0 failures, 0 errors, 0 skipped).

#### Test Suite 2: Existing Procurement Management Suite
Command:
`.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput`
Result:
`Ran 12 tests in 66.851s. OK.` (12 executed, 12 passed, 0 failures, 0 errors, 0 skipped).

#### Test Suite 3: RFQ & Quotation Workflow Suite
Command:
`.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput`
Result:
`Ran 10 tests in 41.170s. OK.` (10 executed, 10 passed, 0 failures, 0 errors, 0 skipped).

#### Test Suite 4: Orders, Milestone 2 Workflows & Finance Suites
Command:
`.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb --noinput`
Result:
`Ran 30 tests in 192.614s. OK.` (30 executed, 30 passed, 0 failures, 0 errors, 0 skipped).

**Total Test Suite Execution:** 70 tests executed, 70 passed (100% pass rate, 0 failures, 0 errors).

---

## 2. Logic Chain

1. **Role Gating & ViewSet Exposure (DEF-01):** The post-acceptance audit identified that 6 out of 7 procurement viewsets were declared with `permission_classes = [IsAuthenticated]`. This exposed sensitive procurement operations (converting PRs to legally binding POs, receiving goods into physical inventory, awarding vendor contracts, and approving supplier invoice financial settlements) to any authenticated user, including line staff (`waiter`, `cashier`, `customer`).
2. **Layered Defense (Views + Service Layer):** Applying `IsProcurementOrFinanceOperator` at the DRF viewset boundary ensures unauthorized roles immediately receive `HTTP 403 Forbidden` on generic list/retrieve/create endpoints. Adding `_validate_procurement_role` in the service functions (`hotel/procurement.py`) provides defense-in-depth against background workers or internal scripts attempting unauthorized mutations.
3. **Operational Department-Scoped Requisitions:** Operational departmental staff (`kitchen`, `bar`, `housekeeping`) require the ability to submit restocking requests. By configuring `IsPurchaseRequisitionStaff` and enforcing row-scoping in `PurchaseRequisitionViewSet.get_queryset()`, departmental staff can submit and view requisitions for their designated department only, while line staff (`waiter`, `cashier`, `customer`) are strictly denied. Crucially, converting requisitions to purchase orders (`convert_to_po`) is decorated with `permission_classes=[IsProcurementOperator]`, ensuring departmental staff cannot issue POs.
4. **Separation of Duties (SoD):**
   - Requisition level: Requester cannot self-approve (`approver_id == requester_id`).
   - Warehouse vs Accounts Payable: Physical dock receiver (`grn.received_by`) cannot approve payment for invoices matched to that PO (`approver_id in grn_receiver_ids`). Furthermore, `SupplierInvoiceViewSet.approve` is restricted to `IsFinanceStaff`, ensuring inventory storekeepers cannot approve payments.
   - Price Variances: Exceeding policy tolerance flags an invoice as `variance_flagged`. Overriding price variances is restricted strictly to hotel administrators (`role == "admin"` or `is_superuser`).
5. **Staging Database Integrity (DEF-02):** The 3 draft payroll entries (IDs 4, 5, 6) in `hotel_erp_staging` were confirmed to have zero GL journal entries and zero incoming foreign keys. The script `scratch/cleanup_staging_payroll.py` verified the connected DB is `hotel_erp_staging`, inspected the exact record specs, executed an atomic delete of only IDs 4, 5, 6, and asserted that all 37 staging user accounts remain untouched.

---

## 3. Caveats

1. **Test Database Isolation:** All automated test suites ran against `test_hotel_erp_staging` using Django's isolated test runner with `--keepdb`. Staging database records were not altered by test execution.
2. **Superuser Bypass in SoD:** In accordance with standard single-tenant ERP practices and existing test conventions, Django superusers retain the ability to bypass SoD self-approval checks for testing and administrative override purposes (`and not is_superuser`).
3. **External Suppliers (`customer` role):** External suppliers authenticate with `role="customer"` and interact via supplier portal endpoints (`/api/users/suppliers/...`). They are strictly blocked (`HTTP 403 Forbidden`) from all internal hotel procurement viewsets.

---

## 4. Conclusion

All six tasks assigned to Worker M1-3 are complete and verified:
1. `users/permissions.py`: `IsSupplierOperator` includes `hotel_manager`; `IsPurchaseRequisitionStaff` defined.
2. `apps/inventory/views.py`: All 7 procurement viewsets protected with authoritative RBAC, row-scoping, and SoD action guards.
3. `hotel/procurement.py`: Service-layer role validation, Tier 1 `hotel_manager` authorization, robust PK SoD checks, dock receiver invoice approval block, and price variance override admin gating implemented.
4. `scratch/cleanup_staging_payroll.py`: Staging database cleaned cleanly (3 draft payroll entries deleted, 0 GL entries affected, 37 users preserved).
5. `apps/inventory/tests/test_procurement_rbac.py`: 18 comprehensive regression tests deployed and passing.
6. Zero regression across existing test suites (70/70 passing).

Milestone 1 Iteration 3 remediation is ready for Forensic Auditor verification.

---

## 5. Verification Method

To independently verify the implementation, execute the following commands in powershell:

```powershell
# 1. Verify compilation of modified files (Exit code 0)
.venv\Scripts\python.exe -m py_compile users/permissions.py apps/inventory/views.py hotel/procurement.py apps/inventory/tests/test_procurement_rbac.py scratch/cleanup_staging_payroll.py

# 2. Run new Procurement RBAC Regression Suite (18 tests, all pass)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput

# 3. Run Procurement Management Regression Suite (12 tests, all pass)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput

# 4. Run RFQ & Quotation Workflow Suite (10 tests, all pass)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput

# 5. Run Orders, Milestone 2, and Finance Suites (30 tests, all pass)
.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb --noinput

# 6. Verify staging database state (37 users, 0 draft payroll entries)
.venv\Scripts\python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from users.models import User
from hotel.models import PayrollEntry
assert User.objects.count() == 37, f'User count mismatch: {User.objects.count()}'
assert PayrollEntry.objects.count() == 0, f'Draft payroll remaining: {PayrollEntry.objects.count()}'
print('STAGING DB VERIFIED: 37 users intact, 0 payroll entries.')
"
```
