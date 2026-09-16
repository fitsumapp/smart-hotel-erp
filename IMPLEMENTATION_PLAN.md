## Phase 1 implementation sign-off (completed 2026-07-20)

Phase 1 identity, session, and authorization hardening is implemented and verified.

### Delivered

- Cryptographically generated, hashed, expiring, attempt-limited, single-use OTP and MFA challenges.
- Generic authentication failures, database-backed account/IP lockout, resend cooldowns, and endpoint throttling.
- Mandatory MFA challenge for administrator and finance logins before token issuance.
- Short-lived versioned access tokens, rotating refresh tokens, refresh-token blacklisting, and session invalidation after sensitive account changes.
- Case-insensitive unique nonblank email enforcement at the database layer.
- Append-only security audit events and soft account deactivation.
- Customer-only public registration and administrator-controlled staff provisioning.
- Centralized role permissions across identity, finance, inventory, reservations, rooms, guests, folios, orders, kitchen/bar, and system settings APIs.
- Identity security operations and incident guide in `docs/IDENTITY_SECURITY.md`.

### Migrations

- `users.0004_user_failed_login_attempts_user_locked_until_and_more`
- `users.0005_alter_user_options_user_unique_user_email_ci`
- SimpleJWT token-blacklist migrations

The migrations were applied successfully to the local PostgreSQL database after a duplicate-email preflight audit found no conflicts.

### Verification evidence

- Full isolated backend suite: **93 passed**, with three PostgreSQL-only concurrency tests skipped as designed.
- Focused Phase 1 identity/RBAC suite: **17 passed**.
- Django system check: **0 issues**.
- Migration drift check: **no changes detected**.
- PostgreSQL migrations: **applied successfully**.

### Production gate

Email MFA is enforced for privileged roles. Production deployment must configure and monitor a reliable SMTP provider and use a shared cache such as Redis so throttling remains consistent across application workers.

## Phase 2 implementation sign-off (completed 2026-07-20)

Phase 2 payment security and financial-integrity work is implemented and verified.

### Delivered

- Immutable `PaymentAttempt` identity containing provider, purpose, exact target, amount, currency, provider reference and idempotency key.
- Database constraints for exactly one target, positive payment amounts, valid purpose/status values and unique provider/idempotency/event references.
- Backend-generated transaction references and request-bound initiation idempotency.
- Bounded tip validation and validated/length-limited customer email/name fields before provider calls.
- Exact provider verification of successful status, transaction reference, amount and currency.
- Official Chapa-compatible HMAC verification for `x-chapa-signature` payload signatures and `chapa-signature` secret signatures.
- Dedicated webhook secret; webhook authentication no longer falls back to the Chapa API secret.
- Immutable `PaymentWebhookEvent` receipt ledger with payload hashes, provider event identity, processing result and linked payment attempt.
- One transactional webhook processor for orders, reservation deposits, check-in and checkout payments.
- Duplicate/replayed callbacks acknowledge success without repeating order, inventory, room, notification or accounting side effects.
- Payment finalization locks both the payment attempt and target business record.
- Verified digital payments link one-to-one to their primary accounting journal entry; accounting failures roll back digital finalization.
- Public order and reservation verification are bound to stored payment expectations and mark attempts verified idempotently.
- QR/confirmation codes are identifiers only; check-in/checkout and their payment operations require reception or administrator authorization.
- Provider reconciliation service and `reconcile_payments` command identify missing, mismatched and orphaned local/provider states without silently repairing financial data.
- Read-only Django administrator views for payment attempts and webhook receipts.
- Payment operations and incident runbook in `docs/PAYMENT_OPERATIONS.md`.

### Migrations

- `0025_paymentattempt_accounting_entry_and_more`
- `0026_remove_paymentattempt_payment_attempt_amount_nonnegative_and_more`

