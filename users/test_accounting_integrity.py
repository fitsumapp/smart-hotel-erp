from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from hotel.accounting import post_entry, reconcile_balances, reverse_entry
from hotel.models import Account, JournalEntry


class AccountingIntegrityTests(TestCase):
    def setUp(self):
        self.cash = Account.objects.create(code="T-CASH", name="Test Cash", account_type="asset")
        self.revenue = Account.objects.create(code="T-REV", name="Test Revenue", account_type="revenue")

    def lines(self, amount):
        return [
            {"account_code": self.cash.code, "debit": amount, "credit": "0"},
            {"account_code": self.revenue.code, "debit": "0", "credit": amount},
        ]

    def test_balanced_post_updates_both_cached_balances(self):
        entry = post_entry(description="Balanced sale", lines=self.lines("125.00"))
        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(entry.items.count(), 2)
        self.assertEqual(self.cash.cached_balance, Decimal("125.00"))
        self.assertEqual(self.revenue.cached_balance, Decimal("125.00"))

    def test_unbalanced_post_rolls_back_completely(self):
        with self.assertRaises(ValidationError):
            post_entry(description="Bad entry", lines=[
                {"account_code": self.cash.code, "debit": "100.00", "credit": "0"},
                {"account_code": self.revenue.code, "debit": "0", "credit": "99.99"},
            ])
        self.assertFalse(JournalEntry.objects.filter(description="Bad entry").exists())

    def test_posted_entry_and_lines_are_immutable(self):
        entry = post_entry(description="Immutable entry", lines=self.lines("50"))
        entry.description = "Tampered"
        with self.assertRaises(ValidationError):
            entry.save()
        with self.assertRaises(ValidationError):
            entry.delete()
        line = entry.items.first()
        line.amount_debit = Decimal("1.00")
        with self.assertRaises(ValidationError):
            line.save()
        with self.assertRaises(ValidationError):
            line.delete()

    def test_reversal_is_balanced_and_idempotent(self):
        original = post_entry(description="Sale to reverse", lines=self.lines("80"))
        reversal, created = reverse_entry(entry_id=original.pk, reason="Operator correction")
        retry, retry_created = reverse_entry(entry_id=original.pk, reason="Duplicate retry")
        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(reversal.pk, retry.pk)
        self.cash.refresh_from_db()
        self.revenue.refresh_from_db()
        self.assertEqual(self.cash.cached_balance, Decimal("0.00"))
        self.assertEqual(self.revenue.cached_balance, Decimal("0.00"))

    def test_reconciliation_reports_and_repairs_cache_drift(self):
        post_entry(description="Drift source", lines=self.lines("20"))
        Account.objects.filter(pk=self.cash.pk).update(cached_balance=Decimal("999.00"))
        self.assertEqual(len(reconcile_balances(repair=False)), 1)
        self.assertEqual(len(reconcile_balances(repair=True)), 1)
        self.assertEqual(reconcile_balances(repair=False), [])
