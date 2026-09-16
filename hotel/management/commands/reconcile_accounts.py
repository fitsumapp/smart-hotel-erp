from django.core.management.base import BaseCommand

from hotel.accounting import reconcile_balances


class Command(BaseCommand):
    help = "Report cached account balance mismatches; use --repair to correct them."

    def add_arguments(self, parser):
        parser.add_argument("--repair", action="store_true")

    def handle(self, *args, **options):
        mismatches = reconcile_balances(repair=options["repair"])
        for row in mismatches:
            self.stdout.write(f"{row['code']}: cached={row['cached']} expected={row['expected']}")
        action = "repaired" if options["repair"] else "found"
        self.stdout.write(self.style.SUCCESS(f"{len(mismatches)} mismatch(es) {action}."))
