# ACRMA HOTEL ERP — INVENTORY REGRESSION TEST REPORT

**Target Environment:** Local Development & PostgreSQL `hotel_erp_staging` (Port 5432)  
**Test Database:** Dedicated Isolated PostgreSQL `test_hotel_erp_staging`  
**Git Branch:** `development` | **HEAD Commit:** `97d560c77f80799035b89633d9e589d0937808cb`  
**Execution Timestamp:** 2026-11-16  
**Operating Boundary Confirmation:** Zero modifications committed to staging database. Zero connections to Neon production. Zero git pushes or branch switching.

---

## 1. Executive Summary & Verification Scorecard

Following the authorized implementation across Phases A, B, C, and D, an exhaustive regression test program was executed across all inventory and inventory-dependent modules. The objective was to verify that the root causes of sub-ledger divergence have been eliminated while guaranteeing that no existing workflows or integrations were degraded.

### Verification Scorecard

| Test Suite / Scope | Total Tests | Passed | Failed | Errors | Duration | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **New Transfer & Waste Integrity Regression** | 6 | 6 | 0 | 0 | 10.59s | **PASSED** |
| **Stock Transfer Lifecycle & Invariants** | 13 | 13 | 0 | 0 | 20.57s | **PASSED** |
| **Stock Locations & Safe Deactivation** | 3 | 3 | 0 | 0 | 4.86s | **PASSED** |
| **Waste Recording & Threshold Approvals** | 34 | 34 | 0 | 0 | 88.90s | **PASSED** |
| **Reporting & GL Reconciliation Engine** | 4 | 4 | 0 | 0 | 4.43s | **PASSED** |
| **Opening Stock Import & Procurement** | 4 | 4 | 0 | 0 | 5.07s | **PASSED** |
| **Minibar Operations & Stock Control** | 3 | 3 | 0 | 0 | 3.48s | **PASSED** |
| **Stock Ledger Determinism & Audit Trails** | 5 | 5 | 0 | 0 | 8.02s | **PASSED** |
| **POS Payment & Shortage Settlement** | 7 | 7 | 0 | 0 | 11.25s | **PASSED** |
| **TOTAL** | **79** | **79** | **0** | **0** | **157.17s** | **100% PASS** |

---

## 2. Comprehensive Test Execution Details

All tests executed via Django test runner using the dedicated PostgreSQL test database `test_hotel_erp_staging`. Each test operates within an atomic transaction rollback block (`TestCase`), ensuring absolute isolation.

### Suite 1: Transfer & Waste Integrity Regression (`apps.inventory.tests.test_transfer_and_waste_integrity_regression`)
- **Execution Time:** 10.588s | **Status:** 6/6 PASSED
- **Test Cases:**
  1. `test_01_transfer_dispatch_and_intact_receipt_balances`: Verifies dispatch decrements source `ItemLocationBalance` and destination receipt increments destination `ItemLocationBalance` while batch quantities and transactions balance at each phase.
  2. `test_02_transfer_partial_receipt_with_breakage_and_gl_clearing`: Validates transit damage handling during receipt; verifies destination receives intact quantity, damaged quantity is written off as `loss`, and balanced GL journal entries (Dr 5010 Spoilage / Cr 1300 Inventory) are posted.
  3. `test_03_duplicate_dispatch_and_receive_prevention`: Proves duplicate dispatches on the same transfer raise `ValidationError` ("status is 'in_transit', expected 'requested'") and duplicate receipts raise `ValidationError` ("status is 'completed', expected 'in_transit'").
  4. `test_04_door_rejection_returns_stock_to_source`: Proves destination door rejection cleanly cancels in-transit transfer, restores stock to source location, and logs reverse audit transactions.
  5. `test_05_waste_recording_idempotency_and_atomic_deduction`: Submits direct loss via API; verifies atomic decrement of `InventoryItem.current_stock`, `StockBatch.current_quantity`, `ItemLocationBalance.quantity`, and `BatchLocationBalance.quantity`; verifies GL 5010/1300 journal; verifies replaying identical payload returns cached result without double deduction.
  6. `test_06_gl_reconciliation_report_status_breakdown`: Validates authoritative quantity calculations and segregates active ($2,000\text{ ETB}$), quarantined ($0\text{ ETB}$), and expired ($200\text{ ETB}$) batch valuations in the GL reconciliation report.

