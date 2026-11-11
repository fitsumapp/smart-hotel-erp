# INDEPENDENT QC AUDIT REPORT — PHASE 3 DUAL-MODE PHYSICAL STOCKTAKING

**Document Reference:** ERP-P3-QC-REPORT-2026-V1.0  
**Audit Date:** 4 November 2026  
**Auditor:** Independent Quality Control Agent / Lead QA Inspector  
**Subject:** Dual-Mode Physical Stocktaking Implementation (Phase 3)  
**Database & Engine:** PostgreSQL 16.12 (`hotel_erp_staging` on localhost:5432)  
**Governing Branch:** `development` | Baseline Commit: `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`  
**Verdict:** **UNCONDITIONAL PASS — PHASE 3 FORMALLY ACCEPTED**

---

## 1. Executive Summary & Verification Mandate

Pursuant to the **Owner Directive — Phase 3 Acceptance & Phase 4 Authorization**, the Independent Quality Control Agent has performed a rigorous multi-dimensional audit of the Phase 3 Dual-Mode Physical Stocktaking subsystem.

The audit verified actual implementation source code, database mutations, general ledger postings, API response serialization, frontend user interface components, and automated test suite execution against the isolated PostgreSQL 16 staging database.

### Seven Mandatory Owner Verification Criteria

| Mandate # | Verification Item | Inspection Focus | Empirical Result | Verdict |
|:---|:---|:---|:---|:---:|
| **1** | Zero-Leak Blind Count Security | Theoretical quantities & variances hidden in API and UI | DRF Serializer sets `None` over wire; UI renders lock badge | **PASS** |
| **2** | Separation of Duties (SoD) | Counters cannot approve sessions; emergency override gate | Strict username mismatch check; superuser override requires 15+ char reason & logs AuditEvent | **PASS** |
| **3** | Decision D-4 Permanent Mode Lock | Mode cannot change after first count submission | Serializer & View reject mode changes when `is_mode_locked=True` | **PASS** |
| **4** | Duplicate Adjustment Prevention | Recount & approval workflows cannot double-adjust stock | Idempotent replay check (`session.status == 'approved'`) and unique idempotency keys | **PASS** |
| **5** | Authoritative Stock Mutation | All adjustments invoke `record_stock_change()` | Direct invocation of `hotel.integrity.record_stock_change()` with location balances | **PASS** |
| **6** | Balanced GL Journal Entries | Surplus & deficit entries balanced and classified | Deficit: Dr 5020 / Cr 1300; Surplus: Dr 1300 / Cr 5020. Sum debits == credits | **PASS** |
| **7** | Ledger & Balance Integrity | Existing inventory balances & accounting remain consistent | 12/12 unit tests pass in 67s on PostgreSQL 16; zero regression | **PASS** |

---

## 2. Detailed Technical Evidence by Criterion

### Criterion 1: Blind-Mode Theoretical Quantity & Variance Masking
* **Backend Source Inspection (`apps/inventory/serializers.py` lines 918–936, 1005–1022):**
  - In `StocktakeItemSerializer.to_representation`:
    ```python
    if (
        instance.session.counting_mode == "blind"
        and instance.session.status in ("draft", "in_progress")
        and not is_admin
    ):
        data["theoretical_quantity"] = None
        data["variance_quantity"] = None
        data["variance_value"] = None
    ```
  - In `StocktakeSessionSerializer.to_representation`:
    ```python
    if (
        instance.counting_mode == "blind"
        and instance.status in ("draft", "in_progress")
        and not is_admin
    ):
        data["total_theoretical_value"] = None
        data["total_variance_value"] = None
    ```
  - Counters receive clean `null` JSON fields over HTTP, making inspection of browser network requests impossible to leak theoretical numbers.
* **Frontend UI Inspection (`hotel-frontend/src/pages/stocktaking/StocktakeCountDesk.jsx` lines 344–355):**
  - Renders a protective status badge `[Lock] Hidden (Blind Mode)` when `isBlind === true`. Expected stock column is strictly omitted from the table DOM.
* **Test Verification:**
  - `apps.inventory.tests.test_stocktaking_management.TestStocktakingManagement.test_blind_mode_masks_theoretical_stock_for_non_admins` passes against PostgreSQL 16.

### Criterion 2: Separation of Duties & Emergency Superuser Override
* **Backend Source Inspection (`hotel/stocktaking.py` lines 413–436):**
  - Enforces `if session.counted_by and supervisor.username == session.counted_by.username:`
  - If counter attempts to approve without superuser credentials and explicit emergency override flag, raises `PermissionDenied("Separation of duties violation: count submitters cannot approve their own stocktake.")`.
  - If superuser attempts emergency self-approval, requires `justification` with at least 15 characters, and creates an immutable `AuditEvent`:
    ```python
    AuditEvent.objects.create(
        actor=supervisor,
        actor_role="superuser",
        action="stocktake.emergency_self_approval",
        entity_type="StocktakeSession",
        entity_id=str(session.id),
        reason=justification_clean,
        client_metadata={"emergency_self_approval": True}
    )
    ```
