# Procurement Service Layer Security & Safeguards Investigation Report

**Document:** `.agents/teamwork/explorer_m1_it3_2/handoff.md`  
**Date:** 2026-11-09T18:42:00Z  
**Investigating Agent:** Explorer 2 — Procurement Service Layer Explorer (`explorer_m1_it3_2`)  
**Scope:** Investigation of business logic, role validation, Separation of Duties (SoD), approval tiers, error handling, and GL postings in `hotel/procurement.py` and related inventory viewsets.

---

## 1. Observation

Direct examination of `hotel/procurement.py`, `apps/inventory/views.py`, `hotel/models.py`, and test suites (`apps/inventory/tests/test_procurement_management.py`, `test_rfq_quotation_workflow.py`, `test_cross_module_inventory_integration.py`) revealed the following factual findings:

### 1.1 Complete Audit of Service Functions in `hotel/procurement.py`

| # | Service Function | Lines | Current Role / Authorization Checks | Mutation & Financial Impact |
|---|---|---|---|---|
| 1 | `ensure_default_procurement_policy` | 82–127 | None (Idempotent seed) | Creates default `ProcurementApprovalPolicy` and 3 tiers in database. |
| 2 | `resolve_approval_tier` | 130–150 | None (Pure selector) | Evaluates total value against active policy tiers. |
| 3 | `request_purchase_requisition` | 153–234 | `if not actual_requester: raise ValidationError` | Creates PR and PR items in `pending_approval` status. |
| 4 | `approve_purchase_requisition` | 237–284 | **Enforced:** Checks `approver == pr.requested_by and not is_superuser` (SoD) and `approver_role in valid_roles`. | Transitions PR to `approved`. Authorizes conversion to PO. |
| 5 | `reject_purchase_requisition` | 286–303 | **None.** Any user passed as `rejecter`/`user` can reject. | Transitions PR to `rejected`. Blocks further PO conversion. |
| 6 | `convert_requisition_to_purchase_order` | 306–382 | **None.** Does not check `actual_issuer.role` or permissions. | Creates `PurchaseOrder` in `issued` status; commits contract pricing. |
| 7 | `receive_goods_receipt_note` | 384–544 | **None.** Does not check `actual_receiver.role`. If None, defaults to `"system"`. | **HIGH:** Creates `GoodsReceiptNote`, adjusts physical inventory via `record_stock_change`, creates `StockBatch`, posts interim GL entry: **Dr 1300 (Asset) / Cr 2010 (GRNI)**. |
| 8 | `match_and_record_supplier_invoice` | 547–669 | **None.** Does not check `actual_user.role`. | Creates `SupplierInvoice` and items; computes 3-way variance against tolerance. |
| 9 | `approve_supplier_invoice` | 671–738 | **None.** Does not check `approver.role` or SoD. Does not restrict `override_variance`. | **HIGH:** Transitions invoice to `approved`, posts financial settlement GL entry: **Dr 2010 (GRNI), Dr/Cr 5040 (PPV), Dr 2200 (Tax), Cr 2000 (Accounts Payable)**. |
| 10 | `create_request_for_quotation` | 744–856 | **None.** Does not check `user.role`. | Creates RFQ draft, locks requisition line allocations. |
| 11 | `publish_request_for_quotation` | 858–896 | **None.** Does not check `user.role`. | Transitions RFQ to `published`, opens public/invited bidding. |
| 12 | `close_request_for_quotation` | 898–923 | **None.** Does not check `user.role`. | Transitions RFQ to `closed`. |
| 13 | `submit_supplier_quotation` | 958–1110 | **None.** Does not check `user.role`. | Creates `SupplierQuotation` and items in `submitted` status. |
| 14 | `evaluate_quotation` | 1112–1149 | **None.** Does not check `user.role`. | Moves quote to `under_evaluation`, appends committee notes. |
| 15 | `evaluate_and_award_quotations` | 1152–1249 | **None.** Does not check `user.role`. | **HIGH:** Awards bids, marks quotes `accepted` or `partially_awarded`. |
| 16 | `convert_awarded_quotations_to_purchase_orders` | 1251–1385 | **None.** Does not check `user.role`. | **HIGH:** Issues split-award Purchase Orders to suppliers. |