Both migrations were applied successfully to the local PostgreSQL database. Existing reservation attempts were safely classified by purpose before constraints were installed. A pre-migration audit confirmed there were no non-positive payment attempts.

### Verification evidence

- Full isolated backend suite: **81 passed**, with three PostgreSQL-only concurrency tests skipped as designed.
- Phase 2 suite on PostgreSQL: **8 passed**, including true concurrent payment finalization.
- Focused payment/webhook/RBAC suite: **19 passed**.
- Concurrent payment finalization creates one paid state and one primary payment journal entry.
- Duplicate webhook delivery creates one immutable receipt and invokes finalization once.
- Official-signature compatibility vectors cover payload HMAC, secret HMAC and invalid signatures.
- Reconciliation tests identify provider-paid/local-unverified and amount-mismatch cases.
- Django system check: **0 issues**.
- Migration drift check: **no changes detected**.

### Operational use

Run payment reconciliation from the production scheduler at least every 15 minutes:

```powershell
python manage.py reconcile_payments --limit 500
```

## Phase 3 implementation sign-off (completed 2026-07-20)

Phase 3 database-integrity and concurrency work is implemented and verified.

### Delivered

- Reservation date, guest-count and financial check constraints.
- PostgreSQL `btree_gist` extension and an active-reservation exclusion constraint using a half-open `daterange`, preventing same-room overlap at the database layer.
- Migration-time overlap audit that stops deployment instead of silently changing conflicting reservations.
- Authoritative, transactional reservation transitions with reservation and room row locks; model-level enforcement prevents bypass through ordinary `save()` calls.
- Authoritative order transitions with row locking and model-level invalid/backwards-transition rejection.
- Idempotent order creation bound to a SHA-256 request fingerprint; reuse with changed input is rejected.
- Locked, idempotent order finalization and immutable finalized price/tax/service-charge snapshots.
- Atomic inventory balance updates, non-negative stock enforcement and immutable ledger entries.
- Idempotent stock reversal records linked one-to-one to their original ledger transaction.
- Stock mutation APIs reject ledger update/delete; an authorized reversal action is provided.
- Direct folio stock mutations were replaced by the authoritative stock service.
- `reconcile_stock` command with safe report-only default and explicit `--repair` mode.
- Opening-stock baseline migration preserves existing balances and makes future reconciliation deterministic.
- Posted journal immutability, balanced posting, reversal workflow and account reconciliation (delivered earlier in Phase 3).

### Migrations

- `0022_order_financials_finalized_at_order_idempotency_key_and_more`
- `0023_reservation_no_active_overlap`
- `0024_inventoryitem_opening_stock_and_more`

All three migrations were applied successfully to the local PostgreSQL database. Migration `0023` is PostgreSQL-specific and safely no-ops in the isolated SQLite test configuration.

### Verification evidence

- Full isolated backend regression suite: **73 passed**, with the two PostgreSQL-only tests skipped as designed.
- PostgreSQL Phase 3 suite: **7 passed**, including real concurrent overlapping-booking and concurrent-stock tests.
- Django system check: **0 issues**.
- Migration drift check: **no changes detected**.
- Stock reconciliation against local PostgreSQL: **0 mismatches**.
- Account reconciliation against local PostgreSQL: **0 mismatches**.
- PostgreSQL overlap migration and GiST exclusion constraint installation: **successful**.

### Operational use

## Phase 7 implementation sign-off (completed 2026-07-23)

Phase 7 production and infrastructure hardening work is implemented and verified.

### Delivered

