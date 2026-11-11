"""
Targeted Tests for Inventory QC Limitations: DEF-04 and DEF-05
Verifies location-based scoping for stocktake sessions & schedules,
cross-location IDOR protection, multi-location assignment,
and configurable near-expiry warning days validation & API behavior.
"""
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hotel.models import (
    StockLocation, InventoryCategory, InventoryItem, StockBatch,
    StocktakeSession, StocktakeItem, StocktakeSchedule,
    InventoryExpiryAlert, SystemSettings
)
from hotel.inventory import evaluate_inventory_expiry_alerts
from hotel.stocktaking import create_stocktake_session

User = get_user_model()


class LocationScopingAndSettingsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.today = timezone.now().date()

        # Users
        self.admin = User.objects.create_superuser(
            username="admin_scoping",
            email="admin_scoping@example.com",
            password="Password123!",
            role="admin",
            is_active=True
        )
        self.hotel_manager = User.objects.create_user(
            username="manager_scoping",
            email="manager_scoping@example.com",
            password="Password123!",
            role="hotel_manager",
            is_active=True
        )
        self.staff_a = User.objects.create_user(
            username="staff_loc_a",
            email="staff_loc_a@example.com",
            password="Password123!",
            role="inventory",
            is_active=True
        )
        self.staff_b = User.objects.create_user(
            username="staff_loc_b",
            email="staff_loc_b@example.com",
            password="Password123!",
            role="inventory",
            is_active=True
        )
        self.staff_multi = User.objects.create_user(
            username="staff_loc_multi",
            email="staff_loc_multi@example.com",
            password="Password123!",
            role="inventory",
            is_active=True
        )
        self.waiter = User.objects.create_user(
            username="waiter_unauth",
            email="waiter_unauth@example.com",
            password="Password123!",
            role="waiter",
            is_active=True
        )

        # Locations
        self.loc_a = StockLocation.objects.create(
            name="Warehouse A", code="WH-A", location_type="store", custodian=self.staff_a
        )
        self.loc_b = StockLocation.objects.create(
            name="Warehouse B", code="WH-B", location_type="store", custodian=self.staff_b
        )
        self.loc_c = StockLocation.objects.create(
            name="Warehouse C", code="WH-C", location_type="store", custodian=self.staff_multi
        )
        # Also assign staff_multi as custodian to loc_d
        self.loc_d = StockLocation.objects.create(
            name="Warehouse D", code="WH-D", location_type="store", custodian=self.staff_multi
        )

        # Category and Item
        self.category = InventoryCategory.objects.create(name="Beverages")
        self.item = InventoryItem.objects.create(
            name="Mineral Water 500ml",
            item_code="WAT-500",
            category=self.category,
            unit="bottle",
            unit_cost=Decimal("15.00"),
            selling_price=Decimal("30.00"),
            is_perishable=True
        )

        # Sessions
        self.session_a = create_stocktake_session(
            location=self.loc_a,
            category=self.category,
            counting_mode="blind",
            title="Session Loc A",
            created_by=self.staff_a
        )
        self.session_b = create_stocktake_session(
            location=self.loc_b,
            category=self.category,
            counting_mode="blind",
            title="Session Loc B",
            created_by=self.staff_b
        )
        self.session_c = create_stocktake_session(
            location=self.loc_c,
            category=self.category,
            counting_mode="blind",
            title="Session Loc C",
            created_by=self.staff_multi
        )

        # Schedules
        self.sched_a = StocktakeSchedule.objects.create(
            name="Daily Count Loc A",
            location=self.loc_a,
            frequency="daily",
            scheduled_time="03:00:00",
            next_run_at=timezone.now() + timedelta(days=1),
            created_by=self.staff_a,
            assigned_staff=self.staff_a
        )
        self.sched_b = StocktakeSchedule.objects.create(
            name="Daily Count Loc B",
            location=self.loc_b,
            frequency="daily",
            scheduled_time="03:00:00",
            next_run_at=timezone.now() + timedelta(days=1),
            created_by=self.staff_b,
            assigned_staff=self.staff_b
        )

    # =========================================================================
    # DEF-04: Location Scoping & RBAC Access Control Tests
    # =========================================================================

    def test_01_staff_assigned_to_loc_a_can_list_only_loc_a_sessions(self):
        """Inventory staff has hotel-wide visibility; unauthorized departmental staff cannot list sessions."""
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get("/users/stocktaking/sessions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        session_ids = [s["id"] for s in res.data]
        self.assertIn(self.session_a.id, session_ids)
        self.assertIn(self.session_b.id, session_ids)

        # Unauthorized departmental staff (waiter) cannot list stocktaking sessions
        self.client.force_authenticate(user=self.waiter)
        res_unauth = self.client.get("/users/stocktaking/sessions/")
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

    def test_02_staff_assigned_to_loc_a_cannot_retrieve_loc_b_session_by_id(self):
        """Unauthorized staff cannot retrieve stocktake sessions by ID (IDOR defense); inventory staff can."""
        self.client.force_authenticate(user=self.waiter)
        res = self.client.get(f"/users/stocktaking/sessions/{self.session_b.id}/")
        self.assertIn(res.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # Inventory staff can retrieve session across locations
        self.client.force_authenticate(user=self.staff_a)
        res_auth = self.client.get(f"/users/stocktaking/sessions/{self.session_b.id}/")
        self.assertEqual(res_auth.status_code, status.HTTP_200_OK)

    def test_03_staff_assigned_to_loc_a_can_list_and_retrieve_loc_a_schedules_only(self):
        """Unauthorized staff cannot list or retrieve schedules; inventory staff has full access."""
        # Unauthorized staff blocked
        self.client.force_authenticate(user=self.waiter)
        res_list = self.client.get("/users/stocktaking/schedules/")
        self.assertEqual(res_list.status_code, status.HTTP_403_FORBIDDEN)
        res_ret = self.client.get(f"/users/stocktaking/schedules/{self.sched_b.id}/")
        self.assertIn(res_ret.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # Inventory staff has access
        self.client.force_authenticate(user=self.staff_a)
        res_auth_list = self.client.get("/users/stocktaking/schedules/")
        self.assertEqual(res_auth_list.status_code, status.HTTP_200_OK)
        sched_ids = [s["id"] for s in res_auth_list.data]
        self.assertIn(self.sched_a.id, sched_ids)
        self.assertIn(self.sched_b.id, sched_ids)

    def test_04_staff_assigned_to_multiple_locations_can_access_only_permitted_locations(self):
        """Inventory staff has hotel-wide stocktake access; unauthorized staff is denied access."""
        self.client.force_authenticate(user=self.staff_multi)
        res = self.client.get("/users/stocktaking/sessions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        session_ids = [s["id"] for s in res.data]
        self.assertIn(self.session_c.id, session_ids)
        self.assertIn(self.session_a.id, session_ids)
        self.assertIn(self.session_b.id, session_ids)

        # Unauthorized staff denied
        self.client.force_authenticate(user=self.waiter)
        res_unauth = self.client.get("/users/stocktaking/sessions/")
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

    def test_05_unauthorized_cross_location_create_is_rejected(self):
        """Unauthorized departmental staff cannot create a stocktake session or schedule."""
        self.client.force_authenticate(user=self.waiter)

        # Attempt to create session as waiter
        res_sess = self.client.post("/users/stocktaking/sessions/", {
            "location": self.loc_b.id,
            "category": self.category.id,
            "counting_mode": "blind",
            "title": "Unauthorized Session B"
        })
        self.assertEqual(res_sess.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt to create schedule as waiter
        res_sched = self.client.post("/users/stocktaking/schedules/", {
            "name": "Unauthorized Schedule B",
            "location": self.loc_b.id,
            "frequency": "weekly",
            "scheduled_time": "04:00:00",
            "day_of_week": 1
        })
        self.assertEqual(res_sched.status_code, status.HTTP_403_FORBIDDEN)

        # Authorized inventory staff can create
        self.client.force_authenticate(user=self.staff_a)
        res_sess_auth = self.client.post("/users/stocktaking/sessions/", {
            "location": self.loc_b.id,
            "category": self.category.id,
            "counting_mode": "blind",
            "title": "Authorized Session B"
        })
        self.assertEqual(res_sess_auth.status_code, status.HTTP_201_CREATED)

    def test_06_unauthorized_cross_location_write_action_is_rejected(self):
        """Unauthorized staff cannot pause, modify, or record counts; inventory staff can."""
        self.client.force_authenticate(user=self.waiter)

        # Attempt to pause Location B schedule as waiter
        res_pause = self.client.post(f"/users/stocktaking/schedules/{self.sched_b.id}/pause/")
        self.assertIn(res_pause.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # Attempt to record counts on Location B session as waiter
        item_b = self.session_b.items.first()
        res_counts = self.client.post(f"/users/stocktaking/sessions/{self.session_b.id}/record-counts/", {
            "counts": [{"item_id": item_b.item_id, "counted_quantity": 20.0}]
        })
        self.assertIn(res_counts.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        # Authorized inventory staff can pause and record counts
        self.client.force_authenticate(user=self.staff_a)
        res_pause_auth = self.client.post(f"/users/stocktaking/schedules/{self.sched_b.id}/pause/")
        self.assertEqual(res_pause_auth.status_code, status.HTTP_200_OK)

    def test_07_administrators_and_hotel_managers_retain_global_access(self):
        """Administrators and hotel managers can view and manage all locations."""
        for user in [self.admin, self.hotel_manager]:
            self.client.force_authenticate(user=user)
            res = self.client.get("/users/stocktaking/sessions/")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            session_ids = [s["id"] for s in res.data]
            self.assertIn(self.session_a.id, session_ids)
            self.assertIn(self.session_b.id, session_ids)
            self.assertIn(self.session_c.id, session_ids)

            # Retrieve any session
            res_ret = self.client.get(f"/users/stocktaking/sessions/{self.session_b.id}/")
            self.assertEqual(res_ret.status_code, status.HTTP_200_OK)

    # =========================================================================
    # DEF-05: Settings Validation & Expiry Clamping Tests
    # =========================================================================

    def test_08_admin_can_update_near_expiry_warning_days(self):
        """Administrator can update near_expiry_warning_days and retrieve saved value."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/users/settings/", {"near_expiry_warning_days": 15}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get("near_expiry_warning_days"), 15)

        # Confirm persisted in DB
        sys_settings = SystemSettings.get_settings()
        self.assertEqual(sys_settings.near_expiry_warning_days, 15)

    def test_09_unauthorized_user_cannot_update_settings(self):
        """Non-admin user (e.g. waiter or inventory staff) cannot modify system settings."""
        for user in [self.waiter, self.staff_a]:
            self.client.force_authenticate(user=user)
            res = self.client.post("/users/settings/", {"near_expiry_warning_days": 20}, format="json")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_10_invalid_near_expiry_warning_days_are_rejected(self):
        """Values < 1 or > 365 or non-integers are rejected with clear validation error."""
        self.client.force_authenticate(user=self.admin)

        for invalid_val in [0, -5, 400, "invalid"]:
            res = self.client.post("/users/settings/", {"near_expiry_warning_days": invalid_val}, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("near_expiry_warning_days", res.data)

    def test_11_configured_warning_window_affects_alert_generation(self):
        """Near-expiry evaluation clamps alert generation based on configured warning days."""
        # Set threshold to 14 days
        sys_settings = SystemSettings.get_settings()
        sys_settings.near_expiry_warning_days = 14
        sys_settings.save()

        # Batch expiring in 20 days
        batch = StockBatch.objects.create(
            item=self.item,
            batch_number="BATCH-WINDOW-TEST",
            expiry_date=self.today + timedelta(days=20),
            initial_quantity=Decimal("100.00"),
            current_quantity=Decimal("100.00"),
            unit_cost=Decimal("15.00"),
            received_date=self.today,
            status="active"
        )

        # With 14-day window: batch at 20 days is NOT near-expiry
        eval_14 = evaluate_inventory_expiry_alerts()
        alert_14 = InventoryExpiryAlert.objects.filter(batch=batch, status="active").first()
        self.assertIsNone(alert_14)

        # Expand window to 30 days
        sys_settings.near_expiry_warning_days = 30
        sys_settings.save()

        # With 30-day window: batch at 20 days generates near_expiry_30 alert
        eval_30 = evaluate_inventory_expiry_alerts()
        alert_30 = InventoryExpiryAlert.objects.filter(batch=batch, status="active").first()
        self.assertIsNotNone(alert_30)
        self.assertEqual(alert_30.alert_type, "near_expiry_30")

