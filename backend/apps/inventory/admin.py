from django.contrib import admin

from .models import (
    EquipmentInventory,
    EquipmentMovement,
    EquipmentRepair,
    InventoryItem,
    InventorySession,
    MaintenanceLog,
)


@admin.register(EquipmentMovement)
class EquipmentMovementAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'from_location', 'to_location', 'from_warehouse', 'to_warehouse', 'moved_by', 'moved_at')
    list_filter = ('legal_entity', 'from_location', 'to_location', 'from_warehouse', 'to_warehouse')
    search_fields = ('equipment__name', 'equipment__serial_number', 'equipment__inventory_number', 'comment')
    readonly_fields = ('id', 'moved_at')


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'performed_at', 'cost', 'contractor', 'next_service_date')
    list_filter = ('legal_entity', 'performed_at', 'next_service_date')
    search_fields = ('equipment__name', 'description', 'contractor')


@admin.register(EquipmentRepair)
class EquipmentRepairAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'status', 'priority', 'repair_date', 'assigned_to', 'accepted_by', 'cost', 'contractor', 'created_by')
    list_filter = ('legal_entity', 'status', 'priority', 'repair_date')
    search_fields = ('equipment__name', 'equipment__serial_number', 'description', 'resolution', 'contractor')
    readonly_fields = ('id', 'created_at', 'accepted_at', 'started_at', 'completed_at', 'status_changed_at')


@admin.register(EquipmentInventory)
class EquipmentInventoryAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'inventory_date', 'condition_status', 'estimated_value', 'checked_by')
    list_filter = ('legal_entity', 'location', 'warehouse', 'condition_status', 'inventory_date')
    search_fields = ('equipment__name', 'equipment__serial_number', 'equipment__inventory_number', 'comment')
    readonly_fields = ('id', 'created_at')


@admin.register(InventorySession)
class InventorySessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'act_number', 'legal_entity', 'location', 'cost_center', 'warehouse', 'status', 'period_start', 'period_end', 'confirmed_by', 'confirmed_at')
    list_filter = ('legal_entity', 'location', 'cost_center', 'warehouse', 'status', 'period_start', 'period_end')
    search_fields = ('name', 'act_number')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('session', 'equipment', 'found', 'actual_location', 'actual_warehouse', 'condition_status', 'checked_by', 'checked_at')
    list_filter = ('found', 'actual_location', 'actual_warehouse', 'condition_status')
    search_fields = ('equipment__name', 'equipment__serial_number', 'equipment__inventory_number', 'comment')
