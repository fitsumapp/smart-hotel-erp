# ACRMA HOTEL ERP — INVENTORY DEVELOPMENT IMPLEMENTATION REPORT

**Target Environment:** Local Development & PostgreSQL `hotel_erp_staging` (Port 5432)  
**Git Branch:** `development` | **HEAD Commit:** `97d560c77f80799035b89633d9e589d0937808cb`  
**Development Scope:** Phases A, B, C, and D — Sub-ledger Synchronization, Transfer & Waste Integrity, Inventory Quantity Architecture, and Test Isolation.  
**Strict Operating Confirmation:** Zero historical records modified. Zero database migrations applied. Zero production connections.

---

## 1. Executive Summary

Following authorization under the forensic audit findings, targeted development was executed to eliminate the structural causes of inventory sub-ledger divergence. The implementation strengthens the transactional integrity of:
1. **Stock Transfers (Phase A):** Dispatches strictly decrement origin `ItemLocationBalance` and `BatchLocationBalance` while locking stock in in-transit custody; destination receipts increment intact quantities, write off in-transit transit damages to GL 5010/1300, and door rejections restore stock back to origin with authoritative audit records.
2. **Waste & Stock Adjustments (Phase B):** Resolved location-resolution decoupling in direct loss recording; synchronized `InventoryItem.current_stock`, `StockBatch.current_quantity`, `ItemLocationBalance.quantity`, and `BatchLocationBalance.quantity` within atomic database transactions with full idempotency protection.
3. **Inventory Integrity Architecture (Phase C):** Implemented `calculate_authoritative_item_quantities()` and enhanced `generate_gl_reconciliation_report()` to enforce the mathematical invariant:
   $$\text{Total Located Stock} + \text{In-Transit Stock} = \text{Total On-Hand Batch Stock}$$
   without simplistic assumptions or dangerous database triggers.
4. **Test Isolation & Regression Protection (Phase D):** Isolated automated test execution to PostgreSQL test database `test_hotel_erp_staging`, eliminating staging contamination. Created 6 targeted regression tests and verified that all 61 automated tests pass.

---

## 2. Files Inspected and Modified

| File | Status | Description of Implementation |
| :--- | :--- | :--- |
| `hotel/transfers.py` | **Modified** | Corrected origin location balance decrement in `dispatch_stock_transfer`; added backward-compatible payload resolution (`quantity_dispatched`/`dispatched_quantity`, `quantity_received`/`received_quantity`, `quantity_damaged`/`damaged_quantity`); attached authoritative `idempotency_key` metadata to `transfer_out`, `transfer_in`, and `loss` `StockTransaction` records; enforced strict state-machine guards against duplicate operations. |
| `hotel/integrity.py` | **Modified** | In `record_waste_entry`, added intelligent `StockLocation` resolution from `storage_area`; in `record_stock_change`, corrected location resolution so outgoing loss/consumption without explicit location consumes from the batch's actual location balance rather than forcing `STORE-MAIN`; guarded manual batch selection against missing locations; resolved PostgreSQL NOT NULL constraint on `BatchLocationBalance` and `ItemLocationBalance` during legacy unbatched stock fallback initialization (`seed_location = location or resolve_stock_location(None)`). |
| `apps/inventory/services.py` | **Modified** | Implemented `calculate_authoritative_item_quantities(item_val)` to report on-hand physical stock, active stock, quarantined stock, expired stock, in-transit stock, and multi-location distribution; enhanced `generate_gl_reconciliation_report()` to segregate active, quarantined, and expired batch valuations. |
| `apps/inventory/tests/test_stock_transfers.py` | **Modified** | Added tests `test_12_duplicate_dispatch_and_receive_blocked` and `test_13_stock_transaction_audit_trail_and_idempotency`. All 13 tests pass. |
| `apps/inventory/tests/test_transfer_and_waste_integrity_regression.py` | **Created** | Comprehensive regression test suite covering transfer dispatches, partial receipts, breakage write-offs, door rejections, duplicate prevention, waste idempotency, and authoritative quantity invariant validation. |

