"""Transactional, append-only double-entry accounting services."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Account, JournalEntry, JournalEntryItem


CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


@transaction.atomic
def post_entry(*, description, lines, entry_date=None, reversal_of=None):
    """Validate and atomically post a balanced journal and its cached balances."""
    if not description or not str(description).strip():
        raise ValidationError("Journal description is required.")
    if len(lines) < 2:
        raise ValidationError("A journal entry requires at least two lines.")

    codes = [line.get("account_code") for line in lines]
    accounts = {
        account.code: account
        for account in Account.objects.select_for_update().filter(code__in=codes)
    }
    if len(accounts) != len(set(codes)):
        missing = sorted(set(codes) - set(accounts))
        raise ValidationError(f"Unknown account code(s): {', '.join(str(x) for x in missing)}")

    prepared = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for line in lines:
        debit = _money(line.get("debit"))
        credit = _money(line.get("credit"))
        if debit < 0 or credit < 0 or (debit == 0 and credit == 0):
            raise ValidationError("Journal amounts must be non-negative and each line must have an amount.")
        prepared.append((accounts[line["account_code"]], debit, credit))
        total_debit += debit
        total_credit += credit
    if total_debit != total_credit:
        raise ValidationError(f"Journal is not balanced: debits {total_debit}, credits {total_credit}.")

    entry = JournalEntry.objects.create(
        description=str(description).strip(), date=entry_date or timezone.now().date(),
        reversal_of=reversal_of,
    )
    for account, debit, credit in prepared:
        JournalEntryItem.objects.create(
            entry=entry, account=account, amount_debit=debit, amount_credit=credit,
        )

    # Compatibility signals update caches for direct historical writes. A
    # service posting additionally proves every cache update succeeded.
    for account in accounts.values():
        account.refresh_from_db(fields=["cached_balance"])
        expected = expected_account_balance(account)
        if account.cached_balance != expected:
            raise ValidationError(
                f"Balance cache update failed for account {account.code}."
            )

    return entry

@transaction.atomic
def reverse_entry(*, entry_id, reason, entry_date=None):
    original = JournalEntry.objects.select_for_update().prefetch_related("items__account").get(pk=entry_id)
    if hasattr(original, "reversed_by"):
        return original.reversed_by, False
    lines = [
        {
            "account_code": item.account.code,
            "debit": item.amount_credit,
            "credit": item.amount_debit,
        }
        for item in original.items.all()
    ]
    reversal = post_entry(
        description=f"REVERSAL of {original.entry_number}: {reason}", lines=lines,
        entry_date=entry_date, reversal_of=original,
    )
    return reversal, True


def expected_account_balance(account):
    totals = account.ledger_items.aggregate(debits=Sum("amount_debit"), credits=Sum("amount_credit"))
    debits = totals["debits"] or Decimal("0.00")
    credits = totals["credits"] or Decimal("0.00")
    return debits - credits if account.account_type in ("asset", "expense") else credits - debits


@transaction.atomic
def reconcile_balances(*, repair=False):
    mismatches = []
    for account in Account.objects.select_for_update().all():
        expected = expected_account_balance(account)
        if account.cached_balance != expected:
            mismatches.append({"id": account.pk, "code": account.code, "cached": account.cached_balance, "expected": expected})
            if repair:
                Account.objects.filter(pk=account.pk).update(cached_balance=expected)
    return mismatches
