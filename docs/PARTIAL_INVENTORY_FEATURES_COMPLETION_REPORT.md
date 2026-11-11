# ACRMA HOTEL ERP — PARTIAL INVENTORY FEATURES COMPLETION REPORT

**Document Reference:** ERP-P2-INVENTORY-COMPLETION-2026-V1.0  
**Date:** 5 November 2026  
**Author:** Main Orchestrator & Technical Lead  
**Governing Branch:** `development`  
**Database & Staging Environment:** PostgreSQL 16.12 (`hotel_erp_staging` on localhost:5432) | Django 5.2 / DRF | React 19 SPA (`http://localhost:3000`)

---

## 1. Executive Summary

Pursuant to the Owner Directive **# ACRMA HOTEL ERP — COMPLETE PARTIAL INVENTORY FEATURES**, all four partially implemented inventory and stocktaking capabilities identified in the preceding Feature Existence Audit have been fully implemented, hardened, and verified:

1. **Persistent Expired Stock Alerts**: Multi-tier alert tracking with location/batch granularity, duplicate prevention, automated lifecycle resolution upon batch waste or consumption, and staff acknowledgment audit trail.
2. **Configurable Near-Expiry Notifications**: Configurable tiered warning windows (`near_expiry_1`, `near_expiry_7`, `near_expiry_14`, `near_expiry_30`), unknown perishable expiry detection, and non-destructive reconciliation without premature stock dumping.
3. **Automated Daily Stocktaking**: Background scheduling service executing recurring daily inventory counts at configurable local hotel times (`Africa/Addis_Ababa`, UTC+3), snapshotting theoretical location balances in Draft mode, with duplicate prevention within the same business period.
4. **Automated Weekly & Monthly Stocktaking**: Calendar-aware day-of-week and day-of-month scheduling, service downtime catch-up recovery, scheduler failure visibility, and designated counter notification.

### Core Safeguards & Governance Enforced
- **Zero Premature Stock Destruction**: Expired and near-expiry alerts notify staff and lock lots from POS/KDS service; they never automatically delete inventory or write off assets without authorized waste approval.
- **Strict Stocktake Governance**: Automated scheduler runs snapshot theoretical balances and generate `StocktakeSession` records in `draft` mode. The scheduler **NEVER** records counts, approves variances, or posts General Ledger journal entries.
- **Segregation of Duties (SoD)**: Designated counters for scheduled sessions cannot approve their own sessions (`counted_by != approved_by`), preserving complete SoD compliance.

---

## 2. Changes Made (Files, Models, Migrations, Endpoints, UI Components)

### 2.1 Backend Architecture & Database Layer

| Component | Path | Description |
| :--- | :--- | :--- |
| **Model** | `hotel/models.py`<br>`apps/inventory/models.py` | • Added `InventoryExpiryAlert` model (status, alert_type, threshold_days, batch, item, location, current_quantity, resolution_reason, resolved_at, resolved_by, indexes).<br>• Added `StocktakeSchedule` model (name, frequency, location, category, counting_mode, assigned_staff, is_active, scheduled_time, day_of_week, day_of_month, last_run_at, last_run_status, next_run_at, created_by).<br>• Enhanced `StocktakeSession` with `schedule` (FK) and `scheduled_date` (DateField). |
| **Migration** | `hotel/migrations/0049_inventory_expiry_alerts_and_stocktake_schedules.py` | Additive, non-destructive migration creating `InventoryExpiryAlert`, `StocktakeSchedule`, and adding `schedule` and `scheduled_date` to `StocktakeSession`. Applied cleanly to PostgreSQL 16 staging database. |
| **Business Logic** | `hotel/inventory.py` | Implemented `evaluate_inventory_expiry_alerts()`: scans batches with `current_quantity > 0`, evaluates expiry dates against hotel local date, creates/updates active alerts idempotently, resolves depleted or wasted batches with audit reason, and broadcasts in-app `Notification` rows. |
| **Stocktake Scheduler** | `hotel/stocktaking.py` | Implemented `compute_next_run()` in `Africa/Addis_Ababa` timezone (UTC+3) and `process_due_stocktake_schedules()` using PostgreSQL `select_for_update(of=("self",))` row locking, period idempotency, downtime catch-up, and SoD counter assignment. |
| **CLI / Background Task** | `hotel/management/commands/run_inventory_scheduler.py` | Management command supporting one-shot execution and continuous daemon polling (`--daemon --interval <sec>`). |
| **Serializers** | `apps/inventory/serializers.py` | Added `InventoryExpiryAlertSerializer` (with computed `days_left`), `StocktakeScheduleSerializer` (with computed `is_overdue` and dynamic `next_run_at`), and updated `StocktakeSessionSerializer`. |
| **Views & APIs** | `apps/inventory/views.py` | • `InventoryExpiryAlertViewSet` (`/api/v1/inventory/expiry-alerts/`, `evaluate/`, `<id>/dismiss/`).<br>• `StocktakeScheduleViewSet` (`/api/v1/stocktaking/schedules/`, `<id>/pause/`, `<id>/activate/`, `<id>/trigger-now/`, `upcoming/`). |
| **URL Routing** | `apps/inventory/urls.py` | Registered `inventory/expiry-alerts` and `stocktaking/schedules`. |

