# Independent Security, Governance & Consistency QC Handoff Report (Areas 6 & 7)

**Document Reference:** QC-SECURITY-PARTIAL-INVENTORY-2026-V1.0  
**Date:** 2026-11-05  
**Author:** Stocktaking & Security Explorer (`explorer_qc_security`)  
**Target Environment:** Django 5.2 backend (`.venv\Scripts\python.exe`), PostgreSQL 16.12 (`hotel_erp_staging` on `localhost:5432`), React 19 SPA (`http://localhost:3000`)  
**Overall Verdict for Evaluated Scope (Areas 6 & 7):** **REJECTED** (Due to 1 Critical Defect breaking all stocktaking count submission, recount, approval, and cancellation REST endpoints with HTTP 404, and 2 High Severity Deficiencies in stocktake session deletion safety and alert dismissal reactivation)

---

## 1. Observation

### 1.1 Automated Test Execution Results Against `hotel_erp_staging`

In accordance with strict verification instructions to execute tests against the active environment without relying on previous reports, both authoritative test suites were run using `.venv\Scripts\python.exe manage.py test --keepdb`:

#### 1. `apps/inventory/tests/test_stocktaking_management.py`
- **Execution Command:** `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb`
- **Observed Result:** 12 tests executed in 81.407s — **FAILED (errors=5, passed=7)**.
- **Direct Error Log:**
  ```text
  ======================================================================
  ERROR: test_05_mode_locking_on_first_count_submission (apps.inventory.tests.test_stocktaking_management.StocktakingManagementTestCase.test_05_mode_locking_on_first_count_submission)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\apps\inventory\tests\test_stocktaking_management.py", line 263, in test_05_mode_locking_on_first_count_submission
      record_url = reverse("stocktakesession-record-counts", args=[session.id])
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\base.py", line 98, in reverse
      resolved_url = resolver._reverse_with_prefix(view, prefix, *args, **kwargs)
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\resolvers.py", line 831, in _reverse_with_prefix
      raise NoReverseMatch(msg)
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-record-counts' not found. 'stocktakesession-record-counts' is not a valid view function or pattern name.

  ======================================================================
  ERROR: test_06_recount_workflow_flagging_and_resubmission (apps.inventory.tests.test_stocktaking_management.StocktakingManagementTestCase.test_06_recount_workflow_flagging_and_resubmission)
  ----------------------------------------------------------------------
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-request-recount' not found. (line 303)

  ======================================================================
  ERROR: test_07_separation_of_duties_prevents_self_approval (apps.inventory.tests.test_stocktaking_management.StocktakingManagementTestCase.test_07_separation_of_duties_prevents_self_approval)
  ----------------------------------------------------------------------
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found. (line 365)

  ======================================================================
  ERROR: test_11_session_cancellation_leaves_balances_intact (apps.inventory.tests.test_stocktaking_management.StocktakingManagementTestCase.test_11_session_cancellation_leaves_balances_intact)
  ----------------------------------------------------------------------
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-cancel' not found. (line 541)

  ======================================================================
  ERROR: test_12_non_manager_cannot_create_or_approve_sessions (apps.inventory.tests.test_stocktaking_management.StocktakingManagementTestCase.test_12_non_manager_cannot_create_or_approve_sessions)
  ----------------------------------------------------------------------
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found. (line 574)
  ```
- **Discrepancy with Implementation Report:** Prior document `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md` (lines 101-107) claimed:
  *"Ran 12 tests in 31.541s; OK. All existing physical stocktaking functions... remain 100% regression-free."*  
  Independent execution confirms this claim is **FALSE**.

