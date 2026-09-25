from django.core.management import call_command
from django.db import migrations


def create_shared_cache(apps, schema_editor):
    if "hotel_api_cache" not in schema_editor.connection.introspection.table_names():
        call_command(
            "createcachetable", "hotel_api_cache",
            database=schema_editor.connection.alias, verbosity=0,
        )


def remove_shared_cache(apps, schema_editor):
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {quote('hotel_api_cache')}")


class Migration(migrations.Migration):
    dependencies = [("hotel", "0029_alter_category_image_alter_guestprofile_id_scan_and_more")]
    operations = [migrations.RunPython(create_shared_cache, remove_shared_cache)]
