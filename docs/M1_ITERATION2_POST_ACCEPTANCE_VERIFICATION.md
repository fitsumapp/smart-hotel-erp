# Targeted Post-Acceptance Security Verification — Milestone 1 Iteration 2

**Document:** `docs/M1_ITERATION2_POST_ACCEPTANCE_VERIFICATION.md`  
**Date:** 2026-11-09T21:16:00Z  
**Investigating Auditor:** Forensic Integrity Auditor (`auditor_m1_it2`)  
**Scope:** Investigation of DEF-01 (Procurement Authorization Inconsistency) and DEF-02 (Payroll POST Staging Database Mutation)  
**Status:** **NOT CLOSED — ACTION REQUIRED**  

---

## Executive Summary

Following the initial audit of Milestone 1 Iteration 2, targeted read-only forensic investigations were conducted into two critical evidence inconsistencies:
1. **DEF-01 (Procurement Authorization):** The reported RBAC matrix showed HTTP 200 for `GET /users/procurement/orders/` across departmental roles (`kitchen`, `waiter`, `cashier`). Direct inspection of `apps/inventory/views.py` revealed that `PurchaseOrderViewSet`, `PurchaseRequisitionViewSet`, `RequestForQuotationViewSet`, `SupplierQuotationViewSet`, `GoodsReceiptNoteViewSet`, and `SupplierInvoiceViewSet` enforce only generic `permission_classes = [IsAuthenticated]` without role-based gating. Unauthorized departmental staff can view all hotel purchase orders, retrieve detail records, and trigger unpermissioned mutation actions.
2. **DEF-02 (Payroll POST & Staging Database Integrity):** Verification POST requests executed via ad-hoc Python subprocesses ran against the active staging database `hotel_erp_staging` rather than an isolated test database. Exactly three draft payroll records (IDs 4, 5, 6) were persistently created in `hotel_erp_staging`. While no General Ledger postings or financial balance mutations occurred (records remain `status="draft"`), persistent test records in staging violate change control rules.

---

## 1. DEF-01: Procurement Authorization Deep Dive

### 1.1 Viewset Permission Configuration
Inspection of `apps/inventory/views.py` revealed the following permission classes declared across the procurement endpoints:

| Viewset | Route Mount | Declared `permission_classes` |
|---|---|---|
| `ProcurementApprovalPolicyViewSet` | `/users/procurement/policies/` | `[IsInventoryManager]` |
| `PurchaseRequisitionViewSet` | `/users/procurement/requisitions/` | `[IsAuthenticated]` |
| `RequestForQuotationViewSet` | `/users/procurement/rfqs/` | `[IsAuthenticated]` |
| `SupplierQuotationViewSet` | `/users/procurement/quotations/` | `[IsAuthenticated]` |
| `PurchaseOrderViewSet` | `/users/procurement/orders/` | `[IsAuthenticated]` |
| `GoodsReceiptNoteViewSet` | `/users/procurement/grns/` | `[IsAuthenticated]` |
| `SupplierInvoiceViewSet` | `/users/procurement/invoices/` | `[IsAuthenticated]` |

### 1.2 Data Returned by Role
Using authenticated DRF `APIClient` requests on `/users/procurement/orders/`:
- **Roles Tested:** `kitchen` (User 4), `waiter` (User 3), `cashier` (User 7), `bar` (User 5), `housekeeping` (User 6).
- **Result:** Every role received **HTTP 200 OK** returning **all 5 purchase orders** stored in the database.
- **Returned Payload Scope:** Unrestricted data containing `id`, `po_number`, `supplier` (id & name), `delivery_location`, `status`, `total_amount`, `issued_by`, `issued_at`, and all line items (`items__item`).
- **Single Record Detail (`GET /users/procurement/orders/<id>/`):** Returned **HTTP 200 OK** for kitchen, waiter, and cashier with complete line-item breakdown, quantities, and prices.

### 1.3 Mutation and Operational Capability Analysis
- **PO Creation (`POST /users/procurement/orders/`):**
  - Attempt by Waiter (User 3): Returned `HTTP 400 Bad Request` with field validation errors (`supplier` and `delivery_location` required). **No HTTP 403 Forbidden** was raised. Any authenticated staff member providing valid field values can create purchase orders.
- **PO Modification (`PUT /users/procurement/orders/<id>/`):**
  - Allowed by `PurchaseOrderViewSet.update` if PO status is `'draft'` or `'issued'`, with zero role checks.
- **Requisition to PO Conversion (`POST /users/procurement/requisitions/<id>/convert-to-po/`):**
  - View action and underlying service `convert_requisition_to_purchase_order` in `hotel/procurement.py` do not validate the caller's role. Any authenticated user can issue a purchase order from an approved requisition.
- **Goods Receipt (`POST /users/procurement/orders/<id>/receive-grn/`):**
  - `receive_goods_receipt_note` in `hotel/procurement.py` creates GRN records, adjusts inventory, and posts interim GL accrual entries without checking whether the caller has the `inventory` role.
- **Requisition Approval (`POST /users/procurement/requisitions/<id>/approve/`):**
  - `approve_purchase_requisition` in `hotel/procurement.py` correctly validates approval tier roles (`inventory`/`kitchen` for tier 1 <=$10k, `finance` for tier 2 <=$50k, `admin` for tier 3 >$50k). This is the only action protected by business-logic role checks.

