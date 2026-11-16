## 2026-11-11T07:33:20Z

You are Worker M2 (Full Regression and Build Verification Worker) for Acrma Hotel ERP RBAC Architecture Corrections.

Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m2\

Mandatory Documents to read first:
- ORIGINAL_REQUEST.md: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md
- PROJECT.md: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md
- Iteration 3 Forensic Closure Report: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\docs\M1_ITERATION3_FORENSIC_CLOSURE_REPORT.md
- Challenger 2 Handoff: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\challenger_m1_it3_2\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope Boundaries & Safety Rules:
- ZERO git commits, ZERO git pushes, ZERO git resets (`git checkout --`, `git reset`, `git clean` are strictly forbidden).
- NEVER modify production databases or connect to anything other than `hotel_erp_staging` / `test_hotel_erp_staging`.
- Exclusive write ownership: `apps/inventory/views.py`, `hotel/procurement.py`, `apps/inventory/tests/test_procurement_rbac.py`. Do NOT touch files owned by other modules unless strictly necessary for compilation/tests.

Tasks to Execute:

Task 1: Targeted Remediation of DEF-M1-IT3-01 (Cross-Department Requisition Rejection Bypass)
- In `apps/inventory/views.py:802` (`PurchaseRequisitionViewSet.reject`):
  Add `req_obj = self.get_object()` before invoking `reject_purchase_requisition`. This ensures DRF's `get_queryset()` row-scoping is evaluated, immediately returning `HTTP 404 NOT FOUND` if a user attempts to reject a requisition outside their department.
- In `hotel/procurement.py:400` (`reject_purchase_requisition`):
  Add defensive role/ownership validation:
  `_validate_procurement_role(rejecter, allowed_roles={"admin", "hotel_manager", "inventory", "kitchen", "bar", "housekeeping"}, action_name="reject requisitions")`
- In `apps/inventory/tests/test_procurement_rbac.py`:
  Add test `test_cross_department_rejection_blocked` asserting `HTTP 404 NOT FOUND` when kitchen staff attempts to call `POST /users/procurement/requisitions/<bar_id>/reject/`.
- Verify with:
  `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_procurement_rbac --keepdb --noinput`
  `.venv\Scripts\python.exe scratch/test_empirical_challenger_m1_it3_2.py` (Must pass 25/25).

Task 2: Full Serial Execution of all Backend Regression Suites (R4)
Execute the following test suites serially (one after another, never in parallel to avoid PostgreSQL index contention on `users_user_username_key`) using `.venv\Scripts\python.exe manage.py test <suite> --keepdb --noinput`:
1. `apps.inventory.tests`
2. `apps.orders.tests`
3. `apps.identity.tests`
4. `users.test_milestone2_workflows`
5. `users.test_phase3_integrity`
6. `apps.finance.tests`
For each test suite, accurately capture:
- Suite name & command executed
- Discovered test count
- Executed test count
- Passed test count
- Failed test count
- Error test count
- Skipped test count
- Execution runtime in seconds
Reconcile all counts into a non-double-counted master regression table.

Task 3: Frontend Test & Build Verification
- In `hotel-frontend`:
  - Run `npm test -- --watchAll=false` (or `npx react-scripts test --watchAll=false --passWithNoTests`)
  - Run frontend build check `npm run build` (or verify that no syntax/transpilation errors exist)
  - Verify that `hotel_manager` and `inventory` routing and sidebar navigation are free of syntax/runtime errors.

Task 4: Staging Database & Safety Invariant Check
- Verify that `hotel_erp_staging` retains exactly 37 user accounts across all 11 roles, 0 draft payroll records, and 84 journal entries.

Task 5: Deliverable
- Write comprehensive handoff report in `.agents/teamwork/worker_m2/handoff.md` following the Handoff Protocol (Observation, Logic Chain, Caveats, Conclusion, Verification Method) with the complete reconciled test table and verification commands.
- Send a completion message to the orchestrator with the handoff path.



## 2026-11-11T08:47:18Z

**Context**: Immediate Coordinator Directive regarding Test Execution
**Content**: Top-level Coordinator Directive received: Do NOT launch any further 'manage.py test' processes. The Coordinator is running all test suites serially to prevent PostgreSQL deadlock collisions on test_hotel_erp_staging.
**Action**: Immediately cease launching any new test commands. If any `manage.py test` process or task (such as task-304) is currently running in your workspace, terminate/cancel it immediately to grant exclusive database access to the Coordinator. Complete your Task 3 (Frontend Test/Build verification, which passed) and Task 4 (Staging Invariant verification, which passed), persist your work in handoff.md, and stand by without initiating any further test executions.
