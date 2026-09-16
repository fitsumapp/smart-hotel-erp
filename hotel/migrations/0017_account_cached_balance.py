"""
Migration: 0017_account_cached_balance.py

Adds ``cached_balance`` to the Account model and back-fills the value
for every existing account row using the same formula as the signal.

RunPython is used (instead of RunSQL) so that:
  • We reuse the Python accounting-convention logic (not raw SQL)
  • The migration is database-agnostic (PostgreSQL, SQLite for tests)
"""

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


# ── Back-fill helper ──────────────────────────────────────────────────────────

def backfill_cached_balances(apps, schema_editor):
    """Recalculate cached_balance for every Account that already exists."""
    Account = apps.get_model("hotel", "Account")
    JournalEntryItem = apps.get_model("hotel", "JournalEntryItem")

    from django.db.models import Sum

    for account in Account.objects.all():
        debits = (
            JournalEntryItem.objects.filter(account=account)
            .aggregate(t=Sum("amount_debit"))["t"]
            or Decimal("0.00")
        )
        credits = (
            JournalEntryItem.objects.filter(account=account)
            .aggregate(t=Sum("amount_credit"))["t"]
            or Decimal("0.00")
        )

        if account.account_type in ("asset", "expense"):
            account.cached_balance = debits - credits
        else:
            account.cached_balance = credits - debits

        account.save(update_fields=["cached_balance"])


def noop(apps, schema_editor):
    """Reverse migration is a no-op: dropping the column is enough."""
    pass


# ── Migration class ───────────────────────────────────────────────────────────

class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0016_payroll_entry"),
    ]

    operations = [
        # 1. Add the column with default=0 so existing rows get 0 immediately.
        migrations.AddField(
            model_name="account",
            name="cached_balance",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                editable=False,
                help_text="Pre-computed ledger balance. Managed automatically by signals.",
                max_digits=14,
            ),
        ),
        # 2. Compute real values for every existing account row.
        migrations.RunPython(backfill_cached_balances, reverse_code=noop),
    ]
