from django.core.management.base import BaseCommand, CommandError

from hotel.inventory import reconcile_stock


class Command(BaseCommand):
    help = "Report inventory balance mismatches; use --repair to correct them."

    def add_arguments(self, parser):
        parser.add_argument("--repair", action="store_true")

    def handle(self, *args, **options):
        mismatches = reconcile_stock(repair=options["repair"])
        for row in mismatches:
            self.stdout.write(f"{row['code']}: cached={row['cached']} expected={row['expected']}")
        if mismatches and not options["repair"]:
            raise CommandError(f"{len(mismatches)} stock balance mismatch(es) found.")
        action = "repaired" if options["repair"] else "found"
        self.stdout.write(self.style.SUCCESS(f"{len(mismatches)} mismatch(es) {action}."))
