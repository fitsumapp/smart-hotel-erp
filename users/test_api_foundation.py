from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from hotel.models import Reservation, Room


class APIFoundationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-foundation", password="StrongPass123!", role="reception", is_active=True,
        )
        self.client.force_authenticate(self.user)
        self.room = Room.objects.create(
            name="API Room", room_number="API-1", room_type="Standard", base_price="100.00",
        )
        for index in range(3):
            Reservation.objects.create(
                room=self.room, guest_name=f"Guest {index}",
                check_in_date=f"2027-02-{index + 1:02d}", check_out_date=f"2027-02-{index + 2:02d}",
            )

    def test_legacy_route_keeps_list_shape(self):
        response = self.client.get("/api/users/reservations/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_v1_route_uses_bounded_pagination(self):
        response = self.client.get("/api/v1/reservations/?page_size=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)

    def test_v1_schema_endpoint_is_exposed(self):
        response = self.client.get("/api/v1/schema/")
        self.assertEqual(response.status_code, 200)
