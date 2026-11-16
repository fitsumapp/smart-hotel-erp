# ACRMA HOTEL ERP — INVENTORY RECONCILIATION DECISION MATRIX

**Target Environment:** Local PostgreSQL `hotel_erp_staging` (Port 5432)  
**Git Branch:** `development` | **Audit Mode:** Read-Only Investigation & Governance Design  
**Related Documents:** [INVENTORY_DATA_INTEGRITY_AUDIT.md](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/INVENTORY_DATA_INTEGRITY_AUDIT.md) | [INVENTORY_ACCOUNTING_IMPACT_ANALYSIS.md](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/INVENTORY_ACCOUNTING_IMPACT_ANALYSIS.md)

---

## 1. Governance Principles & Strict "When NOT to Adjust" Criteria

Reconciliation must never be executed as an automated bulk database script. Every adjustment affects asset balances, departmental accountability, and statutory financial reporting.

### Mandatory Rules: When NOT to Adjust
> [!CAUTION]
> Under NO circumstances may an administrator, developer, or accountant perform an inventory adjustment if any of the following conditions exist:
> 1. **No Independent Physical Count:** Never adjust stock balances based solely on database variance queries without a verified, physically signed stocktake count sheet.
> 2. **In-Flight Transfers or Transactions:** Never adjust a location balance while transfers, requisitions, or purchase orders for that item are in `dispatched`, `in_transit`, or `pending_receipt` status.
> 3. **Open POS or Bar Shifts:** Never adjust Food & Beverage or Minibar balances during active operational service hours. Counts and adjustments must occur during strict inventory freeze windows (e.g., 02:00 – 05:00 AM).
> 4. **Uninvestigated Theft or High-Value Loss:** Never process an ordinary stocktake adjustment for unexplained shortages exceeding `5,000.00 ETB` or high-value beverage items. Such variances must trigger a security escalation and formal investigation report.
> 5. **Synthetic / Test Artifacts:** Never post general ledger adjustments (Journal Vouchers) for synthetic test items (`REMED-ITM-*`, `STK-BROWSER-*`, `WH-AUDIT-*`). These records must be isolated or archived in staging without financial postings.

---

## 2. Comprehensive 13-Item Reconciliation Decision Matrix

The table below outlines the forensic state, root-cause classification, physical count requirements, required sub-ledger actions, general ledger impact, required approval hierarchy, and execution risks for all 13 items.

