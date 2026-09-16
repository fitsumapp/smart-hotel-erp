import re
from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.identity.services import get_tokens_for_user, issue_activation_otp
from users.authentication import VersionedJWTAuthentication
from users.models import AuthenticationAttempt, SecurityAuditEvent, User


def code_from_last_email():
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    if not match:
        raise AssertionError("Verification code not present in test email")
    return match.group(1)


class OTPAndRegistrationCompletionTests(APITestCase):
    def register(self, email="secure@example.com"):
        return self.client.post(reverse("register"), {
            "username": email.split("@")[0], "email": email,
            "password": "Strong-Phase1-Password-123!", "role": "admin", "is_active": True,
        }, format="json")

    def test_registration_stores_only_hashed_expiring_otp(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="secure@example.com")
        self.assertIsNone(user.otp_code)
        self.assertTrue(check_password(code_from_last_email(), user.otp_hash))
        self.assertGreater(user.otp_expires_at, timezone.now())
        self.assertEqual(user.role, User.CUSTOMER)

    def test_expired_otp_is_rejected(self):
        self.register()
        user = User.objects.get(email="secure@example.com")
        code = code_from_last_email()
        User.objects.filter(pk=user.pk).update(otp_expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post(reverse("verify-otp"), {"email": user.email, "otp": code}, format="json")
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_otp_is_single_use(self):
        self.register()
        code = code_from_last_email()
        first = self.client.post(reverse("verify-otp"), {"email": "secure@example.com", "otp": code}, format="json")
        second = self.client.post(reverse("verify-otp"), {"email": "secure@example.com", "otp": code}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_email_identity_is_case_insensitively_unique(self):
        self.register("Case@Test.example")
        response = self.client.post(reverse("register"), {
            "username": "case-two", "email": "case@test.example",
            "password": "Strong-Phase1-Password-456!",
        }, format="json")
        self.assertEqual(response.status_code, 400)


class LoginMFAAndSessionCompletionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="phase1-user", email="phase1-user@example.com",
            password="Phase1-login-password-123!", role=User.WAITER, is_active=True,
        )

    def test_unknown_user_and_wrong_password_use_same_error(self):
        wrong = self.client.post(reverse("login"), {"username": self.user.email, "password": "wrong"}, format="json")
        unknown = self.client.post(reverse("login"), {"username": "missing@example.com", "password": "wrong"}, format="json")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.data, unknown.data)

    def test_repeated_failures_lock_identifier_and_ip(self):
        for _ in range(5):
            self.client.post(reverse("login"), {"username": self.user.email, "password": "wrong"}, format="json")
        response = self.client.post(reverse("login"), {"username": self.user.email, "password": "Phase1-login-password-123!"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(AuthenticationAttempt.objects.filter(locked_until__gt=timezone.now()).exists())

    def test_admin_login_requires_email_mfa_before_tokens(self):
        admin = User.objects.create_user(
            username="phase1-admin", email="phase1-admin@example.com",
            password="Phase1-admin-password-123!", role=User.ADMIN, is_active=True,
        )
        login = self.client.post(reverse("login"), {"username": admin.email, "password": "Phase1-admin-password-123!"}, format="json")
        self.assertEqual(login.status_code, 202)
        self.assertTrue(login.data["mfa_required"])
        self.assertNotIn("tokens", login.data)
        code = code_from_last_email()
        verify = self.client.post(reverse("verify-mfa"), {"email": admin.email, "code": code}, format="json")
        self.assertEqual(verify.status_code, 200)
        self.assertIn("access", verify.data["tokens"])

    def test_token_version_revokes_existing_access_token(self):
        token = get_tokens_for_user(self.user)["access"]
        User.objects.filter(pk=self.user.pk).update(token_version=self.user.token_version + 1)
        request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        with self.assertRaises(Exception):
            VersionedJWTAuthentication().authenticate(request)

    def test_refresh_rotation_blacklists_previous_refresh(self):
        refresh = get_tokens_for_user(self.user)["refresh"]
        first = self.client.post(reverse("token-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(first.status_code, 200)
        replay = self.client.post(reverse("token-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(replay.status_code, 401)


class CentralRoleMatrixTests(APITestCase):
    def setUp(self):
        self.waiter = User.objects.create_user(username="matrix-waiter", password="Strong-Matrix-123!", role=User.WAITER, is_active=True)
        self.reception = User.objects.create_user(username="matrix-reception", password="Strong-Matrix-123!", role=User.RECEPTION, is_active=True)
        self.inventory = User.objects.create_user(username="matrix-inventory", password="Strong-Matrix-123!", role=User.INVENTORY, is_active=True)
        self.finance = User.objects.create_user(username="matrix-finance", password="Strong-Matrix-123!", role=User.FINANCE, is_active=True)

    def test_waiter_cannot_access_guest_inventory_finance_or_room_admin_data(self):
        self.client.force_authenticate(self.waiter)
        for path in ["/api/users/reservations/", "/api/users/inventory-items/", "/api/users/finance/accounts/", "/api/users/rooms/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403, path)

    def test_domain_roles_can_access_their_own_domains(self):
        cases = [
            (self.reception, "/api/users/reservations/"),
            (self.inventory, "/api/users/inventory-items/"),
            (self.finance, "/api/users/finance/accounts/"),
        ]
        for user, path in cases:
            self.client.force_authenticate(user)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)


class SecurityAuditCompletionTests(TestCase):
    def test_security_audit_is_immutable(self):
        event = SecurityAuditEvent.objects.create(action="test")
        event.action = "changed"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