### 2.2 Frontend Architecture (React 19 SPA)

| Component | Path | Enhancements |
| :--- | :--- | :--- |
| **Physical Stocktaking Center** | `hotel-frontend/src/pages/stocktaking/StocktakeCenter.jsx` | • Top desk switcher: **"Count Sessions & History"** vs **"Recurring Schedules & Automation"**.<br>• **Schedules Desk**: KPI stats (Active, Daily, Weekly/Monthly, Overdue), recurring schedule table, "+ New Recurring Schedule" modal (daily/weekly/monthly cadence, location, scope, blind/visible mode, counter assignment, scheduled time).<br>• Row actions: **Run Now** (immediate trigger), **Pause / Activate**, and **Delete**.<br>• Count Sessions table enhanced with `Auto: Scheduled` origin badge. |
| **Inventory Dashboard** | `hotel-frontend/src/pages/InventoryDashboard.js` | • **Persistent Expiry Alerts & Surveillance Feed**: embedded in Batches & Expiry tab with real-time KPI cards (Active, Expired, Near-Expiry, Unknown, Resolved).<br>• **⚡ Run Expiry Scan** on-demand evaluation button.<br>• Multi-tier filter pills (`Active`, `Expired`, `Near Expiry`, `Unknown`, `Resolved`, `All Records`).<br>• Alert action shortcuts: **Route Waste** (pre-fills waste form), **Dismiss** (modal dialog with reason input), and **Locate** (filters batch table). |

---

## 3. Database Migration Records and Verification

Migration `0049_inventory_expiry_alerts_and_stocktake_schedules.py` was executed directly against `hotel_erp_staging`:

```text
Operations to perform:
  Apply all migrations: admin, audit, auth, authtoken, contenttypes, finance, hotel, identity, orders, payments, reporting, reservations, rooms, sessions, users
Running migrations:
  Applying hotel.0049_inventory_expiry_alerts_and_stocktake_schedules... OK
```

### PostgreSQL 16 Staging Table Verification
Direct inspection of PostgreSQL 16 relations in `hotel_erp_staging`:
- `hotel_inventoryexpiryalert`: Table created with primary key, foreign keys to `hotel_stockbatch`, `hotel_inventoryitem`, and `hotel_stocklocation`, plus composite btree indexes `exp_alert_status_type_idx` and `exp_alert_batch_type_idx`.
- `hotel_stocktakeschedule`: Table created with frequency, counting_mode, next_run_at index, and audit foreign keys.
- `hotel_stocktakesession`: Foreign key `schedule_id` and indexed `scheduled_date` added.

---

## 4. Concurrency & Regression Test Results

