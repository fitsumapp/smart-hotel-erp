# ACRMA HOTEL ERP — INVENTORY DATA INTEGRITY & FORENSIC RECONCILIATION AUDIT

**Target Environment:** Local PostgreSQL `hotel_erp_staging` (Port 5432)  
**Git Branch:** `development` | **HEAD Commit:** `97d560c77f80799035b89633d9e589d0937808cb`  
**Audit Scope:** Deep read-only forensic investigation of the 13 discrepant inventory items, transaction reconstruction, test contamination isolation, and inventory architecture review.  
**Strict Operating Status:** Investigation & Design Only — Strictly Non-Mutating (Zero DB Writes, Zero Code Changes).

---

## 1. Executive Summary

This forensic investigation was commissioned to perform an independent, strictly read-only audit of the 13 inventory items identified with structural discrepancies in [INVENTORY_LEGACY_RECONCILIATION_PLAN.md](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/INVENTORY_LEGACY_RECONCILIATION_PLAN.md).

### Key Findings Summary:
1. **Root Cause Reality:** None of the 13 discrepancies stem from active production guest transactions or day-to-day hotel operations. Instead, all 13 items fall squarely into four categories of system evolution and test data contamination:
   - **Automated Test Run Artifacts (5 items):** Selenium E2E tests and remediation test runners injected mock items (`REMED-ITM-*`) and phantom test batches (`BAT-QUAR-TEST-*` on `PER-MILK-01`) directly into the shared staging database without transaction rollback isolation.
   - **Pre-Batch / Migration Seed Data (2 items):** Early development fixtures created master item records (`BEEF-001`, `POT-001`) before batch tracking and multi-location balances were made mandatory in the schema.
   - **Synthetic Audit Scenarios (2 items):** Migrations `0043` and `0048` intentionally seeded partial batches and mismatched stock balances for `ITM-DAIRY-MILK` and `ITM-MEAT-BEEF` to test the Near-Expiry and Audit Alert engines.
   - **Decoupled Workflow Updates (4 items):** UI and automated test interactions for transfer damages (`CORD-LIME-01`, `BEV-JUICE-01`), minibar floor allocations (`MB-SODA-01`), and browser stocktake tests (`STK-BROWSER-01`, `STK-BROWSER-02`) updated either `StockBatch`, `ItemLocationBalance`, or `InventoryItem` without atomic synchronization across all three tiers.

2. **Sub-ledger vs General Ledger Reconciliation:**
   - **Total Master Stock Valuation (all 27 items):** `318,090.00 ETB`
   - **Total Active Batch Valuation:** `215,980.00 ETB` (plus `500.00 ETB` expired)
   - **General Ledger Account 1300 (Inventory Asset):** `138,960.00 ETB`
   - **Bookkeeping Discrepancy:** The `77,020.00 ETB` variance between GL 1300 and Active Batch Valuation is completely explained by un-journalized legacy seed batches (`50,000.00 ETB` on `SEC-BEEF-01`, `11,220.00 ETB` on audit items `ITM-*`, `3,000.00 ETB` on legacy milk batches, and `12,800.00 ETB` on untracked legacy beverage opening balances).
   - **Zero True Cash/Asset Loss:** There is no missing physical cash or active guest liability. The discrepancy is an artifact of staging test data and unposted opening balances.

3. **Critical Correction to Prior Financial Remediation:**
   - The earlier draft plan proposed debiting GL Account `5100` (erroneously labelled "Inventory Write-down / Shrinkage Expense") or `5150`.
   - Forensic audit of the Chart of Accounts revealed that **Account `5100` is Salary Expense** (which would corrupt hotel payroll reporting), and **Account `5150` does not exist**.
   - No automatic Journal Vouchers may be posted until physical inventory counts and executive sign-offs occur.

---

## 2. Revalidated 13-Item Forensic Dataset

Every affected record was independently recalculated directly from local PostgreSQL `hotel_erp_staging`.