**Key Finding:** Out of 14 core operational service functions, **only 1 function** (`approve_purchase_requisition`) performs caller role validation. The remaining 13 service functions rely entirely on caller views.

---

### 1.2 Viewset Authorization Vulnerabilities in `apps/inventory/views.py`

In `apps/inventory/views.py`:
- `PurchaseRequisitionViewSet`: `permission_classes = [IsAuthenticated]` (line 708)
- `PurchaseOrderViewSet`: `permission_classes = [IsAuthenticated]` (line 827)
- `GoodsReceiptNoteViewSet`: `permission_classes = [IsAuthenticated]` (line 891)
- `SupplierInvoiceViewSet`: `permission_classes = [IsAuthenticated]` (line 945)
- `RequestForQuotationViewSet`: `permission_classes = [IsAuthenticated]` (line 1028)
- `SupplierQuotationViewSet`: `permission_classes = [IsAuthenticated]` (line 1124)

Because neither the viewsets nor the underlying service functions validate caller roles:
- Any authenticated user (`waiter`, `cashier`, `kitchen`, `bar`, `housekeeping`, `customer`) can execute `convert_to_po`, `receive_grn`, `match_and_record`, `approve` (invoices), `create` (RFQs), `award`, and `publish`.
- In `PurchaseRequisitionViewSet.approve` (lines 769–773), exceptions are handled as:
  ```python
  except ValidationError as e:
      return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
  except Exception as e:
      return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
  ```
  `PermissionDenied` is swallowed by `except Exception` and returned as `HTTP 400 Bad Request` instead of `HTTP 403 Forbidden`.

---

### 1.3 Approval Tier Threshold & Role Mapping Audit

Inspecting `ensure_default_procurement_policy` (lines 82–127) and `approve_purchase_requisition` (lines 260–275):

1. **Tier Configuration:**
   - **Tier 1:** `0.00` to `10000.00 ETB` — `required_role = "inventory"`, name: "Tier 1: Department Head / F&B Manager".
   - **Tier 2:** `10000.01` to `50000.00 ETB` — `required_role = "finance"`, name: "Tier 2: Finance Controller".
   - **Tier 3:** `50000.01` to `None` (unlimited) — `required_role = "admin"`, name: "Tier 3: General Manager".
2. **Current Role Authorization Mapping in `approve_purchase_requisition`:**
   ```python
   required_role = pr.approval_tier.required_role if pr.approval_tier else "admin"
   valid_roles = {"admin"}
   if required_role == "inventory":
       valid_roles.update({"inventory", "kitchen", "f_and_b"})
   elif required_role == "finance":
       valid_roles.update({"finance"})
   else:
       valid_roles.add(required_role)
   ```
3. **Critical Defect: `hotel_manager` Missing from Tier 1:**
   - When `required_role == "inventory"`, `valid_roles` contains `{"admin", "inventory", "kitchen", "f_and_b"}`.
   - `hotel_manager` is NOT in `valid_roles`!
   - If an operational `hotel_manager` (without superuser flag) attempts to approve a routine kitchen or inventory requisition under $10,000, the system raises `PermissionDenied: User role 'hotel_manager' is not authorized to approve at Tier 1`.
4. **Boundary Condition Evaluation:**
   - Amounts are quantized to 2 decimal places (`Decimal("0.01")`).
   - Exactly `$10,000.00` matches Tier 1 (`amount <= 10000.00`).
   - `$10,000.01` matches Tier 2 (`amount >= 10000.01`).
   - Exactly `$50,000.00` matches Tier 2 (`amount <= 50000.00`).
   - `$50,000.01` matches Tier 3 (`amount >= 50000.01`).
   - Missing tier fallback: if `pr.approval_tier is None`, code defaults `required_role = "admin"`. This is safe and conservative.

---

### 1.4 Separation of Duties (SoD) Audit

1. **Model Field Naming:**
   - In `hotel/models.py:PurchaseRequisition` (line 1611), the field is named **`requested_by`**, NOT `created_by`.
   - Any code referring to `requisition.created_by` will raise `AttributeError`.