| Item Code | Item Name | Current State (Master / Batch / Location) | Confirmed Root Cause | Classification | Recommended Action | Physical Count? | Batch Action | Location Action | GL Adjustment? | Approvals Required | Risk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BEV-JUICE-01` | Mango Juice 1L | Master: 91<br>Batches: 91<br>Loc: 100 | Transfer dispatch did not decrement `STORE-MAIN` location balance upon transit damage. | Operational (Beverage) | Synchronize `STORE-MAIN` location balance to 81.0 to match batch sub-ledger. | **Yes** (Main Store & Main Bar) | None (Batches already accurate at 91.0) | Decrement `STORE-MAIN` by 9.0 (from 90 to 81) | **None** (GL 1300 already credited 60 ETB via JV #8) | F&B Manager, Cost Controller | **Low** |
| `MB-SODA-01` | Artisan Sparkling Soda | Master: 48<br>Batches: 48<br>Loc: 68 | Sub-location `MB-FL1` seeded with 20 bottles without deducting pantry or creating batch balance. | Operational (Minibar) | Verify physical stock on Floor 1 pantry. If physical, link to batch; if phantom, zero out `MB-FL1`. | **Yes** (Floor 1 & Central Pantry) | Allocate batch if stock exists | Zero out `MB-FL1` (reduce by 20) if phantom | **None** (GL 1300 matches master/batch) | Front Office Mgr, Cost Controller | **Low** |
| `CORD-LIME-01` | Fresh Lime Cordial | Master: 135<br>Batches: 121<br>Loc: 135 | Transit damage waste deduction decremented batches but omitted item and location updates. | Operational (Beverage) | Synchronize Master Stock and `WH-MAIN` location balance down to active batch total (121.0). | **Yes** (Central Warehouse & Main Bar) | None (Batches reflect true 121.0) | Decrement `WH-MAIN` by 14.0 (from 90 to 76) | **None** (GL 1300 already credited for all damage) | Bar Manager, Financial Controller | **Medium** |
| `PER-MILK-01` | Fresh Whole Milk 1L | Master: 175<br>Batches: 235 (act) + 10 (exp)<br>Loc: 175 | 3 legacy quarantine test batches (60 L) left with status `'active'` instead of `'quarantined'`. | Test Artifact (on Operational Item) | Reclassify the 3 phantom batches (`BAT-QUAR-TEST-*`) from `active` to `quarantined` or archive. | **No** (Operational 175 L matches master & GL) | Update 3 test batches to `'quarantined'` | None (Location is already 175.0 L) | **None** (GL 1300 already matches 10,500 ETB exactly) | Inventory Controller | **Very Low** |
| `BEEF-001` | Prime Beef Tenderloin | Master: 10<br>Batches: 0<br>Loc: 0 | Early MVP seed fixture created prior to batch & location tracking; duplicate of operational beef. | Legacy Seed Data | Verify physical freezer stock. If duplicate of `SEC-BEEF-01`, set master stock to 0 and archive item. | **Yes** (Central Freezer verification) | None (Create opening batch only if real stock) | None | **None** (No historical JV exists) | Executive Chef, Financial Controller | **Low** |
| `POT-001` | Russet Potatoes | Master: 50<br>Batches: 0<br>Loc: 0 | Early MVP seed fixture created prior to batch & location tracking. | Legacy Seed Data | Verify dry vegetable store. If 50 kg physically present, issue formal Opening Stock Batch; else zero & archive. | **Yes** (Vegetable Store count) | Create opening batch if physically present | Create location balance if physically present | **Conditional** (Post Opening Stock JV if real stock) | Executive Chef, Cost Controller | **Low** |
| `STK-BROWSER-01` | Staging Basmati Rice 25kg | Master: 50<br>Batches: 0<br>Loc: 50 | Browser QA test created item and location balance directly without batch generation. | Test Artifact (Browser QA) | Archive item and purge synthetic `STORE-MAIN` location balance (50 bags). | **No** (Synthetic staging test item) | None | Remove `STORE-MAIN` 50 bag balance | **None** (Zero GL entries exist) | QA Lead, Inventory Controller | **Low** |
| `STK-BROWSER-02` | Staging Olive Oil 5L | Master: 20<br>Batches: 0<br>Loc: 20 | Browser QA test created item and location balance directly without batch generation. | Test Artifact (Browser QA) | Archive item and purge synthetic `STORE-MAIN` location balance (20 cans). | **No** (Synthetic staging test item) | None | Remove `STORE-MAIN` 20 can balance | **None** (Zero GL entries exist) | QA Lead, Inventory Controller | **Low** |
| `ITM-DAIRY-MILK` | Pasteurized Milk 1L | Master: 120<br>Batches: 65<br>Loc: 120 | Migration 0043/0048 seeded partial batches to test near-expiry alert engine in test warehouse `WH-AUDIT-01`. | Synthetic Audit Fixture | Retain as test fixture in staging or flag `is_test_fixture=True`. Exclude from production migrations. | **No** (Warehouse `WH-AUDIT-01` is synthetic) | None | None | **None** (Zero GL entries exist) | Lead Architect | **Low** |
| `ITM-MEAT-BEEF` | Prime Beef Tenderloin | Master: 45<br>Batches: 18<br>Loc: 45 | Migration 0043/0048 seeded partial batches to test unknown batch alerts in test warehouse `WH-AUDIT-01`. | Synthetic Audit Fixture | Retain as test fixture in staging or flag `is_test_fixture=True`. Exclude from production migrations. | **No** (Warehouse `WH-AUDIT-01` is synthetic) | None | None | **None** (Zero GL entries exist) | Lead Architect | **Low** |
| `REMED-ITM-01` | Test Item 01 | Master: 50<br>Batches: 0<br>Loc: 0 | Automated test run on 2026-11-05 injected unbatched test item without teardown. | Test Artifact (Automated Test) | Delete or archive test item record. | **No** (Automated test artifact) | None | None | **None** (Zero GL entries exist) | QA Lead | **Very Low** |
| `REMED-ITM-..106` | Test Item 01 | Master: 50<br>Batches: 15<br>Loc: 0 | Automated test run on 2026-11-05 injected timestamped test item and batch. | Test Artifact (Automated Test) | Delete or archive test item and batch `REMED-BATCH-DISMISS-1793900106`. | **No** (Automated test artifact) | Delete batch | None | **None** (Zero GL entries exist) | QA Lead | **Very Low** |
| `REMED-ITM-..629` | Test Item 01 | Master: 50<br>Batches: 25<br>Loc: 0 | Automated test run on 2026-11-05 injected timestamped test item and 2 batches. | Test Artifact (Automated Test) | Delete or archive test item and batches `REMED-BATCH-DISMISS-*` and `THRESH-25D-*`. | **No** (Automated test artifact) | Delete 2 batches | None | **None** (Zero GL entries exist) | QA Lead | **Very Low** |

---

## 3. Safe, Auditable Execution Guidelines

When hotel management authorizes the remediation of operational items (`BEV-JUICE-01`, `MB-SODA-01`, `CORD-LIME-01`, `PER-MILK-01`, `POT-001`), the execution team must adhere strictly to the following auditable protocol:

### Step 1: Pre-Reconciliation Freeze Window
1. Schedule the reconciliation window between 02:00 AM and 05:00 AM.
2. Place all target inventory locations in **Lockdown Status** (`is_frozen = True`).
3. Ensure no open POS tickets, minibar postings, room service orders, or warehouse transfer requests are pending.

### Step 2: Dual-Blind Physical Stocktake
1. Print blind count sheets (item descriptions and units only, with quantities hidden).
2. Assign two independent counters per store:
   - Counter 1: Department Stock Custodian (e.g., Head Bartender / Storekeeper).
   - Counter 2: Internal Audit / Finance Representative.
3. Counters perform independent counts and sign the physical sheet.
4. If Counter 1 and Counter 2 disagree by more than 0.5%, a supervisor recount is performed immediately.

### Step 3: Formal Stocktake Session Entry
1. Create a formal `StocktakeSession` in the ERP for the specific location with `session_type = 'reconciliation'`.
2. Input the verified physical count into `StocktakeItem.counted_quantity`.
3. The system automatically computes theoretical vs counted variance.
4. Attach scanned PDF of the signed physical count sheet to the session.

### Step 4: Executive Approval Hierarchy & Sign-Off Chain
No adjustment transaction may be committed without multi-level digital approval based on variance thresholds:
- **Variance < 1,000.00 ETB:** Inventory Controller + F&B Supervisor sign-off.
- **Variance 1,000.00 – 10,000.00 ETB:** Cost Controller + F&B Director sign-off.
- **Variance > 10,000.00 ETB:** Financial Controller / CFO + General Manager sign-off.

### Step 5: Atomic Reconciliation Execution
1. The approved reconciliation service executes within `transaction.atomic()`.
2. Stock adjustments decrement or increment the specific `StockBatch` and `BatchLocationBalance`.
3. `ItemLocationBalance` and `InventoryItem.current_stock` are synchronized as derived aggregates.
4. Immutable `StockTransaction` audit records are logged with `transaction_type = 'adjustment'`, linking to the approved `StocktakeSession`.
5. If physical stock differs from GL asset value, an automatic balanced Journal Entry is generated posting to `5020` (Stocktake Variance Expense) against `1300` (Inventory Asset).

### Step 6: Post-Reconciliation Verification
1. Verify that `InventoryItem.current_stock == sum(StockBatch.current_quantity)`.
2. Verify that `ItemLocationBalance.quantity == sum(BatchLocationBalance.quantity)`.
3. Unlock the inventory locations (`is_frozen = False`).
4. Generate the post-reconciliation audit certificate.

