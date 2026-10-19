"""
Regression and authorization test suite for DEFECT-PERM-001.
Verifies role-based access control on Police, X, and Z reports:
- Unauthenticated requests are rejected with HTTP 401.
- Admin, Reception, and Finance are authorized with HTTP 200.
- Unauthorized roles (Waiter, Kitchen, Bar, Housekeeping, Customer) are denied with HTTP 403.
- Denied responses do not leak financial or sensitive guest report data.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import Room, Reservation, Order, SystemSettings
from users.models import User


class ReportPermissionsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Seed SystemSettings if needed by X/Z reports
        SystemSettings.objects.get_or_create(
            id=1,
            defaults={
                "hotel_name": "Acrma Test Grand",
                "tin_number": "0012345678",
                "printer_paper_size": "80mm",
            }
        )

        # Users across roles
        self.password = "Report-Test-Pass-123!"
        self.admin = User.objects.create_user(
            username="rep_admin", password=self.password, role=User.ADMIN, is_active=True
        )
        self.reception = User.objects.create_user(
            username="rep_reception", password=self.password, role=User.RECEPTION, is_active=True
        )
        self.finance = User.objects.create_user(
            username="rep_finance", password=self.password, role=User.FINANCE, is_active=True
        )
        self.waiter = User.objects.create_user(
            username="rep_waiter", password=self.password, role=User.WAITER, is_active=True
        )
        self.kitchen = User.objects.create_user(
            username="rep_kitchen", password=self.password, role=User.KITCHEN, is_active=True
        )
        self.bar = User.objects.create_user(
            username="rep_bar", password=self.password, role=User.BAR, is_active=True
        )
        self.housekeeping = User.objects.create_user(
            username="rep_housekeeping", password=self.password, role=User.HOUSEKEEPING, is_active=True
        )
        self.customer = User.objects.create_user(
            username="rep_customer", password=self.password, role=User.CUSTOMER, is_active=True
        )

        # Seed sample data for reports
        self.room = Room.objects.create(
            room_number="101",
            name="Deluxe 101",
            room_type="deluxe",
            base_price=Decimal("200.00"),
            status="Occupied",
        )
        self.res = Reservation.objects.create(
            guest_name="Tadesse Wolde",
            guest_phone="+251922334455",
            room=self.room,
            check_in_date=timezone.now().date(),
            check_out_date=(timezone.now() + timezone.timedelta(days=1)).date(),
            total_amount=Decimal("200.00"),
            payment_status="paid",
            status="checked_in",
            checked_in_at=timezone.now(),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. POLICE REPORT (/api/users/reports/police/)
    # ─────────────────────────────────────────────────────────────────────────
    def test_police_report_unauthenticated_rejected(self):
        """Unauthenticated request to police report returns 401."""
        self.client.logout()
        res = self.client.get("/api/users/reports/police/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("guests", res.data)

    def test_police_report_admin_authorized(self):
        """Admin can access police report."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/users/reports/police/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("guests", res.data)

    def test_police_report_reception_authorized(self):
        """Reception can access police report."""
        self.client.force_authenticate(user=self.reception)
        res = self.client.get("/api/users/reports/police/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("guests", res.data)

    def test_police_report_finance_authorized(self):
        """DEFECT-PERM-001: Finance role can access police report."""
        self.client.force_authenticate(user=self.finance)
        res = self.client.get("/api/users/reports/police/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("guests", res.data)
        self.assertEqual(res.data["total"], 1)

    def test_police_report_unauthorized_operational_roles_denied(self):
        """Waiter, Kitchen, Bar, Housekeeping, Customer are denied access to police report."""
        unauthorized = [self.waiter, self.kitchen, self.bar, self.housekeeping, self.customer]
        for user in unauthorized:
            self.client.force_authenticate(user=user)
            res = self.client.get("/api/users/reports/police/")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be 403")
            self.assertNotIn("guests", res.data)
            self.assertEqual(res.data.get("error"), "Access denied.")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. X-REPORT (/api/users/reports/x-report/)
    # ─────────────────────────────────────────────────────────────────────────
    def test_x_report_unauthenticated_rejected(self):
        """Unauthenticated request to X-report returns 401."""
        self.client.logout()
        res = self.client.get("/api/users/reports/x-report/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("grand_total", res.data)

    def test_x_report_admin_authorized(self):
        """Admin can access X-report."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/users/reports/x-report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("grand_total", res.data)
        self.assertEqual(res.data["report_type"], "X-Report")

    def test_x_report_reception_authorized(self):
        """Reception can access X-report."""
        self.client.force_authenticate(user=self.reception)
        res = self.client.get("/api/users/reports/x-report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("grand_total", res.data)
        self.assertEqual(res.data["report_type"], "X-Report")

    def test_x_report_finance_authorized(self):
        """DEFECT-PERM-001: Finance role can access X-report."""
        self.client.force_authenticate(user=self.finance)
        res = self.client.get("/api/users/reports/x-report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("grand_total", res.data)
        self.assertEqual(res.data["report_type"], "X-Report")

    def test_x_report_unauthorized_operational_roles_denied(self):
        """Waiter, Kitchen, Bar, Housekeeping, Customer are denied access to X-report."""
        unauthorized = [self.waiter, self.kitchen, self.bar, self.housekeeping, self.customer]
        for user in unauthorized:
            self.client.force_authenticate(user=user)
            res = self.client.get("/api/users/reports/x-report/")
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be 403")
            self.assertNotIn("grand_total", res.data)
            self.assertNotIn("restaurant", res.data)
            self.assertEqual(res.data.get("error"), "Access denied.")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Z-REPORT (/api/users/reports/z-report/)
    # ─────────────────────────────────────────────────────────────────────────
    def test_z_report_unauthenticated_rejected(self):
        """Unauthenticated request to Z-report returns 401."""
        self.client.logout()
        res = self.client.post("/api/users/reports/z-report/", {})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("is_closed", res.data)

    def test_z_report_admin_authorized(self):
        """Admin can close day and access Z-report."""
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/users/reports/z-report/", {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_closed"])
        self.assertEqual(res.data["report_type"], "Z-Report")

    def test_z_report_reception_authorized(self):
        """Reception can close day and access Z-report."""
        self.client.force_authenticate(user=self.reception)
        res = self.client.post("/api/users/reports/z-report/", {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_closed"])
        self.assertEqual(res.data["report_type"], "Z-Report")

    def test_z_report_finance_authorized(self):
        """DEFECT-PERM-001: Finance role can close day and access Z-report."""
        self.client.force_authenticate(user=self.finance)
        res = self.client.post("/api/users/reports/z-report/", {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_closed"])
        self.assertEqual(res.data["report_type"], "Z-Report")

    def test_z_report_unauthorized_operational_roles_denied(self):
        """Waiter, Kitchen, Bar, Housekeeping, Customer are denied access to Z-report."""
        unauthorized = [self.waiter, self.kitchen, self.bar, self.housekeeping, self.customer]
        for user in unauthorized:
            self.client.force_authenticate(user=user)
            res = self.client.post("/api/users/reports/z-report/", {})
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be 403")
            self.assertNotIn("is_closed", res.data)
            self.assertNotIn("restaurant", res.data)
            self.assertEqual(res.data.get("error"), "Access denied.")
