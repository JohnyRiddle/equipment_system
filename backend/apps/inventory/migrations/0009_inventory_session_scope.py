from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_inventory_session_russian_statuses'),
        ('organizations', '0001_initial'),
        ('warehouses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorysession',
            name='cost_center',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_sessions',
                to='organizations.costcenter',
            ),
        ),
        migrations.AddField(
            model_name='inventorysession',
            name='warehouse',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_sessions',
                to='warehouses.warehouse',
            ),
        ),
    ]
