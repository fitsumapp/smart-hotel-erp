# BRIEFING — 2026-11-09T07:37:00Z

## Mission
Investigate the regression impact of removing `hotel_manager` from `IsFinanceStaff`.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
- State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_3\
- Original parent: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Milestone: Milestone 1 Iteration 2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT modify source code or tests
- Write report to .agents/teamwork/explorer_m1_it2_3/handoff.md
- Notify orchestrator via send_message

## Current Parent
- Conversation ID: bf049e91-d4c5-4607-97c7-1c2a2247987f
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `users/permissions.py`: Full audit of all 16 permission classes
  - `apps/finance/views.py`: All 8 views relying on `IsFinanceStaff`
  - `apps/finance/tests/test_expense_manager.py` & `test_tax_report.py`: Finance test suites
  - `apps/orders/views.py`: Dining, bill request, handover supervisory views
  - `apps/inventory/views.py`: Inventory catalog, locations, stocktake, procurement
  - `apps/reporting/views.py`: OperationsTimingReportView
  - `hotel-frontend/src/Sidebar.js` & `App.js`: Navigation and route visibility
  - `apps/identity/serializers.py` & `users/serializers.py`: Circular import diagnosis
- **Key findings**:
  1. `IsFinanceStaff` is used exclusively by 8 views in `apps/finance/views.py` (General Ledger, Accounts, Journal Entries, Expenses, Budgets, Statements, Tax, Payroll).
  2. ZERO existing tests or operational features require `hotel_manager` to pass `IsFinanceStaff`. Operational endpoints use separate permissions (`IsHotelManagerOrAdmin`, `IsWaiterOrAdmin`, `IsInventoryManager`, `HasStocktakeLocationPermission`).
  3. Procurement and inventory operational permissions (`IsInventoryManager`, `IsProcurementOperator`, `IsProcurementOrFinanceOperator`) are completely separate from `IsFinanceStaff`.
  4. Removing `hotel_manager` from `IsFinanceStaff` eliminates the payroll & GL posting exploit while creating ZERO test or feature regressions.
  5. The circular import between `apps.identity.serializers` and `users.serializers` is caused by `apps/identity/serializers.py:2` importing `*` from `users.serializers`. Replacing it with direct DRF/User imports resolves the crash cleanly.
- **Unexplored areas**: None within the scope of this investigation.

## Key Decisions Made
- Confirmed zero regression impact of removing `hotel_manager` from `IsFinanceStaff`.
- Established complete matrix of permissions `hotel_manager` SHOULD and SHOULD NOT possess across `users/permissions.py`.
- Formulated clear code recommendations for Worker M1.

## Artifact Index
- DISPATCH.md — Task assignment
- BRIEFING.md — Persistent working memory
- progress.md — Heartbeat and status tracking
- handoff.md — 5-component handoff report for Worker M1 and Orchestrator
