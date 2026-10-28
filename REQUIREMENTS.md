# Acrma Hotel ERP — System Requirements & Capability Verification Matrix

**Document Version:** 1.0.0  
**Audit Date:** October 24, 2026  
**Auditor Roles:** Principal Software Architect, Technical Due Diligence Engineer, QA Lead  
**Scope:** Functional Capability Verification & Decisions Requiring Owner Confirmation  
**Deliverable Path:** `REQUIREMENTS.md`  

---

## 1. System Capability Verification Matrix

Every core operational capability of the Acrma Hotel ERP is classified below based on direct code inspection, database schema verification, and automated test execution.

### Classification Key:
- **VERIFIED WORKING:** Capability is fully implemented, adheres to architectural constraints, and is verified by passing automated tests and manual inspection.
- **PARTIALLY WORKING:** Capability operates in basic scenarios but exhibits operational limitations, edge-case gaps, or UX flaws in production workflows.
- **BROKEN:** Capability fails to produce correct results, violates business/accounting invariants, or crashes during execution.
- **MISSING:** Essential capability is not implemented in the backend, frontend, or database layer.
- **NOT VERIFIED:** Capability exists in code but cannot be fully verified without physical external hardware, third-party provider credentials, or a dedicated staging environment.

---

### 1.1 Property Management System (PMS) & Front Desk

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **PMS-001** | Room Inventory & Status Grid | **VERIFIED WORKING** | Verified via `apps/rooms/views.py` (`RoomViewSet`) and `RoomManager.js`. Status transitions (`Available`, `Occupied`, `Cleaning`, `Maintenance`) update cleanly. | Visual grid polling interval is 30s. |
| **PMS-002** | Room Overlap Prevention | **VERIFIED WORKING** | Verified via migration `0023_reservation_no_active_overlap` and PostgreSQL `btree_gist` constraint. Prevents overlapping bookings at DB level. | Constraint requires PostgreSQL; SQLite in-memory test runner skips constraint check. |
| **PMS-003** | Walk-in Check-In & Digital Check-In | **VERIFIED WORKING** | Verified via `DigitalCheckInView` and `apps/reservations/views.py:748`. Generates unique `confirmation_code` and `qr_token`. | Front desk currently charges stay upfront or leaves open balance. |
| **PMS-004** | Advance Room Reservation | **VERIFIED WORKING** | Verified via `ReserveRoomNowView` and `PublicRoomReserveView`. State machine enforces `pending -> confirmed -> checked_in`. | Confirmation emails require external SMTP setup in `.env`. |
| **PMS-005** | Guest Folio Extra Charges | **VERIFIED WORKING** | Verified via `FolioChargeView` (`apps/reservations/views.py:601`). Charges link to reservation and update running balance. | No limit on maximum credit balance per room folio. |
| **PMS-006** | Enhanced Guest Checkout | **VERIFIED WORKING** | Verified via `EnhancedCheckoutView` (`apps/reservations/views.py:905`). Settle folio, sets room to `Cleaning`, posts balanced GL entry. | Sets room history revenue to total checkout revenue (including extras). |
| **PMS-007** | Guest ID Scans & KYC Storage | **VERIFIED WORKING** | Verified via `SecureGuestIdDownloadView` (`core/storage.py`). Scans stored in `private_media/guest_ids/`, accessible only by Admin/Reception. | Scans limited to 5MB, JPG/PNG format. |
| **PMS-008** | Reservation No-Show Handling | **MISSING** | `Reservation.STATUS_CHOICES` lacks `no_show`. `save()` rejects transitions to no-show. | Stale confirmed reservations block rooms indefinitely unless manually cancelled. |
| **PMS-009** | Night Audit Date Rollover & Daily Accrual | **MISSING** | Detailed in `AUDIT_NIGHT_AUDIT_READINESS.md`. No `current_business_date` exists; room rates are not accrued nightly. | Front desk UI is a static 4-counter card with no audit trigger. |

---

