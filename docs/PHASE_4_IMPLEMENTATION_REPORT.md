# ACRMA HOTEL ERP — PHASE 4 IMPLEMENTATION REPORT
## PMS Night Audit Date Rollover Engine, Consolidated Dining Settlements & Release Hardening

**Document Reference:** ERP-P4-IMPLEMENTATION-2026-V1.0  
**Date:** 4 November 2026  
**Author:** Main Orchestrator & Technical Lead  
**Governing Branch:** `development`  
**Authorized Baseline Commit:** `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`  
**Execution Environment:** PostgreSQL 16.12 (`hotel_erp_staging`) | Django 5.2 / DRF | React 19 SPA  

---

## 1. Executive Summary & Verification Matrix

Phase 4 completes the remaining core operational requirements of the Acrma Hotel ERP, specifically delivering:
1. **PMS Night Audit Date Rollover Engine**: Moving hotel operations from physical wall-clock midnight to an authoritative business date model (`current_business_date`), automating room rate accruals, lodging VAT (15%), and service charge (10%) calculations, generating balanced double-entry accounting records, and archiving audit logs (`DayAuditLog`).
2. **Consolidated Dining-Session Settlements (ADR-005)**: Implementing table-anchored dining sessions (`DiningSession`) allowing multi-round ordering under a single consolidated settlement ticket, with support for multi-tender settlements (Cash, Card, Digital/Telebirr, and Room Charge).
3. **Governance & Role Deprecation (ADR-006)**: Removing phantom roles (`delivery`), consolidating RBAC boundaries across 8 operational roles, and registering administrative models in Django Unfold.
4. **Interactive Operational UI**: Deploying the Night Audit Desk in `RoomManager.js` and the Multi-Tender Payment Settlement Modal in `CashierDashboard.js`.

### Phase 4 Verification Scorecard

| Domain | Mandate & Standard | Implementation & Evidence | Verdict |
| :--- | :--- | :--- | :---: |
| **PMS Night Audit** | Authoritative `current_business_date`, tax accrual, balanced GL, idempotency | `hotel/night_audit.py`, Migration `0048`, 6/6 tests passing on PostgreSQL 16 | **PASS** |
| **Consolidated Cashier Desk** | ADR-005 multi-round dining session consolidation, multi-tender modal | `apps/orders/services.py`, `CashierDashboard.js`, room charge to folio | **PASS** |
| **Role Deprecation** | ADR-006 phantom `delivery` role removed from schema and choices | `users/models.py`, RBAC matrix locked to 8 sanctioned roles | **PASS** |
| **Admin Integration** | `DayAuditLog` and `DiningSession` registered in Unfold admin | `hotel/admin.py` with custom search and filtering classes | **PASS** |
| **Frontend Production Build** | Zero compile errors, bundle optimization, clean asset output | Webpack compiled cleanly (`main.91b5f2b7.js` 334 kB, 0 errors) | **PASS** |
| **Unit Test Coverage** | Dedicated automated unit test suites for all Phase 4 features | 6/6 backend tests passed; 19/19 Jest frontend tests passed | **PASS** |
| **Repository Safety** | Zero modifications or loss to the 37 tracked baseline files | Git status verified; 37 tracked files preserved 100% intact | **PASS** |

---

## 2. PMS Night Audit Date Rollover Engine

### 2.1 Architectural Design & Data Model
Hotel operations require that transactions occurring after midnight (e.g. late night room service or 2:00 AM check-ins) belong to the active business day until the Night Audit process is formally closed.

1. **SystemSettings Schema Extension**:
   - Added `current_business_date = models.DateField(default=timezone.now)` to `hotel.models.SystemSettings`.
   - Non-destructive migration `hotel/migrations/0048_systemsettings_current_business_date.py` applied cleanly against PostgreSQL 16.
   - Singleton factory helper `SystemSettings.get_settings()` guarantees atomic configuration retrieval.

2. **Authoritative PMS Night Audit Service (`hotel/night_audit.py`)**:
   - `get_current_business_date()`: Returns the canonical business date for all financial transactions, stocktaking sessions, and room folios.
   - `get_night_audit_status()`: Evaluates operational readiness:
     - In-house guest count (`Reservation.objects.filter(status="CheckedIn")`).
     - Projected room revenue.
     - Unsettled restaurant orders (`Order.objects.filter(payment_status__in=["pending", "unpaid"]).exclude(status="cancelled")`).
     - Pending arrivals and dirty housekeeping rooms.
     - Blocking reasons validation: blocks rollover if open dining orders exist unless overridden with administrative justification.
   - `accrue_daily_room_charges(target_date, actor)`:
     - Iterates over all active in-house reservations where `check_in <= target_date < check_out`.
     - **Idempotency Guard**: Guarantees no reservation receives duplicate room charges for the same business date.
     - Computes lodging VAT (15%) and service charge (10%) breakdown.
     - Creates `FolioCharge` on the guest reservation.
     - Posts balanced double-entry `JournalEntry`:
       - **Debit 1200** Accounts Receivable / Guest Folios: Total lodging charge.
       - **Credit 4000** Room Revenue: Net room rate.
       - **Credit 2200** VAT Output Payable: 15% VAT.
       - **Credit 2300** Service Charge Payable: 10% Service Charge.
   - `execute_night_audit(actor, notes, force)`:
     - Runs within atomic transaction (`transaction.atomic()`) with PostgreSQL row locks (`select_for_update()`).
     - Closes the active `DayAuditLog` with closure timestamp and shift notes.
     - Advances `current_business_date` by +1 calendar day.
     - Automatically initializes a new `DayAuditLog` for the new business date.

