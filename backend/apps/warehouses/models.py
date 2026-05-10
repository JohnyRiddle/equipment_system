import uuid
from django.db import models


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cost_center = models.ForeignKey(
        'organizations.CostCenter',
        on_delete=models.CASCADE,
        related_name='warehouses'
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склады'
        unique_together = ('cost_center', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.cost_center.name}'