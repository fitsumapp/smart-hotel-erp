import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hotel.models import (
    StockLocation, InventoryCategory, InventoryItem, StockBatch,
    BatchLocationBalance, ItemLocationBalance, StockTransaction,
    Room, Reservation, MinibarItem, JournalEntry
)
from apps.finance.services import ensure_default_accounts

User = get_user_model()


class MinibarAndStockControlPhase4TestCase(TestCase):
    """
    Validates Phase 4 requirements:
    1. Minibar Replenishment workflow links to StockTransaction(issuance, destination_dept=Housekeeping, destination_room=room_number).
    2. Minibar Consumption updates current_quantity, folio charge, and GL Dr 5000 / Cr 1300 JV.
    3. FEFO batch allocation priority for perishable stock with active expiry date.
    4. Expiry surveillance correctly identifies near-expiry stock batches.
    """

    def setUp(self):
        self.client = APIClient()
        ensure_default_accounts()

        # Users
        self.housekeeper = User.objects.create_user(
            username="housekeeper_jane",
            password="password123",
            role="housekeeping",
            is_active=True,
        )
        self.manager = User.objects.create_user(
            username="inventory_lead",
            password="password123",
            role="admin",
            is_active=True,
        )

        # Locations
        self.pantry, _ = StockLocation.objects.get_or_create(
            code="MINIBAR-PANTRY", defaults={"name": "Minibar Pantry", "is_active": True}
        )
        self.store, _ = StockLocation.objects.get_or_create(
            code="STORE-MAIN", defaults={"name": "Main Store", "is_active": True}
        )

        # Categories & Items
        self.fnb_cat = InventoryCategory.objects.create(name="F&B Pantry", category_type="f_and_b")
        self.water = InventoryItem.objects.create(
            name="Ambo Sparkling Water 500ml",
            item_code="BEV-AMBO-500",
            category=self.fnb_cat,
            unit="bottle",
            unit_cost=Decimal("25.00"),
            selling_price=Decimal("60.00"),
            current_stock=Decimal("100.00"),
            is_perishable=True,
        )

        # Balances
        ItemLocationBalance.objects.create(item=self.water, location=self.pantry, quantity=Decimal("40.00"))
        ItemLocationBalance.objects.create(item=self.water, location=self.store, quantity=Decimal("60.00"))

        today = datetime.date.today()
        self.batch1 = StockBatch.objects.create(
            batch_number="BAT-AMBO-EXP-EARLY",
            item=self.water,
            initial_quantity=Decimal("40.00"),
            current_quantity=Decimal("40.00"),
            unit_cost=Decimal("25.00"),
            expiry_date=today + datetime.timedelta(days=10),
            received_date=today - datetime.timedelta(days=5),
            status="active",
        )
        BatchLocationBalance.objects.create(batch=self.batch1, location=self.pantry, quantity=Decimal("40.00"))

        # Room & Reservation
        self.room = Room.objects.create(
            name="Executive Suite 302",
            room_number="302",
            room_type="Suite",
            base_price=Decimal("1200.00"),
            status="Occupied",
        )
        self.reservation = Reservation.objects.create(
            guest_name="Solomon Haile",
            guest_phone="+251911223344",
            guest_email="solomon@example.com",
            room=self.room,
            check_in_date=today,
            check_out_date=today + datetime.timedelta(days=3),
            status="checked_in",
            total_amount=Decimal("3600.00"),
        )

    def test_01_minibar_replenishment_creates_issuance_stock_transaction(self):
        """Minibar replenishment creates StockTransaction(issuance, destination_dept=Housekeeping, destination_room=room_number)."""
        self.client.force_authenticate(user=self.housekeeper)
        url = reverse("minibar-replenish")
        payload = {
            "room_id": self.room.id,
            "items": [{"item_id": self.water.id, "quantity": 4}],
            "notes": "Routine morning room prep",
        }

        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["room_number"], "302")

        # Verify MinibarItem created/updated
        mb_item = MinibarItem.objects.get(room=self.room, item=self.water)
        self.assertEqual(mb_item.current_quantity, 4)
        self.assertEqual(mb_item.standard_quantity, 4)
        self.assertIsNotNone(mb_item.last_restocked_at)

        # Verify StockTransaction logged
        stx = StockTransaction.objects.filter(
            item=self.water,
            transaction_type="issuance",
            destination_dept="Housekeeping",
            destination_room="Room 302",
        ).latest("id")
        self.assertEqual(stx.quantity, Decimal("4.00"))
        self.assertIn("Minibar replenishment Room 302", stx.notes)

        # Stock deducted from pantry
        self.water.refresh_from_db()
        self.assertEqual(self.water.current_stock, Decimal("96.00"))

    def test_02_minibar_consumption_updates_folio_and_gl_entry(self):
        """Minibar consumption updates current_quantity, folio charge, and posts GL JV."""
        # First set minibar stock to 4
        MinibarItem.objects.create(
            room=self.room,
            item=self.water,
            standard_quantity=4,
            current_quantity=4,
            price=Decimal("60.00"),
        )

        self.client.force_authenticate(user=self.housekeeper)
        url = reverse("minibar-consume")
        payload = {
            "room_id": self.room.id,
            "items": [{"item_id": self.water.id, "quantity": 2, "price": "60.00"}],
            "notes": "Guest consumed 2 bottles",
        }

        res = self.client.post(url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify MinibarItem quantity reduced
        mb_item = MinibarItem.objects.get(room=self.room, item=self.water)
        self.assertEqual(mb_item.current_quantity, 2)

        # Verify guest folio charge created
        folio_charge = self.reservation.folio_charges.latest("id")
        self.assertEqual(folio_charge.amount, Decimal("120.00"))  # 2 * 60
        self.assertIn("Ambo Sparkling Water", folio_charge.description)

        # Verify GL journal entry posted
        jv = JournalEntry.objects.filter(description__icontains="Auto JV: Minibar Issuance").latest("id")
        gl_lines = {line.account.code: (line.amount_debit, line.amount_credit) for line in jv.items.all()}
        self.assertEqual(gl_lines["5000"], (Decimal("50.00"), Decimal("0.00")))  # 2 * 25 cost
        self.assertEqual(gl_lines["1300"], (Decimal("0.00"), Decimal("50.00")))

    def test_03_fefo_perishable_allocation_picks_earliest_expiry_batch(self):
        """FEFO allocation automatically selects the earliest expiring batch first for perishables."""
        from hotel.integrity import record_stock_change
        today = datetime.date.today()

        # Create later expiry batch
        batch2 = StockBatch.objects.create(
            batch_number="BAT-AMBO-EXP-LATER",
            item=self.water,
            initial_quantity=Decimal("30.00"),
            current_quantity=Decimal("30.00"),
            unit_cost=Decimal("28.00"),
            expiry_date=today + datetime.timedelta(days=45),
            received_date=today - datetime.timedelta(days=10),  # Received earlier, but expires LATER
            status="active",
        )
        BatchLocationBalance.objects.create(batch=batch2, location=self.pantry, quantity=Decimal("30.00"))

        # Issue 15 bottles from pantry
        item, stx = record_stock_change(
            item_id=self.water.id,
            transaction_type="issuance",
            quantity=Decimal("15.00"),
            unit_cost=self.water.unit_cost,
            location=self.pantry,
            destination_dept="Housekeeping",
            destination_room="Room 302",
        )

        # Under FEFO, batch1 must be deducted first because expiry is in 10 days vs 45 days
        self.batch1.refresh_from_db()
        batch2.refresh_from_db()
        self.assertEqual(self.batch1.current_quantity, Decimal("25.00"))  # 40 - 15
        self.assertEqual(batch2.current_quantity, Decimal("30.00"))  # Unchanged
