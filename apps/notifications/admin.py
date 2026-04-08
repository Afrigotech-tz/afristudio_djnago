from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('channel', 'recipient', 'subject', 'status', 'causer', 'sent_at')
    list_filter = ('channel', 'status', 'sent_at')
    search_fields = ('recipient', 'subject', 'message', 'causer__email')
    readonly_fields = ('channel', 'recipient', 'subject', 'message', 'status', 'error', 'causer', 'sent_at')
    ordering = ('-sent_at',)
