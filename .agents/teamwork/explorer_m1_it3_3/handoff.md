# Procurement Test Suite & Staging Database Cleanup Investigation Report

**Document:** `.agents/teamwork/explorer_m1_it3_3/handoff.md`  
**Date:** 2026-11-09T18:46:00Z  
**Investigating Agent:** Explorer 3 — Procurement Test & Database Cleanup Explorer (`explorer_m1_it3_3`)  
**Scope:** Automated RBAC regression test suite design across all 7 procurement endpoints and exact non-destructive cleanup strategy for staging database test records (DEF-02).  
**Status:** **INVESTIGATION COMPLETE — READY FOR IMPLEMENTATION**

---

## 1. Observation

### 1.1 Direct Staging Database Inspection (`hotel_erp_staging`)
Using read-only Django ORM inspection connected directly to PostgreSQL database `hotel_erp_staging` (as specified in `.env:11`):

1. **Database Identity:**
   ```
   connection.settings_dict['NAME'] == 'hotel_erp_staging'
   ```
2. **`PayrollEntry` Table Forensics:**
   - Total rows in `PayrollEntry`: **3** (only the three test rows exist in the entire table).
   - Exact records identified:
     | ID | `employee_name` | `department` | `basic_salary` | `gross_pay` | `net_pay` | `status` | `created_at` (UTC) |
     |:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
     | **4** | `'Test'` | `'kitchen'` | `Decimal('1000.00')` | `Decimal('1000.00')` | `Decimal('1000.00')` | `'draft'` | `2026-11-09 07:53:18.651573` |
     | **5** | `'T'` | `'kitchen'` | `Decimal('100.00')` | `Decimal('100.00')` | `Decimal('100.00')` | `'draft'` | `2026-11-09 17:57:07.784178` |
     | **6** | `'T'` | `'kitchen'` | `Decimal('100.00')` | `Decimal('100.00')` | `Decimal('100.00')` | `'draft'` | `2026-11-09 17:57:07.837140` |
3. **General Ledger / Accounting Verification:**
   - `JournalEntry.objects.filter(description__icontains='payroll').count() == 0`.
   - Inspection of `apps/finance/views.py:410`: `_post_payroll_gl(entry)` is triggered **only** when `entry.status == 'paid'`. Because records 4, 5, and 6 are in `status == 'draft'`, **zero GL journal entries or financial ledger adjustments occurred**.
4. **Relational Cascades & Foreign Keys:**
   - `[r.related_model.__name__ for r in PayrollEntry._meta.related_objects] == []`.
   - There are **zero** incoming foreign key relationships from any other model to `PayrollEntry`. Deletion of rows 4, 5, 6 will not cause cascading deletions.
5. **User Account Safety:**
   - `User.objects.count() == 37`.
   - Role breakdown across all 37 staging users:
     - `inventory`: 10
     - `admin`: 9
     - `cashier`: 3
     - `finance`: 3
     - `waiter`: 3
     - `kitchen`: 2
     - `hotel_manager`: 2
     - `customer`: 2
     - `bar`: 1
     - `housekeeping`: 1
     - `reception`: 1
   - All 37 staging accounts remain 100% active and uncorrupted.

---

### 1.2 Procurement API Routes & Permissions Verification
Inspection of `apps/inventory/urls.py`, `apps/inventory/views.py`, and `users/permissions.py`:

1. **7 Procurement Route Mounts & URL Reversal:**
   | Route Slug | Registered Viewset | Declared `permission_classes` | Reverse List URL |
   |---|---|---|---|
   | `procurement/policies` | `ProcurementApprovalPolicyViewSet` | `[IsInventoryManager]` | `/users/procurement/policies/` |
   | `procurement/requisitions` | `PurchaseRequisitionViewSet` | `[IsAuthenticated]` | `/users/procurement/requisitions/` |
   | `procurement/rfqs` | `RequestForQuotationViewSet` | `[IsAuthenticated]` | `/users/procurement/rfqs/` |
   | `procurement/quotations` | `SupplierQuotationViewSet` | `[IsAuthenticated]` | `/users/procurement/quotations/` |
   | `procurement/orders` | `PurchaseOrderViewSet` | `[IsAuthenticated]` | `/users/procurement/orders/` |
   | `procurement/grns` | `GoodsReceiptNoteViewSet` | `[IsAuthenticated]` | `/users/procurement/grns/` |
   | `procurement/invoices` | `SupplierInvoiceViewSet` | `[IsAuthenticated]` | `/users/procurement/invoices/` |

