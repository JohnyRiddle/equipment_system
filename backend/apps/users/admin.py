from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('AYS access', {'fields': ('phone', 'job_title', 'role', 'is_global_access')}),
    )
    list_display = ('username', 'email', 'role', 'is_global_access', 'is_staff', 'is_active')
    list_filter = ('role', 'is_global_access', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