- Mandatory `DEBUG=False` in production mode with strict startup assertions.
- Mandatory production startup failure if `SECRET_KEY`, database credentials (`DATABASE_URL` / `DB_*`), `CHAPA_SECRET_KEY`, or `CHAPA_WEBHOOK_SECRET` are missing or set to insecure defaults.
- Mandatory non-wildcard `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS` in production.
- Disallowed wildcard CORS combined with credential support (`CORS_ALLOW_CREDENTIALS`).
- Configured HTTPS redirect, HSTS (`max-age=31536000`), secure/HttpOnly/SameSite=Lax cookies, and `SECURE_PROXY_SSL_HEADER`.
- Custom `SecurityHeadersMiddleware` adding Content-Security-Policy (CSP), Permissions-Policy, X-Content-Type-Options, Referrer-Policy, and X-Frame-Options.
- Generic error views (`custom_500_handler`, `custom_404_handler`) returning generic error pages with correlation IDs (`X-Request-ID`) while masking Python tracebacks, sys.path, and internal server paths.
- Passenger WSGI startup exception handler (`passenger_wsgi.py`) configured to return generic 500 responses without exposing tracebacks or virtualenv paths.
- Binary magic signature validation (`validate_file_signature`) and 5 MB upload limits (`validate_upload_size`).
- Non-user-controlled UUID storage name generation (`generate_secure_filename`).
- Image re-encoding via Pillow (`reencode_image`) to strip EXIF data and embedded code.
- Guest identity scans stored in private storage (`media/private/guest_ids/`), inaccessible via public static URL.
- Authorized download endpoint (`/api/v1/guest-profiles/<id>/id-scan/`) enforcing reception and administrator role authorization (`SecureGuestIdDownloadView`).
- Execution of scripts in media uploads blocked via `media/.htaccess` and Nginx rules.
- Reverse proxy edge configuration template (`docs/nginx.conf.template`) with HTTPS 301 redirects, body limits, bot/scanner blocking, and edge rate-limiting zones (`limit_req_zone`).
- Infrastructure runbook in `docs/INFRASTRUCTURE_HARDENING.md`.
- Automated hardening test suite in `core/tests_hardening.py`.

### Migrations

- `hotel.0029_alter_category_image_alter_guestprofile_id_scan_and_more`
- `users.0006_alter_user_profile_picture`

### Verification evidence

- Full test suite: **116 passed** (`core.tests_hardening` + `users`).
- Dedicated Phase 7 hardening suite: **14 passed**.
- Production deployment check (`python manage.py check --deploy` under `DJANGO_ENV=production`): **0 issues**.
- Django system check: **0 issues**.
- Migration drift check (`python manage.py makemigrations --check`): **no changes detected**.

# Smart Hotel ERP — Security, Scalability and Reliability Implementation Plan

## 1. Purpose

This document defines the implementation roadmap for strengthening Smart Hotel ERP across:

- Security and access control
- Payment and financial integrity
- Data consistency and concurrency
- Scalability and performance
- Reliability and disaster recovery
- Observability and operational visibility
- Testing and deployment safety
- Maintainability and future development

No system can be guaranteed to be completely unbreakable. The objective is to build a system that:

1. Prevents common and high-impact attacks.
2. Detects suspicious activity and failures quickly.
3. Limits the impact of an incident.
4. Preserves financial and operational data integrity.
5. Recovers safely from failures.
6. Can scale without requiring an immediate rewrite.

## 2. Current Architecture Summary

The current application is a single-tenant hotel ERP consisting of:

- Django and Django REST Framework backend
- PostgreSQL database
- JWT authentication
- React 19 single-page frontend
- Chapa payment integration
- Passenger/WSGI deployment on cPanel-style infrastructure

The system covers rooms, reservations, public booking, restaurant POS, kitchen, cashier, inventory, reports, finance, payroll, guest profiles and hotel settings.

The recommended target is a **modular monolith**, not microservices:

```text
React SPA
   │ HTTPS + CSP
   ▼
Reverse Proxy / WAF / Rate Limiting
   │
   ▼
Django Modular Monolith
   ├── Identity and RBAC
   ├── Reservations and PMS
   ├── Orders and POS
   ├── Payments
   ├── Inventory
   ├── Finance
   ├── Reporting
   └── Audit
   │
   ├── PostgreSQL — source of truth
   ├── Redis — caching, throttling and job broker
   ├── Background workers — email, reports and reconciliation
   └── Monitoring — logs, errors, metrics and alerts
```

