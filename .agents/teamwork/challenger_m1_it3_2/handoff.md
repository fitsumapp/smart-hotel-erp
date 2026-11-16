# Empirical Challenger Report: Procurement RBAC, Department Scoping & SoD Stress-Testing (Milestone 1 Iteration 3)

**Agent:** Empirical Challenger M1-It3-2 (`challenger_m1_it3_2`)  
**Role:** Adversarial Critic / Empirical Specialist  
**Working Directory:** `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment`  
**State Folder:** `.agents/teamwork/challenger_m1_it3_2/`  
**Date:** 2026-11-09T19:26:00Z  
**Formal Verdict:** **REJECT** (Blocking Defect Identified in Cross-Department Requisition Rejection)

---

## 1. Observation

### 1.1 Automated Test Suite Execution
In accordance with mission requirements, the dedicated Procurement RBAC regression test suite was executed against the isolated test database:

**Command:**
```powershell
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput
```

**Verbatim Result:**
```
Found 18 test(s).
Using existing test database for alias 'default'...
..................
----------------------------------------------------------------------
Ran 18 tests in 14.179s

OK
Preserving test database for alias 'default'...
```
- **Discovered:** 18
- **Executed:** 18
- **Passed:** 18
- **Failed:** 0
- **Errors:** 0
- **Skipped:** 0

---

### 1.2 Empirical Adversarial Stress Harness (`scratch/test_empirical_challenger_m1_it3_2.py`)
To rigorously stress-test negative boundaries, Separation of Duties (SoD), and departmental scoping, a standalone 25-scenario empirical test harness was authored and executed in transactional rollback mode against the system.

**Execution Command:**
```powershell
.venv\Scripts\python.exe scratch/test_empirical_challenger_m1_it3_2.py
```

**Verbatim Output Summary:**
```
===========================================================================
SUMMARY OF EMPIRICAL ADVERSARIAL STRESS RESULTS:
===========================================================================
  1.1_kitchen_list_scoping                     : PASS
  1.2_kitchen_query_bar_scoping                : PASS
  1.3_kitchen_query_hk_scoping                 : PASS
  1.4_kitchen_detail_bar_404                   : PASS
  1.5_kitchen_detail_hk_404                    : PASS
  1.6a_kitchen_approve_on_bar_404              : PASS
  1.6b_kitchen_reject_on_bar_scoping           : FAIL_VULNERABILITY
  1.7_non_privileged_blocked_fin_inv           : PASS
  1.8_department_fuzzing_blocked               : PASS
  2.1_grn_receiver_cannot_approve_invoice      : PASS
  2.2_inventory_cannot_approve_invoice         : PASS
  2.3_independent_finance_approves_invoice     : PASS
  2.4_multi_grn_receivers_all_blocked          : PASS
  3.1_flagged_without_override_400             : PASS
  3.2_finance_override_blocked_403             : PASS
  3.3_hotel_manager_override_blocked_403       : PASS
  3.4_inventory_override_blocked_403           : PASS
  3.5_kitchen_override_blocked_403             : PASS
  3.6_admin_without_override_400               : PASS
  3.7_admin_str_false_400                      : PASS
  3.8_admin_authorizes_variance_override       : PASS
  4.1_service_sod_validation_error             : PASS
  4.2_service_inventory_role_denied            : PASS
  4.3_service_hotel_manager_role_denied        : PASS
  4.4_service_kitchen_po_convert_denied        : PASS

===========================================================================
OVERALL EMPIRICAL VERDICT: FAILURES DETECTED
Total Tests Executed: 25 | Passed: 24 | Failed: 1
===========================================================================
DATABASE CLEANLINESS CONFIRMED: 0 records leaked. User count preserved at 37.
```

---

### 1.3 Detailed Finding: Cross-Department Requisition Rejection Vulnerability (DEF-M1-IT3-01)