#### 2. `apps/inventory/tests/test_expiry_alerts_and_schedules.py`
- **Execution Command:** `.venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb`
- **Observed Result:** 13 tests executed in 77.593s — **FAILED (errors=1, passed=12)**.
- **Direct Error Log:**
  ```text
  ======================================================================
  ERROR: test_13_segregation_of_duties_preserved_for_scheduled_session (apps.inventory.tests.test_expiry_alerts_and_schedules.ExpiryAlertsAndStocktakeSchedulesTestCase.test_13_segregation_of_duties_preserved_for_scheduled_session)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\apps\inventory\tests\test_expiry_alerts_and_schedules.py", line 480, in test_13_segregation_of_duties_preserved_for_scheduled_session
      approve_url = reverse("stocktakesession-approve", args=[session.id])
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\base.py", line 98, in reverse
      resolved_url = resolver._reverse_with_prefix(view, prefix, *args, **kwargs)
    File "D:\workspace\ongoing projects\Acrma hotel mangment\Acrma hotel mangment\.venv\Lib\site-packages\django\urls\resolvers.py", line 831, in _reverse_with_prefix
      raise NoReverseMatch(msg)
  django.urls.exceptions.NoReverseMatch: Reverse for 'stocktakesession-approve' not found. 'stocktakesession-approve' is not a valid view function or pattern name.
  ```
- **Discrepancy with Implementation Report:** `docs/PARTIAL_INVENTORY_FEATURES_COMPLETION_REPORT.md` (lines 75-98) claimed:
  *"Ran 13 tests in 71.705s; OK"* with `test_13` marked PASS. Independent verification confirms this claim is **FALSE**.

---

### 1.2 Summary Table of Evaluated Capability Areas (Areas 6 & 7)

| Item | Focus Sub-Area | Evaluated Location | Independent Status | Defect Severity |
| :--- | :--- | :--- | :---: | :---: |
| **6.1** | Stocktaking Draft Safety | `apps/inventory/views.py:3163-3195`<br>`hotel/models.py:2311-2385`<br>`hotel/stocktaking.py:46-250` | **FAIL** | **Critical** (API disconnect)<br>**High** (Unrestricted Deletion) |
| **6.2** | Blind-Mode Zero-Leak Protection | `apps/inventory/serializers.py:920-938, 1011-1028`<br>`hotel-frontend/src/pages/stocktaking/StocktakeCountDesk.jsx:306-360` | **PASS** | None |
| **6.3** | Separation of Duties (SoD) | `hotel/stocktaking.py:413-436`<br>`apps/inventory/views.py:3163`<br>`test_stocktaking_management.py:340-378` | **FAIL** (API Layer)<br>**PASS** (Service Layer) | **Critical** (API disconnect) |
| **6.4** | Approval-Based GL Posting | `hotel/stocktaking.py:488-522`<br>`hotel/accounting.py:20-70`<br>`apps/finance/services.py:48-67` | **FAIL** (API Layer)<br>**PASS** (Service Layer) | **Critical** (API disconnect) |
| **7.1** | API Permissions & Authentication | `users/permissions.py:74-128`<br>`apps/inventory/views.py` (all viewsets) | **PASS** | None |
| **7.2** | IDOR & Queryset Scoping | `apps/inventory/views.py:5756, 5809`<br>`hotel/stocktaking.py:149-249` | **PASS WITH OBSERVATION** | **Medium** |
| **7.3** | Frontend/Backend Consistency | `hotel-frontend/src/pages/stocktaking/` vs `apps/inventory/views.py`<br>`hotel/inventory.py:125-137` | **FAIL** | **Critical** (Action 404)<br>**High** (Alert Reactivation Loop) |

---

### 1.3 Detailed Concrete Observations by Area

#### Area 6: Stocktaking Draft Safety, Blind-Mode Protection, Separation of Duties, and Approval-Based GL Posting

