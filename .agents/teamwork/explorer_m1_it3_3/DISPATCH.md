## 2026-11-09T18:33:47Z
You are Explorer 3 for Milestone 1 Iteration 3: Procurement Test & Database Cleanup Explorer.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_3\

MANDATORY INPUTS (READ FIRST):
1. User Request: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md
2. Project Architecture & Contracts: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md
3. Forensic Auditor Evidence Report: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\docs\M1_ITERATION2_POST_ACCEPTANCE_VERIFICATION.md
4. Target Test Files: apps/inventory/tests/ (e.g. test_rfq_quotation_workflow.py, test_stocktaking_management.py, test_inventory_integrity.py)

YOUR MISSION:
1. Automated Regression Test Suite Design:
   - Design a dedicated test suite (e.g. `apps/inventory/tests/test_procurement_rbac.py`) to systematically test RBAC boundaries across all 7 procurement endpoints:
     - Departmental roles (`kitchen`, `bar`, `waiter`, `cashier`, `reception`, `housekeeping`, `customer`) must receive `HTTP 403 Forbidden` on:
       - List: `GET /users/procurement/orders/`, `requisitions/`, `rfqs/`, `quotations/`, `grns/`, `invoices/`, `policies/`
       - Retrieve: `GET /users/procurement/orders/<id>/`, etc.
       - Create: `POST /users/procurement/orders/`, etc.
       - Custom actions: `convert-to-po`, `receive-grn`, `record-invoice`, `approve`, `reject`
     - Authorized roles (`admin`, `hotel_manager`, `inventory`, `finance`) must retain appropriate access:
       - `inventory`: Can view, create, convert, receive GRN within tier limits.
       - `hotel_manager`: Full operational visibility and management.
       - `finance`: Can view orders/invoices, perform invoice matching, approve Tier 2.
       - `admin`: Full property-wide access including Tier 3 approvals.
     - SoD testing: requester cannot approve own requisition.
     - Tier threshold boundary testing: verify Tier 1/2/3 role enforcement.
   - Ensure tests run cleanly against isolated test DB (`test_hotel_erp_staging` with `--keepdb`).

2. Staging Database Cleanup Strategy (DEF-02):
   - The user has formally authorized deletion of ONLY the three draft test records in `hotel_erp_staging`:
     - `PayrollEntry id=4`: `employee_name='Test'`, `status='draft'`
     - `PayrollEntry id=5`: `employee_name='T'`, `status='draft'`
     - `PayrollEntry id=6`: `employee_name='T'`, `status='draft'`
   - Design an exact, non-destructive script (e.g. `scratch/cleanup_staging_payroll.py`) that:
     - Confirms connection to `hotel_erp_staging`.
     - Inspects records 4, 5, 6: asserts `status == "draft"`, asserts `basic_salary` values, asserts 0 related journal entries.
     - Performs targeted `.delete()` only on `id__in=[4, 5, 6]`.
     - Verifies count after deletion.
     - Verifies all 37 user accounts remain completely intact.
     - Mandates atomic rollbacks for any future verification scripts.

CONSTRAINTS:
- You are READ-ONLY. Do NOT modify source code or database.
- Produce a structured handoff report in `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it3_3\handoff.md`.
- Update your progress.md regularly. Report back via send_message when done.
