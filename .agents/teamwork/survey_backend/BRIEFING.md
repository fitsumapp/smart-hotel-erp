# BRIEFING — 2026-11-09T06:53:00Z

## Mission
Backend Architecture Survey & Investigation for Acrma Hotel ERP RBAC Architecture Corrections (DEF-01, DEF-03, DEF-05, DEF-06, Test Suites, Git status).

## 🔒 My Identity
- Archetype: explorer
- Roles: survey_backend
- Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
- State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_backend\
- Original parent: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Milestone: Survey & Initial Architecture Investigation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement code changes
- Preserve existing user and team modifications without resetting, overwriting, committing, pushing, deploying, or modifying production databases
- Maintain liveness heartbeat in progress.md
- Output structured handoff report in handoff.md

## Current Parent
- Conversation ID: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Updated: 2026-11-09T06:50:48Z

## Investigation State
- **Explored paths**:
  - `users/models.py`, `users/admin.py`, `apps/identity/serializers.py`, `users/permissions.py`
  - Active Staging Database `hotel_erp_staging` (PostgreSQL 16)
  - `apps/orders/views.py`, `apps/orders/urls.py`, `apps/reporting/views.py`
  - `apps/inventory/views.py`, `hotel/stocktaking.py`, `hotel/procurement.py`, `hotel/models.py`
  - `core/settings.py`, `core/settings_test.py`, `core/test_runner.py`
  - Test suites in `apps/inventory/tests/`, `apps/orders/tests/`, `apps/identity/tests/`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`
- **Key findings**:
  - DEF-01: `User.ROLE_CHOICES` lacks `hotel_manager`. Staging database holds 37 accounts including 2 `hotel_manager` (`manager_proc2` id=12, `sec_ops_manager` id=16). Both accounts must be preserved. `CustomUserAdmin.display_role` also lacks `hotel_manager` and `housekeeping`.
  - DEF-03: Inconsistent `"manager"` checks at `apps/orders/views.py:418, 503, 581, 665, 802` and `apps/reporting/views.py:735`. Additionally, `DashboardStatsView` uses `IsHotelAdmin` and `AdminOrdersView` uses `["admin", "finance"]`, inadvertently blocking `hotel_manager` from operational views.
  - DEF-05: Single-hotel global stock permissions require removing unassigned store fallbacks (`custodian IS NULL`) in `apps/inventory/views.py` (L1282, L1502) and `users/permissions.py` (L243), while ensuring departmental users have no general warehouse access. Stocktake SoD in `hotel/stocktaking.py:414` and audit deletion blocks in `apps/inventory/views.py:1449-1480` verified robust.
  - DEF-06: Suppliers (`Supplier`) have no user foreign key. Vendor users (`sec_supplier_alpha`, `sec_supplier_beta`) hold `role="customer"`. RFQ/Quotation views rely on standard DRF authentication and store `created_by=user`.
  - Test Runner: SQLite (`core.settings_test`) is fast but fails on multi-threaded concurrent locking tests. PostgreSQL test database (`test_hotel_erp_staging` via `manage.py test --keepdb`) successfully executes concurrent transaction tests (26/26 in `test_inventory_integrity`).
  - Git status: 43 modified files, 53 untracked files safely cataloged with zero modifications.
- **Unexplored areas**: None within the assigned survey scope.

## Key Decisions Made
- Confirmed that PostgreSQL test runner (`--keepdb`) should be used for concurrency/integrity test execution, while SQLite runner (`--settings=core.settings_test`) provides rapid feedback for unit tests.
- Reconciled exact test counts across all backend suites.

## Artifact Index
- `.agents/teamwork/ORIGINAL_REQUEST.md` — Original approved user request
- `docs/ROLE_AND_PERMISSION_AUDIT_REPORT.md` — Comprehensive RBAC architecture audit report
- `.agents/teamwork/survey_backend/progress.md` — Liveness heartbeat and progress tracker
- `.agents/teamwork/survey_backend/handoff.md` — Structured 5-component handoff report
