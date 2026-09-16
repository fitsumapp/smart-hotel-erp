# Identity and Access Security Operations

## Security controls

- Access tokens expire after 15 minutes. Refresh tokens expire after 7 days, rotate on use, and the old token is blacklisted.
- Every token carries the user's `token_version`. Password, role, active-state, or other sensitive account changes invalidate existing sessions.
- OTP and MFA codes are generated cryptographically, stored only as password hashes, expire after 10 minutes, allow at most five attempts, and are single-use.
- OTP resend is limited by a 60-second cooldown and API throttling.
- Administrator and finance logins require a second, email-delivered MFA code before tokens are issued.
- Login failures are tracked by privacy-preserving identifier and IP hashes. Five failures cause a 15-minute lockout.
- Login responses do not reveal whether an account exists.
- Security audit records are append-only through the application and Django administrator.
- Public registration can create customer accounts only. Staff roles are assigned through an administrator-controlled workflow.

## Role boundaries

| Area | Allowed roles |
|---|---|
| User and system administration | Administrator |
| Finance and accounting | Administrator, finance |
| Inventory management | Administrator, inventory manager |
| Reservations, rooms, guests, folios | Administrator, reception |
| Menu/category management | Administrator |
| Order creation and waiter workflow | Administrator, waiter |
| Kitchen/bar workflow | Administrator, kitchen, bar |

## Production requirements

1. Configure a reliable SMTP provider and monitor OTP/MFA delivery failures and latency.
2. Keep `SECRET_KEY`, database credentials, SMTP credentials, Chapa credentials, and webhook secrets in the deployment secret store; never commit them.
3. Serve only through HTTPS and enable secure cookies and proxy SSL settings for the production environment.
4. Run the application with a shared production cache (Redis is recommended) before horizontal scaling so throttling is consistent across workers.
5. Alert on repeated lockouts, abnormal OTP requests, privileged role changes, disabled accounts, and refresh-token replay attempts.
6. Back up PostgreSQL regularly and test restoration. Security audit records should be exported to retention-controlled storage.

## Incident response

- Compromised user: deactivate the account or increment `token_version`, reset the password, review security audit events, then reactivate only after verification.
- Suspected refresh-token theft: increment `token_version`; this rejects all access and refresh tokens issued under the earlier version.
- OTP/MFA abuse: inspect authentication-attempt and audit records by time window and IP hash, then apply an upstream WAF/IP rule if necessary.
- Privilege escalation suspicion: review role-change audit events and related administrator activity; do not delete audit evidence.

## Verification commands

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --settings=core.settings_test
```

PostgreSQL migrations must also be applied and verified in staging before production deployment:

```powershell
python manage.py migrate --plan
python manage.py migrate
```
