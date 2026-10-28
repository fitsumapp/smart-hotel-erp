"""
Regression tests for DEFECT-OPS-001 and DEFECT-FIN-001.
All assertions check EXACT financial amounts.
"""
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    Room, Reservation, Order, OrderItem, MenuItem, Category, RestaurantTable,
    FolioCharge, RoomHistory, DayAuditLog, SystemSettings,
)
from apps.finance.models import Account, JournalEntry, JournalEntryItem
from apps.finance.services import ensure_default_accounts, post_journal_entry
from users.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _room(room_number, base_price):
    return Room.objects.create(
        room_number=room_number,
        name="Room %s" % room_number,
        room_type="standard",
        base_price=Decimal(str(base_price)),
        status="Available",
    )


def _reservation(room, guest_name, check_in, check_out,
                 payment_status="paid", total_amount=None, status_val="checked_out"):
    nights = max((check_out - check_in).days, 1)
    total = total_amount if total_amount is not None else Decimal(str(room.base_price)) * nights
    return Reservation.objects.create(
        guest_name=guest_name,
        guest_phone="+251900000000",
        room=room,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=total,
        payment_status=payment_status,
        status=status_val,
    )


def _rh(room, event_type, guest_name, check_in, check_out, revenue, created_at=None):
    rh = RoomHistory(
        room=room, event_type=event_type, guest_name=guest_name,
        check_in_date=check_in, check_out_date=check_out,
        revenue=Decimal(str(revenue)),
    )
    rh.save()
    if created_at is not None:
        RoomHistory.objects.filter(pk=rh.pk).update(created_at=created_at)
        rh.refresh_from_db()
    return rh


def _jv(description, items, date):
    """Post a journal entry with the given items list."""
    post_journal_entry(description, items, date=date)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class RevenueBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        SystemSettings.objects.get_or_create(
            id=1,
            defaults={
                "hotel_name": "Test Grand Hotel",
                "tin_number": "0012345678",
                "printer_paper_size": "80mm",
                "module_finance": True,
            },
        )
        ensure_default_accounts()
        pw = "SecuredTestPass123!"
        self.admin = User.objects.create_user(
            username="fin_admin", password=pw, role=User.ADMIN, is_active=True)
        self.finance = User.objects.create_user(
            username="fin_officer", password=pw, role=User.FINANCE, is_active=True)
        self.reception = User.objects.create_user(
            username="rec_staff", password=pw, role=User.RECEPTION, is_active=True)
        self.waiter = User.objects.create_user(
            username="waiter_ops", password=pw, role=User.WAITER, is_active=True)
        self.today = timezone.now().date()
        self.yesterday = self.today - timedelta(days=1)

    def _metrics(self, start=None, end=None):
        self.client.force_authenticate(user=self.finance)
        s, e = start or self.today, end or self.today
        r = self.client.get(
            "/api/users/finance/stats/?start_date=%s&end_date=%s" % (s, e))
        self.assertEqual(r.status_code, 200)
        return r.data.get("metrics", {}), r.data.get("chart_trend", [])

    def _d(self, val):
        return Decimal(str(val))


# ===========================================================================
# Z-Report closure tests (DEFECT-OPS-001)
# ===========================================================================

