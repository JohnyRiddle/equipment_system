import uuid
from django.db import models


class LegalEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Юридическое лицо'
        verbose_name_plural = 'Юридические лица'
        ordering = ['name']

    def __str__(self):
        return self.name


class CostCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.CASCADE,
        related_name='cost_centers'
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.CASCADE,
        related_name='cost_centers'
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'ЦФО'
        verbose_name_plural = 'ЦФО'
        unique_together = ('legal_entity', 'location', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.location.name}'


class UserLegalEntityAccess(models.Model):
    ACCESS_LEVEL_CHOICES = [
        ('view', 'Просмотр'),
        ('edit', 'Редактирование'),
        ('admin', 'Администрирование'),
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='legal_entity_accesses')
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name='user_accesses')
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='view')
    allow_all_locations = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'legal_entity')

    def __str__(self):
        return f'{self.user} -> {self.legal_entity} ({self.access_level})'


class UserLocationAccess(models.Model):
    ACCESS_LEVEL_CHOICES = [
        ('view', 'Просмотр'),
        ('edit', 'Редактирование'),
        ('admin', 'Администрирование'),
    ]

    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='location_accesses')
    location = models.ForeignKey('locations.Location', on_delete=models.CASCADE, related_name='user_accesses')
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='view')

    class Meta:
        unique_together = ('user', 'location')

    def __str__(self):
        return f'{self.user} -> {self.location} ({self.access_level})'
