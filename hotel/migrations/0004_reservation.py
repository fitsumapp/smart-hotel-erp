from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0003_room_front_office_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_name", models.CharField(max_length=200)),
                ("guest_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("guest_phone", models.CharField(blank=True, max_length=50, null=True)),
                ("check_in_date", models.DateField()),
                ("check_out_date", models.DateField()),
                ("adults", models.IntegerField(default=1)),
                ("children", models.IntegerField(default=0)),
                ("notes", models.TextField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("checked_in", "Checked In"), ("checked_out", "Checked Out"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("source", models.CharField(choices=[("public", "Public Booking Engine"), ("reception", "Reception")], default="public", max_length=20)),
                ("payment_status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")], default="pending", max_length=20)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("deposit_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("confirmation_code", models.CharField(blank=True, max_length=32, unique=True)),
                ("qr_token", models.CharField(blank=True, max_length=64, unique=True)),
                ("public_token", models.CharField(blank=True, max_length=64, unique=True)),
                ("chapa_tx_ref", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("chapa_checkout_url", models.URLField(blank=True, max_length=500, null=True)),
                ("payment_reference", models.CharField(blank=True, max_length=100, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("checked_in_at", models.DateTimeField(blank=True, null=True)),
                ("checked_out_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="hotel.room")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
