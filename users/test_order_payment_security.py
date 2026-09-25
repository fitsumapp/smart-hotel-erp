"""Security regression tests for order state changes and Chapa payments."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from hotel.models import (
    Category,
    MenuItem,
    Order,
    OrderItem,
    Reservation,
    RestaurantTable,
    Room,
    SystemSettings,
)
from users.models import User
from users.views import build_payment_summary


class OrderSecurityFixture(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-order",
            password="test-password",
            role=User.ADMIN,
            is_active=True,
        )
        self.cashier = User.objects.create_user(
            username="cashier-order",
            password="test-password",
            role=User.CASHIER,
            is_active=True,
        )
        self.waiter = User.objects.create_user(
            username="waiter-order",
            password="test-password",
            role=User.WAITER,
            is_active=True,
        )
        self.kitchen = User.objects.create_user(
            username="kitchen-order",
            password="test-password",
            role=User.KITCHEN,
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username="customer-order",
            password="test-password",
            role=User.CUSTOMER,
            is_active=True,
        )
        self.table = RestaurantTable.objects.create(table_code="SEC-01")
        category = Category.objects.create(name="Security Test", station="Kitchen")
        menu_item = MenuItem.objects.create(
            name="Security Meal",
            category=category,
            price=Decimal("100.00"),
        )
        self.order = Order.objects.create(
            table=self.table,
            waiter_id_ref=self.waiter.pk,
            waiter_username=self.waiter.username,
            status="pending",
            payment_status="pending",
        )
        OrderItem.objects.create(
            order=self.order,
            menu_item=menu_item,
            quantity=1,
            price_at_order=menu_item.price,
        )


class OrderAuthorizationTests(OrderSecurityFixture):
    def test_cash_payment_rolls_back_when_journal_posting_fails(self):
        from apps.orders.services import finalize_paid_order
        from hotel.models import JournalEntry

        with patch("apps.orders.services.post_journal_entry", side_effect=ValueError("ledger unavailable")):
            with self.assertRaises(ValueError):
                finalize_paid_order(self.order, "Cash", cashier=self.cashier)

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")
        self.assertFalse(JournalEntry.objects.exists())

    def test_customer_cannot_complete_order_as_paid(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse("complete-order", args=[self.order.pk]),
            {"payment_method": "Cash"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")

    def test_cashier_can_complete_order(self):
        self.client.force_authenticate(self.cashier)
        with patch("users.views.finalize_paid_order") as finalize:
            response = self.client.post(
                reverse("complete-order", args=[self.order.pk]),
                {"payment_method": "Cash"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        finalize.assert_called_once()

    def test_customer_cannot_use_cashier_process_endpoint(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse("process_payment", args=[self.order.pk]),
            {"payment_method": "Cash"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kitchen_can_apply_valid_transition(self):
        self.client.force_authenticate(self.kitchen)
        response = self.client.post(
            reverse("update-order-status", args=[self.order.pk]),
            {"status": "preparing"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "preparing")

    def test_customer_cannot_change_order_status(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse("update-order-status", args=[self.order.pk]),
            {"status": "ready"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    def test_invalid_or_skipped_transition_is_rejected(self):
        self.client.force_authenticate(self.kitchen)

        arbitrary = self.client.post(
            reverse("update-order-status", args=[self.order.pk]),
            {"status": "paid"},
            format="json",
        )
        skipped = self.client.post(
            reverse("update-order-status", args=[self.order.pk]),
            {"status": "ready"},
            format="json",
        )

        self.assertEqual(arbitrary.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(skipped.status_code, status.HTTP_400_BAD_REQUEST)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")


class ChapaOrderVerificationTests(OrderSecurityFixture):
    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1,
            defaults={"vat_enabled": False, "service_charge_enabled": False},
        )
        self.order.payment_page_token = "public-payment-token"
        self.order.chapa_tx_ref = "order-secure-reference"
        self.order.tip_amount = Decimal("10.00")
        self.order.save(
            update_fields=["payment_page_token", "chapa_tx_ref", "tip_amount"]
        )
        self.url = reverse("public-payment-verify", args=[self.order.payment_page_token])
        self.expected_amount = Decimal(
            str(build_payment_summary(self.order)["amount_due"])
        )

    @patch("users.views.verify_chapa_transaction")
    def test_client_cannot_substitute_another_successful_tx_ref(self, verify):
        response = self.client.post(
            self.url,
            {"tx_ref": "another-successful-transaction"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        verify.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    def test_underpayment_is_rejected(self, verify, finalize):
        verify.return_value = {
            "data": {
                "status": "success",
                "tx_ref": self.order.chapa_tx_ref,
                "amount": str(self.expected_amount - Decimal("1.00")),
                "currency": "ETB",
            }
        }

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        finalize.assert_not_called()

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    def test_wrong_currency_is_rejected(self, verify, finalize):
        verify.return_value = {
            "data": {
                "status": "success",
                "tx_ref": self.order.chapa_tx_ref,
                "amount": str(self.expected_amount),
                "currency": "USD",
            }
        }

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        finalize.assert_not_called()

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    def test_exact_bound_transaction_can_finalize(self, verify, finalize):
        verify.return_value = {
            "data": {
                "status": "success",
                "tx_ref": self.order.chapa_tx_ref,
                "amount": str(self.expected_amount),
                "currency": "ETB",
            }
        }

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        finalize.assert_called_once()


class ChapaReservationVerificationTests(APITestCase):
    def setUp(self):
        room = Room.objects.create(
            name="Secure Room",
            room_number="SEC-R1",
            room_type="Standard",
            base_price=Decimal("1000.00"),
        )
        self.reservation = Reservation.objects.create(
            room=room,
            guest_name="Secure Guest",
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=2),
            deposit_amount=Decimal("500.00"),
            total_amount=Decimal("1000.00"),
            chapa_tx_ref="reservation-secure-reference",
        )
        self.url = reverse(
            "public-reservation-verify",
            args=[self.reservation.public_token],
        )

    @patch("users.views.verify_chapa_transaction")
    def test_reservation_rejects_substituted_tx_ref(self, verify):
        response = self.client.post(
            self.url,
            {"tx_ref": "transaction-from-another-reservation"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        verify.assert_not_called()
