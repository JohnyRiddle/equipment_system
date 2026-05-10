from django.contrib import admin
from django.utils.html import format_html

from .models import EquipmentTag


@admin.register(EquipmentTag)
class EquipmentTagAdmin(admin.ModelAdmin):
    list_display = ('code', 'tag_type', 'equipment', 'is_active', 'qr_preview')
    list_filter = ('tag_type', 'is_active')
    search_fields = ('code', 'uid')

    readonly_fields = ('qr_preview',)

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="max-width: 150px; border-radius: 6px;" />', obj.qr_image.url)
        return '—'

    qr_preview.short_description = 'QR Preview'