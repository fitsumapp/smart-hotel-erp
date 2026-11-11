"""
Unit and Integration Tests for PMS Night Audit & Business Date Rollover Engine.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import (
    Account,
    AuditEvent,
    DayAuditLog,
    FolioCharge,
    JournalEntry,
    MenuItem,
    Order,
    OrderItem,
    Reservation,
    RestaurantTable,
    Room,
    SystemSettings,
)
from hotel.night_audit import (
    accrue_daily_room_charges,
    execute_night_audit,
    get_current_business_date,
    get_night_audit_status,
)

User = get_user_model()


class TestNightAuditEngine(APITestCase):
    def setUp(self):
        # Configure chart of accounts
        Account.objects.get_or_create(code="1000", defaults={"name": "Cash", "account_type": "asset"})
        Account.objects.get_or_create(code="1010", defaults={"name": "Bank Transfer", "account_type": "asset"})
        Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "asset"})
        Account.objects.get_or_create(code="1300", defaults={"name": "Inventory Asset", "account_type": "asset"})
        Account.objects.get_or_create(code="2200", defaults={"name": "VAT Payable", "account_type": "liability"})
        Account.objects.get_or_create(code="2300", defaults={"name": "Service Charge Payable", "account_type": "liability"})
        Account.objects.get_or_create(code="4000", defaults={"name": "Room Revenue", "account_type": "revenue"})
        Account.objects.get_or_create(code="4100", defaults={"name": "F&B Revenue", "account_type": "revenue"})

        # System settings
        self.settings = SystemSettings.get_settings()
        self.settings.current_business_date = date(2026, 11, 4)
        self.settings.vat_enabled = True
        self.settings.vat_percentage = Decimal("15.00")
        self.settings.service_charge_enabled = True
        self.settings.service_charge_percentage = Decimal("10.00")
        self.settings.save()

        # Users
        self.admin = User.objects.create_superuser("audit_admin", "admin@test.com", "pass1234", role="admin")
        self.reception = User.objects.create_user("audit_reception", "rec@test.com", "pass1234", role="reception")
        self.waiter = User.objects.create_user("audit_waiter", "waiter@test.com", "pass1234", role="waiter")

        # Rooms
        self.room101 = Room.objects.create(
            room_number="101",
            name="Deluxe King 101",
            room_type="Deluxe",
            base_price=Decimal("1000.00"),
            status="Occupied",
        )
        self.room102 = Room.objects.create(
            room_number="102",
            name="Standard Twin 102",
            room_type="Standard",
            base_price=Decimal("800.00"),
            status="Occupied",
        )

        # Reservations
        self.res101 = Reservation.objects.create(
            room=self.room101,
            guest_name="Abebe Bikila",
            check_in_date=date(2026, 11, 3),
            check_out_date=date(2026, 11, 6),
            status="checked_in",
            confirmation_code="CONF-NA-101",
        )
        self.res102 = Reservation.objects.create(
            room=self.room102,
            guest_name="Derartu Tulu",
            check_in_date=date(2026, 11, 4),
            check_out_date=date(2026, 11, 7),
            status="checked_in",
            confirmation_code="CONF-NA-102",
        )

        # Table & Menu
        from hotel.models import Category
        self.cat = Category.objects.create(name="Hot Dishes")
        self.table = RestaurantTable.objects.create(table_code="T-01", capacity=4)
        self.menu_item = MenuItem.objects.create(name="Tibs", price=Decimal("300.00"), category=self.cat)

    def test_01_get_night_audit_status_pre_checks(self):
        """Verifies status endpoint reflects active in-house reservations and business date."""
        self.client.force_authenticate(user=self.reception)
        url = reverse("night-audit-status")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["current_business_date"], "2026-11-04")
        self.assertEqual(data["next_business_date"], "2026-11-05")
        self.assertEqual(data["in_house_guests_count"], 2)
        self.assertEqual(Decimal(str(data["projected_room_revenue"])), Decimal("1800.00"))
        self.assertTrue(data["can_rollover"])

    def test_02_accrue_daily_room_charges_calculates_taxes_and_gl_entry(self):
        """Verifies daily room rate accrual posts FolioCharges with 15% VAT and 10% SC, plus balanced GL."""
        charges, total_accrued, gl_entry = accrue_daily_room_charges(
            business_date=date(2026, 11, 4),
            user=self.admin,
        )

        # Room 101: 1000.00 + 150.00 (VAT) + 100.00 (SC) = 1250.00
        # Room 102: 800.00 + 120.00 (VAT) + 80.00 (SC) = 1000.00
        # Total = 2250.00
        self.assertEqual(len(charges), 2)
        self.assertEqual(total_accrued, Decimal("2250.00"))

        c101 = FolioCharge.objects.filter(reservation=self.res101).latest("id")
        self.assertEqual(c101.amount, Decimal("1250.00"))
        self.assertIn("Room Rate Accrual (2026-11-04)", c101.description)

        c102 = FolioCharge.objects.filter(reservation=self.res102).latest("id")
        self.assertEqual(c102.amount, Decimal("1000.00"))

        # GL Verification
        self.assertIsNotNone(gl_entry)
        items = list(gl_entry.items.all())
        dr_sum = sum(i.amount_debit for i in items)
        cr_sum = sum(i.amount_credit for i in items)
        self.assertEqual(dr_sum, Decimal("2250.00"))
        self.assertEqual(cr_sum, Decimal("2250.00"))

    def test_03_accrual_idempotency_prevents_duplicate_postings(self):
        """Re-running room charge accruals on same business date must be a safe no-op."""
        accrue_daily_room_charges(business_date=date(2026, 11, 4), user=self.admin)
        count_first = FolioCharge.objects.count()

        # Second attempt
        charges_2, total_2, gl_2 = accrue_daily_room_charges(business_date=date(2026, 11, 4), user=self.admin)
        self.assertEqual(len(charges_2), 0)
        self.assertEqual(total_2, Decimal("0.00"))
        self.assertIsNone(gl_2)
        self.assertEqual(FolioCharge.objects.count(), count_first)

    def test_04_unsettled_restaurant_orders_block_night_audit_without_force(self):
        """Unsettled dining orders block date rollover unless force=True."""
        order = Order.objects.create(
            table=self.table,
            status="served",
            payment_status="pending",
            total_amount=Decimal("300.00"),
        )

        self.client.force_authenticate(user=self.reception)
        url = reverse("night-audit-execute")

        # Without force -> HTTP 400
        res_fail = self.client.post(url, {})
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unsettled restaurant order(s) remain open", res_fail.data["error"])

        # With force -> HTTP 200
        res_forced = self.client.post(url, {"force": True, "notes": "Manager approved emergency rollover"})
        self.assertEqual(res_forced.status_code, status.HTTP_200_OK)
        self.assertEqual(res_forced.data["status"], "success")

    def test_05_execute_night_audit_advances_date_and_closes_day(self):
        """Executes full night audit, advances business date from 2026-11-04 to 2026-11-05, and logs audit."""
        self.client.force_authenticate(user=self.reception)
        url = reverse("night-audit-execute")
        response = self.client.post(url, {"notes": "Standard End-of-Day Shift Rollover"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["previous_business_date"], "2026-11-04")
        self.assertEqual(data["new_business_date"], "2026-11-05")
        self.assertEqual(data["accrued_rooms_count"], 2)

        # Settings state
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.current_business_date, date(2026, 11, 5))

        # DayAuditLog closed
        audit_log = DayAuditLog.objects.get(audit_date=date(2026, 11, 4))
        self.assertTrue(audit_log.is_closed)
        self.assertEqual(audit_log.closed_by, "audit_reception")

        # AuditEvent created
        audit_event = AuditEvent.objects.filter(action="night_audit.date_rollover").first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.after_summary["business_date"], "2026-11-05")

    def test_06_rbac_unauthorized_roles_denied(self):
        """Waiters cannot access night audit endpoints."""
        self.client.force_authenticate(user=self.waiter)
        status_url = reverse("night-audit-status")
        exec_url = reverse("night-audit-execute")

        res1 = self.client.get(status_url)
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)

        res2 = self.client.post(exec_url, {})
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)
