# Acrma Hotel ERP — Documentation & Governance Audit Report (Explorer 2)

**Report ID:** EXP-2-DOC-GOV-AUDIT  
**Audit Date:** 2026-11-03  
**Auditor Archetype:** Explorer 2 (Documentation & Governance Audit)  
**Deliverable Target:** `.agents/teamwork/explorer_survey_2/handoff.md`  
**Governing Directive:** `.agents/teamwork/ORIGINAL_REQUEST.md`  

---

## 1. Observation

### 1.1 Documentation Inventory & Direct Code Evidence

An exhaustive filesystem scan across repository root, `docs/`, and `.agents/` identified **14 primary documentation and architectural records** (totaling ~175 KB of specifications, audits, and runbooks). All files were read and analyzed in-place:

| File Path | Version / Date | Scope & Primary Purpose | Key Contents & Metrics |
| :--- | :---: | :--- | :--- |
| `REQUIREMENTS.md` | v1.0.0 (2026-10-24) | System Capability Verification Matrix & Decision Register | PMS (PMS-001..009), POS/KDS (POS-001..008), Inventory (INV-001..006), Finance (FIN-001..007), Housekeeping (HK-001..004), Integrations (EXT-001..005). Defines 8 Owner Decisions. |
| `SYSTEM_AUDIT.md` | v1.0.0 (2026-10-24) | Comprehensive Technical Due Diligence & Health Audit | Audited commit `b6ea79f`. Documented 207 backend / 9 frontend passing tests. Identified Critical P1 triple-counting defect (`DEFECT-FIN-001`), P2 premature Z-report closure (`DEFECT-OPS-001`), P2 missing Night Audit (`DEFECT-PMS-001`), P2 missing `no_show` (`DEFECT-PMS-002`). |
| `IMPLEMENTATION_PLAN.md` | 2026-10-24 | Two-Part Implementation Roadmap | **Part I:** Phases 0–9 (Security, Payments, Concurrency, Modular Monolith, Observability, Performance, Hardening, DR, Testing).<br>**Part II:** Phases 10–13 (Baseline consolidation, Critical bug remediation, PMS Night Audit, Cashier consolidation). |
| `DECISIONS.md` | v1.0.0 (2026-10-24) | Architecture Decision Records (ADRs) | Contains ADR-001 through ADR-008 covering working tree baseline, revenue engine, night audit trigger, no-show status, cashier session billing, role cleanup, background broker, customer portal. |
| `PROJECT_STATUS.md` | 2026-10-24 | Project Health & Defect Tracking Scorecard | Readiness scores across 8 pillars (87% overall). Gate 1 (Baseline), Gate 2 (Critical Defects), Gate 3 (Night Audit). |
| `docs/AUDIT_FUNCTIONAL_COMPLETENESS_AND_WORKFLOW_GAPS.md` | 2026-10-19 | In-depth Operational Workflow & Defect Analysis | Traced KDS/Bar multi-station ticket collision (`DEFECT-ORD-001`), blocked occupied tables (`DEFECT-ORD-002`), missing kitchen prep notes (`DEFECT-ORD-003`), missing housekeeping role (`DEFECT-ROLE-001`), finance 403 on daily reports (`DEFECT-PERM-001`). |
| `docs/AUDIT_NIGHT_AUDIT_READINESS.md` | v1.0.0 (2026-10-19) | Night Audit Architecture & End-of-Day Spec | 546-line specification for 8-stage Night Audit state machine: pre-flight checks, exception resolution, room rate accrual, compound GL journal posting, business date rollover, idempotency, and failure recovery. |
| `docs/IDENTITY_SECURITY.md` | 2026-07-20 | Identity, Session & RBAC Operations Runbook | Documents SimpleJWT token rotation (15m access, 7d refresh), `token_version` invalidation, cryptographic single-use OTP/MFA, 5-failure/15m lockout, append-only security audit events. |
| `docs/PAYMENT_OPERATIONS.md` | 2026-07-20 | Payment Security & Reconciliation Runbook | Chapa HMAC verification (`x-chapa-signature`, `chapa-signature`), immutable `PaymentWebhookEvent`, 1-to-1 GL journal binding, `reconcile_payments` scheduler instructions. |
| `docs/INFRASTRUCTURE_HARDENING.md` | 2026-07-23 | Production Infrastructure & Reverse Proxy Runbook | Fail-closed env assertions (`DJANGO_ENV=production`), generic error masking with `X-Request-ID`, private KYC ID scan storage (`media/private/guest_ids/`), Nginx edge rate limiting. |
| `docs/PHASE0_BASELINE.md` | 2026-07-20 | Baseline Environment & Backup Runbook | Pinned runtimes (Python 3.12, Django 5.2 LTS, Postgres 16), settings split, backup/restore scripts (`scripts/backup_phase0.ps1`). |
| `docs/PHASE5_OBSERVABILITY.md` | 2026-07-23 | Observability, Metrics & Alert Policy | JSON logging with correlation IDs, health checks (`/health/live`, `/health/ready`), `AuditEvent` model, alert thresholds. |
| `docs/PHASE6_1_PERFORMANCE.md` | 2026-07-23 | Database & API Performance Optimization | Date range limits (366 days max), single-query aggregations, index enhancements, PostgreSQL connection timeout settings. |
| `docs/SYSTEM_REVIEW_2026-09-25.md` | 2026-09-25 | Remediation Sign-Off Report | Documents cash rollback on GL failure, mandatory MFA for admin/finance, database-backed API throttling (`hotel.0030_api_cache`). |

