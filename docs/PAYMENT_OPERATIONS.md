# Payment operations

## Required configuration

- `CHAPA_SECRET_KEY`: Chapa API secret used only for server-to-server requests.
- `CHAPA_WEBHOOK_SECRET`: independent random webhook secret configured in the Chapa dashboard.
- `BACKEND_BASE_URL`: public HTTPS backend origin used for callback URLs.

Production must not fall back from `CHAPA_WEBHOOK_SECRET` to the API key. Rotate both values independently and never place either value in frontend code or logs.

## Webhook behavior

The webhook endpoint verifies the Chapa HMAC before parsing business data, re-queries Chapa for transaction truth, binds the result to the stored `PaymentAttempt`, and compares transaction reference, exact amount and currency. Every accepted signed delivery creates an immutable `PaymentWebhookEvent`. Duplicate events and duplicate successful transaction callbacks return success without repeating inventory, accounting or state transitions.

QR and confirmation codes identify a reservation only. Final check-in and checkout require an authenticated reception or administrator account.

## Reconciliation

Run at least every 15 minutes from the production scheduler:

```powershell
python manage.py reconcile_payments --limit 500
```

The command is report-only and exits non-zero when it finds provider/local mismatches. Investigate the referenced attempt and provider transaction before changing any local financial state. Also continue scheduled accounting reconciliation:

```powershell
python manage.py reconcile_accounts
```

## Incident checks

1. Search by internal `PaymentAttempt.provider_tx_ref`.
2. Confirm its target, expected amount, currency and purpose.
3. Inspect linked immutable webhook receipts.
4. Compare `verified_at`, provider event reference and reconciliation status.
5. Confirm exactly one linked accounting entry.
6. Never delete or edit payment history; correct accounting with a reversing entry.