2. **Custom Actions and Method Endpoints:**
   - `purchaserequisition-approve`: `POST /users/procurement/requisitions/<id>/approve/`
   - `purchaserequisition-reject`: `POST /users/procurement/requisitions/<id>/reject/`
   - `purchaserequisition-convert-to-po`: `POST /users/procurement/requisitions/<id>/convert-to-po/`
   - `rfq-publish`: `POST /users/procurement/rfqs/<id>/publish/`
   - `rfq-close-rfq`: `POST /users/procurement/rfqs/<id>/close/`
   - `supplierquotation-evaluate`: `POST /users/procurement/quotations/<id>/evaluate/`
   - `supplierquotation-award-quotations`: `POST /users/procurement/quotations/award/`
   - `supplierquotation-convert-to-po`: `POST /users/procurement/quotations/convert-to-po/`
   - `purchaseorder-receive-grn`: `POST /users/procurement/orders/<id>/receive-grn/`
   - `supplierinvoice-match-and-record`: `POST /users/procurement/invoices/match-and-record/`
   - `supplierinvoice-approve`: `POST /users/procurement/invoices/<id>/approve/`

3. **Existing Permission Classes in `users/permissions.py`:**
   - `IsProcurementOperator` (lines 99–104):
     Allows: `user.is_superuser` or `role in {"admin", "inventory", "hotel_manager"}`.
   - `IsProcurementOrFinanceOperator` (lines 106–111):
     Allows: `user.is_superuser` or `role in {"admin", "inventory", "finance", "hotel_manager"}`.
   - `IsInventoryManager` (lines 92–97):
     Allows: `user.is_superuser` or `role in {"admin", "inventory", "hotel_manager"}`.

---

### 1.3 Crucial Existing Test Interaction (`test_procurement_management.py:609`)
In `apps/inventory/tests/test_procurement_management.py`, lines 608–621:
```python
# 1. API: Requisition creation
self.client.force_authenticate(user=self.chef)
req_res = self.client.post(
    "/api/users/procurement/requisitions/",
    {
        "department": "kitchen",
        "delivery_location": self.main_store.id,
        "notes": "End-to-end API test",
        "items": [{"item_id": item.id, "quantity_requested": 10, "estimated_unit_cost": "150.00"}],
    },
    format="json",
)
self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
```
- **Factual Observation:** `self.chef` has `role="kitchen"`.
- When `PurchaseRequisitionViewSet` declares `[IsAuthenticated]`, `self.chef` receives `HTTP 201 Created`.
- If `PurchaseRequisitionViewSet` is gated with `IsProcurementOperator` or `IsProcurementOrFinanceOperator` (to enforce the dispatch requirement that departmental staff receive `HTTP 403 Forbidden` on requisitions), **`test_procurement_management.py:620` will fail with HTTP 403 unless updated to use `self.storekeeper` (`role="inventory"`)**.

---

### 1.4 Peer Explorer 2 Synthesis (`explorer_m1_it3_2/handoff.md`)
- `PurchaseRequisition` defines `requested_by` (NOT `created_by`).
- In `hotel/procurement.py:approve_purchase_requisition` (lines 260–275), `hotel_manager` is currently missing from `valid_roles` for Tier 1 (`valid_roles = {"admin", "inventory", "kitchen", "f_and_b"}`). Operational hotel managers receive `PermissionDenied` when approving routine Tier 1 requisitions.
- In `apps/inventory/views.py:773`, `except Exception` catches `PermissionDenied` from the service layer and returns `HTTP 400 Bad Request` instead of `HTTP 403`. However, when DRF `permission_classes` gate the ViewSet, DRF's `initial()` throws `rest_framework.exceptions.PermissionDenied()`, which DRF automatically handles as **`HTTP 403 Forbidden`**.

---

## 2. Logic Chain

1. **Premise 1 (DEF-01 Root Cause):** Six out of seven procurement viewsets in `apps/inventory/views.py` declare only `permission_classes = [IsAuthenticated]`. As a result, departmental users (`kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`) can list, retrieve, create, and mutate procurement orders, GRNs, RFQs, quotations, and supplier invoices.
2. **Premise 2 (Specification Alignment):** The authoritative mandate (`ORIGINAL_REQUEST.md` R1, R2, R5, and dispatch instructions) requires:
   - Departmental staff must receive `HTTP 403 Forbidden` across all 7 procurement endpoints.
   - Authorized roles (`admin`, `hotel_manager`, `inventory`, `finance`) must retain appropriate operational access.
   - Separation of Duties (requester cannot approve own requisition) and multi-tier approval threshold boundaries (Tier 1 <=$10k, Tier 2 <=$50k, Tier 3 >$50k) must be strictly enforced.
