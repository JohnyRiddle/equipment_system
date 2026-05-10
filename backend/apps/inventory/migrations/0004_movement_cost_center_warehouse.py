# Generated manually for model stabilization.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_initial'),
        ('organizations', '0002_initial'),
        ('warehouses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipmentmovement',
            name='from_cost_center',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outgoing_equipment_movements', to='organizations.costcenter'),
        ),
        migrations.AddField(
            model_name='equipmentmovement',
            name='to_cost_center',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incoming_equipment_movements', to='organizations.costcenter'),
        ),
        migrations.AddField(
            model_name='equipmentmovement',
            name='from_warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outgoing_equipment_movements', to='warehouses.warehouse'),
        ),
        migrations.AddField(
            model_name='equipmentmovement',
            name='to_warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incoming_equipment_movements', to='warehouses.warehouse'),
        ),
    ]
