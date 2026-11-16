## 2026-11-09T18:46:42Z
You are Worker M1-3: Procurement RBAC and Staging Remediation Worker.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1_it3\

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY INPUTS (READ BEFORE IMPLEMENTING):
1. User Request: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md
2. Project Architecture & Contracts: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md
3. Explorer 1 Handoff: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_1\handoff.md
4. Explorer 2 Handoff: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_2\handoff.md
5. Explorer 3 Handoff: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_3\handoff.md
6. Staged Test Suite: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_3\proposed_test_procurement_rbac.py
7. Staged Cleanup Script: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_3\proposed_cleanup_staging_payroll.py

FILE WRITE OWNERSHIP:
You have EXCLUSIVE write ownership of:
1. `users/permissions.py`
2. `apps/inventory/views.py`
3. `hotel/procurement.py`
4. `apps/inventory/tests/test_procurement_rbac.py`
5. `scratch/cleanup_staging_payroll.py`
DO NOT modify any other files.

TASKS TO EXECUTE:

TASK 1: Update `users/permissions.py`:
- Update `IsSupplierOperator` to include `"hotel_manager"`.
- Define `IsPurchaseRequisitionStaff` per Explorer 1 section 4.1.2: allow admin, hotel_manager, inventory, finance, kitchen, bar, housekeeping; deny waiter, cashier, customer.

TASK 2: Update `apps/inventory/views.py`:
- Update imports from `users.permissions` to include `IsProcurementOperator`, `IsProcurementOrFinanceOperator`, `IsPurchaseRequisitionStaff`, `IsSupplierOperator`.
- `ProcurementApprovalPolicyViewSet`: retain `[IsInventoryManager]`.
- `PurchaseOrderViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`. Add checks on `create()`, `update()`. Decorate `receive_grn` with `permission_classes=[IsProcurementOperator]`.
- `GoodsReceiptNoteViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`. In `create()`, restrict receiving strictly to `admin`, `hotel_manager`, `inventory`.
- `SupplierInvoiceViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`. Decorate `approve` action with `permission_classes=[IsFinanceStaff]` (SoD enforcement: inventory cannot approve invoices).
- `RequestForQuotationViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`. Restrict `create()`, `publish()`, `close_rfq()` to `IsProcurementOperator`.
- `SupplierQuotationViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`. Restrict `create()`, `evaluate()`, `award_quotations()`, `convert_to_po()` to `IsProcurementOperator`.
- `PurchaseRequisitionViewSet`: `permission_classes = [IsPurchaseRequisitionStaff]`. Enforce row-scoping in `get_queryset()` per Explorer 1 (departmental staff only view their own department's requisitions; management has property-wide view). Enforce department check in `create()`. Decorate `convert_to_po` action with `permission_classes=[IsProcurementOperator]`. Catch `PermissionDenied` in `approve()` and return `HTTP 403 Forbidden`.

TASK 3: Update `hotel/procurement.py`:
- Add defensive helper `_validate_procurement_role(user, allowed_roles, action_name)` per Explorer 2 proposal.
- In `approve_purchase_requisition`: add `"hotel_manager"` to Tier 1 valid roles (`valid_roles.update({"inventory", "kitchen", "f_and_b", "hotel_manager"})`). Use robust PK equality for SoD (`approver_id == requester_id and not is_superuser`).
- In `convert_requisition_to_purchase_order`: call `_validate_procurement_role(actual_issuer, {"admin", "hotel_manager", "inventory"})`.
- In `receive_goods_receipt_note`: call `_validate_procurement_role(actual_receiver, {"admin", "hotel_manager", "inventory"})`.
- In `match_and_record_supplier_invoice`: call `_validate_procurement_role(actual_user, {"admin", "hotel_manager", "inventory", "finance"})`.
- In `approve_supplier_invoice`: enforce role check (`{"admin", "finance"}`), SoD check (dock receiver cannot approve invoice payment), and price variance override check (only admin/superuser can override price variances).
- In RFQ/Quotation service functions: add `_validate_procurement_role` per Explorer 2 proposal F.

TASK 4: Deploy & Run Staging Cleanup Script (`scratch/cleanup_staging_payroll.py`):
- Copy `.agents/teamwork/explorer_m1_it3_3/proposed_cleanup_staging_payroll.py` to `scratch/cleanup_staging_payroll.py`.
- Run: `.venv\Scripts\python.exe scratch/cleanup_staging_payroll.py`
- Verify: Connected DB is `hotel_erp_staging`, deletes ONLY PayrollEntry IDs 4, 5, 6, verifies 0 remaining draft payroll entries, and asserts all 37 staging user accounts remain intact.

TASK 5: Deploy & Run Procurement RBAC Regression Test Suite:
- Copy `.agents/teamwork/explorer_m1_it3_3/proposed_test_procurement_rbac.py` to `apps/inventory/tests/test_procurement_rbac.py`.
- Run: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput`
- Run: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput`
- Run: `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput`
- Run: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb --noinput`

TASK 6: Deliver Handoff Report:
Write complete handoff report to `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1_it3\handoff.md` with:
- Files changed and exact diff summary.
- Cleanup execution output log.
- All test execution commands and exact pass/fail outputs.
- Update your progress.md regularly. Notify orchestrator via send_message when complete.
