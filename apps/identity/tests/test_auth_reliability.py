"""Backend authentication reliability, token rotation, and network security tests."""
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.services import get_tokens_for_user

User = get_user_model()


class AuthReliabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "ReliablePassword123!"
        self.user = User.objects.create_user(
            username="reliable_waiter",
            email="waiter@hotel.com",
            password=self.password,
            role=User.WAITER,
            is_active=True,
        )

    def test_login_success_returns_tokens_and_user_profile(self):
        url = reverse("login")
        response = self.client.post(url, {"username": self.user.email, "password": self.password}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertEqual(response.data["user"]["role"], User.WAITER)

    def test_login_invalid_credentials_returns_401(self):
        url = reverse("login")
        response = self.client.post(url, {"username": self.user.email, "password": "WrongPassword!"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Invalid credentials or account unavailable.")

    def test_token_refresh_lifecycle_and_rotation(self):
        tokens = get_tokens_for_user(self.user)
        old_refresh = tokens["refresh"]

        refresh_url = reverse("token-refresh")
        response = self.client.post(refresh_url, {"refresh": old_refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        new_refresh = response.data["refresh"]
        self.assertNotEqual(old_refresh, new_refresh)

        # Because ROTATE_REFRESH_TOKENS and BLACKLIST_AFTER_ROTATION are True,
        # old_refresh is now blacklisted and must be rejected with 401
        retry_response = self.client.post(refresh_url, {"refresh": old_refresh}, format="json")
        self.assertEqual(retry_response.status_code, 401)
        err_payload = retry_response.data.get("error", {})
        code = err_payload.get("code") if isinstance(err_payload, dict) else retry_response.data.get("code")
        self.assertEqual(code, "token_not_valid")

        # The new rotated refresh token must succeed
        new_response = self.client.post(refresh_url, {"refresh": new_refresh}, format="json")
        self.assertEqual(new_response.status_code, 200)

    def test_revoked_session_version_rejects_refresh(self):
        tokens = get_tokens_for_user(self.user)
        refresh_token = tokens["refresh"]

        # Increment token_version on user model (simulating password change or remote logout)
        self.user.token_version += 1
        self.user.save(update_fields=["token_version"])

        refresh_url = reverse("token-refresh")
        response = self.client.post(refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Session has been revoked", str(response.data))

    def test_development_cors_and_allowed_hosts_configuration(self):
        # Verify that development settings permit RFC 1918 private LAN ranges
        cors_patterns = getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", [])
        combined_regex = "|".join(f"(?:{p})" for p in cors_patterns)

        # Localhost and LAN IPs on development port 3000 must match CORS regex
        self.assertTrue(re.match(combined_regex, "http://localhost:3000"))
        self.assertTrue(re.match(combined_regex, "http://127.0.0.1:3000"))
        self.assertTrue(re.match(combined_regex, "http://192.168.1.15:3000"))
        self.assertTrue(re.match(combined_regex, "http://10.0.0.42:3000"))
        self.assertTrue(re.match(combined_regex, "http://172.20.10.5:3000"))

        # In development, ALLOWED_HOSTS includes wildcard or local subnet
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        self.assertTrue("*" in allowed_hosts or "127.0.0.1" in allowed_hosts)
