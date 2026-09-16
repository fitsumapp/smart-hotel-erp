"""Finance transactional and business services."""
from users.views import *  # noqa: F401,F403

def ensure_default_accounts():
    """
    Populates standard general ledger Chart of Accounts if not already created.
    """
    defaults = [
        # Assets (1000 - 1999)
        ("1000", "Cash", "asset"),
        ("1010", "Bank Transfer", "asset"),
        ("1200", "Accounts Receivable", "asset"),
        ("1300", "Inventory Asset", "asset"),
        
        # Liabilities (2000 - 2999)
        ("2000", "Accounts Payable", "liability"),
        ("2200", "VAT Payable", "liability"),
        ("2300", "Service Charge Payable", "liability"),
        
        # Equity (3000 - 3999)
        ("3000", "Retained Earnings", "equity"),
        
        # Revenue (4000 - 4999)
        ("4000", "Room Revenue", "revenue"),
        ("4100", "F&B Revenue", "revenue"),
        ("4200", "Folio Extras Revenue", "revenue"),
        
        # Expenses (5000 - 5999)
        ("5000", "Inventory Cost of Goods Sold", "expense"),
        ("5100", "Salary Expense", "expense"),
        ("5200", "Utility Expense", "expense"),
        ("5300", "Rent Expense", "expense"),
        ("5900", "Miscellaneous Expense", "expense"),
    ]
    for code, name, acct_type in defaults:
        Account.objects.get_or_create(code=code, defaults={"name": name, "account_type": acct_type})


def post_journal_entry(description, items, date=None):
    """
    Creates a balanced double-entry JournalEntry and associated items.
    'items' is a list of dicts: [{'account_code': '1000', 'debit': Decimal('100.00'), 'credit': Decimal('0.00')}]
    """
    ensure_default_accounts()
    try:
        return post_entry(description=description, lines=items, entry_date=date)
    except Exception as exc:
        message = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        raise ValueError(message) from exc