### 4.1 Dedicated Expiry Alerts & Stocktake Schedules Test Suite
A dedicated 13-test integration suite (`apps/inventory/tests/test_expiry_alerts_and_schedules.py`) was executed against PostgreSQL 16:

```text
Ran 13 tests in 71.705s

OK
Destroying test database for alias 'default'...
Found 13 test(s).
System check identified no issues (1 silenced).
```

| Test Case | Domain | Verification Mandate | Result |
| :--- | :--- | :--- | :--- |
| `test_01` | Expiry Alerts | Expired batch (`expiry_date < today`) creates active critical alert with threshold=0 | **PASS** |
| `test_02` | Expiry Alerts | Near-expiry warning tiers (1d, 7d, 14d, 30d) generate respective alert tiers | **PASS** |
| `test_03` | Expiry Alerts | Perishable batch without expiry date generates `unknown_expiry` critical alert | **PASS** |
| `test_04` | Expiry Alerts | Evaluation idempotency and current on-hand quantity synchronization without duplicate rows | **PASS** |
| `test_05` | Expiry Alerts | Lifecycle resolution: alerts automatically resolve when batch quantity hits 0 or is wasted | **PASS** |
| `test_06` | Security/RBAC | Manager dismisses alert with audit reason; unauthorized waiter is rejected (403 Forbidden) | **PASS** |
| `test_07` | Expiry APIs | `POST /api/v1/inventory/expiry-alerts/evaluate/` returns summary counts | **PASS** |
| `test_08` | Scheduling | Schedule creation API sets frequency, location, mode, and computes `next_run_at` | **PASS** |
| `test_09` | Scheduling | Due schedule execution creates draft session snapshotting theoretical stock without counting or GL posting | **PASS** |
| `test_10` | Scheduling | Period idempotency: repeated execution in same period prevents duplicate sessions | **PASS** |
| `test_11` | Scheduling | Service downtime recovery: missed runs generate 1 catch-up session and advance `next_run_at` | **PASS** |
| `test_12` | Schedule APIs | Pause, activate, trigger-now, and upcoming endpoints execute properly | **PASS** |
| `test_13` | SoD Security | Segregation of Duties: counter assigned to scheduled session cannot approve it (403 Forbidden) | **PASS** |

### 4.2 Stocktaking Management Regression Suite
The authoritative dual-mode stocktaking management test suite (`apps/inventory/tests/test_stocktaking_management.py`) was re-verified:

```text
Ran 12 tests in 31.541s

OK
```
All existing physical stocktaking functions, zero-leak blind count security, Decision D-4 mode locking, two-phase recount workflows, and balanced GL postings remain 100% regression-free.

---

## 5. Background Job Execution Logs

The background scheduler management command was verified in one-shot execution against `hotel_erp_staging`:

```text
.venv\Scripts\python.exe manage.py run_inventory_scheduler --verbose
[2026-11-05 11:30:12+03:00] Starting Hotel ERP Inventory Background Scheduler (Africa/Addis_Ababa)
[2026-11-05 11:30:13+03:00] Evaluating inventory expiry alerts...
[2026-11-05 11:30:13+03:00] Expiry Alerts: 2 created, 0 updated, 0 resolved. Active total: 2.
[2026-11-05 11:30:13+03:00] Processing due stocktake schedules...
[2026-11-05 11:30:14+03:00] Stocktake Schedules: 1 executed, 0 skipped, 0 failed.
[2026-11-05 11:30:14+03:00] One-shot scheduler execution finished successfully.
```

Subsequent invocation within the same period demonstrated complete idempotency:
```text
[2026-11-05 11:30:25+03:00] Expiry Alerts: 0 created, 2 updated, 0 resolved. Active total: 2.
[2026-11-05 11:30:25+03:00] Stocktake Schedules: 0 executed, 1 skipped (already_executed_for_period), 0 failed.
```

---

## 6. Real-Browser Acceptance Test Results with Screenshots

An automated real-browser acceptance test suite (`scratch/test_browser_partial_features.py`) was executed using **Selenium WebDriver 4.52 (Headless Google Chrome)** against the live React 19 application (`http://localhost:3000`) and Django backend (`http://127.0.0.1:8000`).

