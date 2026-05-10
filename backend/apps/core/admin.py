from django.contrib import admin

from .models import ActionLog


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'object_repr', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('actor__username', 'object_repr', 'message', 'object_id')
    readonly_fields = (
        'id',
        'actor',
        'action',
        'content_type',
        'object_id',
        'object_repr',
        'message',
        'metadata',
        'ip_address',
        'user_agent',
        'created_at',
    )
