from django.contrib import admin
from .models import Wallet, WalletTransaction


class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    readonly_fields = ('type', 'amount', 'balance_after', 'description', 'reference', 'created_at')
    can_delete = False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'updated_at')
    search_fields = ('user__email', 'user__name')
    readonly_fields = ('balance', 'currency', 'created_at', 'updated_at')
    inlines = [WalletTransactionInline]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'type', 'amount', 'balance_after', 'reference', 'created_at')
    list_filter = ('type',)
    search_fields = ('wallet__user__email', 'reference', 'description')
    readonly_fields = ('wallet', 'type', 'amount', 'balance_after', 'description', 'reference', 'created_at')