class ZReportClosureTests(RevenueBase):

    def test_get_does_not_create_or_close_audit_log(self):
        """GET must never create or mutate DayAuditLog."""
        self.client.force_authenticate(user=self.finance)
        self.assertFalse(DayAuditLog.objects.filter(audit_date=self.today).exists())
        for _ in range(3):
            r = self.client.get(
                "/api/users/reports/z-report/?date=%s" % self.today)
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.data["is_closed"])
        audit = DayAuditLog.objects.filter(audit_date=self.today).first()
        if audit:
            self.assertFalse(audit.is_closed)

    def test_get_returns_preview_label_when_open(self):
        self.client.force_authenticate(user=self.finance)
        r = self.client.get("/api/users/reports/z-report/?date=%s" % self.today)
        self.assertEqual(r.data["report_type"], "Z-Report (Preview)")
        self.assertIsNone(r.data["closed_by"])

    def test_post_closes_day_and_records_metadata(self):
        """POST must close day with correct metadata."""
        self.client.force_authenticate(user=self.finance)
        r = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_closed"])
        self.assertEqual(r.data["closed_by"], "fin_officer")
        self.assertIsNotNone(r.data["closed_at"])
        audit = DayAuditLog.objects.get(audit_date=self.today)
        self.assertTrue(audit.is_closed)
        self.assertEqual(audit.closed_by, "fin_officer")

    def test_get_after_close_shows_finalized_label(self):
        self.client.force_authenticate(user=self.finance)
        self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        r = self.client.get("/api/users/reports/z-report/?date=%s" % self.today)
        self.assertEqual(r.data["report_type"], "Z-Report")
        self.assertTrue(r.data["is_closed"])

    def test_repeat_post_returns_stored_snapshot_not_live_recalculation(self):
        """
        FINALIZATION SEMANTICS:
        A repeat POST on an already-closed day must return the STORED snapshot
        (original closed_at, closed_by, and financial totals) without
        recalculating or overwriting them.
        Finalized Z-Report figures must never change silently.
        """
        self.client.force_authenticate(user=self.finance)
        # First closure - empty day, grand_total = 0
        r1 = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r1.status_code, 200)
        first_closed_at = r1.data["closed_at"]
        first_closed_by = r1.data["closed_by"]
        first_grand_total = float(r1.data["grand_total"])

        # Add revenue AFTER closure - must NOT affect repeat-closure response
        room = _room("099", 1500)
        _reservation(room, "Alice", self.today, self.today + timedelta(days=2))
        RoomHistory.objects.create(
            room=room, event_type="checkin", guest_name="Alice",
            check_in_date=self.today,
            check_out_date=self.today + timedelta(days=2),
            revenue=Decimal("3000.00"),
        )

        # Second POST by a DIFFERENT user
        self.client.force_authenticate(user=self.admin)
        r2 = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data["is_closed"])
        self.assertTrue(r2.data.get("already_closed"))
        # Original closer preserved - admin must NOT replace fin_officer
        self.assertEqual(r2.data["closed_by"], first_closed_by)
        self.assertEqual(r2.data["closed_at"], first_closed_at)
        # Grand total must NOT change (stored=0, new data=3000)
        self.assertEqual(float(r2.data["grand_total"]), first_grand_total)
        self.assertEqual(DayAuditLog.objects.filter(audit_date=self.today).count(), 1)

    def test_get_forbidden_for_waiter(self):
        self.client.force_authenticate(user=self.waiter)
        r = self.client.get("/api/users/reports/z-report/?date=%s" % self.today)
        self.assertEqual(r.status_code, 403)

    def test_post_forbidden_for_waiter(self):
        self.client.force_authenticate(user=self.waiter)
        r = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_concurrent_closure_produces_single_audit_row(self):
        """
        DayAuditLog.audit_date has unique=True.
        Sequential simulation: first closure wins. Second POST returns stored
        snapshot. Exactly one row must exist after both requests.
        """
        self.client.force_authenticate(user=self.finance)
        r1 = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r1.status_code, 200)

        self.client.force_authenticate(user=self.admin)
        r2 = self.client.post(
            "/api/users/reports/z-report/", {"date": str(self.today)}, format="json")
        self.assertEqual(r2.status_code, 200)
        # First closer must be preserved
        self.assertEqual(r2.data["closed_by"], "fin_officer")
        self.assertEqual(DayAuditLog.objects.filter(audit_date=self.today).count(), 1)


# ===========================================================================
# GL revenue tests (DEFECT-FIN-001, GL path)
# ===========================================================================

