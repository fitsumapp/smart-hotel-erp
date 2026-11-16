# ACRMA HOTEL ERP — PRODUCTION DEPLOYMENT & PREFLIGHT AUDIT REPORT

**Document Identifier:** ACRMA-ERP-PROD-DEP-2026-11-16  
**Project:** ACRMA Hotel ERP (`fitsumapp/smart-hotel-erp`)  
**Deployment Target:** Production Environment (`https://hotelerp.acrmatech.com`)  
**Target Host Architecture:** cPanel CloudLinux / LiteSpeed Web Server (IP: `135.181.160.205`)  
**Target Database Architecture:** Neon.tech Serverless PostgreSQL (`DATABASE_URL`, SSL required)  
**Evaluator:** Release Engineering & Deployment Preflight Gate Team  
**Evaluation Date:** November 16, 2026  

---

## 1. Executive Deployment Decision

Pursuant to Section 5, 6, and 10 of the **Owner Authorization Directive**, every release candidate must satisfy all engineering acceptance gates AND all production deployment preflight gates prior to accessing or altering production environments.

Under Section 10 ("FINAL DECISION — NO AMBIGUOUS COMPLETION"):
> *"If any critical defect, unsafe migration, missing backup, failed validation, or deployment risk remains: Stop before deployment or initiate rollback if necessary. Do not bypass the failed gate. Document the exact failure. Identify the affected component. Provide evidence and the minimum required corrective action."*

### Final Gate Assessment

| Preflight Gate | Requirement | Audit Finding | Gate Verdict |
| :--- | :--- | :--- | :---: |
| **Gate 1: Engineering Acceptance** | 100% test pass, zero regressions, browser verification, invariant math verified | 79/79 backend tests pass; 19/19 frontend tests pass; React build compiled; 8 browser workflows validated with 0 console errors. | **PASSED** |
| **Gate 2: Database Protection (Backup)** | Verified production database backup file created and readable before any schema changes | **BLOCKED:** Remote production database credentials (Neon.tech `DATABASE_URL`) are strictly excluded from local development `.env` per security rules ("Do not connect to Neon production"). No production `pg_dump` could be generated or verified locally. | **FAILED / BLOCKED** |
| **Gate 3: Host Deployment Access** | Documented, sanctioned deployment path to production host | **BLOCKED:** SSH ports 22 and 2222 on `135.181.160.205` are closed/refused. Deployment to cPanel web root requires administrative cPanel web console or authenticated FTP credentials not present in this workspace. | **FAILED / BLOCKED** |
| **Gate 4: Schema Migration Safety** | Migrations must be non-destructive, non-data-changing to historical records | Migrations `0051` and `0052` are 100% additive (`UnfulfilledStockDeduction` table, enum choices). Zero historical data modifications. | **PASSED** |
| **Gate 5: Staging Non-Contamination** | Local staging database must remain pristine | Verified: Table counts before and after testing are identical (27 items, 42 batches, 55 stock transactions, 120 JVs). 0 rows mutated. | **PASSED** |

### Formal Verdict
**FINAL STATUS: BLOCKED — PRODUCTION DEPLOYMENT NOT AUTHORIZED BY THE ACCEPTANCE GATES.**

*In strict adherence to the project instructions, deployment was halted at Step Four (Production Deployment Preflight) because the mandatory verified production database backup cannot be taken without authorized production Neon database access.*

---

## 2. Preflight Audit Findings & Root Cause of Block

### 2.1 Production Database Isolation & Missing Backup (Preflight Gate 2)
- **Mandate:** *"Create a verified production database backup. Confirm the backup file exists and is readable. Confirm a recovery procedure is available... Never use production data to run test suites... Do not connect to or modify Neon production."*
- **Empirical Reality:**
  - Local `.env` specifies: `DJANGO_ENV=development`, `DB_NAME=hotel_erp_staging`, `DB_HOST=localhost`.
  - `DATABASE_URL` is empty.
  - Production Neon database credentials are not accessible within this local development environment.
  - While this guarantees 100% compliance with the mandate not to corrupt or connect test suites to Neon, it prevents the generation of an empirical pre-deployment `pg_dump` of the live production database from this workstation.
  - Attempting to push migrations or code blindly to production without a verified, tested backup file would violate the core directive of Database Protection.

### 2.2 Production Host Connectivity & Deployment Pipeline (Preflight Gate 3)
- **Host:** `hotelerp.acrmatech.com` (`135.181.160.205`)
- **Port Probes:**
  - Port 443 (HTTPS): **OPEN** (Returns HTTP 200 on `/`, LiteSpeed Web Server active).
  - Port 22 (SSH): **REFUSED / CLOSED**.
  - Port 2222 (Alternative SSH): **REFUSED / CLOSED**.
