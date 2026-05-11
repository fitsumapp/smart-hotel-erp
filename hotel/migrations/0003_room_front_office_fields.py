from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0002_systemsettings_enabled_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="advance_payment_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="room",
            name="booking_source",
            field=models.CharField(choices=[("front_desk", "Front Desk"), ("online", "Online")], default="front_desk", max_length=20),
        ),
        migrations.AddField(
            model_name="room",
            name="common_amenities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="room",
            name="is_available_online",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="room",
            name="online_deposit_type",
            field=models.CharField(choices=[("Fixed", "Fixed"), ("Percentage", "Percentage")], default="Fixed", max_length=20),
        ),
    ]
