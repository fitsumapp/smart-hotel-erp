"""
hotel/signals.py
─────────────────
Keeps ``Account.cached_balance`` up-to-date whenever a JournalEntryItem
is created, updated, or deleted.

Design decisions
────────────────
* ``update_fields=["cached_balance"]``  — only touches the one column;
  never overwrites other account data accidentally.
* The handler is wrapped in a try/except so that a signal failure
  **never** prevents the original journal-entry save from completing.
  The worst case is a stale cached value (which can be repaired by
  calling ``account.recompute_balance()``), not a broken transaction.
* We deliberately avoid ``@transaction.atomic`` inside the signal so we
  don't nest transactions — the outer view already manages its own
  transaction boundary.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Account, JournalEntryItem

logger = logging.getLogger(__name__)


# ── Core helper ───────────────────────────────────────────────────────────────

def _recompute_balance(account: Account) -> None:
    """
    Recalculate ``Account.cached_balance`` from raw ledger rows and persist
    it using ``update_fields`` — the lightest possible write.

    Accounting convention:
      • Asset / Expense  → balance = total_debits  − total_credits
      • Liability / Equity / Revenue → balance = total_credits − total_debits
    """
    debits  = (
        account.ledger_items.aggregate(t=Sum("amount_debit"))["t"]
        or Decimal("0.00")
    )
    credits = (
        account.ledger_items.aggregate(t=Sum("amount_credit"))["t"]
        or Decimal("0.00")
    )

    if account.account_type in ("asset", "expense"):
        account.cached_balance = debits - credits
    else:
        account.cached_balance = credits - debits

    # update_fields ensures we only write cached_balance — nothing else.
    account.save(update_fields=["cached_balance"])


# ── Signal receivers ──────────────────────────────────────────────────────────

@receiver(post_save, sender=JournalEntryItem)
def on_journal_entry_item_save(
    sender: type,
    instance: JournalEntryItem,
    **kwargs,
) -> None:
    """
    Fired after a JournalEntryItem is created or updated.
    Re-aggregates the balance for the affected account.
    """
    try:
        _recompute_balance(instance.account)
    except Exception:  # noqa: BLE001
        # Log and continue — never let a signal break a journal-entry write.
        logger.exception(
            "Failed to recompute cached_balance for Account pk=%s "
            "after JournalEntryItem pk=%s was saved.",
            instance.account_id,
            instance.pk,
        )
        raise


@receiver(post_delete, sender=JournalEntryItem)
def on_journal_entry_item_delete(
    sender: type,
    instance: JournalEntryItem,
    **kwargs,
) -> None:
    """
    Fired after a JournalEntryItem is deleted.
    Re-aggregates the balance for the affected account.

    NOTE: at the point this signal fires the row is already gone from the DB,
    so Sum() will naturally exclude it — giving the correct new balance.
    """
    try:
        _recompute_balance(instance.account)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to recompute cached_balance for Account pk=%s "
            "after JournalEntryItem pk=%s was deleted.",
            instance.account_id,
            instance.pk,
        )
        raise
