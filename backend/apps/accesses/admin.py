from django.contrib import admin

from .models import AccessChangeLog, AccessGrant, AccessSecret, AccessSecretViewLog, AccessType, EquipmentAccess


@admin.register(AccessType)
class AccessTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(EquipmentAccess)
class EquipmentAccessAdmin(admin.ModelAdmin):
    list_display = ('title', 'access_type', 'equipment', 'legal_entity', 'location', 'host', 'username', 'is_active')
    list_filter = ('access_type', 'legal_entity', 'location', 'is_active')
    search_fields = ('title', 'host', 'url', 'username', 'equipment__name')
    readonly_fields = ('created_at', 'updated_at', 'last_secret_viewed_at')


@admin.register(AccessSecret)
class AccessSecretAdmin(admin.ModelAdmin):
    list_display = ('label', 'secret_type', 'access', 'is_active', 'created_at', 'updated_at')
    list_filter = ('secret_type', 'is_active')
    search_fields = ('label', 'access__title')
    readonly_fields = ('encrypted_value', 'created_at', 'updated_at', 'rotated_at')


@admin.register(AccessSecretViewLog)
class AccessSecretViewLogAdmin(admin.ModelAdmin):
    list_display = ('access', 'secret', 'user', 'result', 'viewed_at', 'ip_address')
    list_filter = ('result',)
    search_fields = ('access__title', 'secret__label', 'user__username', 'ip_address')
    readonly_fields = ('access', 'secret', 'user', 'viewed_at', 'ip_address', 'user_agent', 'result', 'reason')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AccessChangeLog)
class AccessChangeLogAdmin(admin.ModelAdmin):
    list_display = ('access', 'secret', 'user', 'action', 'created_at')
    list_filter = ('action',)
    search_fields = ('access__title', 'secret__label', 'user__username')
    readonly_fields = ('access', 'secret', 'user', 'action', 'created_at', 'metadata')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'access', 'level', 'is_active', 'expires_at', 'granted_by', 'created_at')
    list_filter = ('level', 'is_active')
    search_fields = ('user__username', 'access__title')
    readonly_fields = ('created_at',)
