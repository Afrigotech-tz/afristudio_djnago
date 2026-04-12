from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('uuid', 'artwork', 'source', 'auction', 'price', 'currency', 'created_at')
    can_delete = False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_count', 'updated_at')
    search_fields = ('user__email', 'user__name')
    inlines = [CartItemInline]

    def item_count(self, obj):
        return obj.items.count()


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('artwork', 'cart', 'source', 'price', 'currency', 'created_at')
    list_filter = ('source',)
    search_fields = ('artwork__name', 'cart__user__email')
