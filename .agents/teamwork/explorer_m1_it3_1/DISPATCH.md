## 2026-11-09T18:33:26Z
[Message] timestamp=2026-11-09T18:33:26Z sender=bf049e91-d4c5-4607-97c7-1c2a2247987f priority=MESSAGE_PRIORITY_HIGH content=You are Explorer 1 for Milestone 1 Iteration 3: Procurement ViewSet RBAC Explorer.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_1\

MANDATORY INPUTS (READ FIRST):
1. User Request: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md
2. Project Architecture & Contracts: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md
3. Forensic Auditor Evidence Report: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\docs\M1_ITERATION2_POST_ACCEPTANCE_VERIFICATION.md
4. Gate Status: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\orchestrator\GATE_STATUS.md
5. Target Backend Files: apps/inventory/views.py, users/permissions.py

YOUR MISSION:
Investigate DEF-01 (Procurement Authorization Gap) at the API boundary in `apps/inventory/views.py`:
- All 7 procurement viewsets (`PurchaseOrderViewSet`, `PurchaseRequisitionViewSet`, `RequestForQuotationViewSet`, `SupplierQuotationViewSet`, `GoodsReceiptNoteViewSet`, `SupplierInvoiceViewSet`, `ProcurementApprovalPolicyViewSet`) currently declare only `permission_classes = [IsAuthenticated]`.
- Departmental staff (`kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`) currently receive HTTP 200 and can list/retrieve detail records and call unpermissioned actions (`convert-to-po`, `receive-grn`, etc.).
- Propose exact permission classes to be defined in `users/permissions.py` (e.g., `IsProcurementStaffOrAdmin`, `IsProcurementOrFinanceOperator`) and mapped to each viewset in `apps/inventory/views.py`.
- Ensure role policy strictly adheres to single-hotel requirements:
  - `superuser` / `admin`: Full property-wide access.
  - `hotel_manager`: Full operational access across procurement resources.
  - `inventory`: Primary procurement operations subject to approval tier thresholds.
  - `finance`: Financial review, invoice matching, Tier 2 approvals.
  - Departmental staff: Strictly DENIED (`HTTP 403 Forbidden`) across list, retrieve, create, update, delete, and all custom actions.
  - For `PurchaseRequisitionViewSet`: evaluate whether departmental users should submit requisitions for their own department only or if all procurement is centralized through inventory. Propose exact `get_queryset()` and action-level protections.

CONSTRAINTS:
- You are READ-ONLY. Do NOT modify source code or database.
- Produce a structured handoff report in `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_1\handoff.md` with:
  1. Detailed viewset-by-viewset permission analysis.
  2. Concrete Python code proposals for `users/permissions.py` and `apps/inventory/views.py`.
  3. Action-level protection matrix for custom methods (`approve`, `reject`, `convert_to_po`, `receive_grn`, `record_invoice`).
- Update your progress.md regularly. Report back via send_message when done.