##### 1. Stocktaking Draft Safety
- **Missing Action Endpoints (Source: `apps/inventory/views.py:3163-3195`):**
  In the active repository state, `StocktakeSessionViewSet` is declared at line 3163 as:
  ```python
  class StocktakeSessionViewSet(viewsets.ModelViewSet):
      queryset = StocktakeSession.objects.all().select_related(
          "location", "category", "created_by", "counted_by", "reviewed_by", "journal_entry"
      ).prefetch_related("items__item")
      serializer_class = StocktakeSessionSerializer
      permission_classes = [IsInventoryManager]

      def create(self, request, *args, **kwargs):
          ...
  ```
  Immediately following `create()`, line 3196 starts `class InventoryExpiryAlertViewSet`.
  Direct dynamic inspection of the viewset class via Django shell reveals:
  ```python
  from apps.inventory.views import StocktakeSessionViewSet
  print(StocktakeSessionViewSet.get_extra_actions())
  # Output: []
  ```
  The `@action` endpoints:
  - `record_counts` (`url_path="record-counts"`)
  - `request_recount` (`url_path="request-recount"`)
  - `submit_recount` (`url_path="submit-recount"`)
  - `approve` (`url_path="approve"`)
  - `cancel` (`url_path="cancel"`)
  were severed from `StocktakeSessionViewSet` and accidentally pasted into intermediate declarations of `StocktakeScheduleViewSet` (lines 3365, 3557, 3748, 3945, 4139), and finally overwritten when `StocktakeScheduleViewSet` was re-declared at line 5801.
  **Impact:** No physical count can be submitted, no recount can be initiated or submitted, no approval can occur, and no session can be cancelled through the REST API (`/api/v1/stocktaking/sessions/<id>/...`). Every call returns **HTTP 404 Not Found**.

- **Premature Deletion Safety (Source: `apps/inventory/views.py:3163`, `hotel/models.py:2387-2390`):**
  `StocktakeSessionViewSet` inherits from `viewsets.ModelViewSet` and does **not** override `destroy()`.
  In `hotel/models.py`:
  ```python
  class StocktakeItem(models.Model):
      session = models.ForeignKey(StocktakeSession, on_delete=models.CASCADE, related_name="items")
  ```
  Any authenticated inventory manager can execute `DELETE /api/v1/stocktaking/sessions/<id>/` on any session at any lifecycle state (`draft`, `in_progress`, `under_review`, `recount_required`, or `approved`), resulting in an unlogged cascading deletion of the session and all historical `StocktakeItem` snapshot records. (In contrast, `StockTransferViewSet.destroy()` explicitly raises HTTP 405 Method Not Allowed).

- **Mode Locking (Owner Decision D-4) (Source: `apps/inventory/serializers.py:1030-1037`):**
  When physical counts are entered via `record_counts()` in `hotel/stocktaking.py:172`, `session.is_mode_locked = True` is committed to the database.
  `StocktakeSessionSerializer.validate()` strictly enforces:
  ```python
  if self.instance and self.instance.is_mode_locked:
      new_mode = attrs.get("counting_mode") or self.initial_data.get("counting_mode")
      if new_mode and new_mode != self.instance.counting_mode:
          raise serializers.ValidationError(
              {"counting_mode": "Counting mode is locked and cannot be changed once counting has begun."}
          )
  ```
  Verified by `test_stocktaking_management.py:test_05` (service layer sets `is_mode_locked=True`, and `PATCH` with new mode returns HTTP 400 Bad Request).

- **Service Layer Status Transitions (Source: `hotel/stocktaking.py:164-167, 264-267, 301-304, 410-412, 557-559`):**
  Status transitions are strictly validated in Python:
  - `record_counts()` rejects sessions unless in `("draft", "in_progress", "recount_required")` and transitions to `"under_review"`.
  - `request_recount()` requires status == `"under_review"` and transitions to `"recount_required"`.
  - `submit_recount()` requires status == `"recount_required"` and transitions to `"under_review"`.
  - `approve_stocktake_session()` rejects sessions in `"draft"` status (`if session.status not in ("under_review", "in_progress", "recount_required"): raise ValidationError`). Requires counts on all items (`it.final_quantity is not None`) and zero pending recounts (`it.requires_recount == False`).
  - `cancel_stocktake_session()` strictly rejects `"approved"` sessions (`raise ValidationError("Cannot cancel an already approved stocktake session.")`).

