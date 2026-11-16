# Dispatch Assignment: Survey Backend Explorer
Task: Investigate backend codebase, database, permissions, and test suites for DEF-01, DEF-03, DEF-05, DEF-06.
State folder: .agents/teamwork/survey_backend/


## 2026-11-09T06:23:23Z
You are the Backend Architecture Explorer for Acrma Hotel ERP RBAC Architecture Corrections.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_backend\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md` before starting work.

Your Objective:
Investigate backend codebase, database configurations, and test suites regarding DEF-01, DEF-03, DEF-05, and DEF-06:
1. DEF-01: Inspect `User` model, `ROLE_CHOICES`, serializers, admin registrations in `apps/identity/`, `users/`, and any other apps. Check if `hotel_manager` is currently present or missing. Check the staging database (`hotel_erp_staging` / `.env`) to see what users and roles exist.
2. DEF-03: Find all supervisor authorization checks across `apps/orders/`, `apps/dining/`, `apps/tables/`, etc. (e.g., search for `["admin", "manager"]`, `role in ...`, `is_supervisor`, etc.). Identify all endpoints/services needing normalization to authoritative checks recognizing `hotel_manager`.
3. DEF-05: Inspect `apps/inventory/` for stock location permissions, queries filtering on `custodian` (including `custodian IS NULL`), stocktake session creation/counting/approving logic, separation of duties checks, and audit history protections.
4. DEF-06: Inspect external supplier authentication, portal, and quotation endpoints. How is `customer` vs `supplier` handled?
5. Automated Test Suites: Identify all existing test suites (`apps/inventory/tests/`, `apps/orders/tests/`, `apps/identity/tests/`, `users/test_milestone2_workflows.py`, `users/test_phase3_integrity.py`, etc.). Determine how Django test runners run with PostgreSQL test database or SQLite, and note existing test counts/passing status.
6. Git status check: Inspect `git status` to verify current modified/untracked files so we ensure zero unauthorized deletions or unwanted resets.

Constraints:
- READ-ONLY investigation. Do NOT modify source code or tests.
- Maintain your liveness heartbeat in `.agents/teamwork/survey_backend/progress.md`.
- Write your structured report to `.agents/teamwork/survey_backend/handoff.md`.
- When complete, notify the orchestrator with send_message.


## 2026-11-09T06:50:48Z
**Context**: Survey Backend Explorer Status Check
**Content**: Please check your running test task (task-210). Note that Django `manage.py test` can prompt interactively: "Type 'yes' if you would like to try deleting the test database 'test_hotel_erp_staging'" unless `--keepdb` or `--noinput` is provided. If task-210 is stuck on an interactive prompt, cancel/kill it and rerun with `--keepdb --noinput` (or wrap up your findings and submit handoff.md with what you have so far).
**Action**: Check task-210 status, update progress.md, and provide status.
