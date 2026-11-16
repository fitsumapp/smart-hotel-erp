# BRIEFING — 2026-11-09T07:42:00Z

## Mission
Investigate permission leak in `users/permissions.py:86` (`IsFinanceStaff`) where `hotel_manager` was added, analyze impact on finance views/payroll/GL, determine proper separation for hotel_manager operational reports vs financial accounting mutation privileges, analyze circular import hazard, and provide precise fix recommendation.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
- State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_1
- Original parent: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Milestone: Milestone 1, Iteration 2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT modify source code or tests
- Write report to `.agents/teamwork/explorer_m1_it2_1/handoff.md`
- Notify orchestrator via send_message

## Current Parent
- Conversation ID: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Updated: 2026-11-09T07:40:31Z

## Investigation State
- **Explored paths**:
  - `users/permissions.py` (lines 82-87: `IsFinanceStaff`)
  - `apps/finance/views.py` (8 views/viewsets relying on `IsFinanceStaff`)
  - `apps/finance/urls.py` & `users/urls.py` (finance API route mapping)
  - `apps/reporting/views.py` & `apps/reporting/urls.py` (operational vs financial reports)
  - `apps/orders/views.py` (`DashboardStatsView` & `AdminOrdersView`)
  - `apps/inventory/views.py` (`InventoryDashboardStatsView` & `InventoryItemViewSet`)
  - `hotel-frontend/src/Sidebar.js` & `hotel-frontend/src/App.js` & `hotel-frontend/src/pages/ReportsCenter.js`
  - `apps/identity/serializers.py` & `users/serializers.py` (circular import)
  - Full test suite execution across 70 tests in `apps.orders`, `apps.finance`, `apps.reporting`, `users`
- **Key findings**:
  1. `users/permissions.py:86` (`IsFinanceStaff`): Worker M1 incorrectly added `"hotel_manager"` to `IsFinanceStaff`.
  2. In `apps/finance/views.py`, 8 views rely on `IsFinanceStaff`. While views like `AccountViewSet` and `JournalEntryViewSet` have inline checks on `create()`, `PayrollEntryViewSet.create()` relies solely on `IsFinanceStaff`. When `status='paid'`, it posts directly to GL (`_post_payroll_gl` -> `post_journal_entry`). Furthermore, `AccountViewSet`, `ExpenseTransactionViewSet`, and `BudgetViewSet` do not override `update`/`partial_update`/`destroy`, leaving them vulnerable to modification if `IsFinanceStaff` passes.
  3. Operational reports (`OperationsTimingReportView`, `DashboardStatsView`, `InventoryItemViewSet`, `AdminOrdersView`) live in `apps/reporting/`, `apps/orders/`, and `apps/inventory/`, and use dedicated permissions (`IsHotelManagerOrAdmin`, `IsInventoryManager`, or explicit role lists). They DO NOT rely on `IsFinanceStaff`.
  4. Removing `hotel_manager` from `IsFinanceStaff` does not break operational report access and completely plugs the financial mutation leak.
  5. The circular import in `apps/identity/serializers.py:2` (`from users.serializers import *`) is triggered because `users/serializers.py:87` imports from `apps.identity.serializers`. In `apps/identity/serializers.py`, line 2 is completely unnecessary: importing `serializers` from `rest_framework` and `User = get_user_model()` eliminates the circular dependency.
- **Unexplored areas**: None.

## Key Decisions Made
- Confirmed root causes and concrete remediation steps for both `IsFinanceStaff` permission leak and circular import hazard.
- Formulated clear 5-component handoff report.

## Artifact Index
- DISPATCH.md — Task assignment
- BRIEFING.md — Persistent memory index
- progress.md — Liveness heartbeat
- handoff.md — Final investigation report
