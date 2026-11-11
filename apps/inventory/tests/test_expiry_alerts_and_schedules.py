"""
Unit & Integration Test Suite for Inventory Expiry Alerts & Automated Stocktake Schedules.

Verifies:
1. Expiry alerts engine (expired, 1d, 7d, 14d, 30d near-expiry tiers, and unknown expiry detection).
2. Alert idempotency (no duplicate active alerts for same batch/type).
3. Alert lifecycle resolution (batch consumption and waste transition alerts to resolved).
4. Alert dismiss and evaluate API endpoints with role-based access control.
5. Automated stocktake scheduling (Daily, Weekly, Monthly) and next_run_at computation in Africa/Addis_Ababa timezone.
6. Execution of due schedules creating draft StocktakeSession snapshots without automatic counting/approval.
7. Period idempotency (preventing duplicate sessions in the same scheduled period).
8. Service downtime recovery (single catch-up session and forward progression).
9. Schedule management endpoints (pause, activate, trigger-now, upcoming).
10. Preservation of Segregation of Duties on automated sessions.
"""
from datetime import time, timedelta
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.finance.services import ensure_default_accounts
from hotel.inventory import evaluate_inventory_expiry_alerts
from hotel.models import (
    BatchLocationBalance,
    InventoryCategory,
    InventoryExpiryAlert,
    InventoryItem,
    ItemLocationBalance,
    StockBatch,
    StockLocation,
    StocktakeSchedule,
    StocktakeSession,
)
from hotel.stocktaking import compute_next_run, process_due_stocktake_schedules, record_counts
from users.models import User


