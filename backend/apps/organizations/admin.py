from django.contrib import admin

from .models import CostCenter, LegalEntity, UserLegalEntityAccess, UserLocationAccess


@admin.register(LegalEntity)
class LegalEntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'tax_id', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'short_name', 'tax_id')


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'legal_entity', 'location', 'is_active')
    list_filter = ('legal_entity', 'location', 'is_active')
    search_fields = ('name',)


@admin.register(UserLegalEntityAccess)
class UserLegalEntityAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'legal_entity', 'access_level', 'allow_all_locations')
    list_filter = ('access_level', 'allow_all_locations')
    search_fields = ('user__username', 'legal_entity__name')


@admin.register(UserLocationAccess)
class UserLocationAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'access_level')
    list_filter = ('access_level',)
    search_fields = ('user__username', 'location__name')
