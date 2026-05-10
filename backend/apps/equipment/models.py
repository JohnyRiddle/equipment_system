import uuid

from django.db import models


class EquipmentCategory(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Название'
    )

    class Meta:
        verbose_name = 'Категория оборудования'
        verbose_name_plural = 'Категории оборудования'
        ordering = ['name']

    def __str__(self):
        return self.name


class EquipmentStatus(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name='Название'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Код'
    )

    class Meta:
        verbose_name = 'Статус оборудования'
        verbose_name_plural = 'Статусы оборудования'
        ordering = ['name']

    def __str__(self):
        return self.name


class Equipment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    legal_entity = models.ForeignKey(
        'organizations.LegalEntity',
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='Юридическое лицо'
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='Локация'
    )
    cost_center = models.ForeignKey(
        'organizations.CostCenter',
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='ЦФО'
    )
    warehouse = models.ForeignKey(
        'warehouses.Warehouse',
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='Склад'
    )

    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='Категория'
    )
    status = models.ForeignKey(
        EquipmentStatus,
        on_delete=models.PROTECT,
        related_name='equipment_items',
        verbose_name='Статус'
    )

    name = models.CharField(
        max_length=255,
        verbose_name='Наименование'
    )
    brand = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Бренд'
    )
    model = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Модель'
    )
    serial_number = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Серийный номер'
    )
    inventory_number = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Инвентарный номер'
    )

    purchase_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата покупки'
    )
    warranty_until = models.DateField(
        null=True,
        blank=True,
        verbose_name='Гарантия до'
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Стоимость'
    )
    estimated_current_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Оценочная текущая стоимость'
    )
    placement_zone = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Зона размещения'
    )
    last_inventory_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата последней инвентаризации'
    )
    last_repair_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата последнего ремонта'
    )

    responsible_user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_equipment',
        verbose_name='Ответственный'
    )

    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлено'
    )

    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['name']

    def __str__(self):
        return self.name


class EquipmentNote(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name='Оборудование'
    )
    text = models.TextField(
        verbose_name='Заметка'
    )
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_notes',
        verbose_name='Автор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )

    class Meta:
        verbose_name = 'Заметка оборудования'
        verbose_name_plural = 'Заметки оборудования'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.equipment}: {self.text[:40]}'


class EquipmentRequisite(models.Model):
    TYPE_IP = 'ip'
    TYPE_MAC = 'mac'
    TYPE_DOMAIN = 'domain'
    TYPE_HOSTNAME = 'hostname'
    TYPE_URL = 'url'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_IP, 'IP'),
        (TYPE_MAC, 'MAC'),
        (TYPE_DOMAIN, 'Домен'),
        (TYPE_HOSTNAME, 'Hostname'),
        (TYPE_URL, 'URL'),
        (TYPE_OTHER, 'Прочее'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='requisites',
        verbose_name='Оборудование'
    )
    requisite_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default=TYPE_IP,
        verbose_name='Тип'
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Название'
    )
    value = models.CharField(
        max_length=500,
        verbose_name='Значение'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_equipment_requisites',
        verbose_name='Создал'
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_equipment_requisites',
        verbose_name='Обновил'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлено'
    )

    class Meta:
        verbose_name = 'Реквизит оборудования'
        verbose_name_plural = 'Реквизиты оборудования'
        ordering = ['requisite_type', 'name', 'value']
        indexes = [
            models.Index(fields=['equipment', 'is_active']),
            models.Index(fields=['requisite_type']),
        ]

    def __str__(self):
        label = self.name or self.get_requisite_type_display()
        return f'{self.equipment}: {label} - {self.value}'


class EquipmentFile(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Оборудование'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название'
    )
    file = models.FileField(
        upload_to='equipment_files/',
        verbose_name='Файл'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_equipment_files',
        verbose_name='Загрузил'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Загружено'
    )

    class Meta:
        verbose_name = 'Файл оборудования'
        verbose_name_plural = 'Файлы оборудования'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['equipment', 'is_active']),
        ]

    def __str__(self):
        return f'{self.equipment}: {self.title}'


class EquipmentPhoto(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name='Оборудование'
    )
    image = models.ImageField(
        upload_to='equipment_photos/',
        verbose_name='Фото'
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Подпись'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Основное фото'
    )
    uploaded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_equipment_photos',
        verbose_name='Загрузил'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Загружено'
    )

    class Meta:
        verbose_name = 'Фото оборудования'
        verbose_name_plural = 'Фото оборудования'
        ordering = ['-is_primary', '-uploaded_at']
        indexes = [
            models.Index(fields=['equipment', 'is_active']),
            models.Index(fields=['equipment', 'is_primary']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            EquipmentPhoto.objects.filter(
                equipment=self.equipment,
                is_primary=True,
            ).exclude(pk=self.pk).update(is_primary=False)

    def __str__(self):
        return f'{self.equipment}: {self.caption or self.image.name}'