---

### 1.2 In-Tree Code State vs. Documented Baseline

Direct repository inspection (`git log -n 10 --oneline` and `git status`) revealed significant development progression since the October 24, 2026 audit:

1. **Committed Features on `development` (HEAD: `9d96437`):**
   - `0ce2261`: `feat: complete expense management, tax report hardening, and API error formatting` (Implements Phase 10 / ADR-001).
   - `8be332d`: `fix: correct revenue double-counting and separate Z-Report preview from closure` (Implements Phase 11 / ADR-002, ADR-003).
   - `b7a7303`: `fix: add reservation no-show handling and release room inventory` (Implements Phase 12 / ADR-004).
   - `0c2a984`: `feat: complete hotel ERP release gate and operational workflows`.
   - `eca330f` & `9d96437`: Security dependency remediation (Django, DRF, Pillow).

2. **Active In-Flight Working Tree (Modifications & Untracked Features):**
   - **Procurement & 3-Way Match Backend:** `hotel/procurement.py` (1,386 lines, lines 1–1386) implements the complete backend service layer for:
     - Configurable procurement approval policies & multi-tier thresholds (`ProcurementApprovalPolicy`, `ProcurementApprovalTier`).
     - Purchase Requisitions (`PurchaseRequisition`, `PurchaseRequisitionItem`).
     - Phase 2.1 RFQs, line-item bidding, supplier quotations (`RequestForQuotation`, `SupplierQuotation`).
     - Split-award quotation evaluation (`evaluate_and_award_quotations`) and multi-PO conversion (`convert_awarded_quotations_to_purchase_orders`).
     - Goods Receipt Notes (`GoodsReceiptNote`) with interim GRNI accrual (Dr 1300 / Cr 2010).
     - 3-Way Matching (`SupplierInvoice`, `SupplierInvoiceItem`) and AP settlement with Purchase Price Variance (Dr 2010, Dr/Cr 5040, Cr 2000).
   - **Physical Stocktaking Backend:** `hotel/stocktaking.py` (570 lines) implements Dual-Mode Physical Stocktaking (blind vs visible, mode locking D-4, separation of duties, recount workflow, GL variance posting to Account 5020).
   - **Stock Transfers Backend:** `hotel/transfers.py` (379 lines) implements two-phase custody transfers across locations (`StockTransfer`).
   - **Database Migrations:** Untracked migrations `0039` to `0047` in `hotel/migrations/` define schemas for:
     - `0042_stock_batch_and_locations.py`
     - `0044_stock_transfer_management.py`
     - `0045_configurable_procurement_and_3way_matching.py`
     - `0046_dual_mode_physical_stocktaking.py`
     - `0047_rfq_and_supplier_quotation_workflow.py`
   - **Frontend State:** `hotel-frontend/src/pages/InventoryDashboard.js` (4,446 lines) currently manages SKUs, Categories, Suppliers, Recipes, Transactions, Waste, Batches, and Locations, but **completely lacks operational UI for Requisitions, RFQs, Quotations, Split-Award POs, 3-Way Invoice Matching, and Stocktake Sessions**.

---

## 2. Logic Chain

### 2.1 Requirements Synthesis Across All Lifecycle Phases