#### Verbatim Empirical Reproduction Command:
```powershell
.venv\Scripts\python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import transaction
from rest_framework.test import APIClient
from hotel.models import StockLocation, InventoryItem, PurchaseRequisition
from hotel.procurement import request_purchase_requisition
from users.models import User

client = APIClient()
kitchen_user = User.objects.filter(role='kitchen', is_active=True).first()
bar_user = User.objects.filter(role='bar', is_active=True).first()
loc = StockLocation.objects.first()
item = InventoryItem.objects.first()

with transaction.atomic():
    pr_bar = request_purchase_requisition(
        requester=bar_user,
        department='bar',
        delivery_location=loc,
        items=[{'item_id': item.id, 'quantity_requested': 5, 'estimated_unit_cost': '20.00'}],
    )
    print(f'Initial Bar PR #{pr_bar.requisition_number}: status={pr_bar.status}, dept={pr_bar.department}, requester={pr_bar.requested_by.username}')

    # Authenticate as Kitchen staff
    client.force_authenticate(user=kitchen_user)
    res = client.post(f'/users/procurement/requisitions/{pr_bar.id}/reject/', {'reason': 'Cross-dept sabotage test'}, format='json')
    print(f'Kitchen POST /reject/ HTTP status: {res.status_code}')

    pr_bar.refresh_from_db()
    print(f'Mutated Bar PR status: {pr_bar.status}, reason: {pr_bar.rejection_reason}')
    transaction.set_rollback(True)
"
```

#### Verbatim Output:
```
Initial Bar PR #PR-20261109-545BA1: status=pending_approval, dept=bar, requester=staging_bartender
Kitchen POST /reject/ HTTP status: 200
Mutated Bar PR status: rejected, reason: Cross-dept sabotage test
```

#### Code Inspection & Root Cause:
In `apps/inventory/views.py`:
1. `PurchaseRequisitionViewSet.approve` (lines 787-801) correctly invokes `req_obj = self.get_object()`, triggering `get_queryset()` row-scoping so cross-departmental requests return `HTTP 404 NOT FOUND`:
```python
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req_obj = self.get_object()  # <-- Properly enforces row-scoping
        notes = request.data.get("notes", "")
        ...
```
2. However, `PurchaseRequisitionViewSet.reject` (lines 802-816) **omits `self.get_object()`** and passes `pk` directly to the service layer:
```python
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        reason = request.data.get("reason", "")
        if not reason or not str(reason).strip():
            return Response({"error": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            req = reject_purchase_requisition(requisition_id=pk, rejecter=request.user, reason=reason)  # <-- Bypasses DRF row-scoping!
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)
```
3. In `hotel/procurement.py` (lines 400-415), `reject_purchase_requisition` performs **zero caller role or ownership validation**:
```python
def reject_purchase_requisition(
    *,
    requisition_id,
    rejecter=None,
    user=None,
    reason="",
):
    """Rejects a Purchase Requisition with a documented reason."""
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)
    if pr.status != "pending_approval":
        raise ValidationError(f"Cannot reject requisition #{pr.requisition_number}: status is '{pr.status}', expected 'pending_approval'.")

    pr.status = "rejected"
    pr.rejection_reason = str(reason or "Rejected by reviewer").strip()
    pr.save(update_fields=["status", "rejection_reason", "updated_at"])
    return pr
```
Because `PurchaseRequisitionViewSet` has `permission_classes = [IsPurchaseRequisitionStaff]` (which grants access to `kitchen`, `bar`, and `housekeeping`), any operational line cook or bar tender can issue `POST /users/procurement/requisitions/<id>/reject/` against *any* requisition in the hotel (including Bar, Housekeeping, Finance, or Inventory requisitions), and it will immediately reject it with `HTTP 200 OK`.

---

## 2. Logic Chain