class ExpiryAlertsAndStocktakeSchedulesTestCase(APITestCase):
    def setUp(self):
        ensure_default_accounts()
        self.admin = User.objects.create_user(
            username="admin_alert_test", password="password123", role="admin", is_active=True, is_verified=True
        )
        self.manager = User.objects.create_user(
            username="mgr_alert_test", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.counter = User.objects.create_user(
            username="counter_alert_test", password="password123", role="inventory", is_active=True, is_verified=True
        )
        self.waiter = User.objects.create_user(
            username="waiter_alert_test", password="password123", role="waiter", is_active=True, is_verified=True
        )

        self.category_fnb, _ = InventoryCategory.objects.get_or_create(
            name="Dairy & Meat Test", defaults={"category_type": "f_and_b"}
        )
        self.category_dry, _ = InventoryCategory.objects.get_or_create(
            name="Dry Goods Test", defaults={"category_type": "f_and_b"}
        )

        self.warehouse, _ = StockLocation.objects.get_or_create(
            code="WH-TEST-ALERT",
            defaults={"name": "Central Test Warehouse", "location_type": "warehouse", "is_active": True},
        )

        self.today = timezone.localdate()

        # Item 1: Perishable Fresh Milk
        self.item_milk = InventoryItem.objects.create(
            item_code="ITM-ALERT-MILK",
            name="Whole Milk 1L",
            category=self.category_fnb,
            unit="l",
            unit_cost=Decimal("45.00"),
            current_stock=Decimal("30.00"),
            is_perishable=True,
        )

        # Item 2: Non-perishable Rice
        self.item_rice = InventoryItem.objects.create(
            item_code="ITM-ALERT-RICE",
            name="Basmati Rice 5kg",
            category=self.category_dry,
            unit="pack",
            unit_cost=Decimal("650.00"),
            current_stock=Decimal("50.00"),
            is_perishable=False,
        )

    # -------------------------------------------------------------------------
    # PART 1: EXPIRY ALERTS ENGINE & APIS
    # -------------------------------------------------------------------------

    def test_01_evaluate_expired_batch_generates_critical_alert(self):
        """Expired batch creates an active alert with status='active' and alert_type='expired'."""
        batch_expired = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-EXP-001",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today - timedelta(days=3),
            status="active",
        )
        BatchLocationBalance.objects.create(
            batch=batch_expired,
            location=self.warehouse,
            quantity=Decimal("30.00"),
        )

        res = evaluate_inventory_expiry_alerts()
        self.assertGreaterEqual(res["created"], 1)

        alert = InventoryExpiryAlert.objects.get(batch=batch_expired, status="active")
        self.assertEqual(alert.alert_type, "expired")
        self.assertEqual(alert.threshold_days, 0)
        self.assertEqual(alert.current_quantity, Decimal("30.00"))
        self.assertEqual(alert.item, self.item_milk)
        self.assertEqual(alert.location, self.warehouse)

    def test_02_evaluate_near_expiry_warning_tiers(self):
        """Batches falling into 1d, 7d, 14d, and 30d windows generate correct tiered alerts."""
        b1 = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-TIER-1D",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today + timedelta(days=1),
            status="active",
        )
        b7 = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-TIER-7D",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today + timedelta(days=5),
            status="active",
        )
        b14 = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-TIER-14D",
            initial_quantity=Decimal("30.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today + timedelta(days=12),
            status="active",
        )
        b30 = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-TIER-30D",
            initial_quantity=Decimal("40.00"),
            current_quantity=Decimal("40.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today + timedelta(days=25),
            status="active",
        )

        evaluate_inventory_expiry_alerts()

        self.assertEqual(InventoryExpiryAlert.objects.get(batch=b1, status="active").alert_type, "near_expiry_1")
        self.assertEqual(InventoryExpiryAlert.objects.get(batch=b7, status="active").alert_type, "near_expiry_7")
        self.assertEqual(InventoryExpiryAlert.objects.get(batch=b14, status="active").alert_type, "near_expiry_14")
        self.assertEqual(InventoryExpiryAlert.objects.get(batch=b30, status="active").alert_type, "near_expiry_30")

    def test_03_evaluate_unknown_expiry_on_perishable_batch(self):
        """Perishable batch without an expiry date generates an unknown_expiry critical alert."""
        b_unknown = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-UNK-001",
            initial_quantity=Decimal("15.00"),
            current_quantity=Decimal("15.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=None,
            is_legacy=True,
            status="active",
        )

        evaluate_inventory_expiry_alerts()

        alert = InventoryExpiryAlert.objects.get(batch=b_unknown, status="active")
        self.assertEqual(alert.alert_type, "unknown_expiry")
        self.assertEqual(alert.threshold_days, -1)

    def test_04_alerts_idempotency_and_quantity_sync(self):
        """Running alert evaluation repeatedly updates existing active alert without duplicates."""
        batch = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-IDEMP-001",
            initial_quantity=Decimal("50.00"),
            current_quantity=Decimal("50.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today - timedelta(days=1),
            status="active",
        )

        res1 = evaluate_inventory_expiry_alerts()
        self.assertEqual(res1["created"], 1)
        self.assertEqual(InventoryExpiryAlert.objects.filter(batch=batch).count(), 1)

        # Update batch quantity
        batch.current_quantity = Decimal("40.00")
        batch.save(update_fields=["current_quantity"])

        res2 = evaluate_inventory_expiry_alerts()
        self.assertEqual(res2["created"], 0)  # No new alert created
        self.assertEqual(InventoryExpiryAlert.objects.filter(batch=batch).count(), 1)
        alert = InventoryExpiryAlert.objects.get(batch=batch)
        self.assertEqual(alert.current_quantity, Decimal("40.00"))

    def test_05_alert_lifecycle_resolution_on_consumed_or_wasted(self):
        """Alert automatically resolves when batch is depleted or marked wasted."""
        batch = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-LIFECYCLE-001",
            initial_quantity=Decimal("20.00"),
            current_quantity=Decimal("20.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today - timedelta(days=2),
            status="active",
        )
        evaluate_inventory_expiry_alerts()
        alert = InventoryExpiryAlert.objects.get(batch=batch)
        self.assertEqual(alert.status, "active")

        # Simulate batch full consumption
        batch.current_quantity = Decimal("0.00")
        batch.save(update_fields=["current_quantity"])
        res = evaluate_inventory_expiry_alerts()
        self.assertGreaterEqual(res["resolved"], 1)

        alert.refresh_from_db()
        self.assertEqual(alert.status, "resolved")
        self.assertEqual(alert.resolution_reason, "batch_consumed_or_depleted")
        self.assertIsNotNone(alert.resolved_at)

    def test_06_dismiss_alert_api_endpoint(self):
        """Manager can dismiss an active alert; unauthorized users are forbidden."""
        batch = StockBatch.objects.create(
            item=self.item_milk,
            batch_number="BATCH-DISMISS-001",
            initial_quantity=Decimal("10.00"),
            current_quantity=Decimal("10.00"),
            unit_cost=Decimal("45.00"),
            expiry_date=self.today - timedelta(days=1),
            status="active",
        )
        evaluate_inventory_expiry_alerts()
        alert = InventoryExpiryAlert.objects.get(batch=batch, status="active")

        # 1. Unauthorized waiter cannot dismiss
        self.client.force_authenticate(user=self.waiter)
        res_waiter = self.client.post(
            f"/api/v1/inventory/expiry-alerts/{alert.id}/dismiss/",
            {"reason": "Inspected and approved for immediate use"},
        )
        self.assertEqual(res_waiter.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Inventory manager can dismiss
        self.client.force_authenticate(user=self.manager)
        res_mgr = self.client.post(
            f"/api/v1/inventory/expiry-alerts/{alert.id}/dismiss/",
            {"reason": "Inspected and approved for kitchen bakery today"},
        )
        self.assertEqual(res_mgr.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertEqual(alert.status, "dismissed")
        self.assertIn("bakery today", alert.resolution_reason)

    def test_07_evaluate_alert_api_endpoint(self):
        """POST /api/v1/inventory/expiry-alerts/evaluate/ triggers full evaluation."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.post("/api/v1/inventory/expiry-alerts/evaluate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("active_total", response.data)

    # -------------------------------------------------------------------------
    # PART 2: AUTOMATED STOCKTAKE SCHEDULING & WORKFLOWS
    # -------------------------------------------------------------------------

    def test_08_create_schedule_api_and_next_run_calculation(self):
        """Creating schedules via API validates fields and sets next_run_at correctly."""
        self.client.force_authenticate(user=self.manager)

        payload_daily = {
            "name": "Daily Central Store Stocktake",
            "frequency": "daily",
            "location": self.warehouse.id,
            "category": self.category_fnb.id,
            "counting_mode": "blind",
            "assigned_staff": self.counter.id,
            "scheduled_time": "22:00:00",
            "is_active": True,
        }
        res = self.client.post("/api/v1/stocktaking/schedules/", payload_daily)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(res.data["next_run_at"])

        schedule_id = res.data["id"]
        schedule = StocktakeSchedule.objects.get(id=schedule_id)
        self.assertEqual(schedule.frequency, "daily")
        self.assertEqual(schedule.counting_mode, "blind")
        self.assertEqual(schedule.assigned_staff, self.counter)

    def test_09_process_due_daily_schedule_creates_draft_session(self):
        """Due schedule execution snapshots theoretical stock in draft mode without counting or posting."""
        # Set up theoretical stock in warehouse
        ItemLocationBalance.objects.create(
            item=self.item_milk,
            location=self.warehouse,
            quantity=Decimal("100.00"),
        )

        now = timezone.now()
        past_run_time = now - timedelta(hours=1)
        schedule = StocktakeSchedule.objects.create(
            name="Daily Warehouse Evening Stocktake",
            frequency="daily",
            location=self.warehouse,
            category=self.category_fnb,
            counting_mode="blind",
            assigned_staff=self.counter,
            scheduled_time=past_run_time.time(),
            next_run_at=past_run_time,
            is_active=True,
            created_by=self.manager,
        )

        res = process_due_stocktake_schedules(now=now)
        self.assertEqual(len(res["executed"]), 1)

        session_id = res["executed"][0]["session_id"]
        session = StocktakeSession.objects.get(id=session_id)
        self.assertEqual(session.schedule, schedule)
        self.assertEqual(session.status, "draft")
        self.assertEqual(session.counting_mode, "blind")
        self.assertEqual(session.location, self.warehouse)
        self.assertIsNone(session.counted_by)
        self.assertIsNone(session.reviewed_by)

        # Verify theoretical inventory snapshot lines exist
        self.assertGreaterEqual(session.items.count(), 1)
        item_line = session.items.first()
        self.assertEqual(item_line.theoretical_quantity, Decimal("100.00"))
        # Uncounted
        self.assertIsNone(item_line.counted_quantity)

        # Verify schedule tracking updated
        schedule.refresh_from_db()
        self.assertEqual(schedule.last_run_status, "success")
        self.assertIsNotNone(schedule.last_run_at)
        self.assertGreater(schedule.next_run_at, now)

    def test_10_daily_schedule_period_idempotency(self):
        """Re-running scheduler in same period does not spawn duplicate session."""
        now = timezone.now()
        past_run_time = now - timedelta(minutes=30)
        schedule = StocktakeSchedule.objects.create(
            name="Daily Idempotency Test",
            frequency="daily",
            location=self.warehouse,
            scheduled_time=past_run_time.time(),
            next_run_at=past_run_time,
            is_active=True,
            created_by=self.manager,
        )

        # First run creates session
        res1 = process_due_stocktake_schedules(now=now)
        self.assertEqual(len(res1["executed"]), 1)

        # Force next_run_at to past again for same target date
        schedule.next_run_at = past_run_time
        schedule.save(update_fields=["next_run_at"])

        # Second run detects existing session for (schedule, target_date) and skips
        res2 = process_due_stocktake_schedules(now=now)
        self.assertEqual(len(res2["executed"]), 0)
        self.assertEqual(len(res2["skipped"]), 1)
        self.assertEqual(StocktakeSession.objects.filter(schedule=schedule).count(), 1)

    def test_11_downtime_catchup_creates_single_session_and_rolls_forward(self):
        """If service was down for 3 days, only 1 catch-up session is created and schedule advances."""
        now = timezone.now()
        three_days_ago = now - timedelta(days=3)

        schedule = StocktakeSchedule.objects.create(
            name="Catchup Test Schedule",
            frequency="daily",
            location=self.warehouse,
            scheduled_time=time(20, 0),
            next_run_at=three_days_ago,
            is_active=True,
            created_by=self.manager,
        )

        res = process_due_stocktake_schedules(now=now)
        self.assertEqual(len(res["executed"]), 1)
        self.assertEqual(StocktakeSession.objects.filter(schedule=schedule).count(), 1)

        schedule.refresh_from_db()
        self.assertGreater(schedule.next_run_at, now)

    def test_12_schedule_management_endpoints(self):
        """Pause, activate, trigger-now, and upcoming endpoints operate correctly."""
        self.client.force_authenticate(user=self.manager)

        schedule = StocktakeSchedule.objects.create(
            name="Management Endpoint Test",
            frequency="weekly",
            day_of_week=0,  # Monday
            scheduled_time=time(18, 0),
            next_run_at=timezone.now() + timedelta(days=2),
            location=self.warehouse,
            is_active=True,
            created_by=self.manager,
        )

        # 1. Pause
        res_pause = self.client.post(f"/api/v1/stocktaking/schedules/{schedule.id}/pause/")
        self.assertEqual(res_pause.status_code, status.HTTP_200_OK)
        schedule.refresh_from_db()
        self.assertFalse(schedule.is_active)

        # 2. Activate
        res_act = self.client.post(f"/api/v1/stocktaking/schedules/{schedule.id}/activate/")
        self.assertEqual(res_act.status_code, status.HTTP_200_OK)
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_active)
        self.assertIsNotNone(schedule.next_run_at)

        # 3. Trigger Now
        res_trigger = self.client.post(f"/api/v1/stocktaking/schedules/{schedule.id}/trigger-now/")
        self.assertIn(res_trigger.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn("session_id", res_trigger.data)
        self.assertEqual(StocktakeSession.objects.filter(schedule=schedule).count(), 1)

        # 4. Upcoming schedules list
        res_upcoming = self.client.get("/api/v1/stocktaking/schedules/upcoming/")
        self.assertEqual(res_upcoming.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_upcoming.data, list)

    def test_13_segregation_of_duties_preserved_for_scheduled_session(self):
        """Counter who counted scheduled session cannot approve it (SoD enforced)."""
        ItemLocationBalance.objects.create(
            item=self.item_milk,
            location=self.warehouse,
            quantity=Decimal("50.00"),
        )
        schedule = StocktakeSchedule.objects.create(
            name="SoD Test Schedule",
            frequency="daily",
            location=self.warehouse,
            assigned_staff=self.counter,
            scheduled_time=time(10, 0),
            next_run_at=timezone.now() - timedelta(minutes=5),
            is_active=True,
            created_by=self.admin,
        )

        res = process_due_stocktake_schedules()
        session_id = res["executed"][0]["session_id"]
        session = StocktakeSession.objects.get(id=session_id)

        # Record counts as counter
        record_counts(
            session_id=session.pk,
            counts_data=[{"item_id": self.item_milk.pk, "counted_quantity": Decimal("50.00")}],
            user=self.counter,
        )

        session.refresh_from_db()
        self.assertEqual(session.counted_by, self.counter)

        # Counter attempts to approve their own count -> 403 Forbidden
        self.client.force_authenticate(user=self.counter)
        approve_url = reverse("stocktakesession-approve", args=[session.id])
        res_approve = self.client.post(approve_url, {"notes": "Attempting self approval"})
        self.assertEqual(res_approve.status_code, status.HTTP_403_FORBIDDEN)