##### 2. Blind-Mode Protection (Zero-Leak Security)
- **API/Serializer-Level Masking (Source: `apps/inventory/serializers.py:920-938, 1011-1028`):**
  In `StocktakeItemSerializer.to_representation()`:
  ```python
  is_admin = bool(
      user and (
          user.is_superuser
          or getattr(user, "role", "") in ("admin", "hotel_manager")
      )
  )
  if (
      instance.session.counting_mode == "blind"
      and instance.session.status in ("draft", "in_progress")
      and not is_admin
  ):
      data["theoretical_quantity"] = None
      data["variance_quantity"] = None
      data["variance_value"] = None
  return data
  ```
  In `StocktakeSessionSerializer.to_representation()`:
  ```python
  if (
      instance.counting_mode == "blind"
      and instance.status in ("draft", "in_progress")
      and not is_admin
  ):
      data["total_theoretical_value"] = None
      data["total_variance_value"] = None
  return data
  ```
  **Network Security Assessment:** Expected quantities are masked at the DRF serializer layer before serialization. A counter inspecting raw JSON network responses in browser DevTools receives `null` for `theoretical_quantity`, `variance_quantity`, `variance_value`, `total_theoretical_value`, and `total_variance_value`.
  Theoretical stock is only revealed in `visible` mode or to supervisors/administrators.
- **Frontend DOM Protection (Source: `StocktakeCountDesk.jsx:306-360`):**
  The React table conditionally hides the expected stock column and renders a disabled lock badge: `<Lock size={12} /> Hidden`. No theoretical values exist in DOM attributes.

##### 3. Separation of Duties (SoD)
- **Counter != Approver Backend Enforcement (Source: `hotel/stocktaking.py:413-436`):**
  ```python
  if session.counted_by and supervisor.username == session.counted_by.username:
      if not (supervisor.is_superuser and emergency_self_approval):
          raise PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")
      justification_clean = (justification or notes or "").strip()
      if len(justification_clean) < 15:
          raise ValidationError("A detailed justification (minimum 15 characters) is required for superuser emergency self-approval.")
      from hotel.models import AuditEvent
      AuditEvent.objects.create(
          actor=supervisor,
          actor_role="superuser",
          action="stocktake.emergency_self_approval",
          entity_type="StocktakeSession",
          entity_id=str(session.id),
          before_summary={"status": session.status, "counted_by": session.counted_by.username},
          after_summary={"status": "approved", "reviewed_by": supervisor.username, "emergency_self_approval": True},
          reason=justification_clean,
          client_metadata={
              "counted_by": session.counted_by.username,
              "approved_by": supervisor.username,
              "emergency_self_approval": True,
          },
      )
  ```
- **Creator vs Approver Evaluation:**
  `session.created_by` is **not** compared against `supervisor`. An inventory manager who created or scheduled the stocktake session CAN approve the final variance, provided they did not perform the physical count (`session.counted_by != supervisor`). This aligns with the system's operational hierarchy where managers schedule audits for staff counters and retain review authority.
- **Defect in Test & API Execution:**
  While the service layer logic correctly raises `PermissionDenied` (tested in unit test `test_stocktaking_management.py:test_07`), the API endpoint `POST /api/v1/stocktaking/sessions/<id>/approve/` cannot be reached due to defect DEF-SEC-01.

##### 4. Approval-Based General Ledger (GL) Posting
- **Approval-Only Execution (Source: `hotel/stocktaking.py:488-522`):**
  Stock adjustments and GL journal entries occur **exclusively** during `approve_stocktake_session()`. Automated scheduling (`process_due_stocktake_schedules`), draft creation (`create_stocktake_session`), and count submission (`record_counts`) never post accounting entries or mutate inventory balances.
- **Balanced Double-Entry Posting (Source: `hotel/stocktaking.py:488-522`, `hotel/accounting.py:20-70`):**
  - **Deficit / Shrinkage:**
    - Debit Account `5020` (Inventory Stocktake Variance Expense): `total_deficit_value`
    - Credit Account `1300` (Inventory Asset): `total_deficit_value`
  - **Surplus:**
    - Debit Account `1300` (Inventory Asset): `total_surplus_value`
    - Credit Account `5020` (Inventory Stocktake Variance Expense): `total_surplus_value`
  - `hotel/accounting.py:47-48` enforces: `if total_debit != total_credit: raise ValidationError(f"Journal is not balanced...")`.
