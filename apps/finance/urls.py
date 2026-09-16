from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import *  # noqa: F401,F403

router = DefaultRouter()
router.register(r"finance/accounts", AccountViewSet, basename="account")
router.register(r"finance/journal-entries", JournalEntryViewSet, basename="journalentry")
router.register(r"finance/expenses", ExpenseTransactionViewSet, basename="expensetransaction")
router.register(r"finance/budgets", BudgetViewSet, basename="budget")
router.register(r"finance/payroll", PayrollEntryViewSet, basename="payrollentry")

urlpatterns = [
    path("finance/statements/", FinancialStatementsView.as_view(), name="finance-statements"),
    path("finance/tax-report/", TaxReportView.as_view(), name="finance-tax-report"),
    path("finance/payroll-summary/", PayrollSummaryView.as_view(), name="finance-payroll-summary"),
] + router.urls
