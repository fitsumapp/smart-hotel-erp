from django.core.management.base import BaseCommand, CommandError

from apps.payments.services import reconcile_payment_attempt
from hotel.models import PaymentAttempt


class Command(BaseCommand):
    help = "Compare local Chapa payment attempts with provider truth."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--include-failed", action="store_true")

    def handle(self, *args, **options):
        limit = min(max(options["limit"], 1), 5000)
        statuses = ["initiated", "verified"]
        if options["include_failed"]:
            statuses.append("failed")
        attempts = PaymentAttempt.objects.filter(status__in=statuses).order_by("updated_at")[:limit]
        mismatches = []
        checked = 0
        for attempt in attempts.iterator():
            checked += 1
            result = reconcile_payment_attempt(attempt)
            if result != "matched":
                mismatches.append((attempt.pk, attempt.provider_tx_ref, result))
                self.stdout.write(f"attempt={attempt.pk} tx_ref={attempt.provider_tx_ref} result={result}")
        self.stdout.write(f"Checked {checked} payment attempt(s); {len(mismatches)} mismatch(es).")
        if mismatches:
            raise CommandError("Payment reconciliation found mismatches; investigate before repairing local state.")
