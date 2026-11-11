# Generated for Phase 4: PMS Night Audit Date Rollover Engine

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0047_rfq_and_supplier_quotation_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='current_business_date',
            field=models.DateField(
                default=django.utils.timezone.now,
                help_text='Active PMS business date for operations. Advanced by Night Audit.',
            ),
        ),
    ]