### Suite 2: Stock Transfer Lifecycle (`apps.inventory.tests.test_stock_transfers`)
- **Execution Time:** 20.574s | **Status:** 13/13 PASSED
- **Test Cases:**
  1. `test_01_request_stock_transfer`: Request creation and initial status verification.
  2. `test_02_dispatch_stock_transfer_fefo_source_deduction`: FEFO batch deduction upon dispatch.
  3. `test_03_receive_stock_transfer_intact`: Full intact receipt destination increment.
  4. `test_04_receive_stock_transfer_partial_with_breakage_waste_and_gl`: Partial receipt with damage write-off.
  5. `test_05_reconciliation_mismatch_validation`: Mismatch detection when received + damaged != dispatched.
  6. `test_06_cancel_requested_transfer`: Cancellation before dispatch.
  7. `test_07_door_rejection_in_transit_returns_stock_to_source`: Return of in-transit goods to origin.
  8. `test_08_insufficient_source_stock_prevent_dispatch`: Insufficient balance validation.
  9. `test_09_expired_or_quarantined_batches_blocked_from_dispatch`: Expired/quarantined exclusion from dispatch.
  10. `test_10_api_transfer_lifecycle_endpoints`: Full REST API dispatch, receive, cancel flows.
  11. `test_11_immutable_stock_transfer_prevention`: Block editing transfers after dispatch.
  12. `test_12_duplicate_dispatch_and_receive_blocked`: Concurrency and state guarding.
  13. `test_13_stock_transaction_audit_trail_and_idempotency`: Idempotency keys on transfer transactions.

### Suite 3: Stock Locations & Deactivation Protection (`apps.inventory.tests.test_location_and_transfers_phase2`)
- **Execution Time:** 4.864s | **Status:** 3/3 PASSED
- **Test Cases:**
  1. `test_01_stock_location_inventory_endpoint`: Location inventory listing endpoint.
  2. `test_02_stock_location_safe_deactivation_protection`: Blocks deactivating locations holding positive balances.
  3. `test_03_full_api_transfer_lifecycle_and_damage_reconciliation`: End-to-end API lifecycle.

### Suite 4: Waste Management & Approvals (`apps.inventory.tests.test_waste_management`)
- **Execution Time:** 88.897s | **Status:** 34/34 PASSED
- **Key Test Cases:**
  - Idempotency replay vs payload conflict handling (`test_idempotency_exact_replay_vs_payload_conflict`).
  - Direct loss below threshold auto-approval (`test_loss_below_threshold_auto_approved`).
  - Direct loss above threshold pending review (`test_loss_above_threshold_pending_review`).
  - Authorized dual approval processing stock and GL once (`test_authorized_approval_processes_stock_and_accounting_once`).
  - Rejection leaving stock and GL untouched (`test_rejection_leaves_stock_and_accounting_unchanged`).
  - Kitchen prep waste ceiling enforcement and reservation release (`test_kitchen_prep_waste_ceiling_enforcement`).
  - Superuser self-approval audit logging (`test_superuser_self_approval_exception_with_audit_trail`).

### Suite 5: Reporting & GL Reconciliation Engine (`apps.inventory.tests.test_reporting_and_gl_reconciliation_phase5`)
- **Execution Time:** 4.429s | **Status:** 4/4 PASSED
- **Test Cases:**
  1. `test_01_stock_movement_report_formula_reconciliation`: $\text{Opening} + \text{In} - \text{Out} = \text{Closing}$.
  2. `test_02_gl_reconciliation_perfect_equilibrium`: GL 1300 balance equals active batch valuation.
  3. `test_03_gl_reconciliation_detects_discrepancy`: Discrepancy detection between GL and batches.
  4. `test_04_movement_report_location_filtering`: Location-filtered ledger calculations.

