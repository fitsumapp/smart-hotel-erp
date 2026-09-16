# Phase 5 ? Observability, Visibility and Auditability

Status: implemented in the working tree.

## Delivered

- Every HTTP response has a validated or generated X-Request-ID.
- Production logs are JSON and include request ID, method, path, status, duration and safe actor ID.
- Passwords, tokens, OTP/MFA codes, cookies, payment secrets and identity fields are redacted.
- Admin-only operational metrics cover HTTP traffic/latency/errors, authorization denials, login/MFA failures, payment state and reconciliation mismatches, reservation transitions, stock writes and database readiness.
- /health/live checks process liveness; /health/ready verifies PostgreSQL and exposes the release identifier.
- AuditEvent is append-only, indexed and searchable by request, action, entity and actor.
- Critical user, room, reservation, payment, settings, inventory, journal, expense, budget and payroll writes are audited.
- check_backup_freshness, reconcile_stock, reconcile_accounts and reconcile_payments are scheduler-friendly checks.

Metrics are process-local. Multi-worker production must ship logs and command exit codes to central monitoring. Phase 6 may export counters through Prometheus/OpenTelemetry.

## Alert policy

| Signal | Suggested threshold | Severity |
|---|---:|---|
| readiness failure | 2 consecutive checks | critical |
| HTTP 5xx rate | >2% for 5 minutes | critical |
| p95 request latency | >2 seconds for 10 minutes | warning |
| login/MFA failures | >20 per account/IP in 10 minutes | warning/security |
| payment/webhook failure | any burst or >3 in 10 minutes | critical |
| reconciliation mismatch | any | critical |
| backup stale/failure | >26 hours or any failed job | critical |
| database pool use | >80% | warning |

## Operator response

1. Capture request_id, release, endpoint, timestamp and actor ID.
2. Search /api/v1/audit-events/?request_id=ID and centralized logs.
3. For payments, run python manage.py reconcile_payments; never manually mark a payment paid.
4. For inventory/accounting, run reconcile_stock and reconcile_accounts without --repair; review first.
5. For readiness failures, inspect PostgreSQL availability, pool usage, SSL and credentials.
6. For security alerts, disable the account, revoke sessions, preserve logs and escalate.
7. Record incident timing, impact, root cause, remediation and audit references.

## Scheduled checks

    python manage.py check_backup_freshness --directory .\backups --max-age-hours 26
    python manage.py reconcile_stock
    python manage.py reconcile_accounts
    python manage.py reconcile_payments

Connect non-zero exit status to the deployment alert target.