### Exact Valuation Basis:
- **Master Stock Valuation:** `InventoryItem.current_stock` $\times$ `InventoryItem.unit_cost`.
- **Active Batch Valuation:** $\sum (\text{StockBatch.current\_quantity} \times \text{StockBatch.unit\_cost})$ for all batches where `status = 'active'`.
- **Quarantined Batch Valuation:** $\sum (\text{StockBatch.current\_quantity} \times \text{StockBatch.unit\_cost})$ for `status = 'quarantined'`.
- **Expired Batch Valuation:** $\sum (\text{StockBatch.current\_quantity} \times \text{StockBatch.unit\_cost})$ for `status = 'expired'`.
- **Location Stock Valuation:** $\sum (\text{ItemLocationBalance.quantity} \times \text{InventoryItem.unit\_cost})$ across all active locations.

### Master vs Batch vs Location Summary Table

| Item Code | Item Name | Unit | Unit Cost (ETB) | Master Stock | Master Val (ETB) | Active Batch Qty | Active Batch Val (ETB) | Expired Qty | Location Qty | Location Val (ETB) | Variance (Master vs Batch) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BEV-JUICE-01` | Mango Juice 1L | bottle | 60.00 | 91.00 | 5,460.00 | 91.00 | 5,460.00 | 0.00 | 100.00 | 6,000.00 | 0.00 (Loc +9) |
| `MB-SODA-01` | Artisan Sparkling Soda | bottle | 2.50 | 48.00 | 120.00 | 48.00 | 120.00 | 0.00 | 68.00 | 170.00 | 0.00 (Loc +20) |
| `CORD-LIME-01` | Fresh Lime Cordial | bottle | 5.00 | 135.00 | 675.00 | 121.00 | 605.00 | 0.00 | 135.00 | 675.00 | +70.00 (Batch -14) |
| `PER-MILK-01` | Fresh Whole Milk 1L | L | 60.00 | 175.00 | 10,500.00 | 235.00* | 13,500.00 | 10.00 | 175.00 | 10,500.00 | -3,000.00 (Phantom Batch) |
| `BEEF-001` | Prime Beef Tenderloin | kg | 450.00 | 10.00 | 4,500.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | +4,500.00 (Unbatched) |
| `POT-001` | Russet Potatoes | kg | 35.00 | 50.00 | 1,750.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | +1,750.00 (Unbatched) |
| `STK-BROWSER-01`| Staging Basmati Rice 25kg| bag | 1,200.00 | 50.00 | 60,000.00 | 0.00 | 0.00 | 0.00 | 50.00 | 60,000.00 | +60,000.00 (Missing Batch) |
| `STK-BROWSER-02`| Staging Olive Oil 5L | can | 800.00 | 20.00 | 16,000.00 | 0.00 | 0.00 | 0.00 | 20.00 | 16,000.00 | +16,000.00 (Missing Batch) |
| `ITM-DAIRY-MILK`| Pasteurized Milk 1L | L | 48.00 | 120.00 | 5,760.00 | 65.00 | 3,120.00 | 0.00 | 120.00 | 5,760.00 | +2,640.00 (Partial Batch) |
| `ITM-MEAT-BEEF` | Prime Beef Tenderloin | kg | 450.00 | 45.00 | 20,250.00 | 18.00 | 8,100.00 | 0.00 | 45.00 | 20,250.00 | +12,150.00 (Partial Batch) |
| `REMED-ITM-01` | Test Item 01 | pcs | 100.00 | 50.00 | 5,000.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | +5,000.00 (Test Artifact) |
| `REMED-ITM-..106`| Test Item 01 | pcs | 100.00 | 50.00 | 5,000.00 | 15.00 | 1,500.00 | 0.00 | 0.00 | 0.00 | +3,500.00 (Test Artifact) |
| `REMED-ITM-..629`| Test Item 01 | pcs | 100.00 | 50.00 | 5,000.00 | 25.00 | 2,500.00 | 0.00 | 0.00 | 0.00 | +2,500.00 (Test Artifact) |
| **SUBTOTAL (13 Items)** | | | | | **139,245.00** | | **34,305.00** | **500.00** | | **118,685.00** | **+104,940.00** |

*\*Forensic Note on `PER-MILK-01`: In the database, the 5 operational Selenium test batches (`BAT-PH1-*`) equal exactly 175.0 L @ 60 ETB = 10,500.00 ETB, matching Master Stock (175.0 L) and Location Stock (175.0 L) perfectly. The excess 60.0 L is comprised of 3 legacy quarantine test batches (`BAT-QUAR-TEST-001`, `1429`, `1556`) that were incorrectly flagged as `status='active'` with `is_legacy=True`.*

---

## 3. Reconstructed Chronological Movement Timeline & Root-Cause Analysis

### Item 1: `BEV-JUICE-01` (Mango Juice 1L)
- **Current State:** Master Stock = 91.0 bottle | Active Batches = 91.0 bottle | Locations = 100.0 bottle (`STORE-MAIN`: 90.0, `BAR-MAIN`: 10.0).
- **Movement Timeline:**
  - *2026-11-01:* Stock Transfer `#TRF-20261101-81987E` dispatched 10.0 bottles from `STORE-MAIN` to `BAR-MAIN`. Receiving verified 9.0 received, 1.0 damaged. Waste Record #2 created for 1.0 bottle transit damage (Auto-JV #8 posted Dr 5010 60.00 / Cr 1300 60.00).
  - *2026-11-04 10:28:* Stock adjustment logged +4.0 bottles on `BAR-MAIN`, creating batch `BAT-BEV-JUICE-01-20261104-5BF9FF`.
  - *2026-11-05 18:23:* Stocktake Session `#STK-20261105-466EE4` approved, adjusting `BAR-MAIN` theoretical 22.0 down to counted 10.0 (variance -12.0 bottles logged as decrease transaction on `BATCH-JUICE-001`).