## 3. Current High-Risk Findings

The following risks must be treated as release blockers:

1. Public registration accepts a requested role, allowing a new account to become an administrator after OTP verification.
2. Any authenticated user can perform full CRUD operations on user accounts, including role and activation changes.
3. Any authenticated user can finalize an arbitrary order as paid.
4. Payment verification does not bind the verified Chapa transaction to the expected order, reservation, amount and currency.
5. The public QR check-in endpoint can check a guest in without staff authorization or sufficient payment and reservation-state validation.
6. Several finance, inventory, room, order and guest endpoints use authentication without role or object-level authorization.
7. Reservation creation, payment finalization and stock updates contain concurrency race conditions.
8. Production defaults and the Passenger error handler can expose sensitive configuration and stack traces.

## 4. Guiding Principles

- Security must be enforced by the backend, never only by hidden frontend controls.
- Critical business rules must be enforced at both the service and database layers.
- Financial records must be immutable after posting; corrections use reversal entries.
- Every important state change must be attributable to a user or system process.
- External callbacks and retries must be idempotent.
- Production must fail closed when required secrets or settings are missing.
- Changes must be delivered in small, tested and reversible stages.
- Scaling work must follow measurement rather than guesswork.

---

## Phase 0 — Baseline and Safety Net

Status: implemented in the working tree.

Phase 0 deliverables now include pinned backend dependencies, safe environment examples, development/test/production settings entrypoints, production fail-closed validation, CI checks, and backup/restore runbooks/scripts. The baseline commit/tag and real backup/restore execution must be completed by the repository owner after reviewing the existing dirty worktree and selecting the target PostgreSQL instance.

### Objectives

Create a stable, reproducible baseline before modifying security-critical workflows.

### Implementation tasks

- Review and organize the existing uncommitted changes before beginning the remediation.
- Create a protected baseline commit and tag.
- Select a supported Python version and a supported Django LTS release.
- Pin all Python dependencies to exact reviewed versions.
- Retain and validate the frontend lockfile.
- Create `.env.example` containing names and safe examples only.
- Split settings into development, test and production configurations.
- Make database and Chapa configuration explicit per environment.
- Build a repeatable local and test database setup process.
- Add CI checks for:
  - Backend tests
  - Frontend tests
  - Frontend production build
  - Linting and formatting
  - Migration consistency
  - `manage.py check --deploy`
  - Dependency vulnerability scanning
  - Secret scanning
- Take a database and uploaded-media backup.
- Perform and document a restore test using a separate database.

### Acceptance criteria

- A fresh environment can run the project using documented commands.
- CI runs automatically and passes on the protected baseline.
- Production configuration cannot silently use development defaults.
- A complete backup can be restored successfully.

---

## Phase 1 — Critical Authentication and Authorization Remediation

### 1.1 Secure registration

- Remove `role`, `is_active`, `is_staff`, `is_superuser` and other privileged fields from public registration input.
- Force public registrations to the `customer` role.
- Create staff accounts only through an administrator-protected endpoint.
- Create separate serializers:
  - `PublicRegistrationSerializer`
  - `AdminUserCreateSerializer`
  - `UserSelfSerializer`
  - `AdminUserUpdateSerializer`
- Avoid `fields = "__all__"` for security-sensitive serializers.

### 1.2 Secure OTP verification

- Generate OTP values with a cryptographically secure generator.
- Store only a hash of the OTP.
- Add expiration, maximum attempts and single-use enforcement.
- Add resend cooldown and per-email/per-IP throttling.
- Invalidate old OTP values when a new one is issued.
- Do not activate privileged roles through public OTP verification.

### 1.3 Secure login and JWT lifecycle