- **Deployment Process Analysis:**
  As documented in `docs/PRODUCTION_VALIDATION_REPORT.md` Section 2.3, deployments to `https://hotelerp.acrmatech.com` are performed via cPanel File Manager extraction of `build.zip` into `/home/acrmate1/hotelerp.acrmatech.com/public_html` and restarting CloudLinux Passenger WSGI via the cPanel Python Selector.
  Because no automated CI/CD push pipeline or SSH access exists between this workstation and the live cPanel server, executing the file transfer requires explicit cPanel operator actions.

---

## 3. Verified Release Artifacts Ready for Production

The engineering implementation is fully completed, packaged, and verified. Once the production database backup is performed by the database administrator, the following audited artifacts are ready for immediate promotion:

### 3.1 Git Release Identifier
- **Target Branch:** `development` $\rightarrow$ `main`
- **Starting HEAD Commit:** `97d560c77f80799035b89633d9e589d0937808cb`
- **Release Package Description:** ACRMA Hotel ERP Inventory Module Stabilization & POS Decoupling Release Candidate.

### 3.2 Compiled Production Frontend Artifact
- **Build Directory:** `hotel-frontend/build/`
- **Compiled Bundle Signature:**
  - JavaScript Bundle: `hotel-frontend/build/static/js/main.363f9de7.js` (350.44 kB gzip)
  - CSS Stylesheet: `hotel-frontend/build/static/css/main.c6610b91.css` (3.84 kB gzip)
  - Chunk Artifact: `hotel-frontend/build/static/js/453.a71498bb.chunk.js` (1.77 kB gzip)
- **Features Verified in Build:**
  - Integrated 3-Tier `StockTransferCenter` UI (`hotel-frontend/src/pages/transfers/StockTransferCenter.jsx`).
  - Server-side paginated Stock Ledger (50 records/page with deterministic sort).
  - CORS header support for `idempotency-key`.
  - Backward-compatible Purchase Order GRN intake.

### 3.3 Database Migrations Ready for Neon
1. `hotel/migrations/0051_unfulfilled_stock_deduction_and_order_status.py`:
   - Adds non-blocking `inventory_deduction_status` column to `hotel_order`.
   - Creates `hotel_unfulfilledstockdeduction` table.
   - **Classification:** 100% Additive, Zero Historical Data Modification.
2. `hotel/migrations/0052_alter_stocktransaction_transaction_type.py`:
   - Extends choices for `transaction_type` on `hotel_stocktransaction`.
   - **Classification:** 100% Non-destructive AlterField.

---

## 4. Controlled Production Deployment & Recovery Runbook

To complete the production deployment safely once authorized administrator access is provided:

### Phase 1: Production Database Backup (Mandatory Gate)
Execute on the server or workstation with authorized Neon access:
```bash
# 1. Take snapshot of Neon production database
pg_dump --format=custom --no-owner --no-acl --verbose \
  "$NEON_DATABASE_URL" \
  --file="/srv/backups/neon_prod_backup_$(date +%Y%m%d_%H%M%S).dump"

# 2. Verify backup file readability
pg_restore --list "/srv/backups/neon_prod_backup_$(date +%Y%m%d_%H%M%S).dump" | head -n 20
```

### Phase 2: Code Promotion & Migration Execution
```bash
# 1. Merge verified development branch into main
git checkout main
git merge --ff-only development
git push origin main

# 2. Run approved migrations on Neon
python manage.py migrate hotel 0051 --settings=core.settings_production
python manage.py migrate hotel 0052 --settings=core.settings_production

# 3. Collect static files
python manage.py collectstatic --noinput --settings=core.settings_production
```

### Phase 3: Frontend Deployment to cPanel
```bash
# 1. Package frontend build
cd hotel-frontend
zip -r ../build_release_v1.1.0.zip build/

# 2. Upload and extract build_release_v1.1.0.zip to cPanel document root
# (/home/acrmate1/hotelerp.acrmatech.com/public_html)

# 3. Restart Passenger WSGI application
touch /home/acrmate1/hotelerp.acrmatech.com/tmp/restart.txt
```

### Phase 4: Emergency Rollback Procedure
If any unexpected production anomaly occurs post-deployment:
1. **Frontend Rollback:** Restore previous `index.html` and `static/` from `buildnov11.zip` in cPanel file manager.
2. **Backend Rollback:**
   ```bash
   git checkout 97d560c77f80799035b89633d9e589d0937808cb
   touch /home/acrmate1/hotelerp.acrmatech.com/tmp/restart.txt
   ```
3. **Database Rollback (if necessary):**
   ```bash
   python manage.py migrate hotel 0050 --settings=core.settings_production
   ```
   *(Note: Because migrations 0051 and 0052 are strictly additive, rolling back code without rolling back database schema does not break existing database tables or historical transactions).*

---

## 5. Attestation of Data Preservation

- **Historical Records:** Zero historical stock batches, stock transactions, or journal entries in either staging or production were altered, deleted, or reclassified.
- **Reconciliation Scripts:** No automated balance adjustment or cleanup scripts were executed.
- **Trial Balance:** General Ledger double-entry equilibrium was maintained throughout all test cycles.

