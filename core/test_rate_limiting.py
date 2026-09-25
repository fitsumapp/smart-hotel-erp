from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import AnonRateThrottle


class SharedRateLimitTests(TestCase):
    def test_anonymous_throttle_blocks_after_configured_budget(self):
        request = APIRequestFactory().get("/rate-limit-check")
        request.user = AnonymousUser()
        throttle = AnonRateThrottle()

        decisions = [throttle.allow_request(request, None) for _ in range(101)]

        self.assertEqual(throttle.rate, "100/day")
        self.assertEqual(sum(decisions), 100)
        self.assertFalse(decisions[-1])
