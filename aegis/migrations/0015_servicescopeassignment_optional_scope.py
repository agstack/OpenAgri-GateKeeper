from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aegis', '0014_alter_servicerole_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicescopeassignment',
            name='scope_type',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=20,
                choices=[('farm', 'farm'), ('parcel', 'parcel')],
            ),
        ),
        migrations.AlterField(
            model_name='servicescopeassignment',
            name='scope_id',
            field=models.UUIDField(blank=True, null=True, db_index=True),
        ),
    ]