- Return a generic authentication error that does not reveal whether an account exists.
- Add account lockout or progressive delay after repeated failures.
- Log successful and unsuccessful authentication events without logging credentials.
- Reduce access-token lifetime.
- Enable refresh-token rotation and blacklist/revocation support.
- Revoke sessions after password, role or account-status changes.
- Introduce MFA for administrators and finance users.
- Move toward secure HttpOnly cookies or a hardened token strategy after completing CSRF and frontend compatibility analysis.

### 1.4 Central role-based access control

Create reusable permission classes such as:

- `IsHotelAdmin`
- `IsReceptionist`
- `IsCashier`
- `IsKitchenOrBar`
- `IsInventoryManager`
- `IsFinanceStaff`
- `IsOrderOwnerOrCashier`
- `IsReservationOperator`

Create an endpoint-to-role authorization matrix and enforce it in backend tests.

### 1.5 Object-level authorization

- A waiter accesses only their assigned orders unless explicitly authorized.
- Reception and administrators access guest identity and reservation details.
- Cashiers and administrators finalize payments.
- Finance and administrators access journal, budget, expense and payroll data.
- Inventory staff and administrators perform stock adjustments.
- Apply the same permissions to list, retrieve, create, update and delete operations.

### Acceptance criteria

- A public user cannot request or acquire a privileged role.
- A low-privilege authenticated user cannot modify users or roles.
- Every endpoint has explicit allowed and denied role tests.
- Object-level access tests prevent IDOR attacks.
- Privileged account changes create immutable audit events.

---

## Phase 2 — Payment Security and Financial Integrity

### 2.1 Payment data model

Add an immutable `PaymentAttempt` model containing:

- Provider name
- Internal order or reservation reference
- Expected amount and currency
- Provider transaction reference
- Internal idempotency key
- Current status
- Provider event reference
- Verification timestamp
- Safe response metadata
- Created and updated timestamps

Add unique constraints for transaction and provider-event references.

### 2.2 Secure payment initiation

- Generate transaction references only on the backend.
- Persist the expected entity, amount and currency before contacting Chapa.
- Do not allow a client to replace the stored transaction reference.
- Validate and limit customer-supplied name, email and tip fields.
- Apply idempotency to repeated payment-initiation requests.

### 2.3 Secure verification and webhook handling

Verify all of the following before marking anything paid:

- Valid provider status
- Exact stored transaction reference
- Matching order or reservation
- Exact expected amount
- Expected currency
- Transaction not already assigned elsewhere
- Payment attempt not already processed

Additional requirements:

- Validate webhook signatures using official Chapa test vectors.
- Store webhook receipt and processing state.
- Use `transaction.atomic()` and `select_for_update()` during finalization.
- Make duplicate webhook delivery safe and idempotent.
- Never trust order, reservation, amount or tip metadata received from an unsigned client.
- Add a scheduled reconciliation job to compare local payments with Chapa.

### 2.4 Secure check-in and checkout

- Require an authenticated reception or administrator role for final check-in.
- Treat public QR codes as identifiers, not authorization credentials.
- Validate reservation status, room, booking dates and payment policy.
- Reject cancelled, expired, unpaid or already completed reservations as appropriate.
- Record the staff member and request ID responsible for the operation.

### Acceptance criteria

- A successful transaction cannot pay two different entities.
- Wrong-order, wrong-reservation, wrong-amount and wrong-currency verification attempts fail.
- Duplicate callbacks create one payment and one accounting posting.
- Concurrent payment requests produce one final state.
- Reconciliation identifies missing, mismatched and orphaned transactions.

---

## Phase 3 — Database Integrity and Concurrency Controls

### 3.1 Reservation integrity

- Represent booking periods with PostgreSQL date ranges where appropriate.
- Add a GiST exclusion constraint preventing overlapping active reservations for the same room.
- Add database constraints enforcing:
  - Check-in before check-out
  - Adults greater than or equal to one
  - Children greater than or equal to zero
  - Non-negative financial values
