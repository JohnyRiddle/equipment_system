import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [
        ('system_admin', 'System Admin'),
        ('company_admin', 'Company Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('auditor', 'Auditor'),
        ('technician', 'Technician'),
        ('service_engineer', 'Service Engineer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='staff')
    is_global_access = models.BooleanField(default=False)
    can_view_equipment = models.BooleanField(default=True)
    can_edit_equipment = models.BooleanField(default=True)
    can_view_movements = models.BooleanField(default=True)
    can_view_accesses = models.BooleanField(default=True)
    can_edit_accesses = models.BooleanField(default=True)
    can_reveal_access_secrets = models.BooleanField(default=True)
    can_export_data = models.BooleanField(default=True)
    can_view_admin_panel = models.BooleanField(default=True)
    can_manage_directories = models.BooleanField(default=True)
    can_manage_users = models.BooleanField(default=True)
    can_view_audit_log = models.BooleanField(default=True)

    def __str__(self):
        return self.username