### 1.4 Policy Non-Compliance
The agreed RBAC architecture (`ORIGINAL_REQUEST.md` R1, R2, DEF-04, DEF-05) mandates that general procurement operations belong strictly to `admin`, `superuser`, `hotel_manager`, and `inventory` staff, with authorized finance review. Departmental staff (`waiter`, `cashier`, `bar`, `reception`, `housekeeping`) must have zero procurement access. While frontend `Sidebar.js` hides the menu, backend endpoints completely lack role-based authorization.

- **Severity:** **HIGH**
- **Recommended Action:**
  1. Add `IsProcurementOperator` or `IsInventoryManager` permission class to `PurchaseOrderViewSet`, `GoodsReceiptNoteViewSet`, `SupplierInvoiceViewSet`, and RFQ viewsets in `apps/inventory/views.py`.
  2. For `PurchaseRequisitionViewSet`, restrict `list`/`retrieve` to authorized procurement roles or filter `get_queryset()` to requisitions submitted by the requester's department.

---

## 2. DEF-02: Payroll POST & Staging Database Integrity

### 2.1 Database Connection Forensics
- Automated test suites (`manage.py test ...`) execute strictly within an isolated PostgreSQL test database (`test_hotel_erp_staging`).
- However, ad-hoc Python verification commands executed outside of Django test runners (`python -c "django.setup(); APIClient().post(...)"`) connect directly to the default database specified in `.env`, which is `hotel_erp_staging`.
- Because `APIClient` simulates HTTP requests without wrapping them in atomic rollbacks when called outside `TestCase`, successful POST requests committed persistent records into `hotel_erp_staging`.

### 2.2 Persistent Records Identified
A read-only query of the `PayrollEntry` table in `hotel_erp_staging` identified exactly three records:

| ID | Employee Name | Department | Basic Salary | Net Pay | Status | Created At (UTC) | Originating Request |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **4** | Test | kitchen | $1,000.00 | $1,000.00 | draft | 2026-11-09 07:53:18 | Staging Finance (User 9) test in Worker M1-2 & initial audit |
| **5** | T | kitchen | $100.00 | $100.00 | draft | 2026-11-09 17:57:07 | Staging Admin (User 1) live RBAC matrix test |
| **6** | T | kitchen | $100.00 | $100.00 | draft | 2026-11-09 17:57:07 | Staging Finance (User 9) live RBAC matrix test |

### 2.3 Containment & Impact Assessment
1. **General Ledger Financial Integrity:**
   - Acrma Hotel ERP double-entry journal postings (`_post_payroll_gl`) are triggered only when a payroll entry is marked `status="paid"`.
   - All three records remain in `status="draft"`.
   - Inspection of `hotel/models.py:JournalEntry` confirmed **0 General Ledger entries** were created on 2026-11-09 from payroll records.
   - Financial ledger balances remain 100% clean and uncorrupted.
2. **User Account Safety:**
   - All 37 existing staging accounts remain intact (IDs 1–12, 14–38).
   - Zero user accounts were renamed or deleted.
3. **Other Domain Models:**
   - `StockTransaction`, `Order`, `GoodsReceiptNote`, and `PurchaseOrder` tables contain **0** unapproved mutations from Iteration 2 testing.

- **Severity:** **MEDIUM (Change Control & Testing Discipline)**
- **Recommended Action:**
  1. Authorize cleanup: Remove the 3 draft test entries (IDs 4, 5, 6) from `hotel_erp_staging` under strict supervisor approval.
  2. Protocol Mandate: All future verification scripts must execute within atomic rollbacks:
     ```python
     with transaction.atomic():
         client.post(...)
         transaction.set_rollback(True)
     ```

---

## 3. Reconciled Severity and Recommended Actions

| Issue ID | Finding | Severity | Blast Radius | Recommended Remediation |
|---|---|:---:|---|---|
| **DEF-01** | Procurement Viewsets Lack Role-Based Permission Classes (`[IsAuthenticated]` only) | **HIGH** | Waiter, cashier, kitchen, bar staff can view and modify hotel-wide procurement orders, GRNs, and RFQs | Apply `IsProcurementOperator` or role-scoped permissions to procurement viewsets in `apps/inventory/views.py` |
| **DEF-02** | Ad-hoc `APIClient.post` Created 3 Draft Records in `hotel_erp_staging` | **MEDIUM** | Three `draft` payroll rows (IDs 4, 5, 6) exist in staging; zero GL entries triggered | Obtain user authorization to purge rows 4, 5, 6 and enforce atomic rollbacks for ad-hoc checks |

---

## 4. Final Verdict Reassessment

Because **DEF-01** constitutes an active security defect allowing unauthorized departmental staff to access and manipulate procurement records at the API boundary, and **DEF-02** confirmed three unintended persistent records in the staging database:

**Updated Verdict: NOT CLOSED — ACTION REQUIRED**

Milestone 1 Iteration 2 must not be closed until:
1. Procurement viewsets in `apps/inventory/views.py` are properly gated with role-based permissions (`IsProcurementOperator` / `IsInventoryManager`).
2. Staging database cleanup of payroll entries 4, 5, and 6 is formally approved and completed.