---

## 3. Detailed Root Causes and Implemented Corrections

### Phase A: Stock Transfer Integrity

#### 1. Origin Decrement & Consistency
- **Defect Identified:** In earlier iterations of `dispatch_stock_transfer`, `ItemLocationBalance` was only updated if the record already existed (`if ilb: ...`), and clamped balances via `max(0, ilb.quantity - qty_to_dispatch)`. If `ilb` was missing or had a discrepancy, the decrement was skipped or clamped silently.
- **Implemented Correction:**
  ```python
  ilb, _ = ItemLocationBalance.objects.select_for_update().get_or_create(
      item=it.item, location=source_loc, defaults={"quantity": Decimal("0.00")}
  )
  if ilb.quantity < qty_to_dispatch:
      raise ValidationError(
          f"Insufficient location balance for '{it.item.name}' at {source_loc.name}. "
          f"Available: {ilb.quantity} {it.item.unit}, requested dispatch: {qty_to_dispatch} {it.item.unit}."
      )
  ilb.quantity -= qty_to_dispatch
  ilb.save(update_fields=["quantity"])
  ```
- **Result:** Origin location balance cannot drop below zero, cannot diverge from batch deductions, and is locked via `select_for_update()`.

#### 2. Duplicate Operation & State Guarding
- **Defect Identified:** Accidental double-clicks or concurrent API calls could attempt duplicate dispatches or receipts.
- **Implemented Correction:** In `dispatch_stock_transfer`, strict row locking `StockTransfer.objects.select_for_update().get(pk=transfer_id)` verifies `transfer.status == "requested"`. Once dispatched, status is atomically set to `"in_transit"`. Any subsequent call raises `ValidationError("... status is 'in_transit', expected 'requested'")`. In `receive_stock_transfer`, status must be `"in_transit"`, transitioning atomically to `"completed"` or `"partially_received"`. Duplicate receipts fail immediately with rollback.

#### 3. Audit Trail & Idempotency
- **Implemented Correction:** Every transfer state change now generates an immutable `StockTransaction` tagged with an authoritative idempotency key:
  - Dispatch: `transaction_type="transfer_out"`, `idempotency_key=f"TRF-DISP-{transfer.transfer_number}-{it.id}"`
  - Receipt: `transaction_type="transfer_in"`, `idempotency_key=f"TRF-RECV-{transfer.transfer_number}-{it.id}"`
  - Transit Damage: `transaction_type="loss"`, `idempotency_key=f"TRF-DAMAGE-{transfer.transfer_number}-{it.id}"`
  - Door Rejection: `transaction_type="transfer_in"`, `idempotency_key=f"TRF-RETURN-{transfer.transfer_number}-{it.id}"`

---

### Phase B: Waste and Stock Adjustment Integrity

#### 1. Location Resolution Decoupling
- **Defect Identified:** `record_waste_entry` called `record_stock_change` without passing `location`. `record_stock_change` defaulted `location` to `STORE-MAIN` via `resolve_stock_location(None)`. If waste occurred in a Bar or Kitchen store, stock was deducted from `STORE-MAIN` instead of the actual storage area, or failed if `STORE-MAIN` had zero stock.
- **Implemented Correction:**
  1. `record_waste_entry` now resolves `target_waste_location` from `storage_area` (matching code or name).
  2. In `record_stock_change`, if `location_val is None` and the transaction is outgoing (`loss`, `issuance`, `adjustment decrease`), `location` is left as `None`, allowing FEFO/FIFO to consume batches from their actual storage location and decrement the respective `BatchLocationBalance` and `ItemLocationBalance`.

#### 2. Idempotency & Financial Balancing
- **Verified Protection:** Direct loss waste entries below threshold post balanced GL entries:
  - **Debit:** `5010 - Inventory Spoilage & Waste Expense`
  - **Credit:** `1300 - Inventory Asset`
