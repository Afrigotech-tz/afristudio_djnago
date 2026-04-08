from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'log_name', 'event', 'description', 'causer', 'created_at']
    list_filter = ['log_name', 'event']
    search_fields = ['description', 'causer__email', 'causer__name']
    readonly_fields = ['created_at', 'updated_at']
