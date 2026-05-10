from django.contrib import admin

from .models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'cost_center', 'is_active')
    list_filter = ('cost_center', 'is_active')
    search_fields = ('name', 'cost_center__name')