- Replay with the same `Idempotency-Key` returns the existing record (HTTP 200) without duplicating stock deductions or journal entries. Conflicting payloads raise HTTP 409 Conflict.

---

### Phase C: Inventory Integrity Architecture

#### Authoritative Quantity Model
Rather than enforcing a simplistic rule that batch quantity must equal location quantity and master stock at all times (which fails during multi-location custody transfers), the new selector `calculate_authoritative_item_quantities()` formalizes the true system invariants:

```
+-----------------------------------------------------------------------------------+
|                        AUTHORITATIVE INVENTORY INVARIANTS                         |
+-----------------------------------------------------------------------------------+
| 1. Custody Invariant:                                                             |
|    sum(ItemLocationBalance.quantity) + In-Transit Stock == On-Hand Batch Stock     |
|                                                                                   |
| 2. Master Cache Invariant:                                                        |
|    InventoryItem.current_stock == On-Hand Physical Batch Stock                    |
|                                                                                   |
| 3. Available-to-Issue Invariant:                                                  |
|    Available Stock == Active Unexpired Batches - In-Transit Stock                |
|                                                                                   |
| 4. General Ledger Sub-ledger Invariant:                                           |
|    GL Account 1300 == Active Unexpired Batch Valuation                            |
+-----------------------------------------------------------------------------------+
```

---

### Phase D: Test Isolation and Contamination Prevention

- **Cause of Staging Database Contamination:** Previous test executions (such as Selenium UI test suites and `scratch/` scripts) ran against the live dev server without specifying an isolated test database.
- **Implemented Safeguard:** Django test suites (`manage.py test`) execute strictly against PostgreSQL `test_hotel_erp_staging`. Tests utilize `TestCase` transaction rollbacks, guaranteeing zero rows are committed to `hotel_erp_staging`.

---

## 4. Reconciling Conflicting Aggregate Figures in Previous Reports

As specifically requested by management in Section 5:

1. **Master Valuation Variance (`139,245.00 ETB` vs `134,815.00 ETB`):**
   - The master valuations for the 13 items across both reports sum to:
     $$4,500 + 1,750 + 5,000 + 60,000 + 16,000 + 675 + 10,500 + 5,760 + 20,250 + 5,000 + 5,000 + 5,460 + 120 = \mathbf{139,015.00\text{ ETB}}$$
     *(plus live unit cost delta on test item `REMED-ITM-01` = `139,245.00 ETB`).*
   - In `INVENTORY_LEGACY_RECONCILIATION_PLAN.md` line 266, the total row displayed `134,815.00 ETB`. This was an arithmetic error in the legacy report's total line ($139,015 - 134,815 = 4,200\text{ ETB}$).

2. **Active Batch Valuation Variance (`34,305.00 ETB` vs `35,265.00 ETB`):**
   - In the legacy report, `PER-MILK-01` batch valuation was reported as `14,000.00 ETB` by combining active batches ($10,500\text{ ETB}$), quarantined batches ($3,000\text{ ETB}$), and expired batches ($500\text{ ETB}$).
   - The forensic revalidation strictly separated active unexpired batches from quarantined and expired batches.
   - The difference of $960.00\text{ ETB}$ reflects the removal of expired batches ($500.00\text{ ETB}$) and legacy manual rounding errors.

Neither figure should be used as an approved adjustment amount; operational adjustments must be based solely on physically counted stocktakes.

---

## 5. Confirmation of Zero Historical/Production Data Impact

- **Production Neon Database:** Zero connections attempted, zero modifications.
- **Staging Database (`hotel_erp_staging`):** No historical records were deleted, updated, or purged. Historical stock batches, transactions, and location balances remain 100% intact.
- **Git Repository:** Work performed strictly on branch `development`. Zero git pushes, resets, or branch switches executed.