### Browser Verification Summary
- **13 Steps Executed**: 100% Passed.
- **Visual Artifacts**: 11 screenshots captured and archived in `docs/screenshots/partial_inventory/`.

| Step | Action & Verification | DOM / API Assertion | Result | Screenshot |
| :---: | :--- | :--- | :---: | :--- |
| **1** | Open app & authenticate | Access token stored in `localStorage` | PASS | `01_inventory_dashboard_landing.png` |
| **2** | Sidebar navigation to Inventory Control | Dashboard loads inventory module | PASS | `01_inventory_dashboard_landing.png` |
| **3** | Open Batches & Expiry Tab | Surveillance feed & stats grid rendered | PASS | `02_batches_and_expiry_tab.png` |
| **4** | Click `Run Expiry Scan` | Evaluates batches; banner displays active count | PASS | `03_expiry_scan_completed.png` |
| **5** | DOM inspection for alert tiers | `BATCH-EXP-STAGE-01` (Expired = True)<br>`BATCH-NEAR-STAGE-07` (Near-Expiry = True)<br>`BATCH-UNK-STAGE-99` (Unknown = True) | PASS | `03_expiry_scan_completed.png` |
| **6** | Dismiss Alert Modal Workflow | Filled reason; alert transitions to `DISMISSED` | PASS | `04_dismiss_alert_modal.png`<br>`05_alert_dismissed_state.png` |
| **7** | Sidebar navigation to Physical Stocktaking | Stocktake Center loads sessions table | PASS | `06_stocktake_center_sessions.png` |
| **8** | Switch to Schedules & Automation Tab | Recurring schedules desk rendered | PASS | `07_stocktake_schedules_desk.png` |
| **9** | Open `+ New Recurring Schedule` modal | Form rendered with daily/weekly/monthly controls | PASS | `08_create_schedule_modal.png` |
| **10** | Submit Daily Schedule form | Schedule row appears in table with `Active` status | PASS | `09_schedule_created_table.png` |
| **11** | Trigger immediate run via `Run Now` | Success notification; session spawned | PASS | `10_schedule_triggered_notification.png` |
| **12** | Switch to Count Sessions Tab | Generated session rendered with `Auto: Scheduled` badge | PASS | `11_generated_scheduled_session_in_table.png` |
| **13** | Database Audit in PostgreSQL 16 | Verified `StocktakeSchedule` & `StocktakeSession` linkage | PASS | Audited in `hotel_erp_staging` |

---

## 7. Security and Accounting Verification

1. **Blind Mode Security**: Automated scheduled sessions created under `blind` mode mask theoretical quantities from counters. Theoretical stock balances are strictly stored on the server-side snapshot and never exposed via counter endpoints.
2. **Segregation of Duties (SoD)**: The staff designated as counter on a recurring schedule cannot approve the session upon count completion. Attempting to approve via `POST /api/v1/stocktaking/sessions/<id>/approve/` as the counter returns `403 Forbidden` with `"Separation of duties violation: Counted by and approved by must be different users."`
3. **Draft Snapshot Safety**: The automated scheduler strictly creates `draft` sessions. It **never** adjusts stock or touches the General Ledger. GL postings occur only when an independent supervisor reviews physical counts and approves the session, posting balanced debits and credits between `Account 1300` (Inventory Asset) and `Account 5020` (Variance Expense).
4. **Food Safety Protection**: Expired batches flagged by `InventoryExpiryAlert` are locked from dining room service and POS menu items, preventing expired goods from reaching guests.

---

## 8. Remaining Partial Features or Non-Functional Items

**Zero partial features remain.** All four targeted areas:
- Persistent expired stock alerts
- Configurable near-expiry notifications
- Automated daily stocktaking
- Automated weekly and monthly stocktaking

are now 100% functional, integrated across the React frontend and Django backend, covered by automated unit and browser test suites, and verified in the live PostgreSQL 16 staging environment.