class GLRevenueTests(RevenueBase):

    def test_gl_net_credits_minus_debits_with_partial_refund(self):
        """
        GL path net revenue = credits - debits per account.
        Room: 2000 credit - 150 debit (partial refund) = 1850 net.
        F&B: 500 credit = 500. Total = 2350.
        """
        _jv("Room Checkin",
            [{"account_code": "1000", "debit": "2000.00", "credit": "0.00"},
             {"account_code": "4000", "debit": "0.00",    "credit": "2000.00"}],
            date=self.today)
        _jv("FB Revenue",
            [{"account_code": "1200", "debit": "500.00",  "credit": "0.00"},
             {"account_code": "4100", "debit": "0.00",    "credit": "500.00"}],
            date=self.today)
        _jv("Room Partial Refund",
            [{"account_code": "4000", "debit": "150.00",  "credit": "0.00"},
             {"account_code": "1000", "debit": "0.00",    "credit": "150.00"}],
            date=self.today)

        m, chart = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),   Decimal("1850.00"))
        self.assertEqual(self._d(m["fb_revenue"]),     Decimal("500.00"))
        self.assertEqual(self._d(m["total_revenue"]),  Decimal("2350.00"))

    def test_gl_negative_net_revenue_not_clamped(self):
        """
        All-refund period: debits exceed credits on revenue accounts.
        Net revenue MUST be negative - must NOT be clamped to zero.
        200 credit - 500 debit = -300.
        """
        _jv("Small Revenue",
            [{"account_code": "1000", "debit": "200.00", "credit": "0.00"},
             {"account_code": "4000", "debit": "0.00",   "credit": "200.00"}],
            date=self.today)
        _jv("Full Refund Exceeds",
            [{"account_code": "4000", "debit": "500.00", "credit": "0.00"},
             {"account_code": "1000", "debit": "0.00",   "credit": "500.00"}],
            date=self.today)

        m, chart = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]), Decimal("-300.00"))
        self.assertLess(float(m["total_revenue"]), 0)
        pt = next((p for p in chart if p["date"] == str(self.today)), None)
        self.assertIsNotNone(pt)
        self.assertLess(pt["revenue"], 0, "Chart point must reflect negative net")

    def test_gl_folio_extras_account_4200_included(self):
        """Account 4200 (Folio Extras Revenue) must be included in total_revenue."""
        _jv("Minibar",
            [{"account_code": "1200", "debit": "80.00", "credit": "0.00"},
             {"account_code": "4200", "debit": "0.00",  "credit": "80.00"}],
            date=self.today)
        m, _ = self._metrics()
        self.assertEqual(self._d(m["folio_revenue"]), Decimal("80.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("80.00"))

    def test_gl_category_breakdown_reconciles_with_total(self):
        """room + fb + folio == total_revenue (no rounding gaps)."""
        _jv("Room",  [{"account_code": "1000", "debit": "1000.00", "credit": "0.00"},
                      {"account_code": "4000", "debit": "0.00",    "credit": "1000.00"}], date=self.today)
        _jv("FB",    [{"account_code": "1000", "debit": "300.00",  "credit": "0.00"},
                      {"account_code": "4100", "debit": "0.00",    "credit": "300.00"}],  date=self.today)
        _jv("Folio", [{"account_code": "1000", "debit": "50.00",   "credit": "0.00"},
                      {"account_code": "4200", "debit": "0.00",    "credit": "50.00"}],   date=self.today)
        m, _ = self._metrics()
        breakdown = (self._d(m["room_revenue"]) +
                     self._d(m["fb_revenue"]) +
                     self._d(m["folio_revenue"]))
        self.assertEqual(breakdown, self._d(m["total_revenue"]))

    def test_partial_gl_documented_limitation(self):
        """
        PARTIAL GL LIMITATION (documented behavior):
        When GL exists for any day in the period, dashboard uses GL mode for
        the ENTIRE period. Operational revenue on days without GL entries will
        NOT appear in the total. This test asserts that documented behavior.
        Expected: only GL amount (500) counted, not 500 + 1000 (operational).
        """
        room = _room("310", 1000)
        _reservation(room, "YesterdayGuest", self.yesterday, self.today)
        rh = RoomHistory(
            room=room, event_type="checkin", guest_name="YesterdayGuest",
            check_in_date=self.yesterday, check_out_date=self.today,
            revenue=Decimal("1000.00"),
        )
        rh.save()
        RoomHistory.objects.filter(pk=rh.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        _jv("Today Room",
            [{"account_code": "1000", "debit": "500.00", "credit": "0.00"},
             {"account_code": "4000", "debit": "0.00",   "credit": "500.00"}],
            date=self.today)

        m, _ = self._metrics(start=self.yesterday, end=self.today)
        # Only GL entry (500) counted; yesterday's 1000 operational is absent.
        # This is expected documented behavior for partial GL adoption.
        self.assertEqual(self._d(m["total_revenue"]), Decimal("500.00"))


# ===========================================================================
# Operational fallback tests (DEFECT-FIN-001, no GL)
# ===========================================================================

class OperationalFallbackTests(RevenueBase):

    def test_checkin_and_checkout_same_period_exact_no_double_count(self):
        """
        Non-prepaid: checkin (1800) and checkout (0 extras) in same period.
        room_revenue MUST be 1800, NOT 3600.
        """
        room = _room("101", 900)  # 2 nights = 1800
        today = self.today
        out = today + timedelta(days=2)
        _reservation(room, "Alice", today, out, total_amount=Decimal("1800.00"))
        _rh(room, "checkin",  "Alice", today, out, 1800)
        _rh(room, "checkout", "Alice", today, out, 0)

        m, chart = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),  Decimal("1800.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("1800.00"))
        pt = next(p for p in chart if p["date"] == str(today))
        self.assertEqual(self._d(pt["revenue"]), Decimal("1800.00"))

    def test_checkin_previous_period_checkout_this_period_exact_amount(self):
        """
        Multi-period stay: checkin yesterday (out of range), checkout today.
        room_revenue must equal base_price x 1 night = 1200 reconstructed
        from the matched Reservation record.
        """
        room = _room("102", 1200)
        yesterday, today = self.yesterday, self.today
        _reservation(room, "Bob", yesterday, today, total_amount=Decimal("1200.00"))
        _rh(room, "checkin",  "Bob", yesterday, today, 1200,
            created_at=timezone.now() - timedelta(days=1))
        _rh(room, "checkout", "Bob", yesterday, today, 0)

        m, chart = self._metrics(start=today, end=today)
        self.assertEqual(self._d(m["room_revenue"]), Decimal("1200.00"))
        pt = next(p for p in chart if p["date"] == str(today))
        self.assertEqual(self._d(pt["revenue"]), Decimal("1200.00"))

    def test_zero_revenue_checkin_contributes_zero(self):
        """Complimentary stay (revenue=0) must contribute 0 to all totals."""
        room = _room("103", 800)
        today, out = self.today, self.today + timedelta(days=1)
        _reservation(room, "Carol", today, out, total_amount=Decimal("0.00"))
        _rh(room, "checkin",  "Carol", today, out, 0)
        _rh(room, "checkout", "Carol", today, out, 0)

        m, _ = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),  Decimal("0.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("0.00"))

    def test_multiple_reservations_same_room_same_checkout_date_correct_guest(self):
        """
        Two reservations for the same room, same check_out_date, different guests.
        The guest_name filter must ensure Alice's checkout event (1 night, 1000)
        matches Alice's reservation, NOT Bob's (2 nights, 2000).
        """
        room = _room("104", 1000)
        today, yesterday = self.today, self.yesterday

        _reservation(room, "Alice-104", yesterday, today,
                     total_amount=Decimal("1000.00"))
        _reservation(room, "Bob-104",   today - timedelta(days=2), today,
                     total_amount=Decimal("2000.00"))

        # Alice: checkin yesterday (out of range), checkout today
        _rh(room, "checkin",  "Alice-104", yesterday, today, 1000,
            created_at=timezone.now() - timedelta(days=1))
        _rh(room, "checkout", "Alice-104", yesterday, today, 0)

        m, _ = self._metrics(start=today, end=today)
        # Alice: 1 night x 1000 = 1000; NOT Bob's 2 nights x 1000 = 2000
        self.assertEqual(self._d(m["room_revenue"]), Decimal("1000.00"))

    def test_fb_room_charged_excluded_from_folio_no_double_count(self):
        """
        F&B charged to room: counted once via Order (450), NOT again via FolioCharge.
        Laundry extra (100) counted under folio_revenue.
        Expected: room=1800, fb=450, folio=100, total=2350.
        """
        room = _room("105", 900)
        today, out = self.today, self.today + timedelta(days=2)
        res = _reservation(room, "Dave", today, out, total_amount=Decimal("1800.00"))
        _rh(room, "checkin",  "Dave", today, out, 1800)
        _rh(room, "checkout", "Dave", today, out, 0)

        cat = Category.objects.create(name="Dinner", station="Kitchen")
        mi = MenuItem.objects.create(
            name="Steak", category=cat, price=Decimal("450.00"))
        tbl = RestaurantTable.objects.create(table_code="T01", label_name="Table 1")
        order = Order.objects.create(
            table=tbl, status="paid", payment_status="paid",
            total_amount=Decimal("450.00"))
        OrderItem.objects.create(
            order=order, menu_item=mi, quantity=1,
            price_at_order=Decimal("450.00"))

        # F&B room charge - must NOT appear in folio_revenue
        FolioCharge.objects.create(
            reservation=res,
            description="F&B Order #%d (Table 1)" % order.id,
            amount=Decimal("450.00"))
        # Legitimate folio extra
        FolioCharge.objects.create(
            reservation=res, description="Laundry", amount=Decimal("100.00"))

        m, chart = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),  Decimal("1800.00"))
        self.assertEqual(self._d(m["fb_revenue"]),    Decimal("450.00"))
        self.assertEqual(self._d(m["folio_revenue"]), Decimal("100.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("2350.00"))
        pt = next(p for p in chart if p["date"] == str(today))
        self.assertEqual(self._d(pt["revenue"]), Decimal("2350.00"))

    def test_room_only_stay_three_nights_exact(self):
        """3-night room-only stay: total = 750 x 3 = 2250."""
        room = _room("106", 750)
        today, out = self.today, self.today + timedelta(days=3)
        _reservation(room, "Eve", today, out, total_amount=Decimal("2250.00"))
        _rh(room, "checkin", "Eve", today, out, 2250)

        m, _ = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),  Decimal("2250.00"))
        self.assertEqual(self._d(m["fb_revenue"]),    Decimal("0.00"))
        self.assertEqual(self._d(m["folio_revenue"]), Decimal("0.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("2250.00"))

    def test_restaurant_only_no_rooms(self):
        """F&B-only period: fb_revenue = 600, room_revenue = 0."""
        cat = Category.objects.create(name="Lunch", station="Kitchen")
        mi = MenuItem.objects.create(
            name="Burger", category=cat, price=Decimal("200.00"))
        tbl = RestaurantTable.objects.create(table_code="T02", label_name="Table 2")
        order = Order.objects.create(
            table=tbl, status="paid", payment_status="paid",
            total_amount=Decimal("600.00"))
        OrderItem.objects.create(
            order=order, menu_item=mi, quantity=3,
            price_at_order=Decimal("200.00"))

        m, _ = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]),  Decimal("0.00"))
        self.assertEqual(self._d(m["fb_revenue"]),    Decimal("600.00"))
        self.assertEqual(self._d(m["total_revenue"]), Decimal("600.00"))

    def test_discounted_stay_uses_checkin_history_revenue_not_base_price(self):
        """
        Discounted stay (base_price=1500, actual charged=1200).
        Checkin RoomHistory.revenue stores the actual charged amount (1200).
        checkin_rev uses RoomHistory.revenue directly so result must be 1200, NOT 1500.
        """
        room = _room("108", 1500)
        today, out = self.today, self.today + timedelta(days=1)
        _reservation(room, "Grace", today, out, total_amount=Decimal("1200.00"))
        _rh(room, "checkin", "Grace", today, out, 1200)

        m, _ = self._metrics()
        self.assertEqual(self._d(m["room_revenue"]), Decimal("1200.00"))

    def test_edited_checkout_date_checkout_matches_by_guest_name(self):
        """
        Reservation check_out_date extended after checkin.
        Checkout RoomHistory has new date; Reservation has updated date.
        guest_name filter ensures correct match.
        Same-period checkin means checkout adds 0 lodging (no double-count).
        """
        room = _room("107", 1000)
        today, new_out = self.today, self.today + timedelta(days=2)
        _reservation(room, "Frank", today, new_out, total_amount=Decimal("2000.00"))
        # Checkin recorded with original date
        _rh(room, "checkin",  "Frank", today, today + timedelta(days=1), 1000)
        # Checkout recorded with extended date
        _rh(room, "checkout", "Frank", today, new_out, 0)

        m, _ = self._metrics()
        # checkin_rev=1000 (in range); checkout adds 0 (checkin in same period)
        self.assertEqual(self._d(m["room_revenue"]), Decimal("1000.00"))
