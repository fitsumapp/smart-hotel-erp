from django.test import SimpleTestCase
from unittest.mock import patch
from rest_framework.exceptions import NotAuthenticated

from core.api import api_exception_handler


class SafeAPIErrorTests(SimpleTestCase):
    def test_drf_errors_use_consistent_envelope(self):
        response = api_exception_handler(NotAuthenticated("token detail"), {"view": None})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "not_authenticated")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

    def test_unhandled_exception_does_not_disclose_message(self):
        with patch("core.api.logger.exception"):
            response = api_exception_handler(
                RuntimeError("database password secret-value"), {"view": None}
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"]["code"], "internal_error")
        self.assertNotIn("secret-value", str(response.data))

    def test_field_validation_error_extracts_descriptive_message(self):
        from rest_framework.exceptions import ValidationError
        exc = ValidationError({"name": ["inventory category with this name already exists."]})
        response = api_exception_handler(exc, {"view": None})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid")
        self.assertEqual(response.data["error"]["message"], "Name: inventory category with this name already exists.")
        self.assertEqual(response.data["error"]["details"], {"name": ["inventory category with this name already exists."]})