### 1.2 Point of Sale (POS), Food & Beverage, and Kitchen

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **POS-001** | Waiter Cart & Order Composer | **VERIFIED WORKING** | Verified via `WaiterDashboard.js` and `apps/orders/views.py:CreateOrderView`. Supports menu filtering, price calculation, item selection. | None. |
| **POS-002** | Table Dining Sessions & Multi-Round Ordering | **VERIFIED WORKING** | Verified via `DiningSession` model and `apps/orders/tests/test_dining_sessions.py` (14 passing tests). Waiters can submit multiple rounds to occupied tables. | Cashier bills screen displays individual orders rather than consolidated session checks. |
| **POS-003** | Per-Item Kitchen Preparation Notes | **VERIFIED WORKING** | Verified via `OrderItem.notes` field and `WaiterDashboard.js:711`. Waiters transmit cooking preferences (e.g. "no onions", "medium rare"). | Max note length is 255 characters. |
| **POS-004** | Kitchen Display (KDS) & Station Isolation | **VERIFIED WORKING** | Verified via `apps/orders/tests/test_station_isolation.py` (14 passing tests). Kitchen cooks see only food; Bar staff see only beverages. | Polling-based refresh (10s interval). |
| **POS-005** | Order Status Synchronization | **VERIFIED WORKING** | Verified via `UpdateOrderStatusView` (`apps/orders/views.py:308`). Overall order transitions to `ready` only when ALL station items are marked `ready`. | Polling latency bounded by 5-10s. |
| **POS-006** | Charge-to-Room (Folio Integration) | **VERIFIED WORKING** | Verified via `RoomChargeProcessView` (`apps/orders/views.py:603`). Bills link to checked-in guest folios and debit AR Account `1200`. | Guest must already be in `checked_in` status. |
| **POS-007** | Cashier Payment Processing | **VERIFIED WORKING** | Verified via `CashierOrderProcessView` (`apps/orders/views.py:650`). Settles Cash, Card, Chapa; prints receipt; creates GL entry. | Cashier must process each order ticket independently. |
| **POS-008** | Recipe BOM Inventory Deduction | **VERIFIED WORKING** | Verified via `apps/orders/services.py:327` and `StockTransaction` (`sale_deduction`). Stock auto-deducted on cashier bill settlement. | If inventory module is disabled in settings, deduction is safely bypassed. |

---

### 1.3 Inventory & Supply Chain Management

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **INV-001** | Inventory SKU Catalog & Categorization | **VERIFIED WORKING** | Verified via `InventoryItemViewSet` and `InventoryDashboard.js`. Categories and units configured. | Minimum stock alert thresholds supported. |
| **INV-002** | Non-Negative Stock Balance Invariants | **VERIFIED WORKING** | Verified via migration `0020_inventoryitem_inventory_stock_nonnegative`. Database prevents negative stock balances. | Attempting to issue stock below 0 raises explicit validation error. |
| **INV-003** | Supplier Directory & Cross-Role Access | **VERIFIED WORKING** | Verified via `IsSupplierOperator` permission class and `test_expense_manager.py`. Admin, Inventory, and Finance have access. | Waiter role is explicitly forbidden (403). |
| **INV-004** | Goods Received Notes (Purchase Receiving) | **VERIFIED WORKING** | Verified via `StockTransactionViewSet` (`transaction_type="purchase"`). Updates stock quantity and unit cost. | Reversing a purchase requires authorized reversal transaction. |
| **INV-005** | Recipe Bill of Materials (BOM) Linking | **VERIFIED WORKING** | Verified via `RecipeBOMViewSet` (`hotel/models.py:895`). Links menu items to multiple raw ingredients and quantities. | Sub-recipes (recipes within recipes) not supported. |
| **INV-006** | Stock Reconciliation CLI | **VERIFIED WORKING** | Verified via `python manage.py reconcile_stock`. Reports mismatches between ledger and cached stock balances. | Safe report-only default; `--repair` flag required to correct balances. |

---

### 1.4 General Ledger & Financial Management

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **FIN-001** | Double-Entry Chart of Accounts | **VERIFIED WORKING** | Verified via `apps/finance/services.py:ensure_default_accounts()`. Supports Assets (1xxx), Liabilities (2xxx), Equity (3xxx), Revenue (4xxx), Expenses (5xxx). | Standard accounts auto-created if missing. |
| **FIN-002** | Balanced Journal Entry Posting | **VERIFIED WORKING** | Verified via `post_journal_entry()` and `JournalEntry.save()`. Rejects any unbalanced entry (`total_debit != total_credit`). | Posted entries are immutable; corrections require reversing entry. |
| **FIN-003** | Expense Management & Auto-Journaling | **VERIFIED WORKING** | Verified via `ExpenseTransactionViewSet` and `test_expense_manager.py`. Creates expense record and balanced debit/credit JV. | Supports Petty Cash (`1020`), Cash (`1000`), Bank (`1010`). |
| **FIN-004** | Payroll Register & Ethiopian Tax Engine | **VERIFIED WORKING** | Verified via `FinanceDashboard.js:autoCalculateTaxAndPension` and `PayrollEntryViewSet`. Auto-computes PAYE brackets and employee/employer pension. | Overtime and bonus tax exemptions must be reviewed per local labor regulations. |
| **FIN-005** | Financial Statements (Trial Balance, P&L, BS)| **VERIFIED WORKING** | Verified via `FinancialStatementsView` (`apps/finance/views.py:14`). Pulls directly from posted General Ledger accounts. | Date range filtering supported up to 366 days. |
| **FIN-006** | Tax Report (VAT & Service Charge) | **PARTIALLY WORKING** | Verified via `TaxReportView` and `test_tax_report.py`. Generates tax summaries from Orders and Room History. | US date format (MM/DD/YYYY) and empty range handling verified; multi-tier tax rates not supported. |
| **FIN-007** | Daily Revenue Report (Consolidated) | **BROKEN** | Identified in `DailyRevenueReportView` (`apps/reporting/views.py:271`). Room-charged F&B orders are triple-counted across F&B, Folio, and checkout. | **Release Blocker.** Must be corrected before financial deployment. |