1. **Requisition Department Read Scoping (Observation 1.2, Tests 1.1-1.5):**
   `PurchaseRequisitionViewSet.get_queryset()` applies row-scoping for non-privileged staff:
   `qs.filter(Q(requested_by=user) | Q(department__iexact=user_role))`
   - When kitchen staff queries `GET /requisitions/`, bar and housekeeping requisitions are completely omitted (`1.1 PASS`).
   - When kitchen staff attempts query-parameter filtering (`?department=bar` or `?department=housekeeping`), the viewset ignores the parameter for non-privileged users and returns only kitchen requisitions (`1.2 PASS`, `1.3 PASS`).
   - When kitchen staff attempts direct detail retrieval (`GET /requisitions/<bar_id>/`), DRF calls `self.get_object()`, which evaluates `get_queryset()` and returns `HTTP 404 NOT FOUND` (`1.4 PASS`, `1.5 PASS`).
   - When kitchen staff attempts approval (`POST /requisitions/<bar_id>/approve/`), `self.get_object()` triggers `HTTP 404 NOT FOUND` (`1.6a PASS`).

2. **Requisition Department Mutation Scoping Failure (Observation 1.3, Test 1.6b):**
   - In `PurchaseRequisitionViewSet.reject`, `self.get_object()` is absent.
   - The endpoint receives the ID from the URL parameter `pk` and forwards it directly to `reject_purchase_requisition(requisition_id=pk, ...)`.
   - The service layer `reject_purchase_requisition` fetches the record via `PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)` without checking whether `rejecter` belongs to the requesting department, has managerial approval authority, or is the original requester.
   - Therefore, departmental isolation is completely broken for rejection mutations: `kitchen` staff can sabotage `bar`, `housekeeping`, `finance`, or `inventory` requisitions.

3. **Requisition Creation Departmental Guards (Observation 1.2, Tests 1.7, 1.8):**
   - In `PurchaseRequisitionViewSet.create`, `is_privileged = user.is_superuser or user_role in {"admin", "hotel_manager", "inventory"}`.
   - Non-privileged staff submitting `department="finance"` or `department="inventory"` are checked via `if department and department.lower() != user_role: return 403 Forbidden`.
   - All non-privileged roles (`kitchen`, `bar`, `housekeeping`, `waiter`, `cashier`, `reception`, `customer`) are strictly blocked from requesting under `finance` or `inventory` (`1.7 PASS`).
   - Fuzzed strings (whitespace, uppercase, composite paths) are strictly blocked (`1.8 PASS`).

4. **Separation of Duties (SoD) on Goods Receipt & Invoices (Observation 1.2, Tests 2.1-2.4, 4.1):**
   - The service layer `approve_supplier_invoice` evaluates:
     `grn_receiver_ids = set(invoice.purchase_order.grns.values_list("received_by_id", flat=True))`
     `if approver_id in grn_receiver_ids and not is_superuser: raise ValidationError(...)`
   - An administrator or finance staff member who received the GRN is blocked with `HTTP 400 Bad Request` and message `"Dock receiver cannot approve invoice payment for goods they received"` (`2.1 PASS`, `4.1 PASS`).
   - Inventory staff attempting invoice approval are blocked by viewset guard `permission_classes=[IsFinanceStaff]` (`HTTP 403 Forbidden`) and service validation (`2.2 PASS`, `4.2 PASS`).
   - An independent finance officer who did not receive goods cleanly approves the invoice (`2.3 PASS`).
   - On multi-GRN purchase orders with multiple dock receivers, all cumulative receivers are blocked from approving payment (`2.4 PASS`).

5. **Price Variance Override Safeguards (Observation 1.2, Tests 3.1-3.8):**
   - When an invoice has `match_status == "variance_flagged"`:
     - Approval with `override_variance=False` raises `ValidationError` -> `HTTP 400 Bad Request` (`3.1 PASS`, `3.6 PASS`).
     - Passing string `"false"` is normalized to boolean `False` -> `HTTP 400 Bad Request` (`3.7 PASS`).
     - Approval with `override_variance=True` by `finance` staff raises `PermissionDenied("Only hotel administrators can authorize supplier invoice price variance overrides.")` -> `HTTP 403 Forbidden` (`3.2 PASS`).
     - Approval with `override_variance=True` by `hotel_manager`, `inventory`, or `kitchen` is blocked at the viewset level by `IsFinanceStaff` -> `HTTP 403 Forbidden` (`3.3 PASS`, `3.4 PASS`, `3.5 PASS`).
     - Approval with `override_variance=True` by hotel administrator (`role="admin"`) succeeds -> `HTTP 200 OK` and `match_status="approved"` (`3.8 PASS`).

