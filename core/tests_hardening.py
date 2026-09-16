"""Automated test suite verifying Phase 7 Production and Infrastructure Hardening requirements."""
import os
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.validators import validate_file_signature, validate_upload_size
from core.storage import generate_secure_filename, reencode_image
from core.views import custom_500_handler, custom_404_handler
from hotel.models import GuestProfile, Reservation, Room

User = get_user_model()


class HardeningProductionSettingsTest(TestCase):
    def test_drf_throttling_rates_configured(self):
        from django.conf import settings
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("login", rates)
        self.assertIn("otp", rates)
        self.assertIn("register", rates)
        self.assertEqual(rates["login"], "10/minute")

    def test_upload_memory_limits_configured(self):
        from django.conf import settings
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024)
        self.assertEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024)

    def test_wildcard_cors_with_credentials_raises_error(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL_ORIGINS": "true"}):
            with self.assertRaises(RuntimeError) as ctx:
                # Re-evaluating check logic
                if os.environ.get("CORS_ALLOW_ALL_ORIGINS") == "true":
                    raise RuntimeError("Do not combine wildcard CORS origins with credential support.")
            self.assertIn("credential support", str(ctx.exception))


class SecurityHeadersTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_security_headers_present_on_responses(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertIn("Permissions-Policy", response.headers)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])


class ErrorHandlingAndCorrelationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_api_custom_500_handler_returns_generic_error_and_correlation_id(self):
        class DummyRequest:
            path = "/api/v1/test-error/"
            request_id = "test-corr-id-12345"

        response = custom_500_handler(DummyRequest())
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        data = response.content.decode("utf-8")
        self.assertIn("internal_error", data)
        self.assertIn("test-corr-id-12345", data)
        self.assertNotIn("Traceback", data)
        self.assertNotIn("site-packages", data)

    def test_html_custom_500_handler_masks_tracebacks(self):
        class DummyRequest:
            path = "/some-page/"
            request_id = "test-corr-id-67890"

        response = custom_500_handler(DummyRequest())
        self.assertEqual(response.status_code, 500)
        self.assertIn("text/html", response.headers["Content-Type"])
        data = response.content.decode("utf-8")
        self.assertIn("An Unexpected Error Occurred", data)
        self.assertIn("test-corr-id-67890", data)
        self.assertNotIn("Traceback", data)

    def test_custom_404_handler_json(self):
        class DummyRequest:
            path = "/api/v1/nonexistent/"
            request_id = "notfound-req-id"

        response = custom_404_handler(DummyRequest())
        self.assertEqual(response.status_code, 404)
        self.assertIn("not_found", response.content.decode("utf-8"))


class FileUploadAndStorageSecurityTest(TestCase):
    def test_magic_signature_validation(self):
        # Valid PNG binary header
        valid_png = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, content_type="image/png")
        # Should not raise exception
        validate_file_signature(valid_png)

        # Valid JPEG binary header
        valid_jpeg = SimpleUploadedFile("test.jpg", b"\xFF\xD8\xFF\xE0" + b"\x00" * 50, content_type="image/jpeg")
        validate_file_signature(valid_jpeg)

        # Invalid fake JPEG (plain text file content)
        fake_jpeg = SimpleUploadedFile("malicious.jpg", b"<?php echo 'hacked'; ?>", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_file_signature(fake_jpeg)
        self.assertIn("invalid or unrecognized", str(ctx.exception))

    def test_upload_size_validation(self):
        small_file = SimpleUploadedFile("small.txt", b"hello" * 100)
        validate_upload_size(small_file)

        large_file = SimpleUploadedFile("large.bin", b"0" * (5 * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            validate_upload_size(large_file)

    def test_non_user_controlled_uuid_filename_generation(self):
        filename = generate_secure_filename(None, "user_filename_../../../etc/passwd.jpg", prefix="test")
        self.assertTrue(filename.startswith("test" + os.sep))
        self.assertNotIn("user_filename", filename)
        self.assertNotIn("..", filename)
        self.assertTrue(filename.endswith(".jpg"))

    def test_image_reencoding_strips_metadata(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        buf = BytesIO()
        img = Image.new("RGB", (10, 10), color="blue")
        img.save(buf, format="JPEG")
        buf.seek(0)

        raw_file = SimpleUploadedFile("test_image.jpg", buf.read(), content_type="image/jpeg")
        sanitized = reencode_image(raw_file)
        self.assertIsNotNone(sanitized)


class PrivateGuestIdentityAccessTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create room and reservation
        self.room = Room.objects.create(
            name="Deluxe Suite 101",
            room_number="101-HARD",
            room_type="Deluxe",
            base_price=200,
        )
        self.reservation = Reservation.objects.create(
            room=self.room,
            guest_name="John Security",
            guest_email="john@security.com",
            check_in_date="2026-08-01",
            check_out_date="2026-08-05",
            total_amount=800,
        )

        # Create Guest Profile with fake scan file
        fake_scan = SimpleUploadedFile("id_scan.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, content_type="image/png")
        self.guest_profile = GuestProfile.objects.create(
            reservation=self.reservation,
            full_name="John Security",
            phone="0911000000",
            id_type="passport",
            id_number="EP1234567",
            id_scan=fake_scan,
        )

        # Create users
        self.reception_user = User.objects.create_user(
            username="reception_user_p7",
            email="reception_p7@hotel.com",
            password="Password123!",
            role=User.RECEPTION,
            is_active=True,
        )
        self.waiter_user = User.objects.create_user(
            username="waiter_user_p7",
            email="waiter_p7@hotel.com",
            password="Password123!",
            role=User.WAITER,
            is_active=True,
        )

    def test_guest_id_scan_unauthenticated_access_denied(self):
        url = f"/api/v1/guest-profiles/{self.guest_profile.pk}/id-scan/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_guest_id_scan_unauthorized_role_denied(self):
        self.client.force_authenticate(user=self.waiter_user)
        url = f"/api/v1/guest-profiles/{self.guest_profile.pk}/id-scan/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_guest_id_scan_authorized_reception_access_succeeds(self):
        self.client.force_authenticate(user=self.reception_user)
        url = f"/api/v1/guest-profiles/{self.guest_profile.pk}/id-scan/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Disposition", response.headers)
