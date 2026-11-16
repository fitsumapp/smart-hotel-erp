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