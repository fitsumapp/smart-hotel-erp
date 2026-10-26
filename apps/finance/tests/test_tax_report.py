"""
apps/finance/tests/test_tax_report.py
Focused regression test suite for DEFECT-TAX-001 in TaxReportView (/api/users/finance/tax-report/).
Verifies:
1. Valid date range parsing and response structure
2. Boundary handling (inclusive start, full end-day inclusion, exclusion of outside records)
3. Missing and invalid parameter contracts
4. Inverted date range rejection (400)
5. Timezone awareness (no naive/aware comparison issues)
6. Role-based access control (Admin/Finance allowed; Waiter/Reception/Anon rejected)
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from hotel.models import (
    Room, RoomHistory, RestaurantTable, Category, MenuItem,
    Order, OrderItem, SystemSettings
)
from apps.orders.services import sync_order_financials


class TaxReportViewRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # System settings for VAT and Service Charge
        self.settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
        self.settings_obj.vat_enabled = True
        self.settings_obj.vat_percentage = Decimal("15.00")
        self.settings_obj.service_charge_enabled = True
        self.settings_obj.service_charge_percentage = Decimal("10.00")
        self.settings_obj.save()

        # Staff users
        self.finance_user = User.objects.create_user(
            username="tax_finance", email="finance@tax.test", password="Password123!",
            role=User.FINANCE, is_active=True
        )
        self.admin_user = User.objects.create_superuser(
            username="tax_admin", email="admin@tax.test", password="Password123!",
            role=User.ADMIN, is_active=True
        )
        self.waiter_user = User.objects.create_user(
            username="tax_waiter", email="waiter@tax.test", password="Password123!",
            role=User.WAITER, is_active=True
        )
        self.reception_user = User.objects.create_user(
            username="tax_reception", email="reception@tax.test", password="Password123!",
            role=User.RECEPTION, is_active=True
        )

        # F&B setup
        self.table = RestaurantTable.objects.create(table_code="TAX-T1", capacity=2)
        self.cat = Category.objects.create(name="Tax Kitchen", station="Kitchen")
        self.item = MenuItem.objects.create(name="Tax Burger", price=Decimal("200.00"), category=self.cat)

        # Room setup
        self.room = Room.objects.create(room_number="999", room_type="Standard", base_price=Decimal("1000.00"))

    def test_tax_report_missing_parameters_defaults(self):
        """When query parameters are omitted, defaults to 1st of current month until today"""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        today = timezone.now().date()
        expected_start = today.replace(day=1).isoformat()
        expected_end = today.isoformat()

        self.assertEqual(res.data["start_date"], expected_start)
        self.assertEqual(res.data["end_date"], expected_end)
        self.assertIn("restaurant", res.data)
        self.assertIn("rooms", res.data)
        self.assertIn("aggregated", res.data)

    def test_tax_report_valid_date_range_structure(self):
        """A valid date range returns structured fiscal tax totals without 500 error"""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "2026-10-01",
            "end_date": "2026-10-15"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["start_date"], "2026-10-01")
        self.assertEqual(res.data["end_date"], "2026-10-15")

        # Verify restaurant keys
        for key in ["subtotal", "vat", "service_charge", "total"]:
            self.assertIn(key, res.data["restaurant"])
        # Verify rooms keys
        for key in ["subtotal", "vat", "service_charge", "total"]:
            self.assertIn(key, res.data["rooms"])
        # Verify aggregated keys
        for key in ["vat_collected", "service_charge_collected", "total_tax_collected"]:
            self.assertIn(key, res.data["aggregated"])

    def test_tax_report_boundary_records_handling(self):
        """Records at the exact start (00:00:00) and end of the last day (23:59:59) are included; outside records excluded"""
        tz = timezone.get_current_timezone()

        # Date range: 2026-10-05 to 2026-10-08
        start_date = datetime.date(2026, 10, 5)
        end_date = datetime.date(2026, 10, 8)

        # 1. Record BEFORE range (2026-10-04 23:59:59) -> must be excluded
        t_before = timezone.make_aware(datetime.datetime(2026, 10, 4, 23, 59, 59), tz)
        ord_before = Order.objects.create(
            table=self.table, status="paid", payment_status="paid", payment_method="Cash"
        )
        OrderItem.objects.create(order=ord_before, menu_item=self.item, quantity=1, price_at_order=Decimal("200.00"))
        sync_order_financials(ord_before)
        Order.objects.filter(id=ord_before.id).update(updated_at=t_before)

        # 2. Record AT START BOUNDARY (2026-10-05 00:00:00) -> must be included
        t_start = timezone.make_aware(datetime.datetime(2026, 10, 5, 0, 0, 0), tz)
        ord_start = Order.objects.create(
            table=self.table, status="paid", payment_status="paid", payment_method="Cash"
        )
        OrderItem.objects.create(order=ord_start, menu_item=self.item, quantity=1, price_at_order=Decimal("200.00"))
        sync_order_financials(ord_start)
        Order.objects.filter(id=ord_start.id).update(updated_at=t_start)

        # 3. Record AT END BOUNDARY (2026-10-08 23:59:59) -> must be included (full day)
        t_end = timezone.make_aware(datetime.datetime(2026, 10, 8, 23, 59, 59), tz)
        ord_end = Order.objects.create(
            table=self.table, status="paid", payment_status="paid", payment_method="Cash"
        )
        OrderItem.objects.create(order=ord_end, menu_item=self.item, quantity=1, price_at_order=Decimal("200.00"))
        sync_order_financials(ord_end)
        Order.objects.filter(id=ord_end.id).update(updated_at=t_end)

        # 4. Record AFTER range (2026-10-09 00:00:01) -> must be excluded
        t_after = timezone.make_aware(datetime.datetime(2026, 10, 9, 0, 0, 1), tz)
        ord_after = Order.objects.create(
            table=self.table, status="paid", payment_status="paid", payment_method="Cash"
        )
        OrderItem.objects.create(order=ord_after, menu_item=self.item, quantity=1, price_at_order=Decimal("200.00"))
        sync_order_financials(ord_after)
        Order.objects.filter(id=ord_after.id).update(updated_at=t_after)

        # Execute query
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "2026-10-05",
            "end_date": "2026-10-08"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Each order: subtotal = 200, vat 15% = 30, sc 10% = 20, total = 250
        # Exactly 2 included orders (start + end):
        # subtotal: 400.00, vat: 60.00, sc: 40.00, total: 500.00
        self.assertEqual(res.data["restaurant"]["subtotal"], 400.0)
        self.assertEqual(res.data["restaurant"]["vat"], 60.0)
        self.assertEqual(res.data["restaurant"]["service_charge"], 40.0)
        self.assertEqual(res.data["restaurant"]["total"], 500.0)

    def test_tax_report_invalid_date_strings_fallback(self):
        """Malformed date parameters gracefully fall back to default start and end dates without error"""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "invalid-date-format",
            "end_date": "not-a-valid-date"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        today = timezone.now().date()
        self.assertEqual(res.data["start_date"], today.replace(day=1).isoformat())
        self.assertEqual(res.data["end_date"], today.isoformat())

    def test_tax_report_inverted_date_range_rejected(self):
        """start_date after end_date returns HTTP 400 Bad Request"""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "2026-10-25",
            "end_date": "2026-10-10"
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be after end_date", res.data.get("error", ""))

    def test_tax_report_rbac_permission_guards(self):
        """Finance and Admin are authorized; Reception, Waiter, and Anonymous are denied"""
        # 1. Unauthenticated -> 401
        res_anon = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Waiter -> 403
        self.client.force_authenticate(user=self.waiter_user)
        res_waiter = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_waiter.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Reception -> 403
        self.client.force_authenticate(user=self.reception_user)
        res_reception = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_reception.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Finance -> 200
        self.client.force_authenticate(user=self.finance_user)
        res_finance = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_finance.status_code, status.HTTP_200_OK)

        # 5. Admin -> 200
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get("/api/users/finance/tax-report/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)

    def test_tax_report_us_date_format_parsing(self):
        """MM/DD/YYYY formatted dates are parsed correctly and filter records accurately"""
        tz = timezone.get_current_timezone()
        t_order = timezone.make_aware(datetime.datetime(2026, 10, 5, 12, 0, 0), tz)
        ord_sample = Order.objects.create(
            table=self.table, status="paid", payment_status="paid", payment_method="Cash"
        )
        OrderItem.objects.create(order=ord_sample, menu_item=self.item, quantity=2, price_at_order=Decimal("200.00"))
        sync_order_financials(ord_sample)
        Order.objects.filter(id=ord_sample.id).update(updated_at=t_order)

        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "10/01/2026",
            "end_date": "10/08/2026"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["start_date"], "2026-10-01")
        self.assertEqual(res.data["end_date"], "2026-10-08")
        self.assertEqual(res.data["restaurant"]["subtotal"], 400.0)
        self.assertEqual(res.data["restaurant"]["vat"], 60.0)

    def test_tax_report_empty_range_safe_zero_defaults(self):
        """When no transactions exist, safe zero-value defaults (0.0) are returned with HTTP 200"""
        self.client.force_authenticate(user=self.finance_user)
        res = self.client.get("/api/users/finance/tax-report/", {
            "start_date": "2020-01-01",
            "end_date": "2020-01-02"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["restaurant"]["subtotal"], 0.0)
        self.assertEqual(res.data["restaurant"]["vat"], 0.0)
        self.assertEqual(res.data["restaurant"]["service_charge"], 0.0)
        self.assertEqual(res.data["restaurant"]["total"], 0.0)
        self.assertEqual(res.data["rooms"]["subtotal"], 0.0)
        self.assertEqual(res.data["rooms"]["vat"], 0.0)
        self.assertEqual(res.data["rooms"]["service_charge"], 0.0)
        self.assertEqual(res.data["rooms"]["total"], 0.0)
        self.assertEqual(res.data["aggregated"]["vat_collected"], 0.0)
        self.assertEqual(res.data["aggregated"]["service_charge_collected"], 0.0)
        self.assertEqual(res.data["aggregated"]["total_tax_collected"], 0.0)