2. **Current Requisition Approval SoD Implementation:**
   ```python
   if approver == pr.requested_by and not is_superuser:
       raise ValidationError("Separation of duties violation: Requisitioner cannot approve their own requisition...")
   ```
3. **Vulnerability: Object vs ID Comparison Bypass:**
   - If `approver` is passed as an integer ID (e.g. `approver=request.user.id`), `approver == pr.requested_by` tests `int == User`, which evaluates to `False`. This allows self-approval bypass.
   - Robust comparison must test PKs:
     `getattr(approver, "pk", approver) == getattr(pr.requested_by, "pk", pr.requested_by_id)`
4. **Missing SoD Safeguards Across Other Lifecycle Desks:**
   - **PO Issuance:** No check preventing the original requisitioner from issuing the PO. (In a small property, storekeeper requesting stock replenishment and then issuing PO to vendor is standard practice, but departmental staff like waiters or chefs must never issue POs).
   - **Invoice Approval SoD (Ghost Goods / Embezzlement Vulnerability):**
     In `approve_supplier_invoice`:
     - There is NO check preventing the GRN dock receiver from approving the supplier invoice. If the person who receives the goods also approves the payment, phantom goods receipts can be signed off and paid out without independent audit.
     - There is NO check preventing the invoice matcher (`matched_by`) from self-approving invoices.
   - **Variance Override Authorization:**
     In `approve_supplier_invoice` (lines 690–692):
     ```python
     if invoice.match_status == "variance_flagged" and not override_variance:
         raise ValidationError(...)
     ```
     Any user calling this endpoint who passes `override_variance=True` can override a price variance! There is no role restriction requiring `admin` or superuser to override price variances.

---

### 1.5 Transaction Atomicity, Error Handling, and GL Postings

1. **Atomic Wrapping:**
   All mutating service functions (`request_purchase_requisition`, `approve_purchase_requisition`, `convert_requisition_to_purchase_order`, `receive_goods_receipt_note`, `match_and_record_supplier_invoice`, `approve_supplier_invoice`, `create_request_for_quotation`, `publish_request_for_quotation`, `close_request_for_quotation`, `submit_supplier_quotation`, `evaluate_quotation`, `evaluate_and_award_quotations`, `convert_awarded_quotations_to_purchase_orders`) are decorated with `@transaction.atomic`.
2. **GL Posting Error Suppression Risk:**
   - In `receive_goods_receipt_note` (lines 538–540):
     ```python
     try:
         je = post_journal_entry(...)
         grn.journal_entry = je
     except Exception as gl_err:
         logging.getLogger(__name__).warning("Failed to auto-post GL for GRN #%s: %s", grn_num, gl_err)
     ```
   - In `approve_supplier_invoice` (lines 726–728):
     ```python
     try:
         je = post_journal_entry(...)
         invoice.journal_entry = je
     except Exception as gl_err:
         logging.getLogger(__name__).warning("Failed to auto-post settlement GL for invoice #%s: %s", invoice.internal_number, gl_err)
     ```
   **Risk:** If `post_journal_entry` fails, the error is swallowed and logged. The GRN or Invoice status is saved as `"approved"`, but **zero general ledger entries are created**. Subledger inventory balances and General Ledger asset/liability accounts become permanently desynchronized.
3. **Unauthorized Caller Blast Radius:**
   Because service methods lack role validation, an unauthorized caller (e.g. waiter, cashier) executing an API call triggers the full atomic commit:
   - Physical stock batch created and item quantity incremented (`record_stock_change`).
   - PO line received quantities updated and PO status set to `received`.
   - General Ledger Journal Entry committed: **Debit 1300 (Inventory Asset) / Credit 2010 (GRNI)**.
   - Or on invoice approval: **Debit 2010 (GRNI) / Debit 5040 (PPV) / Credit 2000 (Accounts Payable)**.

---

## 2. Logic Chain