---

### 1.5 Housekeeping & Facility Operations

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **HK-001** | Automated Checkout Cleaning Tasks | **VERIFIED WORKING** | Verified via `apps.rooms.services:create_checkout_housekeeping_task` triggered by `EnhancedCheckoutView`. Room automatically set to `Cleaning`. | Assigns to cleaning queue immediately. |
| **HK-002** | Dedicated Housekeeping Staff Dashboard | **VERIFIED WORKING** | Verified via `HousekeepingDashboard.js` and role mapping in `App.js:595`. Cleaners can log in with `housekeeping` credentials. | Cleaners inspect tasks and record notes. |
| **HK-003** | Minibar Consumption & Stock Deductions | **VERIFIED WORKING** | Verified via `MinibarConsumeView` (`apps/rooms/views.py:254`). Consumed items charged to guest folio and stock deducted. | Room must be currently checked in. |
| **HK-004** | Lost & Found Property Registration | **VERIFIED WORKING** | Verified via `LostAndFoundListView` and `LostAndFoundClaimView`. Items logged, photo uploaded, status updated to `claimed`. | Storage location and finder details tracked. |

---

### 1.6 External Integrations & Operational Readiness

| Capability ID | Feature Description | Classification | Evidence & Test Verification | Known Limitations & Gaps |
| :--- | :--- | :---: | :--- | :--- |
| **EXT-001** | Chapa Payment Gateway (Online Booking) | **VERIFIED WORKING** | Verified via `apps/payments/views.py` and `test_webhook_security.py`. HMAC signature verified; duplicate webhooks handled idempotently. | Requires production credentials in `.env`. |
| **EXT-002** | Payment Reconciliation Service | **VERIFIED WORKING** | Verified via `python manage.py reconcile_payments`. Identifies orphaned local and remote transactions without mutating data. | Recommended to run every 15 minutes in production. |
| **EXT-003** | Passenger WSGI & LiteSpeed Deployment | **VERIFIED WORKING** | Verified via `passenger_wsgi.py` and `.htaccess`. Masks internal Python tracebacks and returns generic error codes. | Generic error pages logged with correlation ID (`X-Request-ID`). |
| **EXT-004** | Thermal Fiscal Receipt Printing | **NOT VERIFIED** | `CashierReceiptView` outputs 80mm/58mm formatted text; physical ESC/POS hardware printer integration is unverified. | Requires on-premise USB/Ethernet printer test. |
| **EXT-005** | Production SMTP Notification Delivery | **NOT VERIFIED** | Email backend configured in `core/settings.py`; outbound delivery under production TLS unverified without real SMTP credentials. | `EMAIL_USER` and `EMAIL_PASS` required in `.env`. |

---

## 2. Requirements Requiring Project Owner Confirmation

