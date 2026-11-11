from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    Category,
    MenuItem,
    Order,
    OrderItem,
    RestaurantTable,
    SystemSettings,
)
from users.models import User


class OperationsTimingReportTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.settings, _ = SystemSettings.objects.get_or_create(
            id=1,
            defaults={
                "hotel_name": "Test Grand Hotel",
                "kds_prep_target_minutes": 15,
                "kds_delay_warning_minutes": 20,
                "bar_fulfillment_target_minutes": 5,
                "bar_delay_warning_minutes": 10,
            },
        )

        self.password = "SecTestPass123!"
        self.admin = User.objects.create_user(username="opt_admin", password=self.password, role=User.ADMIN, is_active=True)
        self.kitchen_user = User.objects.create_user(username="opt_chef", password=self.password, role=User.KITCHEN, is_active=True)
        self.bar_user = User.objects.create_user(username="opt_bartender", password=self.password, role=User.BAR, is_active=True)
        self.waiter = User.objects.create_user(username="opt_waiter", password=self.password, role=User.WAITER, is_active=True)

        self.cat_kitchen = Category.objects.create(name="Main Food", station="Kitchen")
        self.cat_bar = Category.objects.create(name="Bar Beverages", station="Bar")

        self.steak = MenuItem.objects.create(
            name="Ribeye Steak", price=Decimal("450.00"), category=self.cat_kitchen
        )
        self.soup = MenuItem.objects.create(
            name="Tomato Soup", price=Decimal("150.00"), category=self.cat_kitchen
        )
        self.cocktail = MenuItem.objects.create(
            name="Mojito", price=Decimal("200.00"), category=self.cat_bar
        )

        self.table = RestaurantTable.objects.create(table_code="T-01", capacity=4)

    def test_unauthenticated_request_rejected(self):
        res = self.client.get("/api/users/reports/operations-timing/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_and_denied_roles(self):
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get("/api/users/reports/operations-timing/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.kitchen_user)
        res_kitchen = self.client.get("/api/users/reports/operations-timing/")
        self.assertEqual(res_kitchen.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.bar_user)
        res_bar = self.client.get("/api/users/reports/operations-timing/")
        self.assertEqual(res_bar.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.waiter)
        res_waiter = self.client.get("/api/users/reports/operations-timing/")
        self.assertEqual(res_waiter.status_code, status.HTTP_403_FORBIDDEN)

    def test_kitchen_and_bar_timing_metrics_calculation(self):
        now = timezone.now()
        report_date = timezone.localtime(now).date().isoformat()

        order1 = Order.objects.create(
            table=self.table,
            sub_total=Decimal("800.00"),
            total_amount=Decimal("800.00"),
            status="preparing",
            received_at=now - timedelta(minutes=30),
        )

        item_fast = OrderItem.objects.create(
            order=order1,
            menu_item=self.soup,
            quantity=1,
            price_at_order=Decimal("150.00"),
            status="ready",
            received_at=now - timedelta(minutes=25),
            preparation_started_at=now - timedelta(minutes=20),
            ready_at=now - timedelta(minutes=10),
            prepared_by_id_ref=self.kitchen_user.id,
            ready_by_id_ref=self.kitchen_user.id,
        )

        item_delayed = OrderItem.objects.create(
            order=order1,
            menu_item=self.steak,
            quantity=1,
            price_at_order=Decimal("450.00"),
            status="ready",
            received_at=now - timedelta(minutes=30),
            preparation_started_at=now - timedelta(minutes=25),
            ready_at=now - timedelta(minutes=3),
            prepared_by_id_ref=self.kitchen_user.id,
            ready_by_id_ref=self.kitchen_user.id,
        )

        item_bar = OrderItem.objects.create(
            order=order1,
            menu_item=self.cocktail,
            quantity=1,
            price_at_order=Decimal("200.00"),
            status="ready",
            received_at=now - timedelta(minutes=10),
            ready_at=now - timedelta(minutes=7),
            ready_by_id_ref=self.bar_user.id,
        )

        self.client.force_authenticate(user=self.admin)
        res = self.client.get(f"/api/users/reports/operations-timing/?date={report_date}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data

        # Check Kitchen summary
        k = data["kitchen"]
        self.assertEqual(k["total_items"], 2)
        self.assertEqual(k["ready_items"], 2)
        self.assertEqual(k["delayed_target_count"], 1)
        self.assertEqual(k["delayed_warning_count"], 1)
        self.assertEqual(k["delay_rate"], 50.0)
        self.assertAlmostEqual(k["avg_prep_minutes"], 16.0, delta=0.5)

        # Check Bar summary
        b = data["bar"]
        self.assertEqual(b["total_items"], 1)
        self.assertEqual(b["ready_items"], 1)
        self.assertEqual(b["delayed_target_count"], 0)
        self.assertEqual(b["delay_rate"], 0.0)
        self.assertAlmostEqual(b["avg_fulfillment_minutes"], 3.0, delta=0.5)

        # Check Staff Performance
        staff = data["staff_performance"]
        self.assertEqual(len(staff), 2)
        chef_stat = next(s for s in staff if s["role"] == "Kitchen")
        self.assertEqual(chef_stat["completed_items"], 2)
        self.assertEqual(chef_stat["delay_count"], 1)

        # Check Bottlenecks
        bottlenecks = data["top_bottlenecks"]
        self.assertEqual(len(bottlenecks), 1)
        self.assertEqual(bottlenecks[0]["item_name"], "Ribeye Steak")
        self.assertEqual(bottlenecks[0]["station"], "Kitchen")
