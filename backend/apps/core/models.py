import uuid

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ActionLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_ARCHIVE = 'archive'
    ACTION_DELETE = 'delete'
    ACTION_MOVE = 'move'
    ACTION_REVEAL = 'reveal'
    ACTION_EXPORT = 'export'
    ACTION_LOGIN = 'login'
    ACTION_OTHER = 'other'

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Создание'),
        (ACTION_UPDATE, 'Изменение'),
        (ACTION_ARCHIVE, 'Архивирование'),
        (ACTION_DELETE, 'Удаление'),
        (ACTION_MOVE, 'Перемещение'),
        (ACTION_REVEAL, 'Раскрытие секрета'),
        (ACTION_EXPORT, 'Экспорт'),
        (ACTION_LOGIN, 'Вход'),
        (ACTION_OTHER, 'Другое'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='action_logs',
        verbose_name='Пользователь'
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        verbose_name='Действие'
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тип объекта'
    )
    object_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID объекта'
    )
    object_repr = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Объект'
    )
    message = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Метаданные'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP-адрес'
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User-Agent'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )

    class Meta:
        verbose_name = 'Журнал действия'
        verbose_name_plural = 'Журнал действий'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        actor = self.actor or 'system'
        target = self.object_repr or self.object_id or '-'
        return f'{self.created_at:%Y-%m-%d %H:%M} {actor}: {self.action} {target}'