- **Idempotency Safeguards:**
  - Idempotent replay safety: `if session.status == "approved": return session`.
  - Authoritative inventory mutation via `record_stock_change()` incorporates unique idempotency keys:
    - Surplus: `STK-ADJ-INC-{session.session_number}-{it.item.pk}`
    - Deficit: `STK-ADJ-DEC-{session.session_number}-{it.item.pk}`
  - Prevents double-posting on network retry or duplicate approval submissions.

---

#### Area 7: API Permissions, IDOR Protection, and Frontend/Backend Consistency

##### 1. API Permissions & Authentication
- **DRF Permission Classes Inspection:**
  All inventory endpoints in `apps/inventory/views.py` enforce strict permission classes:
  - `StocktakeSessionViewSet`: `permission_classes = [IsInventoryManager]`
  - `StocktakeScheduleViewSet`: `permission_classes = [IsInventoryManager]`
  - `InventoryExpiryAlertViewSet`: `permission_classes = [IsBatchOperator]`
  - `InventoryItemViewSet`, `StockLocationViewSet`, `StockTransactionViewSet`, `BatchLocationBalanceViewSet`, `ItemLocationBalanceViewSet`, `InventoryWasteRecordViewSet`: `[IsInventoryManager]`
  - `StockTransferViewSet`, `PurchaseRequisitionViewSet`, `PurchaseOrderViewSet`, `GoodsReceiptNoteViewSet`, `SupplierInvoiceViewSet`, `RequestForQuotationViewSet`, `SupplierQuotationViewSet`: `[IsAuthenticated]`
- **Unauthenticated / Unauthorized Access Control:**
  - `IsAuthenticated`, `IsInventoryManager`, and `IsBatchOperator` in `users/permissions.py` all require `user and user.is_authenticated and user.is_active`.
  - Unauthenticated requests receive **HTTP 401 Unauthorized** (or HTTP 403 Forbidden).
  - Unprivileged roles (e.g. `waiter`, `cashier`, `customer`) attempting to access stocktaking sessions, schedules, or dismiss expiry alerts receive **HTTP 403 Forbidden**. (Verified in `test_expiry_alerts_and_schedules.py:test_06` and `test_stocktaking_management.py:test_12`).

##### 2. IDOR Protection & Queryset Scoping
- **Single-Tenant / Single-Property Architecture:**
  Direct inspection of PostgreSQL 16 schema in `hotel_erp_staging` and models in `hotel/models.py` confirms that the ACRMA Hotel ERP is a single-property hotel ERP system. There are no multi-tenant or multi-property columns in inventory models (`StockLocation`, `StocktakeSession`, `StocktakeSchedule`, `InventoryExpiryAlert`). All inventory locations belong to the single hotel enterprise.
- **Horizontal Scoping & Object Ownership Observation (Severity: Medium):**
  - In `StocktakeScheduleViewSet`, `get_queryset()` returns `StocktakeSchedule.objects.all()`. Any user with `role="inventory"` can pause, activate, delete, or trigger any schedule, even those created by other staff members. There is no `created_by=request.user` filter or object-level permission (`check_object_permissions`).
  - In `StocktakeSessionViewSet`, `get_queryset()` returns all sessions across all locations without restricting counters to their assigned sessions.
  - In `record_counts()`, the service layer does not verify whether `request.user` matches `session.schedule.assigned_staff`. Any staff member with inventory permissions can submit counts for another staff member's assigned session.

##### 3. Frontend/Backend Contract Consistency
- **Endpoint Disconnects (Critical Defect DEF-SEC-01):**
  Frontend components in `hotel-frontend/src/pages/stocktaking/` call:
  - `POST /api/v1/stocktaking/sessions/${session.id}/record-counts/` (`StocktakeCountDesk.jsx:72`)
  - `POST /api/v1/stocktaking/sessions/${session.id}/submit-recount/` (`StocktakeCountDesk.jsx:71`)
  - `POST /api/v1/stocktaking/sessions/${session.id}/request-recount/` (`StocktakeVarianceDesk.jsx:65`)
  - `POST /api/v1/stocktaking/sessions/${session.id}/approve/` (`StocktakeVarianceDesk.jsx:110`)
  - `POST /api/v1/stocktaking/sessions/${session.id}/cancel/` (`StocktakeVarianceDesk.jsx:142`)
  None of these 5 action endpoints are exposed by `StocktakeSessionViewSet` in `apps/inventory/views.py`. Submitting any of these forms in the React UI fails with **HTTP 404 Not Found**.
