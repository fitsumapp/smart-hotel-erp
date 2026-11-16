# Dispatch Assignment: Survey Spec Miner
Task: Probe and document authoritative audit specifications from docs/ROLE_AND_PERMISSION_AUDIT_REPORT.md (AUDIT-RBAC-ARCHITECTURE-2026-V1.0) and ORIGINAL_REQUEST.md.
State folder: .agents/teamwork/survey_spec_miner/


## 2026-11-09T06:23:09Z
You are the Audit Specification Miner for Acrma Hotel ERP RBAC Architecture Corrections.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\survey_spec_miner\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md` before starting work.

Authoritative source of truth to investigate:
`docs/ROLE_AND_PERMISSION_AUDIT_REPORT.md` (AUDIT-RBAC-ARCHITECTURE-2026-V1.0) and related project docs.

Your Objective:
Mine and document all requirements, defects, acceptance criteria, and technical specifications for:
1. DEF-01: Formalization of `hotel_manager` in User.ROLE_CHOICES, model validation, serializers, admin forms, and backend logic. Preservation of existing accounts.
2. DEF-02: Frontend routing, navigation, and route guards (`App.js`, `Sidebar.js`, `DashboardLayout`) for `hotel_manager`. Operational dashboard rendering without Unauthorized/blank screens or superuser controls.
3. DEF-03: Supervisor checks across orders, cancellations, and dining workflows. Replacement of `["admin", "manager"]` with authoritative checks recognizing `hotel_manager`.
4. DEF-04: Full frontend access for `inventory` users (Inventory Dashboard, Stocktake, Procurement, alerts, transfers, PRs, RFQs, POs, GRNs, invoice matching) without granting `admin`.
5. DEF-05: Single-hotel global stock permissions (`admin`, superuser, `hotel_manager`, `inventory` global access vs departmental users `kitchen`, `bar`, `waiter`, `cashier`), removal of `custodian IS NULL` fallback, stocktaking SoD, audit history, and FIFO/FEFO protections.
6. DEF-06: External supplier identity architecture review (use of `customer` role, portal vs supplier records).
7. Report requirements for `docs/FINAL_RBAC_CORRECTION_REPORT.md` (all 11 required sections).

Constraints:
- READ-ONLY investigation. Do NOT modify source code or tests.
- Maintain your liveness heartbeat in `.agents/teamwork/survey_spec_miner/progress.md`.
- Write your final structured specification report to `.agents/teamwork/survey_spec_miner/handoff.md`.
- When complete, notify the orchestrator with send_message.


## 2026-11-09T06:44:22Z
**Context**: Survey Phase Status Check
**Content**: Status query: Please update your progress.md and let us know your current status on probing DEF-01 through DEF-06 and generating your handoff report.
**Action**: Update progress.md with current timestamp and provide status update.
