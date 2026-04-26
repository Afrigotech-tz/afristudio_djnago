from django.contrib import admin
from .models import PaymentMethod, PaymentTransaction


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display  = ['channel', 'display_name', 'is_active', 'sort_order', 'updated_at']
    list_editable = ['is_active', 'sort_order']
    ordering      = ['sort_order', 'channel']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'channel', 'amount', 'currency', 'status', 'created_at']
    list_filter   = ['channel', 'status']
    search_fields = ['user__email', 'reference', 'external_id']
    readonly_fields = ['created_at', 'updated_at', 'paid_at']
    ordering      = ['-created_at']
