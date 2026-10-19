from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class PublicSiteInfoEndpointTests(APITestCase):
    def test_public_site_endpoint_returns_ok_and_frontend_base_url(self):
        with override_settings(FRONTEND_BASE_URL="https://testhotel.example.com"):
            response = self.client.get(reverse("public-site-info"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, {"public_site_url": "https://testhotel.example.com"})

    def test_public_site_strips_trailing_slash(self):
        with override_settings(FRONTEND_BASE_URL="https://testhotel.example.com/"):
            response = self.client.get(reverse("public-site-info"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data.get("public_site_url"), "https://testhotel.example.com")

    def test_public_site_does_not_leak_internal_settings_or_secrets(self):
        response = self.client.get(reverse("public-site-info"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Strictly verify only allowed public metadata is present
        self.assertEqual(list(response.data.keys()), ["public_site_url"])
        self.assertNotIn("SECRET_KEY", response.data)
        self.assertNotIn("CHAPA_SECRET_KEY", response.data)
        self.assertNotIn("DATABASES", response.data)

    def test_public_site_allows_unauthenticated_access(self):
        self.client.logout()
        response = self.client.get("/api/users/public-site/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_public_site_allows_authenticated_access(self):
        user = User.objects.create_user(
            username="staff_member",
            password="StrongPassword123!",
            role=User.RECEPTION,
            is_active=True
        )
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/users/public-site/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("public_site_url", response.data)

    def test_accessible_via_both_api_users_and_users_fallback_prefixes(self):
        with override_settings(FRONTEND_BASE_URL="https://hotelerp.acrmatech.com"):
            resp1 = self.client.get("/api/users/public-site/")
            self.assertEqual(resp1.status_code, status.HTTP_200_OK)
            self.assertEqual(resp1.data["public_site_url"], "https://hotelerp.acrmatech.com")

            resp2 = self.client.get("/users/public-site/")
            self.assertEqual(resp2.status_code, status.HTTP_200_OK)
            self.assertEqual(resp2.data["public_site_url"], "https://hotelerp.acrmatech.com")
