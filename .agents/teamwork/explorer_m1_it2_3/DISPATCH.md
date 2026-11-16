# Dispatch Assignment: Explorer M1 Iteration 2 - 3
Task: Investigate impact of IsFinanceStaff remediation on other modules and tests.
State folder: .agents/teamwork/explorer_m1_it2_3/


## 2026-11-09T07:26:53Z
You are Explorer 3 for Iteration 2 of Milestone 1.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_3\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md`.
Read PROJECT.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md`.
Read failure details in `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\reviewer_m1_2\handoff.md`.

Your Objective:
Investigate the regression impact of removing `hotel_manager` from `IsFinanceStaff`:
1. Check what endpoints, views, and test suites rely on `IsFinanceStaff`.
2. Verify if any existing test or feature expects `hotel_manager` to pass `IsFinanceStaff`.
3. Check `IsProcurementOrFinanceOperator` and `IsInventoryManager` in `users/permissions.py`: confirm that procurement and inventory operational permissions are separate from general finance staff permissions.
4. Verify the exact set of permissions `hotel_manager` SHOULD and SHOULD NOT possess across `users/permissions.py`.
5. Provide a clear recommendation report for the worker.

Constraints:
- READ-ONLY investigation. Do NOT modify source code or tests.
- Write your report to `.agents/teamwork/explorer_m1_it2_3/handoff.md`.
- Notify orchestrator via send_message.
