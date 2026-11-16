# Dispatch Assignment: Worker M1 Iteration 2
Task: Remediate IsFinanceStaff permission leak in users/permissions.py and decouple circular import in apps/identity/serializers.py.
State folder: .agents/teamwork/worker_m1_it2/


## 2026-11-09T07:42:14Z
You are Worker M1-2 for Milestone 1 Iteration 2 of Acrma Hotel ERP RBAC Architecture Corrections.
Working directory: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment
State folder: d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\worker_m1_it2\

MANDATORY FIRST STEP:
Read ORIGINAL_REQUEST.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\ORIGINAL_REQUEST.md`.
Read PROJECT.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\PROJECT.md`.
Read failure details in GATE_STATUS.md at `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\orchestrator\GATE_STATUS.md`.
Read Explorer findings in:
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_1\handoff.md`
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_2\handoff.md`
- `d:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.agents\teamwork\explorer_m1_it2_3\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Ownership (You own these files exclusively):
- `users/permissions.py`
- `apps/identity/serializers.py`

Detailed Tasks:
1. Fix Permission Leak in `users/permissions.py`:
   - In `class IsFinanceStaff(BasePermission)` (line 82-86), remove `"hotel_manager"` from the role set so it only permits `{"admin", "finance"}` and superusers:
     ```python
     class IsFinanceStaff(BasePermission):
         message = "Finance or hotel administrator access is required."
         def has_permission(self, request, view):
             user = request.user
             return bool(
                 user and user.is_authenticated and user.is_active and
                 (user.is_superuser or getattr(user, "role", "") in {"admin", "finance"})
             )
     ```
   - This ensures `hotel_manager` cannot create payroll entries (`POST /users/finance/payroll/`) or trigger General Ledger journal postings.
2. Fix Circular Import Hazard in `apps/identity/serializers.py`:
   - Replace line 2 (`from users.serializers import *`) with explicit, self-contained imports:
     ```python
     from rest_framework import serializers
     from django.contrib.auth import get_user_model
     User = get_user_model()
     ```
   - Verify that importing `UserSerializer` directly from `apps.identity.serializers` succeeds without `ImportError`.
3. Verification Tests:
   - Verify `POST /users/finance/payroll/` with user 12 (`manager_proc2`) returns HTTP 403 Forbidden.
   - Run: `.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from apps.identity.serializers import UserSerializer; print('Import OK:', UserSerializer)"`
   - Run Django test suite: `.venv\Scripts\python.exe manage.py test apps.orders.tests.test_bill_request_handover users.test_milestone2_workflows apps.finance.tests --keepdb`
   - Run React unit tests: `npm test -- --watchAll=false src/apiClient.test.js` in `hotel-frontend/`.

Deliverables:
- Write your comprehensive handoff report to `.agents/teamwork/worker_m1_it2/handoff.md`.
- Maintain heartbeat in `.agents/teamwork/worker_m1_it2/progress.md`.
- When complete, notify orchestrator via send_message.
