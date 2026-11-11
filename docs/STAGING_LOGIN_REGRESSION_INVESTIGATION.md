# STAGING LOGIN REGRESSION — FORENSIC INVESTIGATION & AUDIT REPORT

**Document Reference:** `docs/STAGING_LOGIN_REGRESSION_INVESTIGATION.md`  
**Classification:** P1 Forensic Audit Deliverable — Read-Only Investigation  
**Investigation Date:** 5 November 2026  
**Investigator:** Main Orchestrator & Technical Lead  
**Governing Branch:** `development`  
**Baseline Commit:** `9d964376345ac47cee79ca7aa2bdc1a41dc71fe2`  
**Investigation Scope:** Identification of root cause for login failures with `inventory@gmail.com`, `kitchen@gmail.com`, and related accounts. Zero state modifications made.

---

## 1. Executive Summary

| Audit Item | Status | Verified Finding |
| :--- | :---: | :--- |
| **Account Destruction / Deletion** | **CLEARED** | **Zero accounts were deleted.** All 10 original accounts (`inventory@gmail.com`, `kitchen@gmail.com`, `admin@example.com`, `cashier@gmail.com`, etc.) are 100% intact. |
| **Password Hash Corruption** | **CLEARED** | Password hashes in the original database are valid, uncorrupted PBKDF2 SHA-256 strings. |
| **Authentication Code Regression** | **CLEARED** | Dual-lookup (`Q(email__iexact=...) \| Q(username__iexact=...)`) is active, functional, and identical to the original implementation. |
| **Frontend/Backend Contract Mismatch** | **CLEARED** | Payload `{ username: "<email>", password: "<pwd>" }` is fully compatible with the serializer and service layer. |
| **Root Cause** | **IDENTIFIED** | **Database target redirection in `.env`**: The active server was switched to `hotel_erp_staging` (seeded with test personas having empty emails) instead of `hotel_erp_db` (where the user accounts reside). |

---

## 2. Forensic Findings by Directive Requirement

### 2.1 Database Connection Verification & Comparison
- **Configuration Default (`core/settings.py:141`):**  
  `"NAME": os.getenv("DB_NAME", "hotel_erp_db")`
- **Template Configuration (`.env.example`):**  
  `DB_NAME=hotel_erp_db`
- **Active Environment File (`.env`):**  
  `DB_NAME=hotel_erp_staging`
- **Active Process Verification:**  
  The active Django process (`PID 3460`, port 8000) loaded `.env` with `DB_NAME=hotel_erp_staging`.
- **Database Catalog on PostgreSQL 16.12 (`localhost:5432`):**
  1. `hotel_erp_db` — The primary database containing the original user accounts, operational operational data, room inventories, and historical transactions.
  2. `hotel_erp_staging` — The secondary database provisioned specifically for Phase 2.1 Concurrency Verification and subsequent staging testing suites.

---

### 2.2 Account Search in Current Staging Database (`hotel_erp_staging`)
A direct read-only SQL query against `hotel_erp_staging.users_user` revealed:
- **Total User Records:** 32 records.
- **Email Values:** **All 32 records have `email = ''` (empty string).**
- **Usernames Present:** Staging test personas created during Phase 2–4 tests:
  - `staging_admin`, `staging_gm`, `staging_finance`, `staging_controller`, `staging_procurement`, `staging_storekeeper`, `staging_auditor`, `staging_receiving`, `sec_hotel_admin`, `admin_proc2`, etc.
- **Target Account Search Result:**
  - `SELECT * FROM users_user WHERE email ILIKE '%inventory%' OR username ILIKE '%inventory%';` -> **0 rows returned**.
  - `SELECT * FROM users_user WHERE email ILIKE '%kitchen%' OR username ILIKE '%kitchen%';` -> **0 rows returned**.

---

### 2.3 Account Search in Original Database (`hotel_erp_db`)
A direct read-only SQL query against `hotel_erp_db.users_user` confirmed that **all original user accounts are completely intact and untouched**:

| User ID | Username | Email | Role | Is Active | Password Algorithm |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `admin` | `admin@example.com` | `admin` | `True` | `pbkdf2_sha256` (Valid) |
| **2** | `waiter` | `waiter@gmail.com` | `waiter` | `True` | `pbkdf2_sha256` (Valid) |
| **3** | `cashier` | `cashier@gmail.com` | `cashier` | `True` | `pbkdf2_sha256` (Valid) |
| **4** | `kitchen` | `kitchen@gmail.com` | `kitchen` | `True` | `pbkdf2_sha256` (Valid) |
| **5** | `finance` | `finance@gmail.com` | `finance` | `True` | `pbkdf2_sha256` (Valid) |
| **6** | `inventory` | `inventory@gmail.com` | `inventory` | `True` | `pbkdf2_sha256` (Valid) |
| **7** | `reacp` | `reacp@gmail.com` | `reception` | `True` | `pbkdf2_sha256` (Valid) |
| **8** | `bar` | `bar@gmail.com` | `bar` | `True` | `pbkdf2_sha256` (Valid) |
| **9** | `testuser` | `test@example.com` | `staff` | `True` | `pbkdf2_sha256` (Valid) |
| **10** | `superadmin` | `superadmin@example.com` | `superadmin` | `True` | `pbkdf2_sha256` (Valid) |

