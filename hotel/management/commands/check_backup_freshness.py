from pathlib import Path
from time import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Fail if the newest PostgreSQL backup is older than the allowed age."
    def add_arguments(self, parser):
        parser.add_argument("--directory", default=str(settings.BASE_DIR / "backups"))
        parser.add_argument("--max-age-hours", type=float, default=26.0)
    def handle(self, *args, **options):
        directory = Path(options["directory"]).resolve()
        if options["max_age_hours"] <= 0:
            raise CommandError("--max-age-hours must be positive.")
        candidates = [p for p in directory.glob("*.dump") if p.is_file()] if directory.exists() else []
        if not candidates:
            raise CommandError(f"No PostgreSQL .dump backup found in {directory}.")
        newest = max(candidates, key=lambda p: p.stat().st_mtime)
        age_hours = (time() - newest.stat().st_mtime) / 3600
        self.stdout.write(f"Newest backup: {newest.name}; age={age_hours:.2f}h")
        if age_hours > options["max_age_hours"]:
            raise CommandError(f"Backup is stale ({age_hours:.2f}h > {options['max_age_hours']:.2f}h).")
        self.stdout.write(self.style.SUCCESS("Backup freshness check passed."))
