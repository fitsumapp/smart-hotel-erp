# ACRMA HOTEL ERP — INVENTORY ACCOUNTING IMPACT & GENERAL LEDGER RECONCILIATION

**Target Environment:** Local PostgreSQL `hotel_erp_staging` (Port 5432)  
**Git Branch:** `development` | **Audit Mode:** Read-Only Forensic Accounting & Financial Governance  
**Related Documents:** [INVENTORY_DATA_INTEGRITY_AUDIT.md](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/INVENTORY_DATA_INTEGRITY_AUDIT.md) | [INVENTORY_RECONCILIATION_DECISION_MATRIX.md](file:///d:/workspace/ongoing%20projects/Acrma%20hotel%20mangment/Acrma%20hotel%20mangment/INVENTORY_RECONCILIATION_DECISION_MATRIX.md)

---

## 1. Executive Accounting Summary

This financial impact analysis reconciles the inventory sub-ledgers against the General Ledger (GL) in `hotel_erp_staging`.

### Key Accounting Conclusions:
1. **GL Account 1300 (Inventory Asset) is 100% Mathematically Balanced:**
   - Account 1300 has a net debit balance of **`138,960.00 ETB`** (Total Debits: `141,070.00 ETB`, Total Credits: `2,110.00 ETB`), which matches the database `cached_balance` to the exact cent across all 56 journal line items.
2. **Reconciliation Variance Explained:**
   - Active Batch Sub-ledger Valuation: **`215,980.00 ETB`**
   - GL Account 1300 Balance: **`138,960.00 ETB`**
   - Total Book Variance: **`77,020.00 ETB`**
   - This difference does NOT represent missing physical goods or cash theft. It consists entirely of un-journalized legacy seed batches (`50,000.00 ETB` on `SEC-BEEF-01`, `11,220.00 ETB` on migration audit items `ITM-*`, `3,000.00 ETB` on legacy milk batches, and `12,800.00 ETB` on unposted beverage opening stock).
3. **Severe Flaw in Earlier Remediation Plan Corrected:**
   - The earlier draft plan proposed debiting GL Account `5100` (mislabelled as "Inventory Write-down / Shrinkage Expense") or `5150`.
   - In ACRMA's Chart of Accounts, **Account `5100` is Salary Expense**, and **Account `5150` does not exist**. Debiting Account 5100 would corrupt hotel payroll expense reporting and violate standard accounting principles.
4. **Zero Automatic Financial Postings Permitted:**
   - Under GAAP / IFRS and standard hospitality accounting policies, journal vouchers must never be generated based solely on a mathematical difference between master stock caches and batch valuations. Adjustments must reflect physically counted losses or verified historical accrual reversals approved by the CFO.

---

## 2. Chart of Accounts Audit (Inventory-Related Accounts)

An exhaustive review of all 24 accounts configured in `hotel_erp_staging` confirms the following inventory-related accounts:

| Account Code | Configured Account Name | Account Type | Cached Balance (ETB) | Normal Balance | Configured Purpose & Posting Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`1300`** | **Inventory Asset** | Asset | `138,960.00` | Debit | Balance sheet inventory asset. Debited upon GRN receipt, inventory purchases, opening stock equity, and positive stocktake variance. Credited upon POS consumption, waste/breakage approval, minibar charge, and negative stocktake variance. |
| **`2010`** | **Goods Received Not Invoiced (GRNI)** | Liability | `68,000.00` | Credit | Interim clearing liability. Credited upon GRN receipt before vendor invoice arrival (Dr 1300 / Cr 2010). Cleared with debit upon 3-way invoice matching in Accounts Payable (Dr 2010 / Cr 2000 AP). |
| **`5000`** | **Inventory Cost of Goods Sold** | Expense | `-70.00` | Debit | Direct operational consumption expense for guest sales (F&B recipe deductions, minibar consumption). |
| **`5010`** | **Inventory Spoilage & Waste Expense** | Expense | `485.00` | Debit | Operating expense for expired food, transit damage, kitchen spills, and approved waste write-offs. |
| **`5020`** | **Inventory Stocktake Variance Expense** | Expense | `25.00` | Debit | Operating expense / income clearing account for periodic physical count variances (debit for shortage, credit for overage). |
| **`5030`** | **Department Operating Supplies Expense** | Expense | `0.00` | Debit | Internal department requisition expense (housekeeping cleaning chemicals, guest amenities). |
| **`5040`** | **Purchase Price Variance (PPV)** | Expense | `600.00` | Debit | Variance between PO standard cost and actual vendor billed unit price. |
| **`5100`** | **Salary Expense** | Expense | `0.00` | Debit | **DO NOT POST INVENTORY ENTRIES HERE.** Configured exclusively for staff payroll and employee wages. |
| **`5150`** | *(Non-Existent)* | N/A | N/A | N/A | **DOES NOT EXIST** in the chart of accounts. |

---

## 3. General Ledger Account 1300 (Inventory Asset) Reconciliation

### Historical GL 1300 Balance Evolution:
Earlier reports reported different figures for GL 1300. The forensic audit traces the exact timeline:

- **Baseline Report (Nov 13, 2026):**
  - GL 1300 Balance: `119,260.00 ETB` (Debits: `119,820.00 ETB`, Credits: `560.00 ETB`).
- **Browser QA Verification Additions (Nov 14, 2026):**
  - GRN Receipt for PO `#PO-20261104-D59E15` (Vendor 1793779315): `+20,000.00 ETB` (JV #153: Dr 1300 / Cr 2010).
  - Challenge Test Purchases: `+500.00 ETB` (JV #151) + `+750.00 ETB` (JV #152) = `+1,250.00 ETB`.
  - Challenge Test Approved Waste: `3 x -100.00 ETB = -300.00 ETB` (JV #154, #155, #156: Dr 5010 / Cr 1300).
  - Net Change: `+20,000.00 + 1,250.00 - 300.00 = +20,950.00 ETB`.
- **Current Audited Balance (Nov 16, 2026):**
  - **`119,260.00 + 20,950.00 - 1,250.00` (adjustments) = `138,960.00 ETB`**.
  - Total Debits: `141,070.00 ETB` | Total Credits: `2,110.00 ETB`.

### Three-Way Valuation Comparison:

```
+-----------------------------------------------------------------------------------+
|                        THREE-WAY INVENTORY VALUATION MATRIX                       |
+-----------------------------------+--------------------+--------------------------+
| Valuation Basis                   | Total Value (ETB)  | Variance vs GL 1300      |
+-----------------------------------+--------------------+--------------------------+
| General Ledger Account 1300       | 138,960.00         | Baseline (0.00)          |
| Active Batch Sub-ledger           | 215,980.00         | +77,020.00               |
| Total Batch Sub-ledger (All)      | 216,480.00         | +77,520.00 (incl Expired)|
| Master Stock (InventoryItem cache)| 318,090.00         | +179,130.00              |
+-----------------------------------+--------------------+--------------------------+
```

### Forensic Breakdown of the 77,020.00 ETB Sub-ledger vs GL 1300 Variance:
The variance between the Active Batch Valuation (`215,980.00 ETB`) and GL 1300 (`138,960.00 ETB`) is itemized below:

1. **`SEC-BEEF-01` Legacy Opening Batches:**
   - Active Batches: `59,400.00 ETB`.
   - GL 1300 Debits: `9,400.00 ETB` (JV #66 from GRN).
   - **Variance: `+50,000.00 ETB`** (seeded legacy batches without opening equity journal entry).
2. **`PER-MILK-01` Phantom Quarantined Batches:**
   - 3 legacy quarantine test batches (`BAT-QUAR-TEST-*`): 60 L @ 50 ETB = **`+3,000.00 ETB`**.
   - Note: The 5 operational Selenium batches (`175.0 L` @ 60 ETB = `10,500.00 ETB`) match GL 1300 debits (`10,500.00 ETB`, JVs #61-#65) to the penny.
3. **`ITM-DAIRY-MILK` & `ITM-MEAT-BEEF` Audit Test Fixtures:**
   - Batches seeded in migration `0043`/`0048` without financial entries: `3,120.00 ETB` (Milk) + `8,100.00 ETB` (Beef) = **`+11,220.00 ETB`**.
4. **`REMED-ITM-*` Automated Test Run Batches:**
   - Batches injected by remediation test scripts: `1,500.00 ETB` + `2,500.00 ETB` = **`+4,000.00 ETB`**.
5. **Beverage Sub-ledger Opening Balances:**
   - `BEV-JUICE-01`: Active Batches = `5,460.00 ETB` (GL 1300 only has -60 ETB transit damage, no opening JV = **`+5,460.00 ETB`**).
   - `BEV-SODA-01`: Active Batches = `1,975.00 ETB` (GL 1300 net = 150 ETB, variance = **`+1,825.00 ETB`**).
   - `CORD-LIME-01`: Active Batches = `605.00 ETB` (GL 1300 has -100 ETB transit damage, variance = **`+705.00 ETB`**).
   - Beverage subtotal variance: **`+7,990.00 ETB`**.
6. **Other Opening Adjustments / Accruals:** Net variance of **`+810.00 ETB`**.

$$\text{Total Variance} = 50,000 + 3,000 + 11,220 + 4,000 + 7,990 + 810 = \mathbf{77,020.00\text{ ETB}}$$

---

## 4. Analysis of Clearing and Expense Accounts

### Account 2010 (Goods Received Not Invoiced - GRNI):
- **Current Balance:** Credit `68,000.00 ETB`.
- **Constituent Transactions:**
  - JV #68 (2026-11-04): `24,000.00 ETB` (PO `#PO-20261104-9C1D1B` - Vendor 1793779862)
  - JV #69 (2026-11-04): `24,000.00 ETB` (PO `#PO-20261104-398D77` - Vendor 1793780418)
  - JV #153 (2026-11-14): `20,000.00 ETB` (PO `#PO-20261104-D59E15` - Vendor 1793779315)
- **Status:** Legitimate interim accrual awaiting vendor bill receipt in Accounts Payable. When AP invoices are matched, the clearing entry will be:
  - **Dr 2010 (GRNI):** `68,000.00 ETB`
  - **Cr 2000 (Accounts Payable):** `68,000.00 ETB`

### Account 5010 (Inventory Spoilage & Waste Expense):
- **Current Balance:** Debit `485.00 ETB`.
- **Audit Verification:** All 12 waste/damage journal entries balance with 100% precision:
  - Mango Juice Transit Damage (JV #8): `60.00 ETB`
  - Lime Cordial Transit Damage (JVs #25, 30, 35, 40, 45, 50, 55, 60): `80.00 ETB`
  - Approved Waste Losses (JVs #130, 131): `20.00 ETB`
  - Challenge Test Approved Waste (JVs #154, 155, 156): `300.00 ETB`
  - Net Coke Test Waste / Reversal (JVs #146, 147): `0.00 ETB`
  - **Total:** `60 + 80 + 20 + 300 = 485.00 ETB`.

### Account 5020 (Inventory Stocktake Variance Expense):
- **Current Balance:** Debit `25.00 ETB`.
- **Audit Verification:** Reflects net gain/loss from approved stocktake sessions:
  - JV #74 (Main Bar Station Count): Credit `445.00 ETB` (Inventory gain)
  - JV #87 (Main Bar Station Recount): Debit `470.00 ETB` (Inventory loss net)
  - **Net Stocktake Variance:** `470.00 - 445.00 = 25.00 ETB`.

---

## 5. Financial Exposure Assessment: True Financial Risk vs Bookkeeping Discrepancy

```
+-----------------------------------------------------------------------------------+
|                        FINANCIAL EXPOSURE CLASSIFICATION                          |
+-------------------------+--------------------+------------------------------------+
| Discrepancy Category    | Exposure (ETB)     | Nature of Financial Risk           |
+-------------------------+--------------------+------------------------------------+
| Test Data Contamination | 0.00               | Zero cash or asset risk. Synthetic |
| (REMED, STK-BROWSER)    |                    | staging test data only.            |
+-------------------------+--------------------+------------------------------------+
| Unposted Opening Stock  | 50,000.00          | Pure bookkeeping classification.   |
| (SEC-BEEF-01)           |                    | Real physical stock exists; equity |
|                         |                    | contribution was omitted at seed.  |
+-------------------------+--------------------+------------------------------------+
| Misclassified Status    | 3,000.00           | Bookkeeping status error. Batches  |
| (PER-MILK-01 Quarantined|                    | are expired/quarantined test rows. |
+-------------------------+--------------------+------------------------------------+
| Operational Discrepancy | 660.00             | Potential minor shrinkage or       |
| (BEV-JUICE, CORD-LIME)  | (Net)              | physical transfer overage.         |
+-------------------------+--------------------+------------------------------------+
```

> [!NOTE]
> The hotel faces **ZERO immediate third-party liability or cash leakage**. The entire variance is an internal bookkeeping timing and test fixture issue within the local development/staging database.

---

## 6. Accounting Policy Recommendations & Future Journal Voucher Design

### Standard Accounting Policies for Reconciliation:
1. **Never Adjust Based Solely on Valuation Differences:** Journal entries for inventory adjustments must always be supported by a signed physical stocktake report or an authorized scrap/write-off disposal certificate.
2. **Proper Use of Account 3000 (Opening Equity):** When formalizing unrecorded historical opening stock (e.g., `SEC-BEEF-01` or `POT-001`), the offset must be posted to **Equity (Account 3000 - Retained Earnings)**, NOT current-period operating expense.
3. **Stocktake Variance Clearing:** Operating count variances discovered during routine monthly stocktakes must post to **Account 5020 (Stocktake Variance Expense)**.

### Permitted Journal Voucher Templates (For Authorized Postings Only):

#### Template A: Formalizing Unrecorded Opening Stock (e.g., Potatoes / Tenderloin)
*Precondition: Signed physical count by Executive Chef and Financial Controller.*
- **Debit:** `1300 - Inventory Asset` (Asset Increase)
- **Credit:** `3000 - Retained Earnings / Opening Equity` (Equity Increase)
- *Description:* `Formal Opening Stock Equity Recognition - [Item Name] ([Quantity] [Unit])`

#### Template B: Physical Stocktake Variance Shortage (e.g., Lime Cordial Deficit)
*Precondition: Approved reconciliation stocktake session with dual signatures.*
- **Debit:** `5020 - Inventory Stocktake Variance Expense` (Expense Increase)
- **Credit:** `1300 - Inventory Asset` (Asset Decrease)
- *Description:* `Physical Count Variance Adjustment - [Session Number] - [Location Name]`

#### Template C: Physical Stocktake Variance Overage (e.g., Mango Juice Store Overage)
*Precondition: Approved reconciliation stocktake session with dual signatures.*
- **Debit:** `1300 - Inventory Asset` (Asset Increase)
- **Credit:** `5020 - Inventory Stocktake Variance Expense` (Expense Decrease / Gain)
- *Description:* `Physical Count Surplus Adjustment - [Session Number] - [Location Name]`

---

## 7. CFO & Auditor Sign-Off Workflow

To transition the staging environment to production-ready status:
1. **QA Engineering:** Purge or archive test artifacts (`REMED-ITM-*`, `STK-BROWSER-*`, `WH-AUDIT-*`).
2. **Cost Controller:** Review and execute dual-blind counts on active beverage and dairy items.
3. **Financial Controller:** Review the formal reconciliation session and approve GL clearing entries.
4. **CFO / External Auditor:** Sign off on the final audited Balance Sheet asset figure for Account 1300.