---

## 3. Caveats

1. **Staging Database Isolation:**
   All empirical stress tests were executed using `with transaction.atomic(): ... transaction.set_rollback(True)`. The staging database was inspected before and after testing; exactly 37 user accounts remain, 0 draft payroll records exist, and 0 test artifacts leaked.
2. **Pre-Existing Automated Suites:**
   The automated test suite `apps.inventory.tests.test_procurement_rbac` passed 18/18 tests because it tested cross-departmental *read* scoping (Bar retrieving Kitchen PR) and *creation* scoping, but omitted testing cross-departmental *rejection* mutations.
3. **Review-Only Constraint:**
   In strict adherence to the Challenger role constraints ("Review-only — do NOT modify implementation code"), no production or implementation code was modified by this agent. The fix must be implemented by the worker agent.

---

## 4. Conclusion & Formal Verdict

### Formal Verdict: **REJECT**

While the implementations of Separation of Duties on Goods Receipt / Invoice Matching, Price Variance Override admin gating, and non-privileged requisition creation guards are robust and passed all empirical checks, the implementation of `PurchaseRequisitionViewSet.reject` suffers from a **critical departmental row-scoping bypass**.

### Actionable Remediation Required:
1. **In `apps/inventory/views.py` (`PurchaseRequisitionViewSet.reject`, line 802):**
   Add `req_obj = self.get_object()` before invoking the service layer. This ensures DRF's `get_queryset()` row-scoping is evaluated, immediately returning `HTTP 404 NOT FOUND` if a user attempts to reject a requisition outside their department.
   ```python
   @action(detail=True, methods=["post"], url_path="reject")
   def reject(self, request, pk=None):
       req_obj = self.get_object()  # <-- Add this line
       reason = request.data.get("reason", "")
       ...
   ```
2. **In `hotel/procurement.py` (`reject_purchase_requisition`, line 400):**
   Add defense-in-depth role/authorization validation on `rejecter` (e.g. verifying that `rejecter` holds an allowed approval/managerial role for that tier or department, is an admin, or is the original requester withdrawing their requisition).
3. **In `apps/inventory/tests/test_procurement_rbac.py`:**
   Add a regression test asserting that a cross-departmental user (e.g. kitchen) receiving `HTTP 404` when attempting to call `POST /users/procurement/requisitions/<bar_id>/reject/`.

---

## 5. Verification Method

To independently verify the vulnerability and all empirical findings:

```powershell
# 1. Run the existing test suite (Passes 18/18)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput

# 2. Run the empirical adversarial stress harness (Executes 25 tests, reproduces 1 failure)
.venv\Scripts\python.exe scratch/test_empirical_challenger_m1_it3_2.py

# 3. Direct reproduction of cross-department rejection bypass
.venv\Scripts\python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.db import transaction
from rest_framework.test import APIClient
from hotel.models import StockLocation, InventoryItem
from hotel.procurement import request_purchase_requisition
from users.models import User

client = APIClient()
k_user = User.objects.filter(role='kitchen', is_active=True).first()
b_user = User.objects.filter(role='bar', is_active=True).first()
loc = StockLocation.objects.first()
item = InventoryItem.objects.first()

with transaction.atomic():
    pr = request_purchase_requisition(requester=b_user, department='bar', delivery_location=loc, items=[{'item_id': item.id, 'quantity_requested': 1}])
    client.force_authenticate(user=k_user)
    res = client.post(f'/users/procurement/requisitions/{pr.id}/reject/', {'reason': 'Cross-dept sabotage test'})
    print(f'VULNERABILITY CONFIRMED: Status code is {res.status_code} (Expected 404, got 200)')
    assert res.status_code == 200
    transaction.set_rollback(True)
"
```