From cross-referencing `ORIGINAL_REQUEST.md`, `IMPLEMENTATION_PLAN.md`, `hotel/procurement.py`, and `hotel/stocktaking.py`, the project roadmap decomposes into the following authoritative structure:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           ACRMA HOTEL ERP — MASTER LIFECYCLE ROADMAP                           │
├───────────────────┬──────────────────────────────────┬─────────────────────────────────────────┤
│ Phase ID          │ Title                            │ Scope & Deliverables                    │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 1**       │ Foundation & Core Stabilization  │ • Identity hardening, SimpleJWT, MFA    │
│                   │                                  │ • Chapa HMAC & payment reconciliation   │
│                   │                                  │ • Postgres GiST anti-double booking     │
│                   │                                  │ • Balanced double-entry General Ledger  │
│                   │                                  │ • Baseline resolution of P1/P2 defects  │
│                   │                                  │ • Location & Batch foundation (0042/43) │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 2.1**     │ Procurement Backend Engineering  │ • Dynamic procurement approval policies │
│                   │                                  │ • Purchase Requisitions & tier routing  │
│                   │                                  │ • RFQs & aggregate allocation locks     │
│                   │                                  │ • Supplier Quotations & landed cost     │
│                   │                                  │ • Split-award evaluation & multi-PO gen │
│                   │                                  │ • GRN receiving & interim GRNI accruals │
│                   │                                  │ • 3-Way match & AP settlement (PPV)     │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 2.2**     │ Procurement Operational Frontend │ • Requisition composer & tier preview   │
│                   │                                  │ • RFQ bidding center & supplier invite  │
│                   │                                  │ • Quotation comparison & landed cost UI │
│                   │                                  │ • Split-award matrix & PO conversion UI │
│                   │                                  │ • GRN physical receiving desk           │
│                   │                                  │ • 3-Way match comparison & invoice UI   │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 2.3**     │ Procurement Integration &        │ • Full-lifecycle E2E integration smoke  │
│                   │ Browser Acceptance               │ • Responsive UX, modals, error envelopes│
│                   │                                  │ • Multi-role browser acceptance testing │
│                   │                                  │ • Independent QC verification gate      │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 3**       │ Dual-Mode Physical Stocktaking   │ • Blind count (theoretical hidden) vs   │
│                   │                                  │   Visible count mode (locked upon entry)│
│                   │                                  │ • Separation of duties (count != approve│
│                   │                                  │ • Recount discrepancy workflow          │
│                   │                                  │ • Atomic stock adjustment & GL post     │
│                   │                                  │ • Mobile-friendly counting UI           │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────────────┤
│ **Phase 4**       │ Final Integration & Release      │ • PMS Night Audit date rollover engine  │
│                   │ Readiness                        │ • Daily room rate & tax accruals        │
│                   │                                  │ • Cashier dining session consolidation  │
│                   │                                  │ • Cross-module regression verification  │
│                   │                                  │ • Production hardening & final sign-off │
└───────────────────┴──────────────────────────────────┴─────────────────────────────────────────┘
```

---

### 2.2 Governance, Accounting & Financial Reconciliation Rules

The ERP enforces standard double-entry accrual accounting (USALI compliant) across all operational sub-modules:

#### A. Authoritative Chart of Accounts (COA) Map
- **1000 — Cash on Hand:** Cashier cash drawer collections.
- **1010 — Operating Bank Account:** Electronic/card deposits and bank settlements.
- **1020 — Petty Cash:** Local operational expenditures and immediate cash purchases.
- **1200 — Accounts Receivable / Guest Ledger:** Guest room folios, city ledger, unpaid billing.
- **1300 — Inventory Asset:** Physical inventory valuation across all warehouse locations.
- **2000 — Accounts Payable (AP):** Supplier liability pending payment disbursement.
- **2010 — Goods Received Not Invoiced (GRNI):** Interim accrual clearing account for received inventory.
- **2200 — VAT Payable:** Ethiopian 15% Value Added Tax liability.
- **2300 — Service Charge Payable:** 10% hospitality service charge pool liability.
- **4000 — Room Accommodation Revenue:** Lodging revenues.
- **4100 — Food & Beverage Revenue:** Restaurant, bar, and dining sales.
- **4200 — Miscellaneous Operating Revenue:** Laundry, minibar markup, space rental.
- **5020 — Inventory Variance Expense:** Physical stocktake shrinkage, breakage, or surplus.
- **5040 — Purchase Price Variance (PPV):** Variance between PO contract price and invoiced price.
- **5400 — Maintenance & Repairs Expense:** Facility upkeep expenses.
- **5500 — Marketing & Advertising Expense:** Promotional expenses.

#### B. Financial Transaction Workflows & Journal Posting Invariants
1. **Double-Entry Invariant:**  
   Every posted `JournalEntry` must satisfy `total_debit == total_credit` before database commit. Posted entries are immutable; corrections strictly require reversing entries (`hotel/accounting.py:reverse_entry`).
2. **Interim Accrual on Goods Receipt (GRNI):**  
   When a GRN is approved in `hotel/procurement.py:receive_goods_against_purchase_order` (lines 528–543), stock enters STORE-MAIN, and the system automatically posts:
   - **Debit:** Account `1300` (Inventory Asset) = `total_grn_cost`
   - **Credit:** Account `2010` (GRNI Accrued Liability) = `total_grn_cost`
3. **3-Way Matching & Final AP Settlement:**  
   When a vendor invoice is approved in `hotel/procurement.py:approve_supplier_invoice` (lines 704–729):
   - **Debit:** Account `2010` (GRNI) = Clears original received cost (`billed_qty * po_unit_price`).
   - **Debit / Credit:** Account `5040` (PPV) = Difference between billed and PO price.
   - **Debit:** Account `2200` (VAT Payable / Input Tax) = Invoiced tax portion.
   - **Credit:** Account `2000` (Accounts Payable) = Total invoice amount payable to vendor.
4. **Physical Stocktake Discrepancy Adjustment:**  
   In `hotel/stocktaking.py:approve_stocktake_session` (lines 280–320), variance between theoretical and physical stock triggers:
   - *Shortage / Shrinkage:* **Debit** Account `5020` (Inventory Variance Expense) / **Credit** Account `1300` (Inventory Asset).
   - *Surplus / Overage:* **Debit** Account `1300` (Inventory Asset) / **Credit** Account `5020` (Inventory Variance Expense).
5. **Lodging Night Accrual vs. Lump-Sum Checkout Settlement:**  
   Under the Night Audit architecture (`docs/AUDIT_NIGHT_AUDIT_READINESS.md`), each room night accrues:
   - **Debit:** Account `1200` (Guest Ledger) = Total daily lodging bill.
   - **Credit:** Account `4000` (Room Revenue) = Net room rate.
   - **Credit:** Account `2200` (VAT Payable) = 15% room tax.
   - **Credit:** Account `2300` (Service Charge) = 10% service fee.
6. **Rounding & Currency Discipline:**  
   All monetary amounts are strictly rounded using Python `Decimal` with two decimal places (`Decimal("0.01")`, `ROUND_HALF_UP`). Floating-point arithmetic for currency is strictly prohibited across all services.

---

### 2.3 Concurrency, Idempotency, and Audit History Invariants

1. **Database Row-Level Locking:**  
   All state transitions, balance updates, and allocations must execute within `transaction.atomic()` blocks using `select_for_update()`:
   - Overlap protection on reservations (`apps/reservations/views.py`).
   - Requisition unallocated balance checks during RFQ line creation (`hotel/procurement.py:810`).
   - Payment attempt and order locking during finalization (`apps/payments/views.py`).
   - Stock balance deductions in `hotel/integrity.py:record_stock_change`.
2. **Idempotency Safeguards:**  
   - Digital payment webhooks verify `PaymentWebhookEvent.event_id` and payload hash before processing (`docs/PAYMENT_OPERATIONS.md`).
   - Stock transactions carry `idempotency_key` and unique payload hashes (`hotel/migrations/0040`, `0041`).
   - Supplier invoice matching checks unique `(supplier, vendor_invoice_number)`.
3. **Immutable Audit History:**  
   All security events, privileged role modifications, price updates, stock write-offs, and procurement approvals emit immutable records to `hotel.models.AuditEvent` via `apps.audit.services.record_audit_event()`.

---

### 2.4 Role-Based Access Control (RBAC) & Separation of Duties

| Role | Operational Scope | Procurement & Stocktake Permissions | Governance & Segregation Rules |
| :--- | :--- | :--- | :--- |
| **`admin`** | Full hotel administration | Approves Tier 3 requisitions (>50k ETB), overrides 3-way match variances, reopens audits | Highest privilege; MFA mandatory. |
| **`finance`** | GL, taxes, AP/AR, payroll | Approves Tier 2 requisitions (10k–50k ETB), approves vendor invoices, runs tax reports | Mandatory MFA; cannot initiate physical stock counts. |
| **`inventory`** | Stores, stock issuance, SKUs | Submits PRs, creates RFQs, enters GRNs, enters physical counts, manages transfers | Cannot approve own PR; cannot approve own stocktake count (`counted_by != approved_by`). |
| **`reception`** | PMS, room grid, check-in | Charges guest folios, triggers front-desk Night Audit modal | Cannot modify GL accounts directly. |
| **`waiter`** | POS ordering, dining sessions | Orders to occupied tables, kitchen prep notes | Strictly barred from supplier and inventory pricing APIs. |
| **`kitchen`** / **`bar`** | KDS / BDS display | Updates item preparation status (`preparing` -> `ready`) | Isolated station views; cannot view financial folios. |
| **`cashier`** | Bill settlement, receipt print | Settles dining bills, processes room charges | Settlement auto-deducts BOM stock; cannot alter menu prices. |
| **`housekeeping`**| Room cleaning, minibar | Cleans rooms, logs minibar consumption | Auto-charges guest folio and issues inventory stock. |
| **`customer`** | Public online booking | Public booking & Chapa checkout | Public / restricted token; cannot access staff endpoints. |
| *`delivery`* | *Phantom / Deprecated* | None (Renders "Unauthorized") | **ADR-006: Slated for formal removal.** |

**Separation of Duties Rules:**
- **Requisition Approval:** A user cannot approve their own Purchase Requisition unless they hold superuser privileges (`hotel/procurement.py:approve_purchase_requisition`).
- **Physical Stocktaking:** The staff member who counts stock cannot approve the stocktake session (`counted_by != approved_by` in `hotel/stocktaking.py:approve_stocktake_session`).
- **Invoice Matching:** Cross-role permission `IsSupplierOperator` permits Finance and Admin to approve supplier invoices, but excludes warehouse receivers.

---

### 2.5 Architecture Decision Records (ADR) Status

Review of `DECISIONS.md` alongside recent commits confirms the following status of the 8 ADRs:

1. **ADR-001 (Preserve and Commit In-Flight Baseline):** **RESOLVED / COMMITTED** in `0ce2261`.
2. **ADR-002 (Derive Daily Revenue from GL Accounts 4000/4100):** **RESOLVED / COMMITTED** in `8be332d`.
3. **ADR-003 (Night Audit Trigger — Manual UI vs. Automated Cron):** **APPROVED IN PRINCIPLE** (Option A: Front-desk manual modal trigger with checklist). Code implementation pending in Phase 4.
4. **ADR-004 (Reservation `no_show` Status & Penalty Policy):** **RESOLVED / COMMITTED** in `b7a7303`.
5. **ADR-005 (Cashier Dining Session Consolidation):** **APPROVED IN PRINCIPLE** (Option A: Single consolidated session check). Frontend UI implementation scheduled for Phase 4.
6. **ADR-006 (Deprecation of Phantom `delivery` Role):** **APPROVED IN PRINCIPLE** (Option A: Deprecate). Slated for cleanup in Phase 4.
7. **ADR-007 (Background Task Architecture — Sync vs. Celery/Redis):** **CONFIRMED** (Option A: Synchronous processing with strict timeouts for pilot deployment).
8. **ADR-008 (Scope of Customer Self-Service Portal):** **CONFIRMED** (Option A: Defer authenticated history portal to post-pilot milestone).
9. **Decision D-4 (Stocktaking Mode Lock):** **CONFIRMED & CODIFIED** in `hotel/stocktaking.py` (Permanent mode lock upon count submission).

---

## 3. Caveats & Ambiguities

During the audit, **four key discrepancies and documentation gaps** were identified that require explicit alignment in the Master Execution Tracker:

1. **Phase Naming & Numbering Divergence:**  
   - In `IMPLEMENTATION_PLAN.md`: Part I numbered security/infrastructure phases as **Phases 0 through 9** (completed/hardened), and Part II numbered takeover tasks as **Phases 10 through 13** (baseline, critical bugs, night audit, cashier).
   - In the Master Engineering Directive (`ORIGINAL_REQUEST.md`): The phases are numbered **Phase 1 (Foundation/Core), Phase 2.1 (Procurement Backend), Phase 2.2 (Procurement Frontend), Phase 2.3 (Procurement Integration), Phase 3 (Physical Stocktaking), and Phase 4 (Final Integration & Release Readiness)**.  
   - *Impact:* The Master Execution Tracker must explicitly document this phase mapping so team members understand that Phase 2.1..2.3 corresponds to the procurement lifecycle extension, Phase 3 to physical stocktaking, and Phase 4 to the night audit and final release gate.

2. **Absence of Standalone "Phase 2.1 Implementation Report" Document:**  
   - The directive asks to "audit the Phase 2.1 implementation report and outstanding evidence requests".  
   - *Reality:* There is **no existing standalone markdown file named `PHASE_2_1_REPORT.md` or similar** in the repository. The Phase 2.1 procurement backend implementation exists directly in Python code (`hotel/procurement.py`, migrations `0045`/`0047`, and `apps/inventory/views.py`).  
   - *Recommendation:* Explorer 1 and the orchestrator must formulate the Phase 2.1 audit findings directly from the code and migrations rather than expecting a pre-existing report document.

3. **PMS Night Audit Implementation Status:**  
   - `docs/AUDIT_NIGHT_AUDIT_READINESS.md` contains an extensive, production-ready architectural specification for the Night Audit state machine and `current_business_date`.  
   - *Reality:* The actual code (`hotel/models.py`) does **not yet contain `current_business_date`**, and `RoomManager.js` still contains the static 4-counter placeholder. Night Audit must be tracked as a major deliverable of Phase 4.

4. **Unused Room Pricing Fields in Catalog:**  
   - In `hotel/models.py:104-108`, the `Room` model declares `weekend_price`, `holiday_price`, `discount_percent`, and `extra_bed_price`.  
   - Code inspection confirms that all reservation billing services calculate strictly `nights * room.base_price`. The auxiliary pricing fields are currently non-functional schema placeholders.

---

## 4. Conclusion & Input for Master Execution Tracker

### 4.1 Master Execution Tracker Phase Definitions

The following table provides the synthesized structure, acceptance criteria, ownership, and gate rules required for `docs/MASTER_EXECUTION_TRACKER.md`:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             MASTER EXECUTION TRACKER SPECIFICATION                               │
├─────────────────┬────────────────────┬───────────┬───────────────────────────────────────────────┤
│ Phase           │ Primary Owner      │ Status    │ Hard Acceptance Criteria                      │
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 1**     │ Security / Arch    │ COMPLETED │ 1. Clean Git baseline preserving changes.     │
│ Core Foundation │ (Agent D / E)      │ & AUDITED │ 2. Zero regression on 207 backend tests.      │
│                 │                    │           │ 3. P1 Revenue triple-counting resolved.       │
│                 │                    │           │ 4. No-show status active in Reservation.      │
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 2.1**   │ Backend Lead       │ COMPLETED │ 1. Multi-tier approval policy engine active.  │
│ Procurement     │ (Agent A)          │ IN CODE / │ 2. RFQ aggregate allocation locks verified.   │
│ Backend         │                    │ AUDIT     │ 3. Split-award quotation evaluation & PO gen. │
│                 │                    │ PENDING   │ 4. GRN receipt with interim GRNI accrual.     │
│                 │                    │           │ 5. 3-Way match & AP settlement with PPV.      │
│                 │                    │           │ 6. Formally audited by Independent QC.        │
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 2.2**   │ Frontend Lead      │ READY FOR │ 1. Requisition composer & tier preview UI.    │
│ Procurement     │ (Agent B)          │ DISPATCH  │ 2. RFQ bidding center & supplier invite UI.   │
│ Operational UI  │                    │ (SERIAL)  │ 3. Quotation comparison matrix & landed cost. │
│                 │                    │           │ 4. Checkbox-driven split-award PO conversion. │
│                 │                    │           │ 5. Physical GRN receiving desk with expiry.   │
│                 │                    │           │ 6. 3-Way matching comparison & override modal.│
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 2.3**   │ QA & Test Lead     │ BLOCKED   │ 1. Full E2E procurement lifecycle test pass.  │
│ Procurement E2E │ (Agent C / QC)     │ ON 2.2    │ 2. Nested error messages formatted cleanly.   │
│ Acceptance      │                    │ (SERIAL)  │ 3. Browser acceptance without mock data.      │
│                 │                    │           │ 4. Formal QC Decision: PASS issued.           │
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 3**     │ Backend & Frontend │ BLOCKED   │ 1. Backend dual-mode stocktaking verified.    │
│ Physical        │ (Agent A & B)      │ ON 2.3    │ 2. Mode lock on entry verified (D-4).         │
│ Stocktaking     │                    │ (GATE)    │ 3. Separation of duties (count != approve).   │
│                 │                    │           │ 4. Atomic stock & GL variance posting (5020). │
│                 │                    │           │ 5. Mobile-friendly counting UI implemented.   │
├─────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ **Phase 4**     │ All Agents         │ BLOCKED   │ 1. `current_business_date` in SystemSettings. │
│ Final Release & │ (Lead Orchestrator)│ ON 3      │ 2. Daily room rate & tax accruals to folios.  │
│ Night Audit     │                    │ (GATE)    │ 3. Interactive Night Audit modal in PMS.      │
│                 │                    │           │ 4. Single-bill dining session settlement.     │
│                 │                    │           │ 5. Full regression suite 100% pass.           │
│                 │                    │           │ 6. Final Owner sign-off for pilot launch.     │
└─────────────────┴────────────────────┴───────────┴───────────────────────────────────────────────┘
```

### 4.2 Serialization vs. Parallel Execution Rules
- **Serialized Paths (Must NOT run concurrently):**
  - Phase 2.2 Implementation **cannot begin** until Phase 2.1 is formally accepted and QC-verified.
  - Phase 2.3 Browser Acceptance **cannot begin** until Phase 2.2 frontend components are rendered and connected to API.
  - Phase 3 Physical Stocktaking **requires formal Owner authorization** after Phase 2.3 sign-off.
  - Phase 4 Release Readiness **is the final integration gate** and requires all prior phases to be locked.
- **Safe Parallel Paths (Can execute simultaneously):**
  - While Phase 2.2 frontend engineering is underway, Agent D (Security & Accounting) and Agent E (Architecture Reviewer) can independently audit GL journal generation and schema safety across migrations `0042` through `0047`.
  - QA test planning (test vectors, edge cases, browser test matrices) can proceed in parallel with Frontend implementation.

---

## 5. Verification Method

To independently verify the observations and findings in this report:

1. **Verify Documentation Files:**
   ```powershell
   Get-ChildItem -Path . -Filter "*.md" | Select-Object Name, Length, LastWriteTime
   Get-ChildItem -Path docs -Filter "*.md" | Select-Object Name, Length, LastWriteTime
   ```
2. **Verify Phase 2.1 Procurement Service Implementation:**
   Inspect `hotel/procurement.py` lines 1–1386:
   - Line 82: `ensure_default_procurement_policy`
   - Line 154: `request_purchase_requisition`
   - Line 238: `approve_purchase_requisition`
   - Line 745: `create_request_for_quotation`
   - Line 959: `submit_supplier_quotation`
   - Line 1152: `evaluate_and_award_quotations`
   - Line 1252: `convert_awarded_quotations_to_purchase_orders`
   - Line 418: `GoodsReceiptNote.objects.create`
   - Line 530: `post_journal_entry` (Dr 1300 / Cr 2010)
   - Line 547: `match_and_record_supplier_invoice`
   - Line 672: `approve_supplier_invoice` (Dr 2010 / Dr 5040 / Cr 2000)
3. **Verify Physical Stocktake Implementation:**
   Inspect `hotel/stocktaking.py` lines 1–570:
   - Line 47: `create_stocktake_session`
   - Line 136: `submit_stocktake_counts` (Enforces mode lock D-4)
   - Line 255: `approve_stocktake_session` (Separation of duties & GL Account 5020 posting)
4. **Verify Frontend Gap:**
   Inspect `hotel-frontend/src/pages/InventoryDashboard.js`:
   - Search for `rfq`, `quotation`, `purchaserequisition`, or `stocktake` — observe 0 operational rendering results.
5. **Invalidation Conditions:**
   - If a standalone `PHASE_2_1_REPORT.md` is discovered outside the workspace, this report's caveat on the missing document is superseded.
   - If `current_business_date` is found in an unexamined branch or migration, the Night Audit status must be adjusted from missing to partial.
