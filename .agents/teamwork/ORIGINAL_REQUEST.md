# Original User Request

## Approved Task Prompt — 2026-11-09T06:16:00Z

Complete the targeted role, permission, and frontend corrections for Acrma Hotel ERP based on AUDIT-RBAC-ARCHITECTURE-2026-V1.0, and verify all changes through automated regression suites and real-browser acceptance.

Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
Integrity mode: development

## Verification Resources
- Role and Permission Audit Report: `docs/ROLE_AND_PERMISSION_AUDIT_REPORT.md` (AUDIT-RBAC-ARCHITECTURE-2026-V1.0)
- Existing automated test suites in `apps/*/tests/` (including `apps/inventory/tests/`, `apps/orders/tests/`, `apps/identity/tests/`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`)
- Verification and audit scripts in `scratch/` (including role auditing scripts and Selenium browser verification scripts)
- Staging database configuration (`hotel_erp_staging` / `.env`) and isolated Django test runners

## Requirements

### R1. Authoritative Role and Supervisor Normalization (DEF-01, DEF-02, DEF-03)
- Formalize `hotel_manager` in `User.ROLE_CHOICES`, model validation, serializers, admin forms, and role-dependent backend logic, preserving existing hotel manager accounts and role values without renaming or deleting users.
- Configure frontend routing, navigation, and route guards (`hotel-frontend/src/App.js`, `Sidebar.js`, `DashboardLayout`) to render the operational dashboard for `hotel_manager` without displaying Unauthorized, blank screens, or exposing superuser technical controls.
- Normalize supervisor authorization checks across orders, cancellations, and dining workflows by replacing `["admin", "manager"]` checks with authoritative role policy checks that recognize `hotel_manager` while preserving superuser privileges and avoiding unintended financial/technical permissions.

### R2. Inventory Role and Hotel-Wide Stock Permissions (DEF-04, DEF-05)
- Provide full frontend access for `inventory` users to Inventory Dashboard, Stocktake Center, Procurement Center, expiry and batch alerts, stock locations, stock transfers, purchase requisitions, RFQs, purchase orders, GRNs, and supplier invoice matching, without assigning the `admin` role.
- Implement single-hotel global stock permissions granting `admin`, superuser, `hotel_manager`, and `inventory` staff global access across all stock locations (including unassigned locations).
- Remove default-allow fallback for unassigned locations (`custodian IS NULL`), ensuring departmental users (`kitchen`, `bar`, `waiter`, `cashier`) receive no general warehouse or stocktaking access unless explicitly authorized.
- Preserve stocktake workflows (draft/count/recount/approval/cancellation), blind mode, separation of duties (preventing self-approval), audit history, and FIFO/FEFO protections.

### R3. External Supplier Identity Architecture Review (DEF-06)
- Inspect external supplier authentication and quotation architecture regarding the use of the `customer` role.
- Determine whether suppliers authenticate through the customer portal, supplier records, or another mechanism without automatically introducing new roles or altering existing accounts.
- Document the safest correction in the final report, implementing code changes only if strictly necessary within the single-hotel RBAC policy.

### R4. Automated Regression and Security Testing
- Execute authentication, role permission, stocktaking, and departmental restriction tests against isolated Django test databases.
- Run regression suites for inventory integrity, procurement/RFQ, stocktaking, expiry alerts, batch allocation (FIFO/FEFO), POS/KDS, accounting integrity, and cross-module integration.
- Separately report discovered, executed, passed, failed, skipped, and errored test counts without double-counting.

### R5. Real-Browser Acceptance Verification
- Execute real-browser acceptance tests using Selenium across all 9 specified roles: Admin, Hotel Manager, Inventory, Kitchen, Bar, Waiter, Cashier, Reception, and Housekeeping.
- Verify dashboard rendering, module navigation, restricted module inaccessibility, workflow completion, and absence of fatal console or API errors.
- Capture screenshots for each role and retain browser logs.

### R6. Safety, Change Control, and Final Deliverable Report
- Inspect git status before making changes; preserve all existing user and team modifications without resetting, overwriting, committing, pushing, deploying, or modifying production databases.
- Produce `docs/FINAL_RBAC_CORRECTION_REPORT.md` covering all 11 required sections: initial state, defect root causes, files changed, database migrations (if any), final role-permission matrix, implementation evidence, reconciled automated test results, browser acceptance results with screenshots, security/regression findings, limitations, and final integrity verification.

## Acceptance Criteria

### Role & Frontend Authorization
- [ ] `hotel_manager` is formally defined in `User.ROLE_CHOICES`, model validation, admin, and serializers, with existing database accounts preserved.
- [ ] Hotel Manager logs in to the frontend operational dashboard without Unauthorized errors, blank screens, or superuser technical controls.
- [ ] Inconsistent `["admin", "manager"]` checks are replaced with authoritative checks recognizing `hotel_manager` across dining and order operations.
- [ ] Inventory users access Inventory Dashboard, Stocktake Center, Procurement Center, alerts, transfers, and RFQs/POs via frontend routes and navigation without being granted `admin`.

### Stock Permissions & Safeguards
- [ ] `admin`, superuser, `hotel_manager`, and `inventory` roles have access to all stock locations.
- [ ] Departmental staff (`kitchen`, `bar`, `waiter`, `cashier`) cannot access general warehouse stock management or unassigned locations (`custodian IS NULL`).
- [ ] Stocktake separation of duties blocks count self-approval while allowing authorized separate approvers.
- [ ] Approved stocktaking sessions, batches, and audit histories cannot be deleted or bypassed.

### Testing & Verification
- [ ] Automated regression suites pass with reconciled counts for discovered, executed, passed, failed, skipped, and errored tests.
- [ ] Selenium browser tests authenticate and verify expected navigation and access restrictions for all 9 roles, with screenshots saved.
- [ ] Supplier identity architecture is reviewed and documented with any applied fix verified safe.
- [ ] `docs/FINAL_RBAC_CORRECTION_REPORT.md` is generated with all 11 required sections.
- [ ] Existing codebase modifications and business records are preserved with zero unauthorized deletions or git commits.


## Follow-up — 2026-11-09T06:54:47Z

The user has confirmed the full detailed requirements for ACRMA HOTEL ERP — FINAL RBAC CORRECTION & ACCEPTANCE:

Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
Mode: Development / Staging only
Architecture: Single-Tenant — One Hotel
Reference: docs/ROLE_AND_PERMISSION_AUDIT_REPORT.md (AUDIT-RBAC-ARCHITECTURE-2026-V1.0)

Key Specifications Confirmed:
- R1. AUTHORITATIVE ROLE STRUCTURE: Formalize hotel_manager across User model, ROLE_CHOICES, serializers, validation, Django Admin, permissions, and frontend routes/navigation. Authoritative roles: admin, superuser, hotel_manager, inventory, finance, kitchen, bar, waiter, cashier, reception, housekeeping, customer. Do not create a separate Store Manager role; inventory is the primary operational stock-management role for this single hotel.
- R2. HOTEL MANAGER PERMISSIONS: Full operational management access across inventory, procurement, and operations. Fix frontend Unauthorized/blank-screen. Distinguish operational supervisor authority from financial approval authority and technical/security admin.
- R3. INVENTORY FRONTEND AND BACKEND: Global hotel-wide access for inventory users to Inventory Dashboard, all stock locations & batches, stock transfers, expiry/batch alerts, Stocktake Center, schedules, Procurement Center, requisitions, RFQs, POs, GRNs, and supplier invoice matching. Do not grant admin role to solve frontend restrictions.
- R4. FINAL STOCK LOCATION ACCESS POLICY: admin/superuser (global), hotel_manager (global operational), inventory (global stock & stocktake access across every location including unassigned). Departmental staff restricted to authorized operational access. Remove custodian IS NULL default-allow fallback. Preserve stocktake draft/count/recount/approval/cancellation, blind mode, SoD, immutable approved records, FIFO/FEFO, expired/quarantined protections.
- R5. PROCUREMENT AND APPROVAL SAFEGUARDS: Preserve approval tiers: Tier 1 (inventory <=$10k), Tier 2 (finance <=$50k), Tier 3 (admin >$50k).
- R6. SUPPLIER IDENTITY REVIEW: Inspect supplier authentication architecture, document why suppliers use customer role and verify quotation separation.
- R7. AUTOMATED TESTING: Isolated Django test databases. Report discovered, executed, passed, failed, errors, skipped with reconciled counts and commands.
- R8. REAL-BROWSER ACCEPTANCE: Selenium testing across all 9 roles (Admin, Hotel Manager, Inventory, Kitchen, Bar, Waiter, Cashier, Reception, Housekeeping) with workflow completion (stocktake + procurement for inventory, supervisory for hotel manager), screenshots and browser logs.
- R9. REPOSITORY AND DATABASE SAFETY: Change control, no destructive operations, isolated test DBs, no git commits/pushes.
- R10. REQUIRED FINAL REPORT: docs/FINAL_RBAC_CORRECTION_REPORT.md covering all 11 required sections.
- R11. FINAL ACCEPTANCE CONDITIONS: Prepare evidence for separate independent read-only QC audit.

Please proceed with Milestone 1 implementation and report progress.


## Follow-up — 2026-11-11T07:26:03Z

The outstanding adversarial finding DEF-M1-IT3-01 has been corrected and verified:
1. `apps/inventory/views.py`: `PurchaseRequisitionViewSet.reject` now calls `req_obj = self.get_object()` before invoking service layer, enforcing DRF row-scoping (cross-department requests return HTTP 404).
2. `hotel/procurement.py`: `reject_purchase_requisition` now includes defense-in-depth role/department validation.
3. `apps/inventory/tests/test_procurement_rbac.py`: Added `test_unauthorized_cross_department_rejection_blocked` and assertions. All 19 tests in the suite passed (100%).
4. Empirical stress suite `scratch/test_empirical_challenger_m1_it3_2.py`: 25/25 passed (100%), including 1.6b.
5. Staging database verified: 37 users, 0 draft payroll, 84 journal entries.
An independent security review subagent is currently verifying the fix before we advance to Milestone 2.


## Follow-up — 2026-11-11T07:30:44Z

User authorization granted: Resume execution and proceed directly to Milestone 2 (Full Automated Regression), Milestone 3 (Real-Browser Acceptance across 9 roles), and Milestone 4 (Independent Release Audit).

Directives:
1. Milestone 2: Execute all backend regression suites and frontend test/build verification; reconcile test counts without double-counting.
2. Milestone 3: Real-browser acceptance across all 9 roles with screenshots.
3. Milestone 4: Independent release audit and release-readiness report with production checklist and rollback plan.
4. Strict boundaries: Zero git commits/pushes, no production database changes, no deployment.

Commence Milestone 2 execution now.


## Follow-up — 2026-11-11T08:46:35Z

Subagent instruction: Do NOT launch any further 'manage.py test' processes. Coordinator is running all test suites serially to prevent PostgreSQL deadlock collisions on test_hotel_erp_staging. Await Coordinator notification when Milestone 2 and Milestone 3 are completed.
