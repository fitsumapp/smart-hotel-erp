from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove multi-tenant fields (is_platform_admin, tenant_schema) from the
    User model. The system is now a single-tenant hotel ERP.
    """

    dependencies = [
        ('users', '0002_alter_user_role'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='is_platform_admin',
        ),
        migrations.RemoveField(
            model_name='user',
            name='tenant_schema',
        ),
    ]