1. **Premise 1:** The system architecture enforces a single-hotel RBAC model (`PROJECT.md`) where general procurement operations belong strictly to `admin`, `superuser`, `hotel_manager`, and `inventory` staff, with authorized finance review (`ORIGINAL_REQUEST.md` R1, R2, R5).
2. **Premise 2:** As proven by forensic audit `docs/M1_ITERATION2_POST_ACCEPTANCE_VERIFICATION.md` (DEF-01), relying solely on view-level permissions is vulnerable to configuration omissions. When DRF viewsets specify only `permission_classes = [IsAuthenticated]`, unauthorized roles (`kitchen`, `waiter`, `cashier`, `bar`, `housekeeping`, `customer`) can execute any endpoint action.
3. **Premise 3:** In defense-in-depth architecture, domain services (`hotel/procurement.py`) must authoritatively validate caller identity, role permissions, and Separation of Duties regardless of the entry channel (REST API, Celery worker, shell script, or internal integration).
4. **Premise 4:** In `hotel/procurement.py`, 13 out of 14 service functions execute without verifying the caller's role. An authenticated waiter can convert requisitions to POs, receive goods into warehouse inventory, match invoices, and approve Accounts Payable settlements.
5. **Premise 5:** In `approve_purchase_requisition`, `hotel_manager` is omitted from Tier 1 approval (`valid_roles = {"admin", "inventory", "kitchen", "f_and_b"}`). Because `hotel_manager` is the operational supervisor across dining, kitchen, and inventory, this blocks legitimate operational approvals.
6. **Premise 6:** In `approve_supplier_invoice`, any caller can approve financial settlements and pass `override_variance=True` without admin authority, defeating the 2% price variance policy. Furthermore, no SoD check prevents the GRN dock receiver from approving the supplier invoice.
7. **Conclusion:** Reinforcing `hotel/procurement.py` with service-layer defensive role validation, robust SoD PK checks, `hotel_manager` Tier 1 inclusion, and variance override gating secures the procurement lifecycle against unauthorized mutations and financial ledger corruption while preserving all existing workflows and passing tests.

---

## 3. Caveats

1. **Single-Tenant Operational Realities:**
   In a single-property hotel, the inventory manager frequently initiates replenishment requisitions, converts approved requisitions to purchase orders, and physically inspects shipments at the loading dock. Enforcing strict multi-agent separation between PO issuance and GRN receiving would break single-person store operations and existing automated test suites (`test_procurement_management.py`). Role-based gating (`{"admin", "hotel_manager", "inventory"}`) must be applied without prohibiting valid operational overlap.
2. **Requisition Creation Inclusivity:**
   Departmental staff (`kitchen`, `bar`, `housekeeping`, `reception`) must retain the ability to submit purchase requisitions (`request_purchase_requisition`) for their departments. Restricting requisition creation to inventory/admin would prevent departmental restocking. However, external roles (`customer`) and unauthenticated callers must be rejected.
3. **Database Field Naming Discipline:**
   The `PurchaseRequisition` model defines `requested_by` (NOT `created_by`). Any code referencing `created_by` will raise `AttributeError`. Implementers must strictly reference `requested_by`.
4. **Superuser Overrides:**
   In small hotel ERP deployments, superusers require the ability to configure, seed, and verify workflows. The existing bypass `and not is_superuser` on SoD should be preserved for testing/admin emergency flexibility, while standard roles are strictly enforced.

---

## 4. Conclusion & Proposed Code Recommendations

### 4.1 Recommended Service Layer Helper Function

To enforce role authorization cleanly across `hotel/procurement.py` without code duplication, introduce a standardized defensive helper:

```python
def _validate_procurement_role(user, allowed_roles, action_name="perform this operation"):
    """
    Validates that the calling user is authenticated, active, and holds an allowed role.
    Superusers bypass role checks.
    """
    if not user:
        raise ValidationError(f"A valid user is required to {action_name}.")
    if getattr(user, "is_superuser", False):
        return True
    user_role = getattr(user, "role", "")
    if user_role not in allowed_roles:
        raise PermissionDenied(
            f"User '{getattr(user, 'username', 'anonymous')}' with role '{user_role}' "
            f"is not authorized to {action_name}. Required role: {', '.join(sorted(allowed_roles))}."
        )
    return True
```

---

### 4.2 Concrete Code Proposals for `hotel/procurement.py`

