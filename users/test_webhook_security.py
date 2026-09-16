"""Regression tests for signed Chapa webhook payment validation."""

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
    RestaurantTable,
    SystemSettings,
)
from users.views import build_payment_summary


class ChapaWebhookOrderSecurityTests(APITestCase):
    def setUp(self):
        SystemSettings.objects.create(
            vat_enabled=False,
            service_charge_enabled=False,
        )
        table = RestaurantTable.objects.create(table_code="WEBHOOK-SEC")
        category = Category.objects.create(name="Webhook", station="Kitchen")
        menu_item = MenuItem.objects.create(
            name="Webhook Meal",
            category=category,
            price=Decimal("125.00"),
        )
        self.order = Order.objects.create(
            table=table,
            chapa_tx_ref="webhook-order-reference",
            payment_status="pending",
            tip_amount=Decimal("5.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            menu_item=menu_item,
            quantity=1,
            price_at_order=menu_item.price,
        )
        self.expected_amount = Decimal(
            str(build_payment_summary(self.order)["amount_due"])
        )
        self.url = reverse("chapa-webhook")

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    @patch("users.views.is_valid_chapa_signature", return_value=True)
    def test_signed_webhook_still_rejects_underpayment(
        self, signature, verify, finalize
    ):
        verify.return_value = {
            "data": {
                "status": "success",
                "tx_ref": self.order.chapa_tx_ref,
                "amount": str(self.expected_amount - Decimal("1.00")),
                "currency": "ETB",
            }
        }

        response = self.client.post(
            self.url,
            {"tx_ref": self.order.chapa_tx_ref},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        finalize.assert_not_called()

    @patch("users.views.finalize_paid_order")
    @patch("users.views.verify_chapa_transaction")
    @patch("users.views.is_valid_chapa_signature", return_value=True)
    def test_signed_exact_webhook_can_finalize_once(
        self, signature, verify, finalize
    ):
        verify.return_value = {
            "data": {
                "status": "success",
                "tx_ref": self.order.chapa_tx_ref,
                "amount": str(self.expected_amount),
                "currency": "ETB",
            }
        }

        response = self.client.post(
            self.url,
            {"tx_ref": self.order.chapa_tx_ref},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        finalize.assert_called_once()