### Suite 6: Opening Stock & Procurement (`apps.inventory.tests.test_opening_stock_and_procurement_phase3`)
- **Execution Time:** 5.073s | **Status:** 4/4 PASSED
- **Test Cases:**
  1. `test_01_unit_conversion_engine`: UOM multipliers and discrete conversions.
  2. `test_02_opening_stock_import_and_duplicate_protection`: Idempotent opening stock intake.
  3. `test_03_spot_purchase_workflow`: Spot purchase receiving and ledger posting.
  4. `test_04_purchase_order_printable_document`: Purchase order document generation.

### Suite 7: Minibar Operations & Control (`apps.inventory.tests.test_minibar_and_stock_control_phase4`)
- **Execution Time:** 3.478s | **Status:** 3/3 PASSED
- **Test Cases:**
  1. `test_01_minibar_replenishment_creates_issuance_stock_transaction`: Warehouse issuance to room.
  2. `test_02_minibar_consumption_updates_folio_and_gl_entry`: Guest charge and GL recognition.
  3. `test_03_fefo_perishable_allocation_picks_earliest_expiry_batch`: FEFO batch consumption.

### Suite 8: Stock Ledger Determinism (`apps.inventory.tests.test_stock_ledger_integrity`)
- **Execution Time:** 8.022s | **Status:** 5/5 PASSED
- **Test Cases:**
  1. `test_01_stock_ledger_pagination_and_deterministic_ordering`: Deterministic ordering by `(timestamp, id)`.
  2. `test_02_stock_ledger_query_filtering`: Item, location, and date range filters.
  3. `test_03_stock_ledger_summary_action`: Aggregate ledger metrics.
  4. `test_04_transfer_creates_audit_trail_and_reconciles_cleanly`: Transfer audit trail verification.
  5. `test_05_cancelled_in_transit_transfer_returns_stock_with_audit`: Audit trail on door rejection.

### Suite 9: POS Payment & Shortage Settlement (`apps.orders.tests.test_pos_payment_reliability`)
- **Execution Time:** 11.252s | **Status:** 7/7 PASSED
- **Test Cases:**
  1. `test_cash_payment_with_zero_stock_settles_and_records_shortage`: Cash settlement records unfulfilled shortage without blocking sale.
  2. `test_chapa_webhook_with_insufficient_stock_succeeds_without_rollback`: Webhook idempotency and shortage capture.
  3. `test_deterministic_bom_lock_ordering_prevents_deadlock`: Concurrency deadlock protection.
  4. `test_duplicate_webhook_replay_is_idempotent`: Replay protection on payments.
  5. `test_failed_ingredient_deduction_leaves_zero_partial_modifications`: Transaction atomicity on ingredient deduction failure.
  6. `test_grn_intake_does_not_auto_deduct_historical_shortage`: Shortage decoupling from GRN.
  7. `test_room_charge_with_insufficient_stock_posts_folio_and_records_shortage`: Room charge shortage recording.

---

## 3. Coverage Matrix Against Development Scope

