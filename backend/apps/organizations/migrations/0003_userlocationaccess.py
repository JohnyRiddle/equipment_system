# Generated manually for model stabilization.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
        ('organizations', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLocationAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_level', models.CharField(choices=[('view', 'View'), ('edit', 'Edit'), ('admin', 'Admin')], default='view', max_length=20)),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_accesses', to='locations.location')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='location_accesses', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='userlocationaccess',
            unique_together={('user', 'location')},
        ),
    ]
