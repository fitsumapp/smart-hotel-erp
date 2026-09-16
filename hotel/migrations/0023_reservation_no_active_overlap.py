from django.db import migrations


CONSTRAINT = "reservation_no_active_room_overlap"


def add_postgres_overlap_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    Reservation = apps.get_model("hotel", "Reservation")
    table = schema_editor.quote_name(Reservation._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        cursor.execute(
            f"""
            SELECT a.id, b.id
            FROM {table} a
            JOIN {table} b
              ON a.room_id = b.room_id
             AND a.id < b.id
             AND a.status IN ('pending', 'confirmed', 'checked_in')
             AND b.status IN ('pending', 'confirmed', 'checked_in')
             AND daterange(a.check_in_date, a.check_out_date, '[)')
                 && daterange(b.check_in_date, b.check_out_date, '[)')
            LIMIT 1
            """
        )
        conflict = cursor.fetchone()
        if conflict:
            raise RuntimeError(
                "Cannot install reservation overlap protection: existing active "
                f"reservations {conflict[0]} and {conflict[1]} overlap. Resolve them first."
            )
        cursor.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {CONSTRAINT}
            EXCLUDE USING gist (
                room_id WITH =,
                daterange(check_in_date, check_out_date, '[)') WITH &&
            )
            WHERE (status IN ('pending', 'confirmed', 'checked_in'))
            """
        )


def remove_postgres_overlap_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    Reservation = apps.get_model("hotel", "Reservation")
    table = schema_editor.quote_name(Reservation._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {CONSTRAINT}")


class Migration(migrations.Migration):
    dependencies = [("hotel", "0022_order_financials_finalized_at_order_idempotency_key_and_more")]
    operations = [migrations.RunPython(add_postgres_overlap_constraint, remove_postgres_overlap_constraint)]
