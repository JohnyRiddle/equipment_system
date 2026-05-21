from django.db import migrations, models


def forwards(apps, schema_editor):
    InventorySession = apps.get_model('inventory', 'InventorySession')
    InventorySession.objects.filter(status__in=['draft', 'in_progress']).update(status='active')
    InventorySession.objects.filter(status='completed').update(status='confirmed')


def backwards(apps, schema_editor):
    InventorySession = apps.get_model('inventory', 'InventorySession')
    InventorySession.objects.filter(status='active').update(status='in_progress')
    InventorySession.objects.filter(status='approval').update(status='in_progress')
    InventorySession.objects.filter(status='confirmed').update(status='completed')


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_alter_equipmentrepair_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventorysession',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Активная'),
                    ('approval', 'Проведение - согласование'),
                    ('confirmed', 'Подтверждено'),
                    ('cancelled', 'Отменена'),
                ],
                default='active',
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
