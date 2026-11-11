from django.db import migrations
from django.utils import timezone


def seed_locations_and_legacy_batches(apps, schema_editor):
    InventoryItem = apps.get_model("hotel", "InventoryItem")
    StockLocation = apps.get_model("hotel", "StockLocation")
    StockBatch = apps.get_model("hotel", "StockBatch")
    BatchLocationBalance = apps.get_model("hotel", "BatchLocationBalance")
    ItemLocationBalance = apps.get_model("hotel", "ItemLocationBalance")
    Account = apps.get_model("hotel", "Account")

    # 1. Seed Default General Ledger Accounts if missing
    new_accounts = [
        ("2010", "Goods Received Not Invoiced (GRNI)", "liability"),
        ("5010", "Inventory Spoilage & Waste Expense", "expense"),
        ("5020", "Inventory Stocktake Variance Expense", "expense"),
        ("5030", "Department Operating Supplies Expense", "expense"),
    ]
    for code, name, acct_type in new_accounts:
        Account.objects.get_or_create(code=code, defaults={"name": name, "account_type": acct_type})

    # 2. Seed Default Stock Locations (Decision 1: MAIN_STORE is primary)
    main_store, _ = StockLocation.objects.get_or_create(
        code="STORE-MAIN",
        defaults={
            "name": "Main Central Store",
            "location_type": "warehouse",
            "is_active": True,
        },
    )
    StockLocation.objects.get_or_create(
        code="KITCHEN-MAIN",
        defaults={
            "name": "Main Kitchen Pantry",
            "location_type": "kitchen",
            "is_active": True,
        },
    )
    StockLocation.objects.get_or_create(
        code="BAR-MAIN",
        defaults={
            "name": "Main Bar Station",
            "location_type": "bar",
            "is_active": True,
        },
    )
    StockLocation.objects.get_or_create(
        code="MINIBAR-PANTRY",
        defaults={
            "name": "Housekeeping Minibar Pantry",
            "location_type": "minibar",
            "is_active": True,
        },
    )

    # 3. Seed Legacy Batches exclusively into MAIN_STORE for positive stock
    positive_items = InventoryItem.objects.filter(current_stock__gt=0)
    for item in positive_items:
        # Decision 2: Perishable legacy items are placed into unverified_quarantine
        # Non-perishable legacy items are placed into active
        initial_status = "unverified_quarantine" if getattr(item, "is_perishable", False) else "active"
        batch_num = f"LEGACY-INITIAL-{item.item_code}"

        batch, created = StockBatch.objects.get_or_create(
            item=item,
            batch_number=batch_num,
            defaults={
                "supplier_batch_number": None,
                "supplier": item.last_supplier,
                "initial_quantity": item.current_stock,
                "current_quantity": item.current_stock,
                "unit_cost": item.unit_cost,
                "received_date": timezone.now().date(),
                "expiry_date": None,  # Strictly None: no synthetic expiry dates
                "is_legacy": True,
                "status": initial_status,
                "verification_notes": "Initial legacy migration from single-pool stock model."
                if initial_status == "active"
                else "Unverified perishable legacy stock. Mandatory physical inspection required.",
            },
        )

        # 4. Location Balances for MAIN_STORE
        BatchLocationBalance.objects.get_or_create(
            batch=batch,
            location=main_store,
            defaults={"quantity": item.current_stock},
        )
        ItemLocationBalance.objects.get_or_create(
            item=item,
            location=main_store,
            defaults={"quantity": item.current_stock},
        )

    # 5. Post-Migration Mathematical Reconciliation
    total_item_stock = sum(it.current_stock for it in positive_items)
    total_batch_stock = sum(b.current_quantity for b in StockBatch.objects.filter(is_legacy=True))
    total_blb_stock = sum(blb.quantity for blb in BatchLocationBalance.objects.filter(location=main_store))
    total_ilb_stock = sum(ilb.quantity for ilb in ItemLocationBalance.objects.filter(location=main_store))

    if total_item_stock != total_batch_stock:
        raise ValueError(
            f"Migration Reconciliation Error: Aggregate stock ({total_item_stock}) does not match legacy batch stock ({total_batch_stock})."
        )
    if total_item_stock != total_blb_stock:
        raise ValueError(
            f"Migration Reconciliation Error: Aggregate stock ({total_item_stock}) does not match BatchLocationBalance ({total_blb_stock})."
        )
    if total_item_stock != total_ilb_stock:
        raise ValueError(
            f"Migration Reconciliation Error: Aggregate stock ({total_item_stock}) does not match ItemLocationBalance ({total_ilb_stock})."
        )


def reverse_locations_and_legacy_batches(apps, schema_editor):
    StockBatch = apps.get_model("hotel", "StockBatch")
    BatchLocationBalance = apps.get_model("hotel", "BatchLocationBalance")
    ItemLocationBalance = apps.get_model("hotel", "ItemLocationBalance")
    StockLocation = apps.get_model("hotel", "StockLocation")

    BatchLocationBalance.objects.filter(batch__is_legacy=True).delete()
    ItemLocationBalance.objects.all().delete()
    StockBatch.objects.filter(is_legacy=True).delete()
    StockLocation.objects.filter(code__in=["STORE-MAIN", "KITCHEN-MAIN", "BAR-MAIN", "MINIBAR-PANTRY"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0042_stock_batch_and_locations"),
    ]

    operations = [
        migrations.RunPython(seed_locations_and_legacy_batches, reverse_locations_and_legacy_batches),
    ]