3. **Premise 3 (Test Suite Design):** A dedicated regression test suite (`apps/inventory/tests/test_procurement_rbac.py`) must be created to test all 7 departmental roles across list, retrieve, create, and custom actions on all 7 endpoints, while also testing authorized access, SoD, and approval tier boundaries.
4. **Premise 4 (DEF-02 Safety):** In `hotel_erp_staging`, exactly three draft payroll records (IDs 4, 5, 6) were committed during ad-hoc verification testing. They have zero general ledger postings, zero foreign keys, and are all `status == 'draft'`. The user has formally authorized deletion of ONLY these three records.
5. **Premise 5 (Non-Destructive Cleanup Script Design):** The cleanup script (`scratch/cleanup_staging_payroll.py`) must enforce pre-checks (verifying DB name is `hotel_erp_staging`, asserting exact record IDs, names, status, and salaries, asserting 0 GL entries, asserting 37 users intact), perform an atomic `.delete()` on `id__in=[4, 5, 6]`, verify post-deletion counts, and mandate atomic rollbacks for all future verification scripts.
6. **Conclusion:** Both deliverables (`apps/inventory/tests/test_procurement_rbac.py` and `scratch/cleanup_staging_payroll.py`) have been fully designed, implemented, and syntax-verified in the explorer state folder, ready for Worker implementation.

---

## 3. Caveats

1. **Requisition Centralization vs Departmental Creation:**
   - Under the **Strict Centralized Model** (specified in the user dispatch), departmental staff cannot submit requisitions directly via API (`POST /users/procurement/requisitions/` returns `HTTP 403 Forbidden`); requisitions are submitted centrally by `inventory`, `hotel_manager`, or `admin`.
   - Under an alternative **Department-Scoped Model**, departmental users could submit requisitions for their own department (`status='pending_approval'`) while being restricted to viewing only their department's requisitions via `get_queryset()`.
   - The proposed test suite `test_procurement_rbac.py` tests the **Strict Centralized Model** mandated by the dispatch. If the orchestrator selects the Department-Scoped Model, only the PR creation assertion for `kitchen` needs adjusting.
2. **Existing Test Suite Line Update (`test_procurement_management.py:609`):**
   - As noted in Observation 1.3, `test_procurement_management.py:609` authenticates as `chef` (kitchen) to create a requisition. When `PurchaseRequisitionViewSet` is gated against departmental roles, this test line must be switched to `self.storekeeper` (`role="inventory"`) to keep the existing suite passing.
3. **Read-Only Constraint Compliance:**
   - In strict compliance with read-only explorer instructions, no code changes were made to `apps/inventory/views.py`, no test files were placed in `apps/inventory/tests/`, and no database deletions were performed in `hotel_erp_staging`. Complete proposed implementations are staged in `.agents/teamwork/explorer_m1_it3_3/`.

---

## 4. Conclusion & Concrete Deliverables

### 4.1 Deliverable 1: Automated Regression Test Suite (`test_procurement_rbac.py`)
- **Staged File:** `.agents/teamwork/explorer_m1_it3_3/proposed_test_procurement_rbac.py`
- **Destination:** `apps/inventory/tests/test_procurement_rbac.py`
- **Class:** `ProcurementRBACRegressionTestCase(APITestCase)`
- **Test Structure (13 Comprehensive Test Cases):**
  1. `test_departmental_roles_forbidden_on_procurement_orders`: Asserts HTTP 403 on list, retrieve, create, and receive-grn for all 7 departmental roles.
  2. `test_departmental_roles_forbidden_on_procurement_requisitions`: Asserts HTTP 403 on list, retrieve, create, approve, reject, and convert-to-po for all 7 departmental roles.
  3. `test_departmental_roles_forbidden_on_procurement_rfqs`: Asserts HTTP 403 on list, retrieve, create, publish, and close for all 7 departmental roles.
  4. `test_departmental_roles_forbidden_on_procurement_quotations`: Asserts HTTP 403 on list, retrieve, create, evaluate, award, and convert-to-po for all 7 departmental roles.
  5. `test_departmental_roles_forbidden_on_procurement_grns`: Asserts HTTP 403 on list, retrieve, and create for all 7 departmental roles.
  6. `test_departmental_roles_forbidden_on_procurement_invoices`: Asserts HTTP 403 on list, retrieve, create, match-and-record, and approve for all 7 departmental roles.
  7. `test_departmental_roles_forbidden_on_procurement_policies`: Asserts HTTP 403 on list, retrieve, and create for all 7 departmental roles.
  8. `test_inventory_role_authorized_procurement_access`: Verifies `inventory` user can view all desks, create PR, convert to PO, receive GRN.
  9. `test_hotel_manager_role_authorized_procurement_access`: Verifies `hotel_manager` operational visibility across all 7 endpoints.
  10. `test_finance_role_procurement_access_and_matching`: Verifies `finance` user accesses orders/invoices, performs 3-way matching and invoice approval.
  11. `test_admin_role_full_property_wide_access`: Verifies `admin` super access across all 7 endpoints and policy management.
  12. `test_separation_of_duties_requester_cannot_approve_own_requisition`: Asserts requester self-approval returns HTTP 400 with "Separation of duties violation", while peer approval succeeds (HTTP 200).
  13. `test_tier_threshold_boundary_enforcement`: Asserts Tier 1 (<= $10k) allows inventory; Tier 2 ($10k-$50k) blocks inventory and allows finance; Tier 3 (> $50k) blocks inventory/finance and allows admin.

