from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('artwork', 'artwork_name', 'price', 'currency', 'auction')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total', 'currency', 'delivery_city', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('user__email', 'user__name', 'delivery_name')
    readonly_fields = ('uuid', 'user', 'total', 'currency', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('artwork_name', 'order', 'price', 'currency')
    search_fields = ('artwork_name', 'order__user__email')
