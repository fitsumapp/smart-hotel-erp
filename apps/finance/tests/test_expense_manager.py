"""Tests for Expense Manager, Supplier permissions, and Chart of Accounts."""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import Account, ExpenseTransaction, JournalEntry, Supplier
from users.models import User


class ExpenseManagerTests(TestCase):
    """Test suite for Task 1: Expense Manager, Supplier permissions, and Account dropdowns."""

    def setUp(self):
        self.client = APIClient()

        self.finance_user = User.objects.create_user(
            username="test_finance", email="finance@test.com", password="Password123!",
            role=User.FINANCE, is_active=True
        )
        self.inventory_user = User.objects.create_user(
            username="test_inventory", email="inventory@test.com", password="Password123!",
            role=User.INVENTORY, is_active=True
        )
        self.waiter_user = User.objects.create_user(
            username="test_waiter", email="waiter@test.com", password="Password123!",
            role=User.WAITER, is_active=True
        )
        self.admin_user = User.objects.create_superuser(
            username="test_admin", email="admin@test.com", password="Password123!",
            role=User.ADMIN, is_active=True
        )

        self.supplier = Supplier.objects.create(
            name="Alpha Supplies", contact_person="John", email="alpha@supplies.test", phone="0911223344"
        )

    def test_finance_role_can_access_suppliers_endpoint(self):
        """Finance staff can access GET /api/users/suppliers/ without 403 Forbidden."""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/suppliers/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(s["name"] == "Alpha Supplies" for s in res.data))

    def test_inventory_and_admin_roles_can_access_suppliers(self):
        """Inventory staff and Admin can access GET /api/users/suppliers/."""
        self.client.force_authenticate(user=self.inventory_user)
        res_inv = self.client.get("/api/users/suppliers/")
        self.assertEqual(res_inv.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.admin_user)
        res_adm = self.client.get("/api/users/suppliers/")
        self.assertEqual(res_adm.status_code, status.HTTP_200_OK)

    def test_unauthorized_roles_cannot_access_suppliers(self):
        """Waiter cannot access GET /api/users/suppliers/ (returns 403)."""
        self.client.force_authenticate(user=self.waiter_user)
        res_waiter = self.client.get("/api/users/suppliers/")
        self.assertEqual(res_waiter.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_accounts_include_petty_cash_and_expenses(self):
        """Accounts endpoint populates default accounts including Petty Cash (1020) and expense accounts."""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/accounts/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        codes = {a["code"]: a for a in res.data}
        # Check payment accounts
        self.assertIn("1000", codes) # Cash
        self.assertEqual(codes["1000"]["account_type"], "asset")
        self.assertIn("1010", codes) # Bank Transfer
        self.assertEqual(codes["1010"]["account_type"], "asset")
        self.assertIn("1020", codes) # Petty Cash
        self.assertEqual(codes["1020"]["account_type"], "asset")
        self.assertEqual(codes["1020"]["name"], "Petty Cash")

        # Check expense accounts
        self.assertIn("5000", codes)
        self.assertEqual(codes["5000"]["account_type"], "expense")
        self.assertIn("5100", codes) # Salary Expense
        self.assertEqual(codes["5100"]["account_type"], "expense")
        self.assertIn("5200", codes) # Utility Expense
        self.assertEqual(codes["5200"]["account_type"], "expense")

    def test_finance_log_expense_creates_record_and_journal_entry(self):
        """Logging an expense creates ExpenseTransaction and double-entry JournalEntry."""
        self.client.force_authenticate(user=self.finance_user)

        # Trigger ensure_default_accounts
        self.client.get("/api/users/finance/accounts/")

        expense_acct = Account.objects.get(code="5200") # Utility Expense
        payment_acct = Account.objects.get(code="1020") # Petty Cash

        payload = {
            "description": "Monthly Office Internet",
            "amount": "1500.00",
            "date": timezone.now().date().isoformat(),
            "expense_account": expense_acct.id,
            "payment_account": payment_acct.id,
            "supplier": self.supplier.id,
            "reference_number": "INV-NET-991",
        }

        res = self.client.post("/api/users/finance/expenses/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["description"], "Monthly Office Internet")
        self.assertEqual(res.data["expense_account_name"], "Utility Expense")
        self.assertEqual(res.data["payment_account_name"], "Petty Cash")

        # Verify ExpenseTransaction created in DB
        expense_obj = ExpenseTransaction.objects.get(id=res.data["id"])
        self.assertEqual(expense_obj.amount, Decimal("1500.00"))

        # Verify JournalEntry created with debit to Utility Expense and credit to Petty Cash
        jv = JournalEntry.objects.filter(description__icontains="Monthly Office Internet").first()
        self.assertIsNotNone(jv)
        items = list(jv.items.all())
        self.assertEqual(len(items), 2)
        debit_item = next(i for i in items if i.amount_debit > 0)
        credit_item = next(i for i in items if i.amount_credit > 0)
        self.assertEqual(debit_item.account.code, "5200")
        self.assertEqual(debit_item.amount_debit, Decimal("1500.00"))
        self.assertEqual(credit_item.account.code, "1020")
        self.assertEqual(credit_item.amount_credit, Decimal("1500.00"))