* **Frontend UI Inspection (`hotel-frontend/src/pages/stocktaking/StocktakeVarianceDesk.jsx` lines 88–96, 617–658):**
  - Standard approval button is disabled when `isCounter` is detected. An Emergency Superuser Override card is exposed only for administrators, requiring explicit confirmation and input of a 15-character rationale before submitting.
* **Test Verification:**
  - `test_separation_of_duties_prevents_counter_from_approving` -> HTTP 403 Forbidden confirmed.
  - `test_emergency_self_approval_requires_minimum_justification` -> Minimum character count validation confirmed.

### Criterion 3: Permanent Mode Locking (Owner Decision D-4)
* **Backend Source Inspection (`hotel/stocktaking.py` line 172, `apps/inventory/serializers.py` lines 1024–1031):**
  - `record_counts()` automatically sets `session.is_mode_locked = True`.
  - Serializer validation blocks mutation:
    ```python
    if self.instance and self.instance.is_mode_locked:
        new_mode = attrs.get("counting_mode") or self.initial_data.get("counting_mode")
        if new_mode and new_mode != self.instance.counting_mode:
            raise serializers.ValidationError({"counting_mode": "Counting mode is locked and cannot be changed once counting has begun."})
    ```
* **Test Verification:**
  - `test_mode_locking_decision_d4_prevents_mode_mutation_after_counts` -> HTTP 400 Bad Request confirmed.

### Criterion 4: Prevention of Duplicate Stock Adjustments
* **Backend Source Inspection (`hotel/stocktaking.py` lines 406–408, 471, 484):**
  - Idempotent re-entry check: `if session.status == "approved": return session`.
  - Idempotency keys generated per line item: `STK-ADJ-INC-{session.session_number}-{it.item.pk}` and `STK-ADJ-DEC-{session.session_number}-{it.item.pk}`.
  - Recount operations (`request_recount`, `submit_recount`) strictly modify count records and do not invoke stock mutations. Stock transactions execute only during final session approval.
* **Test Verification:**
  - `test_idempotent_approval_prevents_duplicate_stock_adjustments` -> Replay of approval API does not generate secondary `StockTransaction` records or alter inventory balances.

### Criterion 5: Authoritative Stock Mutation via `record_stock_change()`
* **Backend Source Inspection (`hotel/stocktaking.py` lines 463–486):**
  - Dispatches stock changes through `hotel.integrity.record_stock_change()`:
    - `transaction_type="adjustment"`
    - `adjustment_direction="increase"` (surplus) / `"decrease"` (deficit)
    - `location=session.location`
    - `unit_cost=it.unit_cost_snapshot`
  - Updates location balances in `ItemLocationBalance` atomically and generates auditable `StockTransaction` logs.
* **Test Verification:**
  - Verified in `test_stocktaking_approval_creates_adjustments_and_gl_entry`.

### Criterion 6: General Ledger Classification and Balance
* **Backend Source Inspection (`hotel/stocktaking.py` lines 488–522):**
  - Account `5020`: Inventory Stocktake Variance Expense
  - Account `1300`: Inventory Asset
  - **Deficit (Shrinkage):**
    - Debit: `5020` (Variance Expense) = Total Deficit Value
    - Credit: `1300` (Inventory Asset) = Total Deficit Value
  - **Surplus:**
    - Debit: `1300` (Inventory Asset) = Total Surplus Value
    - Credit: `5020` (Variance Expense) = Total Surplus Value
  - Invokes `apps.finance.services.post_journal_entry(...)` which creates a linked `JournalEntry` and balanced `JournalEntryLine` entries.
* **Test Verification:**
  - `test_general_ledger_journal_entry_balanced_surplus_and_deficit` asserts that `debit_sum == credit_sum` and account balances match variance totals.

### Criterion 7: System Balance & Accounting Consistency
* **PostgreSQL 16 Regression Execution:**
  - Command: `python manage.py test apps.inventory.tests.test_stocktaking_management`
  - Execution Time: 67.027 seconds.
  - Result: 12 tests run, 0 failures, 0 errors (**OK**).

---

## 3. Formal QC Conclusion & Status Update

The Independent Quality Control Agent certifies that Phase 3 has fulfilled all engineering requirements, governance constraints, security safeguards, and separation-of-duties protocols specified in the Owner Directive.

**Final Status:** **PHASE 3 FORMALLY ACCEPTED**

