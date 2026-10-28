"""
Regression tests for DEFECT-PMS-002: Reservation No-Show Handling.
"""
import users.views  # noqa: F401
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import JournalEntry
from apps.reservations.services import create_reservation_safely, reservation_overlaps
from hotel.integrity import transition_reservation
from hotel.models import Reservation, Room, SystemSettings
from users.models import User


class NoShowReservationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        SystemSettings.objects.get_or_create(
            id=1,
            defaults={
                "hotel_name": "Acrma Grand Hotel",
                "tin_number": "0012345678",
                "printer_paper_size": "80mm",
            },
        )
        pw = "SecuredPass123!"
        self.admin = User.objects.create_user(
            username="admin_operator", password=pw, role=User.ADMIN, is_active=True
        )
        self.reception = User.objects.create_user(
            username="reception_staff", password=pw, role=User.RECEPTION, is_active=True
        )
        self.waiter = User.objects.create_user(
            username="waiter_staff", password=pw, role=User.WAITER, is_active=True
        )
        self.cashier = User.objects.create_user(
            username="cashier_staff", password=pw, role=User.CASHIER, is_active=True
        )

        self.room = Room.objects.create(
            room_number="301",
            name="Deluxe 301",
            room_type="deluxe",
            base_price=Decimal("1500.00"),
            status="Available",
        )
        self.today = timezone.now().date()
        self.tomorrow = self.today + timedelta(days=1)
        self.checkout_date = self.today + timedelta(days=3)

    def _create_reservation(self, status_val="confirmed", room=None, check_in=None, check_out=None):
        r = room or self.room
        ci = check_in or self.today
        co = check_out or self.checkout_date
        nights = max((co - ci).days, 1)
        res = Reservation.objects.create(
            room=r,
            guest_name="John Traveler",
            guest_email="john@example.com",
            guest_phone="+251911223344",
            check_in_date=ci,
            check_out_date=co,
            status=status_val,
            total_amount=Decimal(str(r.base_price)) * nights,
            deposit_amount=Decimal("500.00"),
            payment_status="paid",
        )
        res.ensure_tokens()
        res.save()
        return res

    # -----------------------------------------------------------------------
    # 1. Valid Transition: confirmed -> no_show
    # -----------------------------------------------------------------------

    def test_transition_confirmed_to_no_show_via_api(self):
        """Confirmed reservation transitions cleanly to no_show via API."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="confirmed")
        self.assertIsNone(res.no_show_at)

        response = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reservation"]["status"], "no_show")
        self.assertIsNotNone(response.data["reservation"]["no_show_at"])

        res.refresh_from_db()
        self.assertEqual(res.status, "no_show")
        self.assertIsNotNone(res.no_show_at)

    def test_transition_confirmed_to_no_show_via_model_and_integrity(self):
        """Model save and transition_reservation permit confirmed to no_show."""
        res = self._create_reservation(status_val="confirmed")
        now = timezone.now()
        res, transitioned = transition_reservation(
            reservation_id=res.pk, to_status="no_show", no_show_at=now
        )
        self.assertTrue(transitioned)
        self.assertEqual(res.status, "no_show")
        self.assertEqual(res.no_show_at, now)

    # -----------------------------------------------------------------------
    # 2. Invalid Transitions: only confirmed -> no_show is allowed
    # -----------------------------------------------------------------------

    def test_invalid_transition_from_pending_to_no_show(self):
        """Pending reservation cannot transition to no_show."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="pending")

        response = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot transition reservation", response.data["error"])

        res.refresh_from_db()
        self.assertEqual(res.status, "pending")
        self.assertIsNone(res.no_show_at)

    def test_invalid_transition_from_checked_in_to_no_show(self):
        """Checked-in reservation cannot transition to no_show."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="checked_in")

        response = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        res.refresh_from_db()
        self.assertEqual(res.status, "checked_in")

    def test_invalid_transition_from_checked_out_to_no_show(self):
        """Checked-out reservation cannot transition to no_show."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="checked_out")

        response = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        res.refresh_from_db()
        self.assertEqual(res.status, "checked_out")

    def test_invalid_transition_from_cancelled_to_no_show(self):
        """Cancelled reservation cannot transition to no_show."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="cancelled")

        response = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        res.refresh_from_db()
        self.assertEqual(res.status, "cancelled")

    def test_invalid_transition_from_no_show_to_other_statuses(self):
        """no_show is terminal; cannot transition to checked_in, checked_out, confirmed, or cancelled."""
        res = self._create_reservation(status_val="confirmed")
        res.status = "no_show"
        res.no_show_at = timezone.now()
        res.save()

        for target in ["checked_in", "checked_out", "confirmed", "cancelled", "pending"]:
            with self.assertRaises(ValidationError):
                res.status = target
                res.save()
            res.refresh_from_db()
            self.assertEqual(res.status, "no_show")

    # -----------------------------------------------------------------------
    # 3. Room Rebooking & Availability Restoration (GiST / Overlap Check)
    # -----------------------------------------------------------------------

    def test_room_rebooking_same_dates_allowed_after_no_show(self):
        """
        A confirmed reservation blocks rebooking for the same room and dates.
        Once marked as no_show, rebooking for those exact dates succeeds.
        """
        # Step 1: Create confirmed booking
        res1 = self._create_reservation(
            status_val="confirmed",
            check_in=self.today,
            check_out=self.checkout_date,
        )
        self.assertTrue(reservation_overlaps(self.room, self.today, self.checkout_date))

        # Attempting a second reservation for same room and dates fails
        with self.assertRaises(ValidationError):
            create_reservation_safely(
                room_id=self.room.id,
                guest_name="Jane Walkin",
                check_in_date=self.today,
                check_out_date=self.checkout_date,
            )

        # Step 2: Mark res1 as no_show via API
        self.client.force_authenticate(user=self.reception)
        r = self.client.post(f"/api/users/reservations/{res1.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        # Step 3: Verify overlap helper reports room is no longer overlapping
        self.assertFalse(reservation_overlaps(self.room, self.today, self.checkout_date))

        # Step 4: Rebooking for the exact same room and dates now succeeds
        res2 = create_reservation_safely(
            room_id=self.room.id,
            guest_name="Jane Walkin",
            check_in_date=self.today,
            check_out_date=self.checkout_date,
            status="confirmed",
        )
        self.assertIsNotNone(res2.pk)
        self.assertEqual(res2.room.id, self.room.id)
        self.assertEqual(res2.status, "confirmed")

    # -----------------------------------------------------------------------
    # 4. Room Status Updates on No-Show
    # -----------------------------------------------------------------------

    def test_room_status_resets_to_available_when_no_other_active_booking(self):
        """When a room was 'Reserved' for a booking and marked no-show, status becomes Available."""
        self.room.status = "Reserved"
        self.room.save()

        res = self._create_reservation(status_val="confirmed", check_in=self.today, check_out=self.checkout_date)
        self.client.force_authenticate(user=self.reception)
        r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Available")

    def test_room_status_retains_reserved_if_another_active_booking_today(self):
        """If another active reservation exists for the same room today, room stays Reserved."""
        self.room.status = "Reserved"
        self.room.save()

        # res2: active today [today, tomorrow)
        res2 = self._create_reservation(
            status_val="confirmed", room=self.room, check_in=self.today, check_out=self.tomorrow
        )
        # res1: future consecutive booking [tomorrow, checkout_date) - zero overlap with res2
        res1 = self._create_reservation(
            status_val="confirmed", room=self.room, check_in=self.tomorrow, check_out=self.checkout_date
        )

        self.client.force_authenticate(user=self.reception)
        r = self.client.post(f"/api/users/reservations/{res1.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        self.room.refresh_from_db()
        # res2 is still active for today, so room remains Reserved
        self.assertEqual(self.room.status, "Reserved")

    def test_room_status_does_not_override_occupied_or_cleaning_or_maintenance(self):
        """No-show on a reservation must not touch rooms in Occupied, Cleaning, or Maintenance."""
        for non_reserved_status in ["Occupied", "Cleaning", "Maintenance"]:
            self.room.status = non_reserved_status
            self.room.save()

            res = self._create_reservation(status_val="confirmed", check_in=self.today, check_out=self.tomorrow)
            self.client.force_authenticate(user=self.reception)
            r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

            self.room.refresh_from_db()
            self.assertEqual(self.room.status, non_reserved_status)

    # -----------------------------------------------------------------------
    # 5. Repeated Requests (Idempotency)
    # -----------------------------------------------------------------------

    def test_repeat_no_show_request_is_idempotent(self):
        """Second call to no-show endpoint returns 200 OK without altering original timestamp."""
        self.client.force_authenticate(user=self.reception)
        res = self._create_reservation(status_val="confirmed")

        r1 = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        first_no_show_at = r1.data["reservation"]["no_show_at"]
        self.assertIsNotNone(first_no_show_at)

        # Repeat request by Admin
        self.client.force_authenticate(user=self.admin)
        r2 = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertTrue(r2.data.get("already_no_show"))
        self.assertEqual(r2.data["reservation"]["no_show_at"], first_no_show_at)

    # -----------------------------------------------------------------------
    # 6. Endpoint Permissions & Authentication
    # -----------------------------------------------------------------------

    def test_reception_and_admin_permitted(self):
        """Both reception and admin roles are authorized to mark no-show."""
        res_rec = self._create_reservation(status_val="confirmed")
        self.client.force_authenticate(user=self.reception)
        r = self.client.post(f"/api/users/reservations/{res_rec.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        res_adm = self._create_reservation(status_val="confirmed")
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/users/reservations/{res_adm.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unauthorized_roles_forbidden(self):
        """Waiter and Cashier roles receive 403 Forbidden."""
        res = self._create_reservation(status_val="confirmed")

        self.client.force_authenticate(user=self.waiter)
        r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.cashier)
        r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

        res.refresh_from_db()
        self.assertEqual(res.status, "confirmed")

    def test_unauthenticated_request_rejected(self):
        """Anonymous call returns 401 Unauthorized."""
        res = self._create_reservation(status_val="confirmed")
        self.client.logout()
        r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_reservation_returns_404(self):
        """Invalid reservation ID returns 404 Not Found."""
        self.client.force_authenticate(user=self.reception)
        r = self.client.post("/api/users/reservations/999999/no-show/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    # -----------------------------------------------------------------------
    # 7. Accounting Boundary: No Automatic Journal Postings
    # -----------------------------------------------------------------------

    def test_accounting_boundary_no_automatic_journal_entries_created(self):
        """
        Marking a reservation as no-show must NOT post journal entries,
        forfeit deposits automatically, or mutate GL ledger balances.
        """
        res = self._create_reservation(status_val="confirmed")
        initial_jv_count = JournalEntry.objects.count()

        self.client.force_authenticate(user=self.reception)
        r = self.client.post(f"/api/users/reservations/{res.id}/no-show/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        final_jv_count = JournalEntry.objects.count()
        self.assertEqual(final_jv_count, initial_jv_count, "No journal entries must be posted for no-show")
