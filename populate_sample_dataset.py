"""
populate_sample_dataset.py
Safe, repeatable test-data script for Acrma Hotel ERP.
Strictly scoped to development/test environment.
"""
import os
import sys
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.conf import settings
from django.utils import timezone
from users.models import User
from hotel.models import (
    SystemSettings, Room, Reservation, FolioCharge, HousekeepingTask,
    RestaurantTable, Category, MenuItem,
    InventoryCategory, Supplier, InventoryItem, RecipeBOM, StockTransaction,
    Order, OrderItem, Account, JournalEntry, JournalEntryItem
)
from apps.finance.services import ensure_default_accounts
from apps.orders.services import sync_order_financials
from hotel.accounting import post_entry


def run():
    print("[1/10] Verifying environment safety...")
    if getattr(settings, "IS_PRODUCTION", False) or os.getenv("DJANGO_ENV") == "production":
        print("ERROR: Safety gate blocked! Cannot run in production environment.")
        sys.exit(1)
    
    print("[2/10] Seeding SystemSettings...")
    settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
    settings_obj.hotel_name = "Acrma Grand Hotel & Suites"
    settings_obj.tin_number = "0012345678"
    settings_obj.address = "Bole Sub-City, Addis Ababa, Ethiopia"
    settings_obj.phone_number = "+251911000000"
    settings_obj.currency_symbol = "ETB"
    settings_obj.vat_enabled = True
    settings_obj.vat_percentage = Decimal("15.00")
    settings_obj.service_charge_enabled = True
    settings_obj.service_charge_percentage = Decimal("10.00")
    settings_obj.module_rooms = True
    settings_obj.module_pos = True
    settings_obj.module_inventory = True
    settings_obj.module_finance = True
    settings_obj.save()

    print("[3/10] Ensuring Chart of Accounts...")
    ensure_default_accounts()

    print("[4/10] Seeding Staff & Role Accounts...")
    roles_data = [
        ("admin", "admin@example.com", "admin", True, True),
        ("reacp", "reacp@gmail.com", "reception", False, True),
        ("waiter", "waiter@gmail.com", "waiter", False, True),
        ("cashier", "cashier@gmail.com", "cashier", False, True),
        ("kitchen", "kitchen@gmail.com", "kitchen", False, True),
        ("bar", "bar@gmail.com", "bar", False, True),
        ("inventory", "inventory@gmail.com", "inventory", False, True),
        ("finance", "finance@gmail.com", "finance", False, True),
        ("customer", "customer@gmail.com", "customer", False, True),
        ("delivery", "delivery@gmail.com", "delivery", False, True),
    ]
    for username, email, role, is_super, is_staff in roles_data:
        u = User.objects.filter(username=username).first()
        if not u:
            u = User(username=username, email=email, role=role)
        u.email = email
        u.role = role
        u.is_superuser = is_super
        u.is_staff = is_staff or is_super
        u.is_active = True
        u.is_verified = True
        u.set_password("123456789")
        u.save()

    print("[5/10] Seeding Hotel Rooms...")
    rooms_data = [
        {"room_number": "101", "name": "Deluxe King Suite 101", "room_type": "Deluxe", "floor_number": 1, "base_price": Decimal("3500.00"), "status": "available", "max_adults": 2, "max_children": 1, "bed_type": "King", "num_beds": 1, "amenities": "WiFi, Smart TV, Balcony, Minibar, Safe"},
        {"room_number": "102", "name": "Executive Ocean View 102", "room_type": "Executive Suite", "floor_number": 1, "base_price": Decimal("5500.00"), "status": "occupied", "max_adults": 3, "max_children": 2, "bed_type": "King + Sofa Bed", "num_beds": 2, "amenities": "WiFi, Smart TV, Jacuzzi, Ocean View, Espresso Machine"},
        {"room_number": "103", "name": "Twin Standard 103", "room_type": "Standard Twin", "floor_number": 1, "base_price": Decimal("2200.00"), "status": "dirty", "max_adults": 2, "max_children": 1, "bed_type": "Twin", "num_beds": 2, "amenities": "WiFi, TV, Desk"},
        {"room_number": "104", "name": "Presidential Grand 104", "room_type": "Presidential Suite", "floor_number": 2, "base_price": Decimal("12000.00"), "status": "maintenance", "max_adults": 4, "max_children": 2, "bed_type": "Super King", "num_beds": 2, "amenities": "Private Dining, Terrace, Butler, Whirlpool"},
        {"room_number": "105", "name": "Classic King 105", "room_type": "Standard King", "floor_number": 1, "base_price": Decimal("2500.00"), "status": "available", "max_adults": 2, "max_children": 0, "bed_type": "King", "num_beds": 1, "amenities": "WiFi, Work Desk, King Bed"},
    ]
    created_rooms = {}
    for r_data in rooms_data:
        r, _ = Room.objects.update_or_create(
            room_number=r_data["room_number"],
            defaults=r_data
        )
        created_rooms[r.room_number] = r

    print("[6/10] Seeding Fictional Reservations & Folio Charges...")
    now = timezone.now()
    today = now.date()
    
    # 1. Checked-in reservation for Room 102
    res_102, _ = Reservation.objects.update_or_create(
        confirmation_code="RES-102-OCC",
        defaults={
            "room": created_rooms["102"],
            "guest_name": "Dr. Abebe Bekele",
            "guest_email": "abebe.sample@example.com",
            "guest_phone": "+251911223344",
            "check_in_date": today - timedelta(days=1),
            "check_out_date": today + timedelta(days=2),
            "adults": 2,
            "children": 1,
            "status": "checked_in",
            "source": "front_desk",
            "payment_status": "partially_paid",
            "total_amount": Decimal("16500.00"),
            "deposit_amount": Decimal("5500.00"),
            "checked_in_at": now - timedelta(days=1),
            "notes": "VIP Guest - Late checkout requested."
        }
    )
    # Folio charges for Room 102
    FolioCharge.objects.get_or_create(
        reservation=res_102,
        description="Airport Transfer - VIP Sedan",
        defaults={"amount": Decimal("850.00"), "added_by": "reacp"}
    )
    FolioCharge.objects.get_or_create(
        reservation=res_102,
        description="Laundry Service - Express Wash",
        defaults={"amount": Decimal("420.00"), "added_by": "reacp"}
    )

    # 2. Upcoming Confirmed reservation for Room 105
    Reservation.objects.update_or_create(
        confirmation_code="RES-105-CONF",
        defaults={
            "room": created_rooms["105"],
            "guest_name": "Sarah Jenkins",
            "guest_email": "sarah.sample@example.com",
            "guest_phone": "+251922334455",
            "check_in_date": today + timedelta(days=1),
            "check_out_date": today + timedelta(days=3),
            "adults": 2,
            "children": 0,
            "status": "confirmed",
            "source": "online",
            "payment_status": "deposit_paid",
            "total_amount": Decimal("5000.00"),
            "deposit_amount": Decimal("2500.00"),
            "notes": "Honeymoon setup with welcome fruit basket."
        }
    )

    # 3. Past Checked-out reservation for Room 103
    Reservation.objects.update_or_create(
        confirmation_code="RES-103-OUT",
        defaults={
            "room": created_rooms["103"],
            "guest_name": "Marcus Aurelius",
            "guest_email": "marcus.sample@example.com",
            "guest_phone": "+251933445566",
            "check_in_date": today - timedelta(days=2),
            "check_out_date": today,
            "adults": 1,
            "children": 0,
            "status": "checked_out",
            "source": "front_desk",
            "payment_status": "paid",
            "total_amount": Decimal("4400.00"),
            "deposit_amount": Decimal("4400.00"),
            "checked_out_at": now - timedelta(hours=2),
            "notes": "Corporate rate applied."
        }
    )

    print("[7/10] Seeding Housekeeping Tasks...")
    HousekeepingTask.objects.update_or_create(
        room=created_rooms["103"],
        task_type="checkout_cleaning",
        defaults={
            "priority": "high",
            "status": "pending",
            "assigned_to_username": "reacp",
            "notes": "Guest checked out; deep clean and linen replenishment needed."
        }
    )
    HousekeepingTask.objects.update_or_create(
        room=created_rooms["102"],
        task_type="daily_cleaning",
        defaults={
            "priority": "medium",
            "status": "in_progress",
            "assigned_to_username": "reacp",
            "notes": "Daily refresh requested with extra towels."
        }
    )
    HousekeepingTask.objects.update_or_create(
        room=created_rooms["101"],
        task_type="routine_cleaning",
        defaults={
            "priority": "low",
            "status": "inspected",
            "assigned_to_username": "reacp",
            "inspected_by_username": "reacp",
            "inspected_at": now - timedelta(hours=3),
            "notes": "Ready for arrival inspection."
        }
    )

    print("[8/10] Seeding Restaurant Tables, Menus & BOM...")
    tables_data = [
        ("T1", "Terrace 1", 4, "occupied"),
        ("T2", "Terrace 2", 2, "available"),
        ("T3", "Main Dining 3", 6, "available"),
        ("T4", "VIP Lounge 4", 8, "available"),
    ]
    created_tables = {}
    for code, lbl, cap, st in tables_data:
        tbl, _ = RestaurantTable.objects.update_or_create(
            table_code=code,
            defaults={"label_name": lbl, "capacity": cap, "status": st}
        )
        created_tables[code] = tbl

    cat_kitchen, _ = Category.objects.get_or_create(name="Gourmet Kitchen", defaults={"station": "Kitchen", "description": "Hot culinary offerings"})
    cat_bar, _ = Category.objects.get_or_create(name="Artisan Beverages", defaults={"station": "Bar", "description": "Craft drinks, juices & coffee"})

    menu_items_data = [
        ("Prime Wagyu Beef Burger", Decimal("450.00"), cat_kitchen, "Wagyu patty with brioche bun and house dressing"),
        ("Artisan Club Sandwich", Decimal("320.00"), cat_kitchen, "Triple-decker smoked turkey and egg sandwich"),
        ("Freshly Squeezed Citrus Blend", Decimal("140.00"), cat_bar, "Fresh orange, lime and mint juice"),
        ("Specialty Ethiopian Sidama Latte", Decimal("90.00"), cat_bar, "Single origin espresso with steamed whole milk"),
    ]
    created_menu = {}
    for name, price, cat, desc in menu_items_data:
        m, _ = MenuItem.objects.update_or_create(
            name=name,
            defaults={"price": price, "category": cat, "description": desc, "is_available": True}
        )
        created_menu[name] = m

    print("[9/10] Seeding Inventory Items & Recipe BOM...")
    inv_cat_fb, _ = InventoryCategory.objects.get_or_create(name="Food Provisions", defaults={"category_type": "f_and_b"})
    inv_cat_bar, _ = InventoryCategory.objects.get_or_create(name="Bar Supplies", defaults={"category_type": "bar"})

    supplier_1, _ = Supplier.objects.get_or_create(name="Highland Agro Farms", defaults={"contact_person": "Ato Girma", "email": "sales@highlandagro.sample", "phone": "+251911334455"})
    supplier_2, _ = Supplier.objects.get_or_create(name="Great Rift Roasters", defaults={"contact_person": "W/ro Selam", "email": "orders@greatrift.sample", "phone": "+251922445566"})

    inv_items_data = [
        ("BEEF-WAGYU", "Ground Beef Grade A", inv_cat_fb, "kg", Decimal("25.000"), Decimal("320.00"), Decimal("5.000"), supplier_1),
        ("BREAD-BUNS", "Artisan Brioche Buns", inv_cat_fb, "pcs", Decimal("80.000"), Decimal("25.00"), Decimal("20.000"), supplier_1),
        ("FRUIT-ORANGE", "Fresh Citrus Oranges", inv_cat_bar, "kg", Decimal("40.000"), Decimal("95.00"), Decimal("10.000"), supplier_1),
        ("COFFEE-SIDAMA", "Sidama Single Origin Coffee", inv_cat_bar, "kg", Decimal("15.000"), Decimal("480.00"), Decimal("3.000"), supplier_2),
    ]
    created_ingredients = {}
    for code, name, cat, unit, stock, cost, min_lvl, sup in inv_items_data:
        inv, created = InventoryItem.objects.update_or_create(
            item_code=code,
            defaults={
                "name": name,
                "category": cat,
                "unit": unit,
                "current_stock": stock,
                "opening_stock": stock,
                "unit_cost": cost,
                "min_reorder_level": min_lvl,
                "last_supplier": sup,
            }
        )
        created_ingredients[code] = inv
        if created or not StockTransaction.objects.filter(item=inv, transaction_type="purchase").exists():
            StockTransaction.objects.create(
                item=inv,
                transaction_type="purchase",
                quantity=stock,
                unit_cost=cost,
                supplier=sup,
                reference_number=f"PO-{code}-INIT",
                notes="Initial sample inventory stock batch",
                destination_dept="Kitchen" if "BEEF" in code or "BREAD" in code else "Bar",
                logged_by_username="inventory"
            )

    # Recipe BOMs
    RecipeBOM.objects.update_or_create(
        menu_item=created_menu["Prime Wagyu Beef Burger"],
        ingredient=created_ingredients["BEEF-WAGYU"],
        defaults={"quantity_required": Decimal("0.250")}
    )
    RecipeBOM.objects.update_or_create(
        menu_item=created_menu["Prime Wagyu Beef Burger"],
        ingredient=created_ingredients["BREAD-BUNS"],
        defaults={"quantity_required": Decimal("1.000")}
    )
    RecipeBOM.objects.update_or_create(
        menu_item=created_menu["Freshly Squeezed Citrus Blend"],
        ingredient=created_ingredients["FRUIT-ORANGE"],
        defaults={"quantity_required": Decimal("0.400")}
    )
    RecipeBOM.objects.update_or_create(
        menu_item=created_menu["Specialty Ethiopian Sidama Latte"],
        ingredient=created_ingredients["COFFEE-SIDAMA"],
        defaults={"quantity_required": Decimal("0.020")}
    )

    print("[10/10] Seeding POS Orders & General Ledger Journals...")
    # 1. Active Order for Table 1 (Kitchen KDS testing)
    ord1, created = Order.objects.get_or_create(
        idempotency_key="SAMPLE-ORDER-T1-ACTIVE",
        defaults={
            "table": created_tables["T1"],
            "waiter_username": "waiter",
            "status": "preparing",
            "payment_status": "unpaid",
        }
    )
    if created:
        OrderItem.objects.create(order=ord1, menu_item=created_menu["Prime Wagyu Beef Burger"], quantity=2, price_at_order=Decimal("450.00"))
        OrderItem.objects.create(order=ord1, menu_item=created_menu["Freshly Squeezed Citrus Blend"], quantity=2, price_at_order=Decimal("140.00"))
        sync_order_financials(ord1)

    # 2. Historical Paid Cash Order
    ord2, created = Order.objects.get_or_create(
        idempotency_key="SAMPLE-ORDER-PAID-001",
        defaults={
            "table": created_tables["T2"],
            "waiter_username": "waiter",
            "status": "pending",
            "payment_status": "unpaid",
        }
    )
    if created:
        OrderItem.objects.create(order=ord2, menu_item=created_menu["Artisan Club Sandwich"], quantity=1, price_at_order=Decimal("320.00"))
        OrderItem.objects.create(order=ord2, menu_item=created_menu["Specialty Ethiopian Sidama Latte"], quantity=1, price_at_order=Decimal("90.00"))
        sync_order_financials(ord2)
        ord2.status = "paid"
        ord2.payment_status = "paid"
        ord2.payment_method = "Cash"
        ord2.payment_reference = "POS-CASH-SAMPLE-01"
        ord2.financials_finalized_at = now - timedelta(hours=1)
        ord2.save()

    # 3. Post Balanced General Ledger Opening Journal
    if not JournalEntry.objects.filter(description="Sample Hotel Opening Ledger").exists():
        post_entry(
            description="Sample Hotel Opening Ledger",
            lines=[
                {"account_code": "1000", "debit": Decimal("100000.00"), "credit": Decimal("0.00")},
                {"account_code": "1300", "debit": Decimal("25000.00"), "credit": Decimal("0.00")},
                {"account_code": "3000", "debit": Decimal("0.00"), "credit": Decimal("125000.00")},
            ],
            entry_date=today
        )

    print("\nSUCCESS: Realistic sample dataset created cleanly and safely!")


if __name__ == "__main__":
    run()