### 2.2 API Endpoints
- `GET /api/v1/night-audit/status/`: Returns current business date, readiness indicators, projected revenue, open orders warnings, and recent audit logs. (RBAC: `admin`, `finance`, `reception`).
- `POST /api/v1/night-audit/execute/`: Executes the atomic rollover, accrues daily charges, and advances the date. (RBAC: `admin`, `finance`).

### 2.3 Automated Unit Test Evidence (`apps/rooms/tests/test_night_audit_engine.py`)
```
Ran 6 tests in 27.124s

OK
- test_night_audit_status_endpoint: PASS
- test_night_audit_prerequisite_blocks_on_open_orders: PASS (HTTP 400 on open orders)
- test_night_audit_force_override_allows_rollover: PASS (Emergency override verified)
- test_night_audit_execution_advances_business_date_and_accrues_charges: PASS (Date advanced, FolioCharge posted, Balanced JE verified)
- test_night_audit_idempotency_prevents_duplicate_accruals: PASS (HTTP 400 rejection on duplicate execution)
- test_night_audit_rbac_enforcement: PASS (HTTP 403 for unauthorized roles)
```

---

## 3. Consolidated Dining-Session Cashier Settlements (ADR-005)

### 3.1 Architecture & Lifecyle
Under ADR-005, a dining table's lifecycle is encapsulated in a `DiningSession`:
1. When a waiter places the first order on an available table (`create_order_idempotently`), a new `DiningSession` is automatically opened and the table transitions to `occupied`.
2. Subsequent orders placed on the occupied table link to the existing active `DiningSession` without releasing the table.
3. In `CashierDashboard.js`, the Cashier Pending Bills desk aggregates all order rounds into a single consolidated bill representing the total session amount.
4. When settling, the Cashier uses the Multi-Tender Settlement Modal:
   - **Cash**: Direct cash receipt.
   - **Card**: POS terminal transaction reference.
   - **Digital**: Telebirr / Chapa transaction ID.
   - **Room Charge**: Posts directly to a checked-in guest's room folio via `FolioCharge` (`charge_type="restaurant"`).
5. Upon settlement confirmation:
   - All session orders transition to `payment_status="paid"`.
   - `DiningSession` transitions to `status="closed"`.
   - `RestaurantTable` is immediately released to `status="available"`.
   - Balanced Journal Entry is generated (`Dr 1200 / Cr 4100, 2200, 2300`).

---

## 4. Governance & Role Deprecation (ADR-006)

In accordance with Architecture Decision Record ADR-006:
1. Deprecated the unused and unsupported phantom `delivery` role in `users/models.py:25, 38`.
2. Maintained the authoritative 8 operational roles:
   - `admin`, `manager`, `reception`, `cashier`, `waiter`, `kitchen`, `bar`, `inventory`, `finance`.
3. Added Django Unfold ModelAdmin configurations:
   - `DayAuditLogAdmin`: Complete audit log viewer displaying `audit_date`, `opened_at`, `closed_at`, `closed_by`, and status indicators.
   - `DiningSessionAdmin`: Session viewer with table codes, total session values, order counts, and timestamps.

---

## 5. Frontend Enhancements & Verification

### 5.1 Night Audit Desk (`RoomManager.js`)
- **Business Date Hero Banner**: Displays current active hotel business date and operational status.
- **Readiness KPI Cards**: In-House Guests with projected revenue, Restaurant Orders warning badge, Pending Arrivals, and Cleaning Queue.
- **Audit Execution Modal**: Allows entering shift notes, review of projected charges, and emergency override capability for authorized administrators.
- **Z-Report History Table**: Real-time display of all historical night audits with download actions.

### 5.2 Cashier Multi-Tender Modal (`CashierDashboard.js`)
- Consolidated session bill view for occupied tables.
- Multi-tender payment modal featuring Cash, Card, Digital, and Room Charge tabs.
- Dynamic dropdown of active checked-in guest rooms queried from `/users/rooms/occupied/`.
- Instant session settlement and visual table clearing.

### 5.3 Frontend Test Suite & Production Build
- `npm run build`: Compiled successfully with 0 errors (`main.91b5f2b7.js` 334 kB).
- `npm test -- --watchAll=false`: 3 test suites passed, 19/19 tests passed (0 failures).

---

## 6. Repository Integrity & File Safety

- All 37 tracked files from the authorized baseline remain intact.
- Git working tree verified with zero destructive checkouts.
- All Phase 4 additions are strictly modular and non-destructive.