- **Discrepancy Mechanism:** `ItemLocationBalance` for `STORE-MAIN` was never decremented by 10.0 upon dispatch, remaining stuck at 90.0 instead of 80.0. When `BAR-MAIN` was adjusted to 10.0, the location total became 90 + 10 = 100.0.
- **Root Cause Classification:** **Confirmed.** Transfer dispatch service in earlier commit failed to decrement the origin location's `ItemLocationBalance` while decrementing the batch and item balances.

### Item 2: `MB-SODA-01` (Artisan Sparkling Soda)
- **Current State:** Master Stock = 48.0 bottle | Active Batches = 48.0 bottle | Locations = 68.0 bottle (`MINIBAR-PANTRY`: 48.0, `MB-FL1`: 20.0).
- **Movement Timeline:**
  - *2026-11-03 13:10 – 13:42:* 11 consecutive Minibar Issuances of 2.0 bottles each to Room 101. Transactions logged against `MINIBAR-PANTRY` and batch `BATCH-MB-SODA-01`. Each created Auto-JV (Dr 5000 5.00 / Cr 1300 5.00).
- **Discrepancy Mechanism:** Sub-location `MB-FL1` (Floor 1 Pantry) holds 20.0 bottles in `ItemLocationBalance`, but has 0 batch records attached (`BatchLocationBalance` count = 0).
- **Root Cause Classification:** **Confirmed.** An unbatched manual location seed or uncommitted floor stock replenishment initialized `MB-FL1` without creating a corresponding batch allocation or deducting from `MINIBAR-PANTRY`.

