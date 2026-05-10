import uuid
from django.db import models


class EquipmentMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='movements'
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='equipment_movements'
    )

    from_location = models.ForeignKey(
        'locations.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outgoing_movements'
    )
    to_location = models.ForeignKey(
        'locations.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_movements'
    )
    from_cost_center = models.ForeignKey(
        'organizations.CostCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outgoing_equipment_movements'
    )
    to_cost_center = models.ForeignKey(
        'organizations.CostCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_equipment_movements'
    )
    from_warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outgoing_equipment_movements'
    )
    to_warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_equipment_movements'
    )

    moved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_movements'
    )

    moved_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f'{self.equipment} | {self.from_location} -> {self.to_location}'


class MaintenanceLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='maintenance_logs'
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='maintenance_logs'
    )

    description = models.TextField()
    performed_at = models.DateTimeField()
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contractor = models.CharField(max_length=255, blank=True)
    next_service_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance_logs'
    )

    def __str__(self):
        return f'{self.equipment} - {self.performed_at}'


class EquipmentRepair(models.Model):
    STATUS_REQUESTED = 'requested'
    STATUS_ACCEPTED = 'accepted'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING_PARTS = 'waiting_parts'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Заявка создана'),
        (STATUS_ACCEPTED, 'Принято техником'),
        (STATUS_IN_PROGRESS, 'В работе'),
        (STATUS_WAITING_PARTS, 'Ожидает запчасти'),
        (STATUS_COMPLETED, 'Завершено'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Низкий'),
        (PRIORITY_NORMAL, 'Обычный'),
        (PRIORITY_HIGH, 'Высокий'),
        (PRIORITY_CRITICAL, 'Критический'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='repairs'
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='equipment_repairs'
    )

    repair_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    description = models.TextField()
    resolution = models.TextField(blank=True)
    status_comment = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contractor = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_equipment_repairs'
    )
    accepted_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_equipment_repairs'
    )
    assigned_to = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_equipment_repairs'
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-repair_date']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        equipment = self.equipment
        if self.status == self.STATUS_COMPLETED and (
            not equipment.last_repair_date or self.repair_date >= equipment.last_repair_date
        ):
            equipment.last_repair_date = self.repair_date
            equipment.save(update_fields=['last_repair_date', 'updated_at'])

    def __str__(self):
        return f'{self.equipment} - {self.repair_date}'


class EquipmentInventory(models.Model):
    CONDITION_OK = 'ok'
    CONDITION_NEEDS_REPAIR = 'needs_repair'
    CONDITION_BROKEN = 'broken'
    CONDITION_WRITTEN_OFF = 'written_off'

    CONDITION_CHOICES = [
        (CONDITION_OK, 'В рабочем состоянии'),
        (CONDITION_NEEDS_REPAIR, 'Требует ремонта'),
        (CONDITION_BROKEN, 'Не работает'),
        (CONDITION_WRITTEN_OFF, 'К списанию'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='inventory_checks'
    )
    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='equipment_inventory_checks'
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_inventory_checks'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_inventory_checks'
    )
    inventory_date = models.DateField()
    condition_status = models.CharField(max_length=30, choices=CONDITION_CHOICES, default=CONDITION_OK)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True)
    checked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_equipment_inventory_checks'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-inventory_date', '-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        equipment = self.equipment
        update_fields = ['last_inventory_date', 'updated_at']
        if not equipment.last_inventory_date or self.inventory_date >= equipment.last_inventory_date:
            equipment.last_inventory_date = self.inventory_date
            if self.estimated_value is not None:
                equipment.estimated_current_value = self.estimated_value
                update_fields.append('estimated_current_value')
            equipment.save(update_fields=update_fields)

    def __str__(self):
        return f'{self.equipment} - {self.inventory_date}'


class InventorySession(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.CASCADE,
        related_name='inventory_sessions'
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.CASCADE,
        related_name='inventory_sessions'
    )

    name = models.CharField(max_length=255)
    act_number = models.CharField(max_length=100, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_inventory_sessions'
    )
    confirmed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_inventory_sessions'
    )

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        InventorySession,
        on_delete=models.CASCADE,
        related_name='items'
    )
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='inventory_items'
    )

    found = models.BooleanField(default=True)
    scanned_tag = models.ForeignKey(
        'tags.EquipmentTag',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items'
    )
    actual_location = models.ForeignKey(
        'locations.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items'
    )
    actual_warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items'
    )
    condition_status = models.CharField(
        max_length=30,
        choices=EquipmentInventory.CONDITION_CHOICES,
        default=EquipmentInventory.CONDITION_OK
    )
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    comment = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    checked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_inventory_items'
    )

    class Meta:
        unique_together = ('session', 'equipment')

    def __str__(self):
        return f'{self.session} - {self.equipment}'