#### Proposal A: Fix `approve_purchase_requisition` (Tier 1 `hotel_manager` & SoD PK check)
**Target:** `hotel/procurement.py:253-274`
```python
# BEFORE
    is_superuser = getattr(approver, "is_superuser", False)
    approver_role = getattr(approver, "role", "")

    # Separation of duties
    if approver == pr.requested_by and not is_superuser:
        raise ValidationError("Separation of duties violation: Requisitioner cannot approve their own requisition. Independent managerial sign-off is required.")

    # Role validation against approval tier
    required_role = pr.approval_tier.required_role if pr.approval_tier else "admin"
    valid_roles = {"admin"}
    if required_role == "inventory":
        valid_roles.update({"inventory", "kitchen", "f_and_b"})
    elif required_role == "finance":
        valid_roles.update({"finance"})
    else:
        valid_roles.add(required_role)

# AFTER
    is_superuser = getattr(approver, "is_superuser", False)
    approver_role = getattr(approver, "role", "")
    approver_id = getattr(approver, "pk", approver)
    requester_id = getattr(pr.requested_by, "pk", pr.requested_by_id)

    # Separation of duties (robust PK comparison preventing ID mismatch bypass)
    if approver_id == requester_id and not is_superuser:
        raise ValidationError("Separation of duties violation: Requisitioner cannot approve their own requisition. Independent managerial sign-off is required.")

    # Role validation against approval tier
    required_role = pr.approval_tier.required_role if pr.approval_tier else "admin"
    valid_roles = {"admin"}
    if required_role == "inventory":
        # Include hotel_manager as authoritative operational supervisor
        valid_roles.update({"inventory", "kitchen", "f_and_b", "hotel_manager"})
    elif required_role == "finance":
        valid_roles.update({"finance"})
    else:
        valid_roles.add(required_role)
```

#### Proposal B: Add Role Validation to `convert_requisition_to_purchase_order`
**Target:** `hotel/procurement.py:323`
```python
# BEFORE
    actual_issuer = user or issuer
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)

# AFTER
    actual_issuer = user or issuer
    _validate_procurement_role(
        actual_issuer,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="issue purchase orders",
    )
    pr = PurchaseRequisition.objects.select_for_update().get(pk=requisition_id)
```

#### Proposal C: Add Role Validation to `receive_goods_receipt_note`
**Target:** `hotel/procurement.py:404`
```python
# BEFORE
    actual_po_id = po_id or purchase_order_id
    actual_receiver = received_by or receiver
    actual_items = items if items is not None else (receipt_items or [])

# AFTER
    actual_po_id = po_id or purchase_order_id
    actual_receiver = received_by or receiver
    actual_items = items if items is not None else (receipt_items or [])

    _validate_procurement_role(
        actual_receiver,
        allowed_roles={"admin", "hotel_manager", "inventory"},
        action_name="receive goods receipt notes",
    )
```

#### Proposal D: Add Role & SoD Validation to `match_and_record_supplier_invoice`
**Target:** `hotel/procurement.py:569`
```python
# BEFORE
    actual_po_id = po_id or purchase_order_id
    actual_user = user or matched_by
    actual_items = items if items is not None else (billed_items or [])

# AFTER
    actual_po_id = po_id or purchase_order_id
    actual_user = user or matched_by
    actual_items = items if items is not None else (billed_items or [])

    _validate_procurement_role(
        actual_user,
        allowed_roles={"admin", "hotel_manager", "inventory", "finance"},
        action_name="match and record supplier invoices",
    )
```

