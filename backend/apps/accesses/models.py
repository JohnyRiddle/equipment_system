import uuid

from django.core.exceptions import ValidationError
from django.db import models


class AccessType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class EquipmentAccess(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='accesses',
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.PROTECT,
        related_name='equipment_accesses',
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.PROTECT,
        related_name='equipment_accesses',
    )
    cost_center = models.ForeignKey(
        'organizations.CostCenter',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='equipment_accesses',
    )
    access_type = models.ForeignKey(
        AccessType,
        on_delete=models.PROTECT,
        related_name='equipment_accesses',
    )

    title = models.CharField(max_length=255)
    host = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    url = models.URLField(blank=True)
    username = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_secret_viewed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_equipment_accesses',
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_equipment_accesses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['legal_entity', 'location']),
            models.Index(fields=['equipment']),
            models.Index(fields=['access_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.equipment:
            if self.legal_entity_id and self.equipment.legal_entity_id != self.legal_entity_id:
                raise ValidationError({'legal_entity': 'Legal entity must match equipment.'})
            if self.location_id and self.equipment.location_id != self.location_id:
                raise ValidationError({'location': 'Location must match equipment.'})
            if self.cost_center_id and self.equipment.cost_center_id != self.cost_center_id:
                raise ValidationError({'cost_center': 'Cost center must match equipment.'})
        if self.cost_center_id:
            if self.legal_entity_id and self.cost_center.legal_entity_id != self.legal_entity_id:
                raise ValidationError({'cost_center': 'Cost center belongs to another legal entity.'})
            if self.location_id and self.cost_center.location_id != self.location_id:
                raise ValidationError({'cost_center': 'Cost center belongs to another location.'})


class AccessSecret(models.Model):
    SECRET_TYPE_CHOICES = [
        ('password', 'Password'),
        ('private_key', 'Private key'),
        ('token', 'Token'),
        ('recovery_code', 'Recovery code'),
        ('note', 'Secret note'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.ForeignKey(
        EquipmentAccess,
        on_delete=models.CASCADE,
        related_name='secrets',
    )
    secret_type = models.CharField(max_length=30, choices=SECRET_TYPE_CHOICES)
    label = models.CharField(max_length=255)
    encrypted_value = models.TextField()
    encryption_version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_access_secrets',
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_access_secrets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['secret_type', 'label']
        indexes = [
            models.Index(fields=['access', 'is_active']),
            models.Index(fields=['secret_type']),
        ]

    def __str__(self):
        return f'{self.get_secret_type_display()} - {self.label}'


class AccessSecretViewLog(models.Model):
    RESULT_CHOICES = [
        ('allowed', 'Allowed'),
        ('denied', 'Denied'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.ForeignKey(
        EquipmentAccess,
        on_delete=models.PROTECT,
        related_name='secret_view_logs',
    )
    secret = models.ForeignKey(
        AccessSecret,
        on_delete=models.PROTECT,
        related_name='view_logs',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_secret_view_logs',
    )
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['access', 'viewed_at']),
            models.Index(fields=['secret', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['result']),
        ]

    def __str__(self):
        return f'{self.secret} viewed by {self.user} ({self.result})'


class AccessChangeLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('archived', 'Archived'),
        ('secret_added', 'Secret added'),
        ('secret_rotated', 'Secret rotated'),
        ('secret_archived', 'Secret archived'),
        ('grant_added', 'Grant added'),
        ('grant_archived', 'Grant archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.ForeignKey(
        EquipmentAccess,
        on_delete=models.PROTECT,
        related_name='change_logs',
    )
    secret = models.ForeignKey(
        AccessSecret,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='change_logs',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_change_logs',
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['access', 'created_at']),
            models.Index(fields=['secret', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f'{self.access} - {self.action}'


class AccessGrant(models.Model):
    LEVEL_CHOICES = [
        ('view_meta', 'View metadata'),
        ('view_secret', 'View secrets'),
        ('edit', 'Edit'),
        ('admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='access_grants',
    )
    access = models.ForeignKey(
        EquipmentAccess,
        on_delete=models.CASCADE,
        related_name='grants',
    )
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES)
    granted_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_access_grants',
    )
    expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'access')
        ordering = ['user__username']
        indexes = [
            models.Index(fields=['access', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['level']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'{self.user} -> {self.access} ({self.level})'
