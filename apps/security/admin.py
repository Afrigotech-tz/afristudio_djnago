from django.contrib import admin
from .models import BlockedIP, RateLimitViolation, RequestLog


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ['ip', 'reason', 'is_permanent', 'expires_at', 'blocked_by', 'created_at']
    list_filter = ['is_permanent']
    search_fields = ['ip', 'reason']
    ordering = ['-created_at']


@admin.register(RateLimitViolation)
class RateLimitViolationAdmin(admin.ModelAdmin):
    list_display = ['ip', 'violation_count', 'first_violation', 'last_violation']
    ordering = ['-last_violation']
    search_fields = ['ip']


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ['method', 'path', 'status_code', 'response_time_ms', 'ip', 'created_at']
    list_filter = ['method', 'status_code']
    search_fields = ['ip', 'path']
    ordering = ['-created_at']
    readonly_fields = ['ip', 'path', 'method', 'status_code', 'response_time_ms',
                       'user_agent', 'country_code', 'created_at']