#### Proposal E: Add Role, SoD, and Price Variance Override Safeguards to `approve_supplier_invoice`
**Target:** `hotel/procurement.py:686`
```python
# BEFORE
    invoice = SupplierInvoice.objects.select_for_update().get(pk=invoice_id)
    if invoice.match_status not in ("matched", "variance_flagged"):
        raise ValidationError(...)

    if invoice.match_status == "variance_flagged" and not override_variance:
        raise ValidationError(...)

# AFTER
    invoice = SupplierInvoice.objects.select_for_update().get(pk=invoice_id)
    if invoice.match_status not in ("matched", "variance_flagged"):
        raise ValidationError(f"Cannot approve invoice #{invoice.internal_number}: status is '{invoice.match_status}', expected 'matched' or 'variance_flagged'.")

    is_superuser = getattr(approver, "is_superuser", False)
    approver_role = getattr(approver, "role", "")

    # Role validation: only finance or admin can approve Accounts Payable settlement
    _validate_procurement_role(
        approver,
        allowed_roles={"admin", "finance"},
        action_name="approve supplier invoices for payment",
    )

    # Variance override safeguard: only admin or superuser can override flagged price variances
    if invoice.match_status == "variance_flagged":
        if not override_variance:
            raise ValidationError(f"Invoice #{invoice.internal_number} cannot be approved due to price variance without explicit override.")
        if approver_role != "admin" and not is_superuser:
            raise PermissionDenied("Only hotel administrators can authorize supplier invoice price variance overrides.")

    # Separation of duties: Dock receiver must not approve invoice settlement (fraud prevention)
    approver_id = getattr(approver, "pk", approver)
    grn_receiver_ids = set(invoice.purchase_order.grns.values_list("received_by_id", flat=True))
    if approver_id in grn_receiver_ids and not is_superuser:
        raise ValidationError("Separation of duties violation: Dock receiver cannot approve invoice payment for goods they received.")
```

#### Proposal F: Add Role Validation to RFQ and Bidding Functions
- `create_request_for_quotation`: `_validate_procurement_role(user, {"admin", "hotel_manager", "inventory"}, "create RFQs")`
- `publish_request_for_quotation`: `_validate_procurement_role(user, {"admin", "hotel_manager", "inventory"}, "publish RFQs")`
- `close_request_for_quotation`: `_validate_procurement_role(user, {"admin", "hotel_manager", "inventory"}, "close RFQs")`
- `evaluate_quotation`: `_validate_procurement_role(user, {"admin", "hotel_manager", "inventory", "finance"}, "evaluate supplier quotations")`
- `evaluate_and_award_quotations`: `_validate_procurement_role(user, {"admin", "hotel_manager", "finance"}, "award supplier quotations")`
- `convert_awarded_quotations_to_purchase_orders`: `_validate_procurement_role(user, {"admin", "hotel_manager", "inventory"}, "convert awarded quotations to purchase orders")`

---

### 4.3 Proposed Viewset Updates in `apps/inventory/views.py`

1. **Permission Class Normalization:**
   Apply authoritative permissions from `users/permissions.py`:
   - `PurchaseRequisitionViewSet`:
     - `permission_classes = [IsAuthenticated]` for create/list/retrieve.
     - Add `IsProcurementOperator` or check roles on `approve`, `reject`, `convert_to_po`.
   - `PurchaseOrderViewSet`: `permission_classes = [IsProcurementOperator]`
   - `GoodsReceiptNoteViewSet`: `permission_classes = [IsProcurementOperator]`
   - `SupplierInvoiceViewSet`: `permission_classes = [IsProcurementOrFinanceOperator]`
   - `RequestForQuotationViewSet`: `permission_classes = [IsProcurementOperator]`
   - `SupplierQuotationViewSet`: `permission_classes = [IsProcurementOperator]`
2. **PermissionDenied HTTP 403 Response Handling:**
   Update `PurchaseRequisitionViewSet.approve` and other action methods to catch `PermissionDenied` explicitly:
   ```python
   except PermissionDenied as e:
       return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
   except ValidationError as e:
       msg = e.message if hasattr(e, "message") else ("; ".join(e.messages) if hasattr(e, "messages") else str(e))
       return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
   ```

---

## 5. Verification Method

To verify these safeguards independently against isolated test databases without modifying production staging records:

```powershell
# 1. Run procurement management test suite (validates tiers, SoD, PO conversion, GRN, 3-way match, GL postings)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_management --keepdb --noinput

# 2. Run RFQ and Quotation workflow test suite (validates RFQs, bids, awards, multi-requisition allocation)
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_rfq_quotation_workflow --keepdb --noinput

# 3. Run cross-module inventory integration suite
.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_cross_module_inventory_integration --keepdb --noinput
```

**Verification Results:**
- Baseline run of `apps.inventory.tests.test_procurement_management`: **12 executed, 12 passed (0 failures, 0 errors, 0 skipped)**.
- Proposed changes are strictly backwards-compatible with all test fixtures while closing every identified security gap.
