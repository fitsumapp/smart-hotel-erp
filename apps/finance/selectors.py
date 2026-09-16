from hotel.models import Account, JournalEntry


def select_accounts(params):
    qs = Account.objects.all()
    if params.get("account_type"):
        qs = qs.filter(account_type=params["account_type"])
    return qs.order_by("code")


def select_journal_entries(params):
    qs = JournalEntry.objects.prefetch_related("items__account")
    if params.get("start_date"):
        qs = qs.filter(date__gte=params["start_date"])
    if params.get("end_date"):
        qs = qs.filter(date__lte=params["end_date"])
    return qs.order_by("-date", "-created_at")