- **Data Contract & Schema Verification:**
  - Field names, enums, and request schemas match between frontend and backend services:
    - Initial count payload: `{ counts: [{ id, counted_quantity, notes }] }`
    - Recount payload: `{ recounts: [{ id, recounted_quantity, notes }] }`
    - Approval payload: `{ notes, emergency_self_approval, justification }`
    - Recount request payload: `{ item_ids, reason }`
  - Computed serializer fields (`is_overdue`, `next_run_at`, `days_left`) correctly match frontend display cards and filter pills.
- **Dismissed Expiry Alert Reactivation Loop (High Defect DEF-SEC-03):**
  - In `hotel/inventory.py:125-137`:
    ```python
    alert, created = InventoryExpiryAlert.objects.get_or_create(
        batch=batch,
        alert_type=alert_type,
        status="active",
        defaults={...}
    )
    ```
  - When staff dismisses an alert in `InventoryDashboard.js` via `POST /api/v1/inventory/expiry-alerts/<id>/dismiss/`, the alert status transitions to `"dismissed"`.
  - On the next background scheduler run or manual scan ("⚡ Run Expiry Scan"), `get_or_create` searches for an alert with `status="active"`. Because the existing alert is `"dismissed"`, it creates a **new duplicate active alert** for the still-expired batch. This breaks staff acknowledgment persistence.

---

## 2. Logic Chain

1. **Premise 1 (Draft Safety & Workflow Operability):**
   A draft stocktaking system cannot be considered safe or functional if its lifecycle state transitions cannot be executed via the authoritative API layer.
   - *Observation:* `StocktakeSessionViewSet` in `apps/inventory/views.py:3163-3195` does not define `record-counts`, `request-recount`, `submit-recount`, `approve`, or `cancel` actions.
   - *Inference:* All 5 stocktaking action routes return HTTP 404 Not Found. Automated tests calling `reverse("stocktakesession-record-counts")` and `reverse("stocktakesession-approve")` fail with `NoReverseMatch`. The frontend UI cannot record counts or approve sessions.
   - *Conclusion:* Area 6 fails the draft safety and API operability mandate (**DEF-SEC-01**, Severity: **Critical**).

2. **Premise 2 (Zero-Leak Blind Mode Security):**
   Blind-mode security requires that theoretical balances and variances must be stripped before responses are transmitted across the network to non-administrative counters.
   - *Observation:* `StocktakeItemSerializer.to_representation()` (`apps/inventory/serializers.py:920-938`) and `StocktakeSessionSerializer.to_representation()` (lines 1011-1028) set theoretical and variance fields to `None` when `counting_mode == "blind"`, status is in `("draft", "in_progress")`, and `not is_admin`.
   - *Inference:* Theoretical balances are stripped at the backend serializer layer before serialization into JSON. No theoretical balance data is transmitted over HTTP or present in the browser DOM.
   - *Conclusion:* Blind-mode zero-leak protection **PASSES** all requirements.

3. **Premise 3 (Separation of Duties):**
   Segregation of duties requires that the user who physically counted stock cannot approve variances and trigger financial adjustments.
   - *Observation:* `hotel/stocktaking.py:413-436` explicitly compares `session.counted_by` against `supervisor` and raises `PermissionDenied` unless an emergency superuser override is provided with a >= 15-character justification and an immutable `AuditEvent` log.
   - *Inference:* The backend service enforces `counted_by != approved_by`. However, because the API route `POST /api/v1/stocktaking/sessions/<id>/approve/` fails with HTTP 404, SoD cannot be exercised or validated via the REST API.
   - *Conclusion:* SoD is sound at the service layer, but fails at the API layer due to DEF-SEC-01.

