"""
Regression tests for Front Office module operations and defect repairs.
Covers:
- Future reservations when room is occupied today (DEFECT-FO-001)
- Room status preservation for future bookings (DEFECT-FO-001)
- Front desk check-in with explicit reservation_id and today date filtering (DEFECT-FO-002)
- Prevention of duplicate check-in on already occupied rooms (DEFECT-FO-002)
- Rejection of check-in on pending or invalid status reservations (DEFECT-FO-002)
- Enforcement of payment method when balance owed at checkout (DEFECT-FO-003)
- Final bill balance_due calculation for prepaid vs unpaid stays (DEFECT-FO-003)
- Checkout idempotency and repeat checkout handling (DEFECT-FO-004)
- Rejection of checkout on non-checked-in reservations (DEFECT-FO-004)
- Reservation cancellation and room inventory release (DEFECT-FO-005)
"""
import users.views  # noqa: F401
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import Account, JournalEntry
from apps.reservations.services import create_reservation_safely
from hotel.integrity import transition_reservation
from hotel.models import FolioCharge, Reservation, Room, RoomHistory, SystemSettings
from users.models import User


class FrontOfficeOperationsTests(TestCase):
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
            username="fo_admin", password=pw, role=User.ADMIN, is_active=True
        )
        self.reception = User.objects.create_user(
            username="fo_reception", password=pw, role=User.RECEPTION, is_active=True
        )
        self.waiter = User.objects.create_user(
            username="fo_waiter", password=pw, role=User.WAITER, is_active=True
        )

        self.room = Room.objects.create(
            room_number="401",
            name="Executive Suite 401",
            room_type="suite",
            base_price=Decimal("2000.00"),
            status="Available",
        )

        self.today = timezone.now().date()
        self.tomorrow = self.today + timedelta(days=1)
        self.future_checkin = self.today + timedelta(days=7)
        self.future_checkout = self.today + timedelta(days=10)

        # Setup GL accounts needed for auto JVs
        Account.objects.get_or_create(code="1000", defaults={"name": "Cash", "account_type": "asset"})
        Account.objects.get_or_create(code="1010", defaults={"name": "Bank Transfer", "account_type": "asset"})
        Account.objects.get_or_create(code="1200", defaults={"name": "Accounts Receivable", "account_type": "asset"})
        Account.objects.get_or_create(code="4000", defaults={"name": "Room Revenue", "account_type": "revenue"})

    def _create_reservation(self, **overrides):
        defaults = {
            "room_id": self.room.id,
            "guest_name": "Dawit Tesfaye",
            "guest_email": "dawit@example.com",
            "guest_phone": "+251911223344",
            "check_in_date": self.today,
            "check_out_date": self.tomorrow,
            "adults": 1,
            "children": 0,
            "notes": "VIP guest",
            "source": "reception",
            "total_amount": Decimal("2000.00"),
            "deposit_amount": Decimal("0.00"),
        }
        defaults.update(overrides)
        res = create_reservation_safely(**defaults)
        res.ensure_tokens()
        return res

    # -------------------------------------------------------------------------
    # DEFECT-FO-001: Future bookings and room status preservation
    # -------------------------------------------------------------------------
    def test_future_reservation_allowed_when_room_occupied_today(self):
        """A room occupied today must not block bookings for future dates."""
        self.room.status = "Occupied"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/reserve-now/"
        payload = {
            "guest_name": "Future Guest",
            "check_in_date": self.future_checkin.isoformat(),
            "check_out_date": self.future_checkout.isoformat(),
            "adults": 1,
            "source": "reception",
            "pay_now": "false",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Room status for today must remain Occupied (not overwritten to Reserved)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Occupied")

    def test_future_reservation_preserves_available_room_status_today(self):
        """Booking a future date must not set today's room status to Reserved."""
        self.room.status = "Available"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/reserve-now/"
        payload = {
            "guest_name": "Next Week Guest",
            "check_in_date": self.future_checkin.isoformat(),
            "check_out_date": self.future_checkout.isoformat(),
            "adults": 1,
            "source": "reception",
            "pay_now": "false",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Available")

    def test_immediate_reservation_sets_room_to_reserved(self):
        """Booking for today sets the room status to Reserved."""
        self.room.status = "Available"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/reserve-now/"
        payload = {
            "guest_name": "Today Guest",
            "check_in_date": self.today.isoformat(),
            "check_out_date": self.tomorrow.isoformat(),
            "adults": 1,
            "source": "reception",
            "pay_now": "false",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Reserved")

    # -------------------------------------------------------------------------
    # DEFECT-FO-002: Front desk check-in correctness and occupancy protection
    # -------------------------------------------------------------------------
    def test_checkin_with_explicit_reservation_id(self):
        """Check-in endpoint must honor the passed reservation_id rather than picking another."""
        # Create earlier reservation for today
        res_today = self._create_reservation(
            check_in_date=self.today, check_out_date=self.tomorrow, guest_name="Today Guest"
        )
        res_today, _ = transition_reservation(reservation_id=res_today.pk, to_status="confirmed")

        # Create future reservation for next month (created more recently)
        res_future = self._create_reservation(
            check_in_date=self.today + timedelta(days=30),
            check_out_date=self.today + timedelta(days=33),
            guest_name="Future Guest",
        )
        res_future, _ = transition_reservation(reservation_id=res_future.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        payload = {
            "reservation_id": res_today.id,
            "payment_method": "Cash",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        res_today.refresh_from_db()
        res_future.refresh_from_db()
        self.assertEqual(res_today.status, "checked_in")
        self.assertEqual(res_future.status, "confirmed")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Occupied")

    def test_checkin_prevented_when_room_occupied_by_another_guest(self):
        """Cannot check in a new reservation if the room is currently occupied by an active stay."""
        res_active = self._create_reservation(guest_name="Active Guest")
        res_active, _ = transition_reservation(reservation_id=res_active.pk, to_status="confirmed")
        res_active, _ = transition_reservation(reservation_id=res_active.pk, to_status="checked_in")
        self.room.status = "Occupied"
        self.room.save(update_fields=["status"])

        res_second = self._create_reservation(
            check_in_date=self.today + timedelta(days=5),
            check_out_date=self.today + timedelta(days=7),
            guest_name="Second Guest",
        )
        res_second, _ = transition_reservation(reservation_id=res_second.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        response = self.client.post(url, {"reservation_id": res_second.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("occupied", response.data.get("error", "").lower())

    def test_checkin_rejected_for_pending_status(self):
        """A pending reservation cannot be directly checked in without confirmation."""
        res = self._create_reservation()  # initial status is pending
        self.assertEqual(res.status, "pending")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        response = self.client.post(url, {"reservation_id": res.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res.refresh_from_db()
        self.assertEqual(res.status, "pending")

    # -------------------------------------------------------------------------
    # DEFECT-FO-003: Outstanding balance enforcement & final bill calculation
    # -------------------------------------------------------------------------
    def test_checkout_requires_payment_method_when_balance_owed(self):
        """Checkout with payment_method='None' must be rejected if the guest has an unpaid balance."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        res, _ = transition_reservation(reservation_id=res.pk, to_status="checked_in")
        res.payment_status = "pending"
        res.save(update_fields=["payment_status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/reservations/{res.id}/enhanced-checkout/"
        payload = {
            "payment_method": "None",
            "payment_status": "paid",
            "payment_reference": "No Extras",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment method", response.data.get("error", "").lower())

        # Submitting with valid Cash payment method succeeds
        payload["payment_method"] = "Cash"
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res.refresh_from_db()
        self.assertEqual(res.status, "checked_out")
        self.assertEqual(res.payment_status, "paid")

    def test_generate_final_bill_returns_accurate_balance_due(self):
        """Final bill must show exact balance_due for prepaid and unpaid reservations."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        res, _ = transition_reservation(reservation_id=res.pk, to_status="checked_in")
        res.payment_status = "paid"
        res.save(update_fields=["payment_status"])

        # Add minibar folio charge of ETB 250
        FolioCharge.objects.create(
            reservation=res, description="Minibar Soda", amount=Decimal("250.00"), added_by="staff"
        )

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/reservations/{res.id}/final-bill/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Because room is prepaid, balance_due should equal extras only (250)
        self.assertEqual(response.data["balance_due"], 250.0)
        self.assertEqual(response.data["payment_status"], "paid")
        self.assertFalse(response.data["is_paid"])

    # -------------------------------------------------------------------------
    # DEFECT-FO-004: Checkout idempotency and state protection
    # -------------------------------------------------------------------------
    def test_checkout_idempotency_prevents_duplicate_history_and_gl(self):
        """Calling checkout on an already checked out reservation returns 200 without duplicate entries."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        res, _ = transition_reservation(reservation_id=res.pk, to_status="checked_in")
        res.payment_status = "paid"
        res.save(update_fields=["payment_status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/reservations/{res.id}/enhanced-checkout/"
        payload = {"payment_method": "Cash", "payment_status": "paid"}

        # First checkout
        resp1 = self.client.post(url, payload, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        history_count = RoomHistory.objects.filter(room=self.room, event_type="checkout").count()
        self.assertEqual(history_count, 1)

        # Repeated checkout call
        resp2 = self.client.post(url, payload, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.data.get("already_checked_out"))

        # History count must still be 1 (no duplicate record)
        history_count_after = RoomHistory.objects.filter(room=self.room, event_type="checkout").count()
        self.assertEqual(history_count_after, 1)

    def test_checkout_rejected_if_reservation_not_checked_in(self):
        """Checkout endpoint must reject reservations that are not checked in."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/reservations/{res.id}/enhanced-checkout/"
        response = self.client.post(url, {"payment_method": "Cash"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("checked-in", response.data.get("error", "").lower())

    # -------------------------------------------------------------------------
    # DEFECT-FO-005: Reservation cancellation releases room inventory
    # -------------------------------------------------------------------------
    def test_reservation_cancellation_releases_room_inventory(self):
        """Cancelling a reservation transitions status to cancelled and sets room to Available."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        self.room.status = "Reserved"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/reservations/{res.id}/cancel/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        res.refresh_from_db()
        self.assertEqual(res.status, "cancelled")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Available")

        # Booking the room again for the same dates now succeeds without overlap conflict
        url_book = f"/api/users/rooms/{self.room.id}/reserve-now/"
        book_resp = self.client.post(url_book, {
            "guest_name": "New Replacement Guest",
            "check_in_date": self.today.isoformat(),
            "check_out_date": self.tomorrow.isoformat(),
            "adults": 1,
            "source": "reception",
            "pay_now": "false",
        }, format="json")
        self.assertEqual(book_resp.status_code, status.HTTP_201_CREATED)

    def test_front_desk_patch_cancel_action(self):
        """Front desk status PATCH with action='cancel' properly cancels reservation and frees room."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        self.room.status = "Reserved"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        response = self.client.patch(url, {"action": "cancel", "reservation_id": res.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        res.refresh_from_db()
        self.assertEqual(res.status, "cancelled")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Available")

    def test_waiter_cannot_perform_front_office_operations(self):
        """Unauthorized roles like Waiter must be rejected with 403 Forbidden."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.waiter)
        # Check cancel
        url_cancel = f"/api/users/reservations/{res.id}/cancel/"
        resp = self.client.post(url_cancel, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Check check-in
        url_checkin = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        resp2 = self.client.post(url_checkin, {"reservation_id": res.id}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # DEFECT-FO-006: Legacy checkout financial bypass remediation
    # -------------------------------------------------------------------------
    def test_legacy_checkout_cannot_bypass_payment_validation(self):
        """Legacy checkout action must reject unpaid stays without a valid payment method."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        res, _ = transition_reservation(reservation_id=res.pk, to_status="checked_in")
        res.payment_status = "pending"
        res.save(update_fields=["payment_status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        # Attempt to checkout via legacy route with payment_method="None"
        payload = {"action": "checkout", "reservation_id": res.id, "payment_method": "None"}
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment method", response.data.get("error", "").lower())

        # Submitting with valid Cash payment method through legacy route succeeds and settles payment
        payload["payment_method"] = "Cash"
        response2 = self.client.patch(url, payload, format="json")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        res.refresh_from_db()
        self.assertEqual(res.status, "checked_out")
        self.assertEqual(res.payment_status, "paid")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Cleaning")

    def test_legacy_checkout_does_not_duplicate_gl_or_history(self):
        """Repeating legacy checkout call returns idempotent 200 without duplicate records."""
        res = self._create_reservation()
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        res, _ = transition_reservation(reservation_id=res.pk, to_status="checked_in")
        res.payment_status = "paid"
        res.save(update_fields=["payment_status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        payload = {"action": "checkout", "reservation_id": res.id, "payment_method": "Cash"}

        # First checkout
        resp1 = self.client.patch(url, payload, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        history_count = RoomHistory.objects.filter(room=self.room, event_type="checkout").count()
        self.assertEqual(history_count, 1)

        # Repeated checkout call
        resp2 = self.client.patch(url, payload, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.data.get("already_checked_out"))

        # History count must not duplicate
        self.assertEqual(RoomHistory.objects.filter(room=self.room, event_type="checkout").count(), 1)

    # -------------------------------------------------------------------------
    # DEFECT-FO-007: Legacy cancellation room-status preservation
    # -------------------------------------------------------------------------
    def test_legacy_cancel_preserves_maintenance_and_cleaning_room_status(self):
        """Legacy cancellation must not change Maintenance or Cleaning rooms to Available."""
        res = self._create_reservation(
            check_in_date=self.future_checkin,
            check_out_date=self.future_checkout,
            guest_name="Future Maint Guest",
        )
        res, _ = transition_reservation(reservation_id=res.pk, to_status="confirmed")
        self.room.status = "Maintenance"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        response = self.client.patch(url, {"action": "cancel", "reservation_id": res.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        res.refresh_from_db()
        self.assertEqual(res.status, "cancelled")
        # Room status MUST remain Maintenance
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Maintenance")

    def test_legacy_cancel_without_reservation_rejected(self):
        """Cancelling on a room without a pending or confirmed reservation returns 400 and preserves status."""
        self.room.status = "Cleaning"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/front-desk-status/"
        response = self.client.patch(url, {"action": "cancel"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Cleaning")

    # -------------------------------------------------------------------------
    # OBSERVATION FO-008: Check-in date eligibility window enforcement
    # -------------------------------------------------------------------------
    def test_checkin_rejected_for_future_reservation(self):
        """Check-in for a future reservation date must be rejected (no early check-in)."""
        res_future = self._create_reservation(
            check_in_date=self.future_checkin,
            check_out_date=self.future_checkout,
            guest_name="Next Week Guest",
        )
        res_future, _ = transition_reservation(reservation_id=res_future.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        response = self.client.post(url, {"reservation_id": res_future.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("future date", response.data.get("error", "").lower())
        res_future.refresh_from_db()
        self.assertEqual(res_future.status, "confirmed")

    def test_checkin_rejected_for_expired_reservation(self):
        """Check-in for an expired reservation date must be rejected."""
        res_past = self._create_reservation(
            check_in_date=self.today - timedelta(days=3),
            check_out_date=self.today,
            guest_name="Past Guest",
        )
        res_past, _ = transition_reservation(reservation_id=res_past.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        response = self.client.post(url, {"reservation_id": res_past.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data.get("error", "").lower())
        res_past.refresh_from_db()
        self.assertEqual(res_past.status, "confirmed")

    # -------------------------------------------------------------------------
    # OBSERVATION FO-009: Check-in without linked reservation rejected
    # -------------------------------------------------------------------------
    def test_checkin_rejected_without_linked_reservation(self):
        """Calling check-in on a room with no confirmed reservation must return 400 Bad Request."""
        self.room.status = "Available"
        self.room.save(update_fields=["status"])

        self.client.force_authenticate(user=self.reception)
        url = f"/api/users/rooms/{self.room.id}/digital-checkin/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reservation", response.data.get("error", "").lower())

        # Room status must NOT be blindly mutated to Occupied
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Available")

    def test_public_qr_checkin_enforces_date_eligibility(self):
        """QR check-in for a future reservation must be rejected."""
        res_future = self._create_reservation(
            check_in_date=self.future_checkin,
            check_out_date=self.future_checkout,
            guest_name="QR Future Guest",
        )
        res_future, _ = transition_reservation(reservation_id=res_future.pk, to_status="confirmed")

        self.client.force_authenticate(user=self.reception)
        url = "/api/users/reservations/qr-checkin/"
        response = self.client.post(url, {"qr_token": res_future.qr_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("future date", response.data.get("error", "").lower())