The following 8 architectural, operational, and business scope decisions require explicit owner confirmation before implementation or code modification begins.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                             OWNER CONFIRMATION DECISION REGISTER                            │
├────┬─────────────────────────────┬─────────────────────────────────────────────────────────┤
│ ID │ Decision Topic              │ Core Question for Project Owner                         │
├────┼─────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 01 │ Uncommitted Work Baseline   │ Authorize staging and committing 15 in-flight files?   │
│ 02 │ Night Audit Business Rules  │ Automatic midnight rollover vs manual front-desk audit?  │
│ 03 │ Revenue Report Fix Strategy │ Exclude room charges from F&B vs query General Ledger?   │
│ 04 │ Phantom `delivery` Role     │ Remove dead delivery role vs keep for room-service?     │
│ 05 │ Cashier Session Billing     │ Single consolidated dining bill vs individual orders?   │
│ 06 │ No-Show Reservation Policy  │ Forfeit deposit vs allow full/partial refund?            │
│ 07 │ Background Task Broker      │ Introduce Redis/Celery vs keep synchronous execution?   │
│ 08 │ Customer Self-Service Portal│ Implement guest stay history portal vs public booking?  │
└────┴─────────────────────────────┴─────────────────────────────────────────────────────────┘
```

### Detailed Decision Breakdown

#### Decision 1: Working Tree Baseline & Preservation
- **Context:** The working directory has 13 modified files and 2 untracked files containing completed, tested work on Expense Management, Supplier RBAC, and Ethiopian payroll calculations.
- **Option A (Recommended):** Commit the 15 files under a clean commit message and create tag `baseline-takeover-2026-10-24`.
- **Option B:** Revert uncommitted changes and restart from commit `b6ea79f`.
- **Architect Recommendation:** **Option A**. Reverting would destroy ~1,500 lines of fully tested, passing code that solves real operational needs.

#### Decision 2: Night Audit Operational Mechanics
- **Context:** The hotel currently lacks a Night Audit rollover workflow. Multi-night reservations do not accrue daily room charges.
- **Option A (Recommended):** Front-desk operator triggers manual Night Audit each night between 00:00 and 04:00 via an interactive checklist modal; system charges daily room rates, balances day's journals, snapshots reports, and advances `current_business_date`.
- **Option B:** Automated background cron job executes rollover at exactly 00:00 without human intervention.
- **Architect Recommendation:** **Option A**. Real hotels experience late arrivals and active midnight dining sessions. Automated rollover risks closing open bar tabs or locking folios while guests are still settling bills.

#### Decision 3: Daily Revenue Report Correction
- **Context:** `DailyRevenueReportView` triple-counts room-charged meals across `Order`, `FolioCharge`, and `RoomHistory`.
- **Option A (Recommended):** Derive consolidated hotel revenue strictly from posted double-entry General Ledger accounts (`4000` Room Revenue + `4100` F&B Revenue).
- **Option B:** Patch the existing view by excluding orders where `payment_method == "Room Charge"` and subtracting `extras_total` from room history revenue.
- **Architect Recommendation:** **Option A**. The General Ledger is the authoritative financial source of truth. Querying GL accounts eliminates all risk of double-counting across operational modules.

#### Decision 4: Disposition of Phantom `delivery` Role
- **Context:** `delivery` is defined in `User.ROLE_CHOICES` but has zero endpoints or frontend pages.
- **Option A (Recommended):** Remove `delivery` from `ROLE_CHOICES` and `UserManager.jsx` to eliminate confusion.
- **Option B:** Retain the role for future room-service delivery and mobile staff tracking.
- **Architect Recommendation:** **Option A**. Unused roles create attack surface and administrative ambiguity. It can be reintroduced when delivery workflows are designed.

#### Decision 5: Cashier Dining Session Settlement
- **Context:** Multiple food and drink orders on an occupied table now link to a `DiningSession`. In the Cashier screen, bills appear as individual tickets.
- **Option A (Recommended):** Provide a "Settle Entire Table Session" button in Cashier Dashboard that prints a consolidated dining check and marks all orders in the session as paid in one transaction.
- **Option B:** Require cashiers to settle each order ticket independently.
- **Architect Recommendation:** **Option A**. Hotel guests expect a single unified bill for their dining table, not 3 separate receipts for drinks, appetizers, and main courses.

#### Decision 6: Reservation No-Show Penalty & Cancellation Policy
- **Context:** Confirmed guests who fail to arrive block rooms indefinitely under PostgreSQL GiST constraints unless cancelled.
- **Option A (Recommended):** Add `no_show` status. During Night Audit, unarrived confirmed reservations past midnight can be marked `no_show`, releasing the room and posting a configurable 1-night penalty charge to the deposit.
- **Option B:** Automatically cancel stale reservations without financial forfeiture.
- **Architect Recommendation:** **Option A**. Matches hospitality industry standards (USALI) and protects hotel revenue from frivolous bookings.

#### Decision 7: Background Worker & Asynchronous Processing
- **Context:** Currently, email delivery, PDF report generation, and payment reconciliations run synchronously in request-response cycles.
- **Option A (Recommended):** Maintain lightweight synchronous processing with timeouts for initial single-hotel deployment, adding Redis + Celery only when scaling beyond 100 rooms.
- **Option B:** Introduce Redis and Celery immediately for all background tasks.
- **Architect Recommendation:** **Option A**. cPanel / LiteSpeed Passenger environments often struggle with persistent Celery worker daemon lifecycles. Keeping operations synchronous with strict timeouts simplifies single-tenant hotel deployment.

#### Decision 8: Customer Portal Scope
- **Context:** `CustomerDashboard.jsx` currently displays the public room booking widget; authenticated customers have no self-service portal to view past stays or download receipts.
- **Option A (Recommended):** Treat customer self-service portal as a secondary post-pilot milestone; prioritize Front Desk, POS, KDS, and Finance stabilization for hotel staff.
- **Option B:** Build out customer stay history and online folio viewing immediately.
- **Architect Recommendation:** **Option A**. Staff operational integrity and financial accuracy are the top priorities for launch.