- Introduce a reservation state machine:
  - `pending → confirmed → checked_in → checked_out`
  - `pending/confirmed → cancelled`
- Reject invalid or backwards transitions.
- Use transactions and row locks for room status and reservation changes.

### 3.2 Order integrity

- Define allowed order transitions centrally.
- Reject arbitrary order status values and invalid transitions.
- Lock the order during payment, cancellation and inventory deduction.
- Add idempotency to order creation and finalization.
- Preserve the price, tax and service-charge snapshot used at the time of sale.

### 3.3 Inventory integrity

- Replace read-modify-write stock updates with atomic database expressions and row locking.
- Establish and enforce a negative-stock policy.
- Store every stock change in an immutable stock ledger.
- Prevent deleting stock history; create reversal or adjustment records.
- Validate quantities, costs and permitted transaction types.
- Add periodic stock-balance reconciliation.

### 3.4 Accounting integrity

- Make posted journal entries immutable.
- Correct errors using reversing entries.
- Guarantee total debit equals total credit before commit.
- Move balance management from failure-swallowing signals to a transactionally safe accounting service.
- Do not allow a journal write to succeed if its balance update fails.
- Add a repair/reconciliation command and alert on mismatches.
- Add non-negative and domain-specific constraints where applicable.

### Acceptance criteria

- Concurrent booking tests never create overlapping active reservations.
- Concurrent stock operations never lose an update.
- Concurrent payments never create duplicate ledger entries.
- Ledger totals and cached account balances always reconcile.
- Invalid state transitions fail at the service boundary.

---

## Phase 4 — Backend Modularization and API Quality

Split the current large backend modules into domain applications:

```text
apps/
├── identity/
├── reservations/
├── rooms/
├── orders/
├── payments/
├── inventory/
├── finance/
├── reporting/
└── audit/
```

Recommended internal structure:

```text
models.py
serializers.py
permissions.py
services.py
selectors.py
views.py
urls.py
tests/
```

### Implementation tasks

- Move business rules from views and signals into transactional service functions.
- Keep read queries in selector/query modules where this improves clarity.
- Use explicit serializer fields.
- Add a centralized DRF exception handler and consistent error envelope.
- Never return raw exception text to clients.
- Add API versioning under `/api/v1/`.
- Generate and validate an OpenAPI schema.
- Add pagination, filtering, ordering and maximum page sizes.
- Add idempotency support to high-impact write endpoints.
- Keep backward-compatible URLs temporarily during frontend migration.

### Acceptance criteria

- No domain depends on frontend-specific behavior for security.
- Critical business operations have one authoritative service implementation.
- Large list endpoints are paginated.
- API errors do not disclose internal exceptions or paths.
- Existing workflows continue passing end-to-end tests during refactoring.

---

## Phase 5 — Visibility, Observability and Auditability

### 5.1 Structured operational logging

- Emit JSON logs in production.
- Assign a request/correlation ID to every request.
- Include safe actor, endpoint, status, duration and result metadata.
- Redact passwords, tokens, OTP values, payment secrets, identity documents and sensitive guest data.
- Log authentication success/failure, authorization denial and privileged actions.

### 5.2 Error tracking and metrics

Add monitoring for:

- Request volume, latency and error rate
- Database query count and duration
- Slow queries and connection exhaustion
- Login and OTP failures
- Authorization denials
- Payment initiation and verification failures
- Webhook retries and reconciliation mismatches
- Background-job failures and queue depth
- Inventory and ledger reconciliation mismatches
- Backup age and backup failures

Add:

- `/health/live` for process health
- `/health/ready` for database and required-service readiness
- Release/version identifiers in diagnostics
- Alerts with documented escalation and response steps

### 5.3 Immutable business audit trail

Create an `AuditEvent` model containing:

