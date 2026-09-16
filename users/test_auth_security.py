"""Regression tests for authentication and user-management security."""

from django.core import mail
import re
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User


class PublicRegistrationSecurityTests(APITestCase):
    def test_public_registration_cannot_choose_admin_role_or_activation(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "A-secure-password-123!",
                "role": "admin",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="attacker")
        self.assertEqual(user.role, User.CUSTOMER)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("A-secure-password-123!"))
        self.assertEqual(len(mail.outbox), 1)

    def test_otp_activation_does_not_elevate_public_account(self):
        self.client.post(
            reverse("register"),
            {
                "username": "customer",
                "email": "customer@example.com",
                "password": "A-secure-password-123!",
                "role": "admin",
            },
            format="json",
        )
        user = User.objects.get(username="customer")
        self.assertIsNone(user.otp_code)
        otp = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

        response = self.client.post(
            reverse("verify-otp"),
            {"email": user.email, "otp": otp},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, User.CUSTOMER)
        self.assertIsNone(user.otp_code)


class UserManagementAuthorizationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="hotel-admin",
            email="admin@example.com",
            password="Admin-password-123!",
            role=User.ADMIN,
            is_active=True,
        )
        self.waiter = User.objects.create_user(
            username="waiter",
            email="waiter@example.com",
            password="Waiter-password-123!",
            role=User.WAITER,
            is_active=True,
        )
        self.list_url = reverse("user-list")

    def test_anonymous_user_cannot_list_users(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_admin_cannot_list_or_create_users(self):
        self.client.force_authenticate(self.waiter)

        list_response = self.client.get(self.list_url)
        create_response = self.client.post(
            self.list_url,
            {
                "username": "created-by-waiter",
                "email": "created@example.com",
                "password": "Created-password-123!",
                "role": User.ADMIN,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username="created-by-waiter").exists())

    def test_non_admin_cannot_promote_themselves(self):
        self.client.force_authenticate(self.waiter)
        response = self.client.patch(
            reverse("user-detail", args=[self.waiter.pk]),
            {"role": User.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.waiter.refresh_from_db()
        self.assertEqual(self.waiter.role, User.WAITER)

    def test_admin_can_create_active_staff_with_hashed_password(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url,
            {
                "username": "cashier",
                "email": "cashier@example.com",
                "password": "Cashier-password-123!",
                "role": User.CASHIER,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cashier = User.objects.get(username="cashier")
        self.assertEqual(cashier.role, User.CASHIER)
        self.assertTrue(cashier.is_active)
        self.assertTrue(cashier.check_password("Cashier-password-123!"))
        self.assertNotEqual(cashier.password, "Cashier-password-123!")

    def test_admin_password_update_is_hashed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("user-detail", args=[self.waiter.pk]),
            {"password": "Updated-password-123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.waiter.refresh_from_db()
        self.assertTrue(self.waiter.check_password("Updated-password-123!"))
        self.assertNotEqual(self.waiter.password, "Updated-password-123!")