4. **Premise 4 (Approval-Based GL Posting):**
   General Ledger posting for inventory variances must occur strictly upon authorized approval, produce balanced debit/credit entries, and resist duplicate postings.
   - *Observation:* `hotel/stocktaking.py:488-522` posts entries strictly inside `approve_stocktake_session()`. Deficits debit 5020 and credit 1300; surpluses debit 1300 and credit 5020. `hotel/accounting.py:47-48` enforces `total_debit == total_credit`. Replay of approved sessions returns early, and stock mutations use unique idempotency keys.
   - *Inference:* The GL accounting logic is balanced, idempotent, and restricted to approval. However, triggering approval via the API fails with HTTP 404.
   - *Conclusion:* GL posting logic is mathematically sound and idempotent at the service layer, but inoperable via the API.

5. **Premise 5 (API Permissions & IDOR):**
   All inventory endpoints must block unauthenticated and unauthorized users, and querysets must prevent unauthorized cross-property or cross-user tampering.
   - *Observation:* All viewsets enforce DRF permission classes (`IsInventoryManager`, `IsBatchOperator`, `IsAuthenticated`). Unauthenticated requests are rejected with HTTP 401; non-inventory roles receive HTTP 403. The ERP is single-property (no multi-property isolation needed). However, any inventory user can modify/delete any schedule or submit counts on another counter's session.
   - *Conclusion:* Role-based permissions are enforced. Horizontal object-level scoping is noted as an observation (**DEF-SEC-04**, Severity: **Medium**).

6. **Premise 6 (Alert Dismissal Integrity):**
   Staff acknowledgment of an expiry alert must persist and not be undone by subsequent automated scans.
   - *Observation:* In `hotel/inventory.py:125-137`, `evaluate_inventory_expiry_alerts()` executes `get_or_create(..., status="active")`. Dismissing an alert sets `status="dismissed"`. On the next scan, `get_or_create` creates a new active alert for the same batch.
   - *Conclusion:* Staff dismissals are undone on subsequent scans, violating lifecycle expectations (**DEF-SEC-03**, Severity: **High**).

---

## 3. Caveats

1. **Read-Only Constraint Compliance:**
   Zero lines of application code or migrations were modified during this investigation. No git clean, reset, commit, or push was performed. The working tree was preserved in its exact existing state.
2. **Database Integrity Preservation:**
   All inspections were read-only queries against `hotel_erp_staging`. Automated tests were executed using `--keepdb` against the dedicated test database (`test_hotel_erp_staging`), leaving staging data intact.
3. **Multi-Tenancy Scope:**
   This assessment verified single-property security architecture. If the ERP is expanded to a multi-property chain in the future, explicit `property_id` queryset scoping and object-level permissions must be added to all viewsets.

---

## 4. Defect Register

| Defect ID | Severity | Category | Description | Source Reference |
| :--- | :---: | :--- | :--- | :--- |
| **DEF-SEC-01** | **Critical** | API Routing / ViewSet | `StocktakeSessionViewSet` lacks `@action` decorators for `record-counts`, `request-recount`, `submit-recount`, `approve`, and `cancel`. All form submissions fail with HTTP 404 Not Found, and automated tests fail with `NoReverseMatch`. | `apps/inventory/views.py:3163-3195` |
| **DEF-SEC-02** | **High** | Data Integrity / Safety | `StocktakeSessionViewSet` lacks `destroy()` override, allowing inventory managers to issue `DELETE /api/v1/stocktaking/sessions/<id>/` on sessions in any lifecycle state (`in_progress`, `approved`), triggering CASCADE deletion of all historical `StocktakeItem` snapshot records. | `apps/inventory/views.py:3163`<br>`hotel/models.py:2387-2390` |
| **DEF-SEC-03** | **High** | Alert Lifecycle | `evaluate_inventory_expiry_alerts()` uses `status="active"` in `get_or_create()`, causing dismissed alerts (`status="dismissed"`) to be resurrected as new active duplicate alerts on the next scan or scheduler run. | `hotel/inventory.py:125-137` |
| **DEF-SEC-04** | **Medium** | IDOR / Object Scoping | Absence of object-level authorization on `StocktakeScheduleViewSet` and `StocktakeSession`: Any user with `role="inventory"` can modify, pause, trigger, or delete schedules created by any other staff member, and any inventory user can submit counts for sessions assigned to another counter. | `apps/inventory/views.py:5801-5825`<br>`hotel/stocktaking.py:149-249` |