- Actor/user and role
- Action
- Entity type and identifier
- Safe before/after summary
- Timestamp
- Request ID
- Source IP and client metadata
- Reason or approval reference when required

Audit at minimum:

- Role and account-status changes
- Login security events
- Room and reservation status changes
- Check-in and checkout
- Payment and refund operations
- Price and system-setting changes
- Stock adjustments
- Journal, expense, budget and payroll changes

### Acceptance criteria

- An operator can trace a payment or booking across requests and jobs using one correlation ID.
- Critical failures generate alerts.
- Security and business events are searchable without exposing secrets.
- Every privileged change identifies who performed it and when.

---

## Phase 6 — Scalability and Performance

### 6.1 Database and API performance

- Establish query-count and latency baselines.
- Use `select_related()` and `prefetch_related()` to eliminate N+1 queries.
- Paginate all potentially large collections.
- Add maximum date ranges to expensive reports.
- Perform aggregation in PostgreSQL instead of Python loops where practical.
- Add indexes based on real query plans and production measurements.
- Configure connection pooling, query timeouts and slow-query logging.

### 6.2 Caching

- Replace the dummy cache with Redis where caching or shared throttling is required.
- Cache only suitable data such as menus, public room catalogs and stable settings.
- Do not cache sensitive authenticated responses without correct user/role variation and invalidation.
- Define ownership, TTL and invalidation rules for every cached object.

### 6.3 Background processing

Move the following away from request-response paths:

- Email and OTP delivery
- Reservation confirmation email
- Long-running reports and exports
- Payment reconciliation
- Notification fan-out
- Periodic accounting and stock reconciliation

Jobs must include retries, exponential backoff, idempotency and dead-letter/failure visibility.

### 6.4 Frontend efficiency

- Replace duplicate API helpers with one configured API client.
- Add centralized token refresh and error handling.
- Split large dashboard components into domain components and hooks.
- Add route-level code splitting.
- Replace unnecessary fixed polling with adaptive polling, SSE or WebSocket updates where justified.
- Cancel stale requests and prevent overlapping refresh calls.

### 6.5 Load testing

Test at minimum:

- Concurrent public bookings
- Concurrent order creation
- Kitchen and waiter status updates
- Cashier payment bursts
- Duplicate and concurrent webhooks
- Inventory issuance bursts
- Monthly finance and occupancy reports

Define performance service-level objectives after measuring the baseline, including p95 latency, error rate and supported concurrency.

---

## Phase 7 — Production and Infrastructure Hardening

### Django and application settings

- Make production `DEBUG=False` mandatory.
- Fail startup if `SECRET_KEY`, database credentials or payment secrets are missing.
- Use strict `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` values.
- Replace wildcard CORS with an explicit allowlist.
- Do not combine wildcard origins with credential support.
- Configure HTTPS redirect, HSTS, secure cookies and trusted proxy SSL headers.
- Configure content-type, frame, referrer and permissions policies.
- Add a Content Security Policy for the React application.

### Error handling

- Remove the Passenger response that exposes tracebacks and Python paths.
- Return a generic public error page with a correlation ID.
- Send detailed exceptions only to protected logs/error tracking.

### Files and sensitive media

- Enforce upload-size limits at the reverse proxy and application levels.
- Validate MIME type and file signature.
- Re-encode uploaded images when practical.
- Generate non-user-controlled storage names.
- Store guest identity scans in private storage.
- Deliver sensitive files through authorized, short-lived download links.
- Ensure uploaded files can never be executed by the web server.

### Edge protection

- Enforce HTTPS at the reverse proxy.
- Add request/body size limits.
- Add edge-level rate limiting for login, OTP, registration, booking and payment endpoints.
- Add bot and abuse protection where public traffic requires it.
- Treat DRF throttling as application policy, not complete DDoS protection.

### Acceptance criteria

- Production cannot start with insecure defaults.
- Public errors reveal no stack traces, source paths or secrets.
- Sensitive uploads are inaccessible without authorization.
- Security headers pass automated checks.
- Login, OTP and payment abuse tests are rate-limited at appropriate layers.