**Conclusion:** No accounts were deleted, overwritten, or modified.

---

### 2.4 History & Provenance Analysis (What Changed, When, and Why)
- **Event:** On November 4, 2026, the Owner Directive mandated:  
  *"Execute a dedicated concurrency verification against the isolated PostgreSQL 16 staging database... simulate simultaneous RFQ allocation attempts... verify transaction rollback."*
- **Action Taken:** To prevent polluting or corrupting operational data in `hotel_erp_db`, the engineering team provisioned `hotel_erp_staging` and set `DB_NAME=hotel_erp_staging` in `.env`.
- **Side Effect:** After automated concurrency, integration, and release preflight suites were completed, `.env` remained pointed to `hotel_erp_staging`. Because test seed fixtures only populated `username` (leaving `email=""`), logging in with email identifiers against `hotel_erp_staging` returned "User does not exist."

---

### 2.5 Email-Based Login Support & Git History Audit
- **Model Definition (`apps/users/models.py:34`):**
  - `USERNAME_FIELD = "username"`
  - `email = models.EmailField(blank=True)`
- **Authentication Service (`apps/identity/services.py:117-122`):**
  ```python
  normalized = (username_or_email or "").strip().lower()
  user = User.objects.filter(
      Q(email__iexact=normalized) | Q(username__iexact=normalized)
  ).first()
  ```
- **Git Audit:**
  - No changes were made that broke or removed email-based login.
  - The authentication backend has always supported dual lookup (`email` or `username`).
  - The reason `inventory@gmail.com` worked previously is that it exists in `hotel_erp_db`. It only stopped working when requests hit `hotel_erp_staging` where `email=""`.

---

### 2.6 Frontend & Backend Contract Compatibility
- **Frontend Submission (`frontend/src/services/auth.service.js`):**
  - Submits JSON to `POST /api/v1/auth/login/`:
    ```json
    {
      "username": "<email or username entered by user>",
      "password": "<plain text password>"
    }
    ```
- **Backend Serializer (`apps/identity/serializers.py`):**
  - Accepts `username` (CharField) and `password` (CharField).
  - Passes `username` directly into `authenticate_user(username_or_email=username, ...)`.
- **Verdict:** The contract is 100% compatible. No serialization or payload schema mismatches exist.

---

### 2.7 Authentication Logs and Lockout Status
Inspection of `hotel_erp_staging.users_authenticationattempt`:
- Recent records indicate 6 consecutive login attempts for identifier `inventory@gmail.com` from client IP `127.0.0.1`.
- Failure Reason logged: `USER_NOT_FOUND` (because `inventory@gmail.com` does not exist in `hotel_erp_staging`).
- Result: Standard security rate limiting temporarily flagged `inventory@gmail.com` from `127.0.0.1` on `hotel_erp_staging` with a 15-minute lock window.
- In `hotel_erp_db.users_authenticationattempt`:
  - Zero lockouts recorded for `inventory@gmail.com`.

---

## 3. Recommended Minimal Fix Options

Pursuant to the strict read-only directive, no configuration or database state has been changed. The following two clean remediation paths are available for Owner approval:

### Option A: Switch Active Database back to `hotel_erp_db` (Recommended)
- **Mechanism:** Change `DB_NAME=hotel_erp_staging` back to `DB_NAME=hotel_erp_db` in `.env` and reload the Django service.
- **Impact:**
  - Instantly restores access for `inventory@gmail.com`, `kitchen@gmail.com`, `admin@example.com`, `cashier@gmail.com`, etc.
  - No database migration or data mutation required.
  - User can immediately log in with their existing passwords.
- **Risk:** Staging procurement test records created during Phases 2.1–4 in `hotel_erp_staging` will remain in `hotel_erp_staging`, while primary application state returns to `hotel_erp_db`.

### Option B: Reconcile / Mirror Accounts into `hotel_erp_staging`
- **Mechanism:** Keep `hotel_erp_staging` active, but execute a non-destructive migration script that copies the 10 original user accounts (including their exact hashed passwords and email addresses) from `hotel_erp_db` into `hotel_erp_staging`.
- **Impact:**
  - Retains all Phase 2–4 staging test artifacts while allowing login with `inventory@gmail.com`, `kitchen@gmail.com`, etc.
- **Risk:** Divergence between `hotel_erp_db` and `hotel_erp_staging` remains.

---

## 4. Required Post-Remediation Verification & Regression Tests
Once the approved option is authorized:
1. **Direct Login Verification:**
   - Execute an automated test authenticating with `inventory@gmail.com` and `kitchen@gmail.com`.
   - Confirm HTTP 200 and receipt of valid JWT access and refresh tokens.
2. **Browser Acceptance Check:**
   - Verify frontend navigation to `http://localhost:3000/login` accepts the credentials and redirects to the correct role dashboard (`/inventory` and `/kitchen`).
3. **Audit Trail Verification:**
   - Check `users_authenticationattempt` to confirm successful authentication log generation.

