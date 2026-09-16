# Production Infrastructure & Security Hardening Runbook

This runbook documents production hardening configuration, reverse proxy setup, upload security controls, and operational troubleshooting for Smart Hotel ERP.

---

## 1. Django & Application Environment Hardening

### Mandatory Production Environment Variables
When `DJANGO_ENV=production`, startup will fail immediately if any of the following parameters are omitted or insecure:

| Variable | Requirement |
| :--- | :--- |
| `DJANGO_ENV` | Must be explicitly set to `production`. |
| `DEBUG` | Must be `False`. Startup aborts if `True`. |
| `SECRET_KEY` | Must be a strong random secret. Aborts if `django-insecure` prefix is found. |
| `ALLOWED_HOSTS` | Explicit comma-separated domain list (e.g. `hotelerp.acrmatech.com`). Wildcards prohibited. |
| `CSRF_TRUSTED_ORIGINS` | Explicit trusted origin list (e.g. `https://hotelerp.acrmatech.com`). Wildcards prohibited. |
| `CORS_ALLOWED_ORIGINS` | Explicit allowed origins. `CORS_ALLOW_ALL_ORIGINS=True` is prohibited with credentials. |
| `DATABASE_URL` / `DB_*` | Valid PostgreSQL credentials. `sslmode=require` enforced for Neon.tech. |
| `CHAPA_SECRET_KEY` | Production Chapa API secret key. |
| `CHAPA_WEBHOOK_SECRET` | Production HMAC webhook signature secret. |

---

## 2. HTTP Security Headers & Cookie Controls

The application automatically emits the following security headers on all responses via `core.security.SecurityHeadersMiddleware` and `SecurityMiddleware`:

- **Strict-Transport-Security**: `max-age=31536000; includeSubDomains; preload`
- **Content-Security-Policy**: `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https:; connect-src 'self' https://api.chapa.co; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self';`
- **Permissions-Policy**: `camera=(), microphone=(), geolocation=(), payment=()`
- **X-Content-Type-Options**: `nosniff`
- **X-Frame-Options**: `DENY`
- **Referrer-Policy**: `strict-origin-when-cross-origin`
- **Cookies**: `HttpOnly=True`, `Secure=True`, `SameSite=Lax`

---

## 3. Generic Error Handling & Correlation Tracking

- **No Public Tracebacks**: Detailed exceptions and stack traces are suppressed in public responses and written exclusively to protected logs (`logging.exception`).
- **Correlation IDs**: Every request is assigned a unique `X-Request-ID` (or `correlation_id`). All 500/404 JSON and HTML error responses return this correlation ID to assist customer support and audit tracing.
- **Passenger WSGI Guard**: If Django fails during application boot under Passenger WSGI, `passenger_wsgi.py` returns a generic 500 error page without exposing virtual environment paths or Python tracebacks.

---

## 4. File Upload & Sensitive Media Protection

- **Size Limits**: Enforced at 5 MB via `FILE_UPLOAD_MAX_MEMORY_SIZE` and `DATA_UPLOAD_MAX_MEMORY_SIZE`.
- **Magic Signature Validation**: Every upload is validated against its binary header bytes (`\xFF\xD8\xFF` for JPEG, `\x89PNG\r\n\x1a\n` for PNG, `%PDF-` for PDF, `RIFF...WEBP` for WEBP). Disguised scripts (e.g. text or PHP files with `.jpg` extension) are rejected.
- **Non-User-Controlled Storage Names**: Uploaded filenames are converted to UUID4 hashes (`uuid4().hex + ext`), preventing path traversal and name collisions.
- **Image Re-encoding**: Uploaded images are parsed and re-encoded using Pillow, stripping EXIF tags and embedded malicious metadata.
- **Private Guest Identity Storage**: Guest identity scans (`GuestProfile.id_scan`) are stored in `media/private/guest_ids/`.
- **Authorized Download Endpoint**: Direct web access to `media/private/` is denied. Downloads are served exclusively through `/api/v1/users/guest-profiles/<id>/id-scan/` requiring valid reception or administrator JWT credentials.
- **Script Execution Block**: Upload directories contain `.htaccess` and Nginx rules denying CGI/script execution.

---

## 5. Edge Protection & Reverse Proxy Setup

Nginx must be deployed in front of the application using `docs/nginx.conf.template`:
1. **HTTPS Enforcement**: HTTP traffic automatically redirects to HTTPS.
2. **Edge Rate Limiting**:
   - `/api/v1/auth/login/`: 5 requests / minute
   - `/api/v1/auth/verify-otp/`: 3 requests / minute
   - `/api/v1/auth/register/`: 5 requests / minute
   - `/api/v1/payments/`: 10 requests / minute
3. **Scanner Blocking**: User-Agent block rules for malicious scanners (`nikto`, `sqlmap`, `nmap`, etc.).

---

## 6. Automated Verification

Run security and infrastructure hardening tests:
```powershell
python manage.py test core.tests_hardening
```