---

## Phase 8 — Deployment, Backup and Disaster Recovery

### Deployment pipeline

- Build immutable, versioned application artifacts.
- Run CI and security checks before deployment.
- Apply backward-compatible migrations using an expand-migrate-contract strategy.
- Use staged or blue/green deployment where infrastructure permits.
- Run post-deployment smoke tests.
- Retain the previous backend and frontend release for rollback.

### Database and media protection

- Schedule encrypted database backups.
- Back up private uploaded media.
- Maintain off-site or provider-independent backup copies.
- Define retention rules.
- Test restores regularly rather than assuming backups are usable.
- Document recovery time and recovery point objectives.

### Operational runbooks

Create runbooks for:

- Database outage
- Chapa outage or mismatch
- Compromised administrator account
- Leaked secret rotation
- Failed migration
- Incorrect financial posting
- Backup restoration
- Rollback to the previous release

### Acceptance criteria

- A failed deployment can be rolled back without data loss.
- Backup restoration is tested on a schedule.
- Operators have documented incident and recovery procedures.
- Releases and database migrations are traceable to a commit and operator.

---

## Phase 9 — Testing Strategy

The testing program must include:

### Security tests

- Registration privilege-escalation tests
- Role and object-permission matrix tests
- IDOR tests
- Login, OTP and token-abuse tests
- Payment replay and transaction-binding tests
- Webhook signature and idempotency tests
- Sensitive-file authorization tests
- Error-disclosure tests

### Data-integrity tests

- Concurrent booking tests
- Concurrent payment finalization tests
- Concurrent stock update tests
- Order and reservation state-machine tests
- Journal balancing and reversal tests
- Cached balance reconciliation tests

### Functional tests

- Booking → payment → check-in → checkout
- Order → kitchen/bar → waiter → cashier → accounting
- Purchase → stock receipt → recipe issuance → folio charge
- Payroll posting and financial reporting

### Operational tests

- Backup and restore smoke tests
- Health/readiness endpoint tests
- Migration tests against realistic data
- Load and performance tests
- Dependency and secret scanning
- Static analysis and linting

Coverage percentage is not the only goal. Critical business and security invariants require complete scenario coverage.

---

## 5. Recommended Implementation Order

Work must proceed in the following dependency order:

1. Establish the baseline, environments, backups and CI.
2. Close public administrator registration.
3. Protect user management and implement central RBAC.
4. Protect order, finance, inventory, PMS and guest endpoints.
5. Introduce secure payment attempts, transaction binding and idempotency.
6. Add reservation, payment, stock and ledger concurrency controls.
7. Harden production settings, error handling, CORS and private media.
8. Add audit trails, structured logging, metrics and alerts.
9. Refactor the backend into domain modules behind passing tests.
10. Add pagination, query optimization, background jobs and safe caching.
11. Conduct load testing and staged production deployment.

New feature development should be limited until Phases 1–3 are complete because those phases close the highest risks of system takeover, payment loss, double booking and accounting corruption.

## 6. Delivery Rules for Every Phase

Every implementation phase must include:

- A narrowly scoped change set
- Automated tests written with or before the fix
- Migration and rollback notes
- Security and privacy review
- Updated API or operator documentation
- CI verification
- Staging validation
- Explicit acceptance-criteria sign-off
- Post-deployment monitoring

No phase is considered complete because code was written. It is complete only when its tests, migration, deployment and operational validation have succeeded.

## 7. External Standards and References

- [Django deployment checklist](https://docs.djangoproject.com/en/dev/howto/deployment/checklist/)
- [Django REST Framework throttling guidance](https://www.django-rest-framework.org/api-guide/throttling/)
- [PostgreSQL range types and exclusion constraints](https://www.postgresql.org/docs/10/rangetypes.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)