---

### 4.2 Deliverable 2: Staging Database Cleanup Script (`cleanup_staging_payroll.py`)
- **Staged File:** `.agents/teamwork/explorer_m1_it3_3/proposed_cleanup_staging_payroll.py`
- **Destination:** `scratch/cleanup_staging_payroll.py`
- **Execution Script Design:**
  ```python
  # 1. Safety check
  if connection.settings_dict["NAME"] != "hotel_erp_staging":
      raise RuntimeError("SAFETY ABORT: Refusing to run on non-staging DB.")

  # 2. Forensics assertions
  assert User.objects.count() == 37
  assert JournalEntry.objects.filter(description__icontains="payroll").count() == 0
  assert PayrollEntry.objects.count() == 3

  # Assert exact records
  entries = PayrollEntry.objects.filter(id__in=[4, 5, 6])
  # Asserts id=4: Test, basic_salary=1000.00, status='draft', dept='kitchen'
  # Asserts id=5: T,    basic_salary=100.00,  status='draft', dept='kitchen'
  # Asserts id=6: T,    basic_salary=100.00,  status='draft', dept='kitchen'

  # 3. Targeted atomic delete
  with transaction.atomic():
      deleted_count, details = PayrollEntry.objects.filter(id__in=[4, 5, 6]).delete()
      assert deleted_count == 3

  # 4. Post-cleanup verification
  assert PayrollEntry.objects.count() == 0
  assert User.objects.count() == 37
  assert set(User.objects.values_list("id", flat=True)) == user_ids_before
  ```

---

### 4.3 Deliverable 3: Protocol Mandate for Future Ad-Hoc Scripts
All future ad-hoc verification scripts connecting to staging outside Django `TestCase` must use atomic rollbacks:
```python
with transaction.atomic():
    try:
        response = client.post(...)
        # Perform verification assertions on response
    finally:
        transaction.set_rollback(True)  # Strictly guarantees zero persistent database mutations
```

---

## 5. Verification Method

### 5.1 Verification Commands for Implementers

1. **Compile and Verify Staged Files:**
   ```powershell
   .venv\Scripts\python.exe -m py_compile .agents\teamwork\explorer_m1_it3_3\proposed_test_procurement_rbac.py
   .venv\Scripts\python.exe -m py_compile .agents\teamwork\explorer_m1_it3_3\proposed_cleanup_staging_payroll.py
   ```
   *Expected Result:* Exit code 0, zero syntax or import errors.

2. **Execute Staging Cleanup Script (by Worker upon approval):**
   ```powershell
   # Worker copies proposed_cleanup_staging_payroll.py to scratch/cleanup_staging_payroll.py
   .venv\Scripts\python.exe scratch/cleanup_staging_payroll.py
   ```
   *Expected Output:*
   ```
   [*] Connected Database: hotel_erp_staging
   [*] Pre-cleanup User count: 37
   [*] Pre-cleanup PayrollEntry count: 3
   [*] Pre-cleanup Payroll JournalEntry count: 0
   [*] Deletion result: 3 record(s) deleted: {'hotel.PayrollEntry': 3}
   [*] Post-cleanup target records remaining: 0
   [*] Post-cleanup total PayrollEntry count: 0
   [*] Post-cleanup User count: 37
   SUCCESS: DEF-02 Staging Database Cleanup Completed Cleanly.
   ```

3. **Deploy and Run Dedicated Regression Test Suite:**
   ```powershell
   # Worker copies proposed_test_procurement_rbac.py to apps/inventory/tests/test_procurement_rbac.py
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb
   ```
   *Expected Output:* `Ran 13 tests ... OK` against `test_hotel_erp_staging`.

4. **Verify Existing Regression Suites:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb
   ```
   *Expected Output:* All existing test suites pass cleanly without regressions.

### 5.2 Invalidation Conditions
- Any deletion of User accounts (total User count deviating from 37).
- Any deletion of `PayrollEntry` records other than IDs `[4, 5, 6]`.
- Failure of departmental roles to receive `HTTP 403 Forbidden` on procurement endpoints.
- Any test execution modifying the active staging database rather than `test_hotel_erp_staging`.
