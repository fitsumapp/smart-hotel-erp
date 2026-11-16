# Dispatch Assignment: Reviewer M1-2
Task: Adversarial Review of Milestone 1 implementation (DEF-01 to DEF-06) per PROJECT.md and worker_m1/handoff.md.
State folder: .agents/teamwork/reviewer_m1_2/


## 2026-11-09T07:14:23Z
You are Reviewer M1-2 (Adversarial Reviewer) for Milestone 1 of Acrma Hotel ERP RBAC Architecture Corrections.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\reviewer_m1_2\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md`.
Read PROJECT.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md`.
Read Worker M1 handoff at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1\handoff.md`.

Your Objective:
Adversarially scrutinize Milestone 1 changes for subtle security bypasses, permission leaks, or broken edge cases:
1. DEF-01: Does `User.ROLE_CHOICES` or serializer allow arbitrary invalid roles? Does `0009_alter_user_role.py` have any reverse migration hazards or data truncation?
2. DEF-02: Can a `hotel_manager` access `/api/users/` or `/users/settings/` if they manipulate the frontend URL or API client directly? Verify that `IsHotelAdmin` still blocks `hotel_manager` from user management and system settings.
3. DEF-03: Are supervisor permissions over-permissive? Does `hotel_manager` gain unintended financial or technical privileges? Verify cashier handover vs accounting ledger postings.
4. DEF-04: Can an `inventory` user navigate to finance, cashier, or front office routes? Verify route guards and layout separation.
5. DEF-05: Adversarially test the removal of `custodian IS NULL`: can a `kitchen` or `waiter` user still access any unassigned stock location or create stocktake sessions? Verify SoD: can a supervisor approve their own count?
6. Run tests: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows --keepdb`.

Deliverables:
- Write your structured report to `.agents/teamwork/reviewer_m1_2/handoff.md`.
- Conclude with an explicit verdict: APPROVE or REQUEST_CHANGES.
- Notify orchestrator via send_message.
