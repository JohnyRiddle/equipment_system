from django.contrib import admin

from .models import (
    Equipment,
    EquipmentCategory,
    EquipmentFile,
    EquipmentNote,
    EquipmentPhoto,
    EquipmentRequisite,
    EquipmentStatus,
)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'legal_entity',
        'location',
        'cost_center',
        'warehouse',
        'category',
        'status',
        'inventory_number',
        'serial_number',
        'is_active',
    )
    list_filter = ('legal_entity', 'location', 'cost_center', 'warehouse', 'category', 'status', 'is_active')
    search_fields = ('name', 'brand', 'model', 'serial_number', 'inventory_number')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(EquipmentStatus)
class EquipmentStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(EquipmentNote)
class EquipmentNoteAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('equipment__name', 'text')
    readonly_fields = ('id', 'created_at')


@admin.register(EquipmentRequisite)
class EquipmentRequisiteAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'requisite_type', 'name', 'value', 'is_active')
    list_filter = ('requisite_type', 'is_active')
    search_fields = ('equipment__name', 'name', 'value')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(EquipmentFile)
class EquipmentFileAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'title', 'uploaded_by', 'uploaded_at', 'is_active')
    list_filter = ('is_active', 'uploaded_at')
    search_fields = ('equipment__name', 'title', 'comment')
    readonly_fields = ('id', 'uploaded_at')


@admin.register(EquipmentPhoto)
class EquipmentPhotoAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'caption', 'is_primary', 'uploaded_by', 'uploaded_at', 'is_active')
    list_filter = ('is_primary', 'is_active', 'uploaded_at')
    search_fields = ('equipment__name', 'caption')
    readonly_fields = ('id', 'uploaded_at')