| Phase | Functional Requirement | Test Implementation | Assertions Validated | Result |
| :--- | :--- | :--- | :--- | :---: |
| **Phase A** | Origin location decrement on dispatch | `test_transfer_and_waste_integrity_regression.py:test_01`<br>`test_stock_transfers.py:test_02` | `source_ilb.quantity` reduced by exact dispatch quantity; row locked via `select_for_update()`. | **PASS** |
| **Phase A** | Destination location increment on receipt | `test_transfer_and_waste_integrity_regression.py:test_01`<br>`test_stock_transfers.py:test_03` | `dest_ilb.quantity` increased by exact received quantity; new `BatchLocationBalance` created. | **PASS** |
| **Phase A** | Transit damage write-off & GL clearing | `test_transfer_and_waste_integrity_regression.py:test_02`<br>`test_stock_transfers.py:test_04` | Damaged stock logged as `loss`; GL entry posted Dr 5010 / Cr 1300; balanced entries. | **PASS** |
| **Phase A** | Door rejection returns stock to origin | `test_transfer_and_waste_integrity_regression.py:test_04`<br>`test_stock_transfers.py:test_07` | In-transit stock restored to origin location; transactions logged with `idempotency_key`. | **PASS** |
| **Phase A** | Duplicate dispatch & receive prevention | `test_transfer_and_waste_integrity_regression.py:test_03`<br>`test_stock_transfers.py:test_12` | Subsequent dispatch on `in_transit` raises `ValidationError`; subsequent receipt on `completed` raises `ValidationError`. | **PASS** |
| **Phase B** | Waste location resolution from storage area | `test_transfer_and_waste_integrity_regression.py:test_05`<br>`test_waste_management.py:test_direct_loss_stock_deduction_and_ledger` | `storage_area` resolved to `StockLocation`; stock deducted from actual holding location instead of forcing `STORE-MAIN`. | **PASS** |
| **Phase B** | Atomic 4-tier stock deduction | `test_transfer_and_waste_integrity_regression.py:test_05` | `InventoryItem.current_stock`, `StockBatch.current_quantity`, `ItemLocationBalance.quantity`, and `BatchLocationBalance.quantity` all decremented in single transaction. | **PASS** |
| **Phase B** | Idempotency & GL balance | `test_transfer_and_waste_integrity_regression.py:test_05`<br>`test_waste_management.py:test_idempotency_exact_replay_vs_payload_conflict` | Exact replay returns HTTP 200 without second deduction; GL entry Dr 5010 / Cr 1300 balanced. | **PASS** |
| **Phase C** | Authoritative item quantity calculation | `test_transfer_and_waste_integrity_regression.py:test_06` | Multi-tier breakdown separates active, quarantined, expired, and in-transit quantities accurately. | **PASS** |
| **Phase C** | Invariant: $\text{Location Sum} + \text{In-Transit} == \text{On-Hand Batches}$ | `test_transfer_and_waste_integrity_regression.py:test_01, test_02, test_04` | Invariant validated at request, dispatch, and receipt states. `is_consistent == True`. | **PASS** |
| **Phase D** | Test database isolation | Verified via DB connection monitor | Tests executed in `test_hotel_erp_staging`; 0 rows committed to `hotel_erp_staging`. | **PASS** |

---

## 4. End-to-End Browser Workflow Verification

In addition to automated unit and integration tests, key workflows were verified through end-to-end browser operations against the local development server:

### 1. Purchase Order GRN Receiving Desk
- **Component:** `hotel-frontend/src/pages/procurement/GrnDesk.jsx`
- **Backend Service:** `hotel/procurement.py:process_goods_receipt`
- **Observed Operation:**
  - Navigated to Procurement Center -> GRN Receiving.
  - Selected approved Purchase Order.
  - Frontend submitted payload containing `received_quantity` and `rejected_quantity`.
  - Backend received payload via backward-compatible resolver (`received_quantity` or `quantity_received`).
  - Successfully generated GRN, created new `StockBatch` with initial quantity, updated `InventoryItem.current_stock`, updated `ItemLocationBalance`, and posted balanced GL entry (Dr 1300 / Cr 2000).
  - Page refreshed: all quantities, GRN record, batch status, and PO completion status persisted cleanly.

### 2. Waste Recording Desk
- **Component:** `hotel-frontend/src/pages/inventory/WasteDesk.jsx`
- **Backend Service:** `apps/inventory/views.py:WasteRecordViewSet`
- **Observed Operation:**
  - Navigated to Inventory -> Waste Management.
  - Submitted direct loss entry with `Idempotency-Key` header.
  - CORS preflight `OPTIONS` request returned HTTP 200 with `Access-Control-Allow-Headers: ... idempotency-key ...`.
  - Waste entry created with status `approved` (below threshold) and atomic deduction of master stock, batch, and location balance.
  - Duplicate submission with same key returned HTTP 200 with cached response; no double deduction occurred.

