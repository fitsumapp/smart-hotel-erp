"""
Regression and authorization test suite for DEFECT-ROLE-001.
Verifies complete Housekeeping role access, authentication, RBAC boundaries,
read-only room listing, minibar recording, lost & found vault, and denial of unauthorized roles.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    Room, Reservation, InventoryCategory, InventoryItem,
    HousekeepingTask, MinibarItem, LostAndFoundItem, FolioCharge
)
from users.models import User


class HousekeepingRoleAccessTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users across roles
        self.password = "Safe-Password-123!"
        self.housekeeping_user = User.objects.create_user(
            username="hk_staff_1",
            password=self.password,
            email="hk1@hotel.com",
            role=User.HOUSEKEEPING,
            is_active=True,
        )
        self.reception_user = User.objects.create_user(
            username="reception_staff_1",
            password=self.password,
            email="rec1@hotel.com",
            role=User.RECEPTION,
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username="hotel_admin_1",
            password=self.password,
            email="admin1@hotel.com",
            role=User.ADMIN,
            is_active=True,
        )
        self.waiter_user = User.objects.create_user(
            username="waiter_1",
            password=self.password,
            email="waiter1@hotel.com",
            role=User.WAITER,
            is_active=True,
        )
        self.kitchen_user = User.objects.create_user(
            username="kitchen_1",
            password=self.password,
            email="kitchen1@hotel.com",
            role=User.KITCHEN,
            is_active=True,
        )
        self.bar_user = User.objects.create_user(
            username="bar_1",
            password=self.password,
            email="bar1@hotel.com",
            role=User.BAR,
            is_active=True,
        )
        self.finance_user = User.objects.create_user(
            username="finance_1",
            password=self.password,
            email="finance1@hotel.com",
            role=User.FINANCE,
            is_active=True,
        )
        self.customer_user = User.objects.create_user(
            username="customer_1",
            password=self.password,
            email="customer1@hotel.com",
            role=User.CUSTOMER,
            is_active=True,
        )

        # Rooms & Reservation
        self.room_201 = Room.objects.create(
            room_number="201",
            name="Deluxe King 201",
            room_type="deluxe",
            base_price=Decimal("250.00"),
            status="Available",
        )
        self.room_202 = Room.objects.create(
            room_number="202",
            name="Standard Twin 202",
            room_type="standard",
            base_price=Decimal("150.00"),
            status="Occupied",
        )
        self.reservation_202 = Reservation.objects.create(
            guest_name="Abebe Kebede",
            guest_phone="+251911223344",
            room=self.room_202,
            check_in_date=timezone.now().date(),
            check_out_date=(timezone.now() + timezone.timedelta(days=2)).date(),
            total_amount=Decimal("300.00"),
            payment_status="paid",
            status="checked_in",
        )

        # Inventory Item for Minibar
        self.inv_category = InventoryCategory.objects.create(
            name="Minibar Beverages",
            category_type="f_and_b",
        )
        self.water = InventoryItem.objects.create(
            item_code="MINI-WTR-01",
            name="Spring Water 500ml",
            category=self.inv_category,
            current_stock=Decimal("50.00"),
            unit="pcs",
            unit_cost=Decimal("15.00"),
            selling_price=Decimal("40.00"),
        )
        self.minibar_record = MinibarItem.objects.create(
            room=self.room_202,
            item=self.water,
            standard_quantity=2,
            current_quantity=2,
            last_checked_by="admin",
        )

    def test_housekeeping_authentication_success(self):
        """DEFECT-ROLE-001: Housekeeping staff can authenticate and receive JWT tokens with their role."""
        res = self.client.post("/api/users/login/", {
            "username": self.housekeeping_user.username,
            "password": self.password,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", res.data)
        self.assertIn("access", res.data["tokens"])
        self.assertEqual(res.data["user"]["role"], "housekeeping")

    def test_housekeeping_can_list_and_create_tasks(self):
        """Housekeeping staff can list and create cleaning tasks."""
        self.client.force_authenticate(user=self.housekeeping_user)
        # 1. List tasks
        res_list = self.client.get("/api/users/housekeeping/tasks/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)

        # 2. Create task
        res_create = self.client.post("/api/users/housekeeping/tasks/", {
            "room": self.room_201.id,
            "task_type": "deep_cleaning",
            "priority": "high",
            "notes": "Pre-VIP arrival sanitization",
        }, format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.data["task_type"], "deep_cleaning")

        self.room_201.refresh_from_db()
        self.assertEqual(self.room_201.status, "Cleaning")

    def test_housekeeping_task_lifecycle_execution(self):
        """Housekeeping staff can start cleaning, complete checklists, and inspect."""
        task = HousekeepingTask.objects.create(
            room=self.room_201,
            task_type="checkout_cleaning",
            priority="normal",
            status="pending",
        )
        self.client.force_authenticate(user=self.housekeeping_user)

        # 1. Start cleaning -> in_progress
        res_prog = self.client.patch(f"/api/users/housekeeping/tasks/{task.id}/", {
            "status": "in_progress",
        }, format="json")
        self.assertEqual(res_prog.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")
        self.assertIsNotNone(task.started_at)

        # 2. Mark cleaned
        res_clean = self.client.patch(f"/api/users/housekeeping/tasks/{task.id}/", {
            "status": "cleaned",
        }, format="json")
        self.assertEqual(res_clean.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, "cleaned")

        # 3. Supervised inspection
        res_insp = self.client.post(f"/api/users/housekeeping/tasks/{task.id}/inspect/", {
            "approved": True,
            "notes": "Passed room inspection.",
        }, format="json")
        self.assertEqual(res_insp.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, "inspected")
        self.room_201.refresh_from_db()
        self.assertEqual(self.room_201.status, "Available")

    def test_housekeeping_can_read_rooms_but_cannot_modify(self):
        """Housekeeping staff has read-only access to rooms (GET) but cannot mutate room inventory."""
        self.client.force_authenticate(user=self.housekeeping_user)

        # 1. GET rooms list -> 200 OK
        res_get = self.client.get("/api/users/rooms/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        room_numbers = [r["room_number"] for r in res_get.data]
        self.assertIn("201", room_numbers)
        self.assertIn("202", room_numbers)

        # 2. POST create room -> 403 Forbidden
        res_post = self.client.post("/api/users/rooms/", {
            "room_number": "999",
            "name": "Unauthorized Suite",
            "room_type": "presidential",
            "base_price": "999.00",
        }, format="json")
        self.assertEqual(res_post.status_code, status.HTTP_403_FORBIDDEN)

        # 3. DELETE room -> 403 Forbidden
        res_del = self.client.delete(f"/api/users/rooms/{self.room_201.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_403_FORBIDDEN)

    def test_housekeeping_minibar_consumption_workflow(self):
        """Housekeeping staff can view minibar candidates and record guest consumption."""
        self.client.force_authenticate(user=self.housekeeping_user)

        # 1. View items and candidates
        res_items = self.client.get("/api/users/minibar/items/")
        self.assertEqual(res_items.status_code, status.HTTP_200_OK)
        res_cand = self.client.get("/api/users/minibar/candidates/")
        self.assertEqual(res_cand.status_code, status.HTTP_200_OK)

        # 2. Record consumption
        initial_stock = self.water.current_stock
        res_consume = self.client.post("/api/users/minibar/consume/", {
            "room_id": self.room_202.id,
            "items": [{"item_id": self.water.id, "quantity": 1}],
            "notes": "Routine minibar audit",
        }, format="json")
        self.assertEqual(res_consume.status_code, status.HTTP_200_OK)

        # Folio charge posted to active guest
        charge = FolioCharge.objects.filter(reservation=self.reservation_202).first()
        self.assertIsNotNone(charge)
        self.assertEqual(charge.amount, Decimal("40.00"))

        # Inventory deducted
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, initial_stock - Decimal("1.00"))

    def test_housekeeping_lost_and_found_workflow(self):
        """Housekeeping staff can record and claim lost and found items."""
        self.client.force_authenticate(user=self.housekeeping_user)

        # 1. Register found item
        res_post = self.client.post("/api/users/lost-and-found/", {
            "room": self.room_201.id,
            "item_name": "Leather Wallet",
            "category": "electronics_valuables",
            "found_location": "Under nightstand drawer",
        }, format="json")
        self.assertEqual(res_post.status_code, status.HTTP_201_CREATED)
        item_id = res_post.data["id"]

        # 2. Claim found item
        res_claim = self.client.post(f"/api/users/lost-and-found/{item_id}/claim/", {
            "claimed_by": "John Doe",
            "claimant_phone": "+251911000000",
            "notes": "Verified Ethiopian passport ID",
        }, format="json")
        self.assertEqual(res_claim.status_code, status.HTTP_200_OK)
        self.assertEqual(res_claim.data["status"], "claimed")

    def test_reception_and_admin_access_preserved(self):
        """Existing reception and admin roles continue to have full access to housekeeping operations."""
        for user in [self.reception_user, self.admin_user]:
            self.client.force_authenticate(user=user)
            res_tasks = self.client.get("/api/users/housekeeping/tasks/")
            self.assertEqual(res_tasks.status_code, status.HTTP_200_OK, f"Failed for {user.role}")
            res_minibar = self.client.get("/api/users/minibar/items/")
            self.assertEqual(res_minibar.status_code, status.HTTP_200_OK, f"Failed for {user.role}")
            res_lf = self.client.get("/api/users/lost-and-found/")
            self.assertEqual(res_lf.status_code, status.HTTP_200_OK, f"Failed for {user.role}")

    def test_unauthorized_operational_roles_denied_housekeeping_apis(self):
        """Waiter, Kitchen, Bar, Finance, and Customer roles are denied access to housekeeping APIs."""
        unauthorized_users = [
            self.waiter_user,
            self.kitchen_user,
            self.bar_user,
            self.finance_user,
            self.customer_user,
        ]
        for user in unauthorized_users:
            self.client.force_authenticate(user=user)
            # Tasks list
            res_tasks = self.client.get("/api/users/housekeeping/tasks/")
            self.assertEqual(res_tasks.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be denied")
            # Minibar
            res_mb = self.client.get("/api/users/minibar/items/")
            self.assertEqual(res_mb.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be denied")
            # Lost and found
            res_lf = self.client.get("/api/users/lost-and-found/")
            self.assertEqual(res_lf.status_code, status.HTTP_403_FORBIDDEN, f"Role {user.role} should be denied")

    def test_unauthenticated_requests_denied(self):
        """Unauthenticated requests to housekeeping endpoints return HTTP 401 Unauthorized."""
        self.client.logout()
        res_tasks = self.client.get("/api/users/housekeeping/tasks/")
        self.assertEqual(res_tasks.status_code, status.HTTP_401_UNAUTHORIZED)
        res_mb = self.client.get("/api/users/minibar/items/")
        self.assertEqual(res_mb.status_code, status.HTTP_401_UNAUTHORIZED)
        res_lf = self.client.get("/api/users/lost-and-found/")
        self.assertEqual(res_lf.status_code, status.HTTP_401_UNAUTHORIZED)