---

## 5. Conclusion

Based on independent inspection of Django models, serializers, views, permissions, services, frontend components, and live execution of automated tests against PostgreSQL 16 `hotel_erp_staging`:

1. **Area 6 (Stocktaking draft safety, blind-mode protection, separation of duties, and approval-based GL posting)** is **REJECTED**:
   - Blind-mode zero-leak masking is verified and passes at the serializer level.
   - Separation of Duties (`counted_by != approved_by`) and balanced GL posting are verified and mathematically correct at the service layer.
   - **However**, the backend API layer (`apps/inventory/views.py`) is missing all action endpoints on `StocktakeSessionViewSet`, rendering physical count recording, recounts, SoD verification, and GL approval inoperable via HTTP (HTTP 404) and breaking both automated regression test suites.
   - Furthermore, `StocktakeSessionViewSet` permits cascading deletion of in-progress and approved stocktakes via unconstrained `DELETE`.

2. **Area 7 (API permissions, IDOR protection, and frontend/backend consistency)** is **REJECTED**:
   - Role-based permissions (`IsInventoryManager`, `IsBatchOperator`, `IsAuthenticated`) properly reject unauthenticated and unauthorized roles with HTTP 401/403.
   - The ERP is a single-property system; no cross-property data leaks exist.
   - **However**, the frontend React SPA cannot complete stocktaking workflows due to the HTTP 404 disconnect on action endpoints, and staff dismissal of expiry alerts is repeatedly reversed by the background scheduler.

### Final Verdict: **REJECTED**
Pursuant to the governing criteria in `ORIGINAL_REQUEST.md` (lines 46-50):
*"REJECTED: Any Critical or High severity defect identified."*  
Due to 1 Critical Defect (**DEF-SEC-01**) and 2 High Severity Defects (**DEF-SEC-02**, **DEF-SEC-03**), the implementation cannot be accepted in its current state.

---

## 6. Verification Method

To independently reproduce and verify every finding in this report:

1. **Reproduce Automated Test Regressions:**
   ```powershell
   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_stocktaking_management --keepdb
   # Expected result: FAILED (errors=5). Notice NoReverseMatch on record-counts, request-recount, approve, cancel.

   .venv\Scripts\python.exe manage.py test apps.inventory.tests.test_expiry_alerts_and_schedules --keepdb
   # Expected result: FAILED (errors=1). Notice NoReverseMatch on test_13 (stocktakesession-approve).
   ```

2. **Verify Missing Endpoints via Django Shell:**
   ```powershell
   .venv\Scripts\python.exe manage.py shell -c "import users.serializers; from apps.inventory.views import StocktakeSessionViewSet; print('Extra actions:', [a.__name__ for a in StocktakeSessionViewSet.get_extra_actions()])"
   # Expected output: Extra actions: []  (Demonstrating record_counts, approve, etc. are missing)
   ```

3. **Verify Serializer Blind-Mode Masking:**
   Inspect `apps/inventory/serializers.py` lines 920-938 (`StocktakeItemSerializer.to_representation`) and lines 1011-1028 (`StocktakeSessionSerializer.to_representation`). Confirm `theoretical_quantity = None` when `counting_mode == "blind"` and `not is_admin`.

4. **Verify SoD and GL Balancing at Service Layer:**
   Inspect `hotel/stocktaking.py` lines 413-436 (`session.counted_by.username == supervisor.username`) and lines 488-522 (Dr 5020/1300, Cr 1300/5020).

5. **Verify Alert Dismissal Reactivation Loop:**
   Inspect `hotel/inventory.py` lines 125-137. Observe `get_or_create(..., status="active")`. When an alert has `status="dismissed"`, the query creates a new duplicate active alert.