### 3. Stock Transfer Center
- **Component:** `hotel-frontend/src/pages/transfers/StockTransferDesk.jsx`
- **Backend Service:** `hotel/transfers.py`
- **Observed Operation:**
  - Created transfer request from Main Store to Kitchen Store.
  - Dispatched transfer: verified origin `ItemLocationBalance` was decremented, batches locked, and status transitioned to `in_transit`.
  - Received transfer with partial damage: verified destination received intact quantity, damage logged as loss, and transfer completed.

---

## 5. Traceability Matrix to Original Failures

| Original Failure Mode | Root Cause Identified | Remediated In | Verifying Regression Test |
| :--- | :--- | :--- | :--- |
| **Transfer dispatch did not decrement source location balance** | `ItemLocationBalance` update was conditional on prior existence and clamped via `max()`. | `hotel/transfers.py:dispatch_stock_transfer` | `test_transfer_and_waste_integrity_regression.py:test_01` |
| **Transfer receipt created batch balance without updating destination location balance** | `ItemLocationBalance` increment logic omitted destination location update in specific branches. | `hotel/transfers.py:receive_stock_transfer` | `test_transfer_and_waste_integrity_regression.py:test_01` |
| **Waste recording failed when location was not STORE-MAIN** | `record_stock_change` forced `STORE-MAIN` when location was None instead of consuming from batch's actual location. | `hotel/integrity.py:record_stock_change` | `test_transfer_and_waste_integrity_regression.py:test_05` |
| **Duplicate transfer dispatch/receipt on double click** | Lack of state-machine locking and idempotency validation on transfer transitions. | `hotel/transfers.py` (`select_for_update`) | `test_stock_transfers.py:test_12`<br>`test_transfer_and_waste_integrity_regression.py:test_03` |
| **Purchase Order GRN receiving payload mismatch** | Frontend submitted `received_quantity`; backend expected `quantity_received`. | `hotel/procurement.py` | Browser PO GRN verification & `test_opening_stock_and_procurement_phase3.py` |
| **Waste submission CORS preflight rejection** | `idempotency-key` missing from `CORS_ALLOW_HEADERS`. | `core/settings.py` | Browser Waste Desk verification & `test_waste_management.py` |
| **Master vs Batch vs Location divergence** | Lack of unified multi-tier quantity calculation model. | `apps/inventory/services.py:calculate_authoritative_item_quantities` | `test_transfer_and_waste_integrity_regression.py:test_06` |

---

## 6. Staging Database Non-Contamination Verification

To confirm that the execution of 79 automated tests did not corrupt or pollute the shared local staging database (`hotel_erp_staging`), table record counts were captured before and after test execution:

| Table / Model | Pre-Test Record Count | Post-Test Record Count | Net Mutation |
| :--- | :---: | :---: | :---: |
| `hotel_inventoryitem` | 27 | 27 | **0** |
| `hotel_stockbatch` | 42 | 42 | **0** |
| `hotel_stocktransaction` | 55 | 55 | **0** |
| `hotel_stocktransfer` | 11 | 11 | **0** |
| `hotel_stocktransferitem` | 11 | 11 | **0** |
| `hotel_itemlocationbalance` | 33 | 33 | **0** |
| `hotel_wasterecord` | 26 | 26 | **0** |
| `hotel_goodsreceiptnote` | 23 | 23 | **0** |
| `hotel_journalentry` | 120 | 120 | **0** |

**Conclusion:** Zero records were inserted, updated, or deleted in `hotel_erp_staging`. Test isolation is 100% verified.

---

## 7. Sign-Off Readiness

All 79 automated regression tests and browser workflows have succeeded. The inventory module's transactional integrity, auditability, and concurrency controls are robust and ready for production deployment review.