### Item 3: `CORD-LIME-01` (Fresh Lime Cordial)
- **Current State:** Master Stock = 135.0 bottle | Active Batches = 121.0 bottle | Locations = 135.0 bottle (`WH-MAIN`: 90.0, `BAR-MAIN`: 45.0).
- **Movement Timeline:**
  - *2026-11-03:* 8 stock transfers (TRF 3, 4, 5, 6, 7, 8, 9, 11) dispatched 10.0 bottles each from `WH-MAIN` to `BAR-MAIN` with 2.0 bottles damaged per transfer.
  - *2026-11-03:* 8 Waste Records (#3 through #10) recorded for transit damage (2.0 bottles each = 16.0 bottles total). Auto-JVs posted Dr 5010 10.00 / Cr 1300 10.00 each.
  - *2026-11-04 10:28:* Stock adjustment created batch `BAT-CORD-LIME-01-20261104-EFDE72` with 41.0 bottles.
  - *2026-11-11 08:55:* Approved waste loss deducted 2.0 bottles twice from `BATCH-LIME-001`.
- **Discrepancy Mechanism:** Waste recording service decremented `StockBatch.current_quantity` (reducing `BATCH-LIME-001` down to 80.0), but did not deduct from `InventoryItem.current_stock` or `ItemLocationBalance` for `WH-MAIN`.
- **Root Cause Classification:** **Confirmed.** Asymmetric deduction in legacy waste approval service where batch stock was decremented without firing item-level or location-level deduction.

### Item 4: `PER-MILK-01` (Fresh Whole Milk 1L)
- **Current State:** Master Stock = 175.0 L | Active Batches = 235.0 L | Expired Batches = 10.0 L | Locations = 175.0 L (`STORE-MAIN`: 175.0).
- **Movement Timeline:**
  - *2026-11-03 15:48 – 15:59:* Selenium E2E automated purchase test executed 5 purchases of 35.0 L each (`INV-PH1-SELENIUM`). Created batches `BAT-PH1-1793720907`, `1122`, `1309`, `1460`, `1588`. Total = 175.0 L @ 60.00 ETB = 10,500.00 ETB. Generated JVs #61 through #65 (Dr 1300 2,100 / Cr 1000 2,100).
- **Discrepancy Mechanism:** Prior to the Selenium run, legacy test scripts created 3 quarantine test batches: `BAT-QUAR-TEST-001` (20 L), `BAT-QUAR-TEST-1793721429` (20 L), and `BAT-QUAR-TEST-1793721556` (20 L). While marked `is_legacy=True`, their database status column was left as `'active'`.
- **Root Cause Classification:** **Confirmed.** Automated test script fixture failure. The 3 batches (60.0 L) are phantom test records that were never cleaned up and were misclassified as active instead of quarantined.

### Items 5 & 6: `BEEF-001` (Tenderloin) & `POT-001` (Potatoes)
- **Current State:**
  - `BEEF-001`: Master Stock = 10.0 kg | Batches = 0 | Locations = 0.
  - `POT-001`: Master Stock = 50.0 kg | Batches = 0 | Locations = 0.
- **Movement Timeline:** No transactions, GRNs, transfers, or journal entries exist in the entire database.
- **Discrepancy Mechanism:** Records exist strictly on `InventoryItem`.
- **Root Cause Classification:** **Confirmed.** Legacy pre-batch seed fixtures created during initial MVP prototyping before multi-location balances and stock batches were enforced.

### Items 7 & 8: `STK-BROWSER-01` (Rice 25kg) & `STK-BROWSER-02` (Olive Oil 5L)
- **Current State:**
  - `STK-BROWSER-01`: Master Stock = 50.0 bag | Location `STORE-MAIN` = 50.0 bag | Batches = 0.
  - `STK-BROWSER-02`: Master Stock = 20.0 can | Location `STORE-MAIN` = 20.0 can | Batches = 0.
- **Movement Timeline:** Created during Phase 0 browser test verification for Stocktake UI.
- **Discrepancy Mechanism:** Items and location balances were seeded directly by browser automation test fixtures without invoking the GRN or opening stock service, bypassing batch generation.
- **Root Cause Classification:** **Confirmed.** Browser QA test setup script omitted the batch creation step.

### Items 9 & 10: `ITM-DAIRY-MILK` & `ITM-MEAT-BEEF`
- **Current State:**
  - `ITM-DAIRY-MILK`: Master Stock = 120.0 L | Location `WH-AUDIT-01` = 120.0 L | Active Batches = 65.0 L (`BATCH-EXP-STAGE-01`: 25.0, `BATCH-NEAR-STAGE-07`: 40.0). Deficit = -55.0 L.
  - `ITM-MEAT-BEEF`: Master Stock = 45.0 kg | Location `WH-AUDIT-01` = 45.0 kg | Active Batches = 18.0 kg (`BATCH-UNK-STAGE-99`: 18.0). Deficit = -27.0 kg.
- **Movement Timeline:** Seeded in migration `0043` / `0048` specifically to validate the expiry alert dashboard.
- **Discrepancy Mechanism:** The migration authors intentionally seeded partial batches to test how the system reports "unbatched" stock and near-expiry warnings in warehouse `WH-AUDIT-01`.
- **Root Cause Classification:** **Confirmed.** Deliberate synthetic test fixture designed for alert testing.

### Items 11, 12, & 13: `REMED-ITM-01`, `REMED-ITM-1793900106`, `REMED-ITM-1793900629`
- **Current State:**
  - `REMED-ITM-01`: Master Stock = 50.0 pcs | Locations = 0 | Batches = 0.
  - `REMED-ITM-1793900106`: Master Stock = 50.0 pcs | Locations = 0 | Batches = 15.0 pcs (`REMED-BATCH-DISMISS-1793900106`).
  - `REMED-ITM-1793900629`: Master Stock = 50.0 pcs | Locations = 0 | Batches = 25.0 pcs (`REMED-BATCH-DISMISS-1793900629`: 15.0, `REMED-BATCH-THRESH-25D-1793900629`: 10.0).
- **Movement Timeline:** Injected into `hotel_erp_staging` on 2026-11-05 during remediation test suite execution for batch threshold alerts.
- **Discrepancy Mechanism:** Test fixtures injected items directly into the live staging database without tearing them down upon completion.
- **Root Cause Classification:** **Confirmed.** Automated test suite contamination.

---

## 4. Test-Data Contamination Investigation & Isolation Strategy

### Contamination Classification:
```
+-----------------------------------------------------------------------------------+
|                        STAGING DATABASE CONTAMINATION MATRIX                      |
+--------------------------+------------------------------------+-------------------+
| Contamination Source     | Affected Item Codes                | Volume / Impact   |
+--------------------------+------------------------------------+-------------------+
| Automated Test Runner    | REMED-ITM-01, REMED-ITM-1793900106,| 15,000.00 ETB     |
| (Pytest / Unittest)      | REMED-ITM-1793900629               | (Master Stock)    |
+--------------------------+------------------------------------+-------------------+
| Selenium UI Test Scripts | PER-MILK-01 (Quarantine Batches)   | 3,000.00 ETB      |
|                          |                                    | (Phantom Batches) |
+--------------------------+------------------------------------+-------------------+
| Browser QA Manual Tests  | STK-BROWSER-01, STK-BROWSER-02     | 76,000.00 ETB     |
|                          |                                    | (Unbatched)       |
+--------------------------+------------------------------------+-------------------+
| Migration Audit Fixtures | ITM-DAIRY-MILK, ITM-MEAT-BEEF      | 14,790.00 ETB     |
|                          |                                    | (Partial Batches) |
+--------------------------+------------------------------------+-------------------+
| Early MVP Fixtures       | BEEF-001, POT-001                  | 6,250.00 ETB      |
|                          |                                    | (Unbatched)       |
+--------------------------+------------------------------------+-------------------+
```

### Why Test Records Polluted the Staging Database:
1. **Lack of Isolated Test Database Settings:** Automated test scripts were executed directly against `DJANGO_SETTINGS_MODULE=core.settings` without `--settings=core.test_settings` pointing to an isolated in-memory or ephemeral PostgreSQL database.
2. **Missing Transaction Rollback Fixtures:** Test cases used `django.test.TestCase` alternatives or raw script executions that committed transactions rather than rolling them back on teardown.
3. **Hardcoded Staging Connection Strings:** Test runner scripts in `scratch/` and test suites connected directly to `hotel_erp_staging`.

### Recommended Test Isolation Architecture:
1. **Strict Test Database Segregation:** Enforce in `manage.py` and CI/CD that `pytest` or `test` commands automatically provision an isolated database `hotel_erp_test` and refuse to run against `hotel_erp_staging` or `hotel_erp_prod`.
2. **Atomic Test Fixtures:** Wrap all integration and E2E browser tests in `TestCase` transaction rollbacks or provide deterministic teardown hooks (`post_test_cleanup()`).
3. **Prefix Isolation Rule:** All automated test records MUST use designated prefixes (`TEST-RUN-*`) and be automatically purged by a nightly scheduled maintenance job if found in staging.

---

## 5. Inventory Architecture Review & System Invariants

### Current System Design Flaw:
The inventory system currently maintains stock quantities in three distinct database tables:
1. `InventoryItem.current_stock` (Master Denormalized Total)
2. `ItemLocationBalance.quantity` (Per-Location Denormalized Total)
3. `StockBatch.current_quantity` & `BatchLocationBalance.quantity` (Per-Batch Sub-ledger)

Because mutations (transfers, waste records, adjustments, PO receipts) did not always wrap updates to all three tables inside atomic database transactions (`transaction.atomic()`), operations frequently updated one or two tables while leaving the third unchanged.

### Authoritative Source of Truth Hierarchy:

```
+-----------------------------------------------------------------------------------+
|                            AUTHORITATIVE HIERARCHY                                |
+-------------------------------+---------------------------------------------------+
| Operational Quantity          | Authoritative Source of Truth                     |
+-------------------------------+---------------------------------------------------+
| Physical On-Hand Stock        | StockBatch sub-ledger + BatchLocationBalance      |
| Available-to-Issue Stock      | Active StockBatches (status='active', not expired)|
| Balance Sheet Asset (GL 1300) | General Ledger Journal Entries (posted debits)    |
| Cost of Goods Sold (GL 5000)  | StockTransaction issuance cost $\times$ quantity  |
| Denormalized UI Displays      | InventoryItem.current_stock (DERIVED CACHE ONLY)  |
+-------------------------------+---------------------------------------------------+
```

> [!IMPORTANT]
> `InventoryItem.current_stock` and `ItemLocationBalance.quantity` must be treated as **read-only derived caches**. They must never be updated independently without updating or being driven directly by `StockBatch` and `StockTransaction` sub-ledgers.

### Mandatory Reconciliation Invariants:
To prevent divergence, the ERP backend must enforce the following four invariants via model save validations and database triggers:

1. **Item-Batch Invariant:**
   $$\text{InventoryItem.current\_stock} = \sum_{b \in \text{batches}} \text{StockBatch.current\_quantity}$$
2. **Location-Batch Invariant:**
   $$\text{ItemLocationBalance.quantity} = \sum_{b \in \text{batches}} \text{BatchLocationBalance.quantity} \quad (\forall \text{ location})$$
3. **Transaction-Batch Invariant:**
   $$\text{StockBatch.current\_quantity} = \text{initial\_quantity} + \sum \text{StockTransactions(in)} - \sum \text{StockTransactions(out)}$$
4. **General Ledger-Inventory Invariant:**
   $$\text{Account.objects.get(code='1300').balance} = \sum_{b \in \text{active batches}} (\text{current\_quantity} \times \text{unit\_cost})$$

---

## 6. Unresolved Risks and Decisions Required from Hotel Management

Before any reconciliation or remediation can occur, the following executive decisions must be made:

1. **Purge vs Archive of Test Items:**
   - *Decision:* Shall test artifacts (`REMED-ITM-*`, `STK-BROWSER-*`) be hard-deleted from `hotel_erp_staging` (safe because no guest transactions are linked), or flagged with `is_archived=True` to preserve audit logs?
   - *Recommendation:* Archive records with clear `test_artifact=True` metadata to prevent foreign key cascade issues.

2. **Legacy Pre-Batch Seed Items (`BEEF-001`, `POT-001`):**
   - *Decision:* Are these items physically present in the central kitchen?
   - *Action:* If physically present, perform a formal opening count and issue an Opening Stock Batch. If duplicates of operational items (`ITM-MEAT-BEEF`), zero them out and archive.

3. **Transit Damage Waste Ledger Sync (`CORD-LIME-01`, `BEV-JUICE-01`):**
   - *Decision:* Authorize the synchronization of `ItemLocationBalance` and `InventoryItem.current_stock` to align with the physically received and batch-deducted quantities.

