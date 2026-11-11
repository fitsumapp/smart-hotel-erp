import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from hotel.inventory import evaluate_inventory_expiry_alerts
from hotel.stocktaking import process_due_stocktake_schedules

logger = logging.getLogger("smart_hotel.scheduler")


class Command(BaseCommand):
    help = "Periodic execution worker for inventory expiry alerts and automated stocktaking schedules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run as a persistent daemon polling periodically.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Polling interval in seconds when running in daemon mode (default: 60).",
        )
        parser.add_argument(
            "--expiry-only",
            action="store_true",
            help="Run only the expiry alert evaluation.",
        )
        parser.add_argument(
            "--stocktake-only",
            action="store_true",
            help="Run only the automated stocktaking schedule processing.",
        )

    def handle(self, *args, **options):
        is_daemon = options["daemon"]
        interval = options["interval"]
        expiry_only = options["expiry_only"]
        stocktake_only = options["stocktake_only"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting inventory scheduler worker (daemon={is_daemon}, interval={interval}s)..."
            )
        )

        while True:
            cycle_start = timezone.now()
            self.stdout.write(f"[{cycle_start.isoformat()}] Running scheduled inventory jobs...")

            # 1. Expiry alerts
            if not stocktake_only:
                try:
                    expiry_res = evaluate_inventory_expiry_alerts()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [Expiry Alerts] Created: {expiry_res['created']}, "
                            f"Updated: {expiry_res['updated']}, "
                            f"Resolved: {expiry_res['resolved']}, "
                            f"Active Total: {expiry_res['active_total']}"
                        )
                    )
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"  [Expiry Alerts Error] {exc}"))
                    logger.exception("Failed during evaluate_inventory_expiry_alerts")

            # 2. Automated stocktake schedules
            if not expiry_only:
                try:
                    sched_res = process_due_stocktake_schedules()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [Stocktake Schedules] Executed: {len(sched_res['executed'])}, "
                            f"Skipped: {len(sched_res['skipped'])}, "
                            f"Failed: {len(sched_res['failed'])}"
                        )
                    )
                    for item in sched_res["executed"]:
                        self.stdout.write(f"    - Generated session #{item['session_number']} for schedule #{item['schedule_id']}")
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"  [Stocktake Schedules Error] {exc}"))
                    logger.exception("Failed during process_due_stocktake_schedules")

            if not is_daemon:
                self.stdout.write(self.style.SUCCESS("Scheduler one-shot execution complete."))
                break

            time.sleep(interval)

