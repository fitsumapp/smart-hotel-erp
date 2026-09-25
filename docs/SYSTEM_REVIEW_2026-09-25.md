# Smart Hotel ERP: remediation report

Date: 2026-09-25

## Changes made

- Cash order finalization now rolls back completely if journal posting fails. A regression test verifies both the pending payment state and absence of a journal entry after a simulated ledger failure.
- Email MFA is mandatory for administrators and finance users. The frontend now handles the email challenge and verifies its six-digit code before saving tokens.
- API throttling uses a shared database cache, installed by migration `hotel.0030_api_cache`. The ordinary authenticated budget is 120 requests/minute, which accommodates the cashier dashboard's three requests every five seconds. Refresh requests have a separate limit. Tests clear the shared cache between database-backed tests and prove the anonymous limit rejects request 101.
- Access tokens last 15 minutes. Refresh rotation checks account activity and token version while holding a user-row lock. Logout accepts the refresh token even after the short-lived access token expires, blacklists the presented refresh, increments token version to revoke all sessions, and clears the browser session only after revocation succeeds.
- Django and Chapa secrets now fail closed in production if absent, too short, low-diversity, or recognizable placeholders. Production also requires SMTP credentials, `DEBUG=False`, secure cookies and HTTPS, explicit hosts/CSRF/CORS origins, and non-placeholder payment secrets. Broad default credentialed CORS subdomain matching was removed; custom regex origins are opt-in. Development keeps a stable local-only signing key.
- Identity scans are stored outside the public media root. Direct `/media/private/` requests are blocked in Django; the Nginx template also blocks the legacy private path. Existing scans under the old path remain readable through the authenticated download endpoint. `id_scan_url` now points to that endpoint.
- Browser API requests default to same-origin `/api`, with `REACT_APP_API_BASE_URL` available at build time for a separately hosted API. The shared Axios client limits request time, refreshes failed sessions, handles concurrent refreshes, and normalizes API error messages.
- Nginx authentication rate-limit locations now match the API routes the Django URL configuration actually serves, including legacy aliases. General API edge capacity was adjusted to accommodate dashboard polling.
- Frontend Jest now maps the CommonJS router entry points used by the installed React Router 7 package and loads its Node text encoders. The generated placeholder UI test now checks that the login screen renders.

## Verification

- Backend: 121 tests passed; 3 PostgreSQL-only concurrency tests were skipped by the SQLite test configuration.
- Django deployment security check: no issues when run with production HTTPS and HSTS values supplied.
- Migration drift: no changes detected. The new cache-table migration applied in the isolated test database.
- PostgreSQL: all 121 backend tests also passed against a unique temporary test database on the local PostgreSQL server; no concurrency tests were skipped. Migration `hotel.0030_api_cache` is applied to the local development database.
- Frontend: 1 Jest test passed; production build compiled successfully (267.05 kB main JavaScript bundle, gzip).
- Targeted regression tests cover MFA login, cash-accounting rollback, logout revocation, production secret validation, private-media denial, and actual throttle enforcement.

## Production rollout requirements

The live server was not changed. Before deployment, configure unique random values of at least 32 characters for `SECRET_KEY`, `CHAPA_SECRET_KEY`, and `CHAPA_WEBHOOK_SECRET`; valid SMTP credentials; `DJANGO_ENV=production`; `DEBUG=False`; explicit `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and CSRF origins; HTTPS redirects and secure cookies; and an API base URL if frontend and backend use different origins. Review the current `.env` values privately and never include them in logs or this report. Back up the PostgreSQL database, run `python manage.py migrate --settings=core.settings_production`, and deploy the rebuilt frontend and updated Nginx configuration. Verify authentication email delivery and a reversible payment/accounting check in the real environment.

The local Jest assertion checks initial rendering; it does not replace browser testing of the MFA flow against the live SMTP provider.
