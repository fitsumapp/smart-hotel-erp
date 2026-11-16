# BRIEFING — 2026-11-09T19:13:00Z

## Mission
Implement Procurement RBAC enforcement across permissions, views, and service layer, deploy and run staging payroll cleanup, and ensure full test suite passes.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
- State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1_it3\
- Original parent: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Milestone: M1-3 Procurement RBAC and Staging Remediation

## 🔒 Key Constraints
- EXCLUSIVE write ownership of:
  1. `users/permissions.py`
  2. `apps/inventory/views.py`
  3. `hotel/procurement.py`
  4. `apps/inventory/tests/test_procurement_rbac.py`
  5. `scratch/cleanup_staging_payroll.py`
- DO NOT modify any other files.
- DO NOT CHEAT. All implementations must be genuine.
- Maintain real state and logic, no facade or hardcoded returns.
- Connect to `hotel_erp_staging` for the staging cleanup script, deleting strictly PayrollEntry IDs 4, 5, 6.
- Run all regression and new tests with `--keepdb --noinput`.

## Current Parent
- Conversation ID: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Updated: 2026-11-09T19:13:00Z

## Task Summary
- **What to build**:
  1. `users/permissions.py`: Add `hotel_manager` to `IsSupplierOperator`, create `IsPurchaseRequisitionStaff`.
  2. `apps/inventory/views.py`: Apply RBAC permissions, row-level scoping for PRs, action-level permission overrides, SoD checks.
  3. `hotel/procurement.py`: Add `_validate_procurement_role`, enforce role checks & SoD across all procurement lifecycle service functions.
  4. `scratch/cleanup_staging_payroll.py`: Deploy and run payroll entry cleanup (IDs 4, 5, 6) in staging.
  5. `apps/inventory/tests/test_procurement_rbac.py`: Deploy and verify 18 comprehensive RBAC test cases.
- **Success criteria**:
  - All staging payroll cleanup assertions pass (DB verified, IDs 4, 5, 6 deleted, 0 drafts left, 37 users preserved).
  - All test suites pass: `test_procurement_rbac` (18 passed), `test_procurement_management` (12 passed), `test_rfq_quotation_workflow` (10 passed), `test_bill_request_handover` + `test_milestone2_workflows` + `apps.finance.tests` (30 passed). Total: 70/70 passed.
- **Interface contracts**: PROJECT.md, Explorer handoffs 1, 2, 3.

## Key Decisions Made
- Implemented Department-Scoped Requisition Submission (Option B) for `PurchaseRequisitionViewSet`: allows operational departments (kitchen, bar, housekeeping) to submit requisitions for their own department while enforcing row-level isolation in `get_queryset()` and reserving `convert_to_po` strictly for procurement operators.
- Enforced strict Separation of Duties in `hotel/procurement.py` using robust PK comparison to prevent integer vs User comparison bypass.
- Enforced dock receiver SoD check on invoice settlement approval (`approve_supplier_invoice`) preventing dock receivers from signing off invoice payments for goods they received.
- Enforced admin-only authorization for supplier invoice price variance overrides.

## Artifact Index
- `.agents/teamwork/worker_m1_it3/DISPATCH.md` — Dispatch instructions
- `.agents/teamwork/worker_m1_it3/BRIEFING.md` — Worker briefing
- `.agents/teamwork/worker_m1_it3/progress.md` — Liveness and task progress
- `.agents/teamwork/worker_m1_it3/handoff.md` — Comprehensive completion report

## Change Tracker
- **Files modified**:
  1. `users/permissions.py` — Updated `IsSupplierOperator` to include `hotel_manager`; defined `IsPurchaseRequisitionStaff`.
  2. `apps/inventory/views.py` — Applied `IsProcurementOrFinanceOperator`, `IsPurchaseRequisitionStaff`, `IsProcurementOperator`, action guards, row-scoping, and HTTP 403 response handling.
  3. `hotel/procurement.py` — Added `_validate_procurement_role`, robust SoD PK comparisons, Tier 1 `hotel_manager` authorization, AP invoice approval safeguards, and RFQ service validations.
  4. `apps/inventory/tests/test_procurement_rbac.py` — Created 18 comprehensive RBAC and SoD regression tests.
  5. `scratch/cleanup_staging_payroll.py` — Executed non-destructive deletion of draft payroll records 4, 5, 6 in `hotel_erp_staging`.
- **Build status**: PASS (70/70 tests passed across all suites).
- **Pending issues**: None.

## Quality Status
- **Build/test result**: PASS (0 failures, 0 errors, 0 skipped across 70 tests).
- **Lint status**: Clean (py_compile 0 errors).
- **Tests added/modified**: 18 new automated tests in `test_procurement_rbac.py`.
