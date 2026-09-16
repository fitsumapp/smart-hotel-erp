import json
import logging
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient
from apps.audit.services import record_audit_event
from core.observability import JsonFormatter, request_context
from hotel.models import AuditEvent
from users.models import User

class Phase5ObservabilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="phase5admin", email="phase5@example.com", password="Strong-Test-Password-55!", role=User.ADMIN, is_active=True, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_health_correlation_and_admin_metrics(self):
        response = self.client.get("/health/live", HTTP_X_REQUEST_ID="phase5-trace-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], "phase5-trace-1")
        self.assertEqual(self.client.get("/health/ready").status_code, 200)
        metrics_response = self.client.get("/api/v1/ops/metrics/")
        self.assertEqual(metrics_response.status_code, 200)
        self.assertIn("http_requests_total", metrics_response.data["metrics"])

    def test_metrics_are_not_public(self):
        self.assertIn(APIClient().get("/api/v1/ops/metrics/").status_code, (401, 403))

    def test_critical_write_creates_searchable_actor_audit(self):
        response = self.client.post("/api/v1/rooms/", {"name": "Audit Room", "room_number": "P5-01", "room_type": "single", "base_price": "100.00", "capacity": 1, "status": "Available"}, format="json", HTTP_X_REQUEST_ID="booking-correlation-5")
        self.assertEqual(response.status_code, 201, response.data)
        event = AuditEvent.objects.get(entity_type="hotel.Room", entity_id=str(response.data["id"]))
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.request_id, "booking-correlation-5")
        search = self.client.get("/api/v1/audit-events/?request_id=booking-correlation-5")
        self.assertEqual(search.status_code, 200)
        results = search.data.get("results", search.data)
        self.assertEqual(len(results), 1)

    def test_audit_is_immutable_and_secrets_are_redacted(self):
        request = RequestFactory().post("/sensitive", REMOTE_ADDR="127.0.0.1")
        request.user, request.request_id = self.admin, "secret-redaction"
        token = request_context.set({"request": request, "request_id": request.request_id})
        try:
            event = record_audit_event(action="test.secret", entity_type="test.Entity", entity_id="1", after={"password": "never-log-me", "nested": {"otp_code": "123456"}})
        finally:
            request_context.reset(token)
        self.assertEqual(event.after_summary["password"], "[REDACTED]")
        self.assertEqual(event.after_summary["nested"]["otp_code"], "[REDACTED]")
        event.action = "tampered"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(action="tampered")
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_json_log_formatter_redacts_sensitive_event_values(self):
        record = logging.LogRecord("phase5", logging.INFO, __file__, 1, "event", (), None)
        record.event = {"token": "secret", "safe": "ok"}
        output = json.loads(JsonFormatter().format(record))
        self.assertEqual(output["event"]["token"], "[REDACTED]")
        self.assertEqual(output["event"]["safe"], "ok")
