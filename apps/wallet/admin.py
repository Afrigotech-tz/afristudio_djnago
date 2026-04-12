from django.contrib import admin
from .models import Wallet, WalletTransaction


class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    readonly_fields = ('balance_after', 'created_at')
    can_delete = False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'updated_at')
    search_fields = ('user__email', 'user__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [WalletTransactionInline]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'type', 'amount', 'balance_after', 'reference', 'created_at')
    list_filter = ('type',)
    search_fields = ('wallet__user__email', 'reference', 'description')
    # Only auto-computed fields are read-only; everything else is editable
    readonly_fields = ('balance_after', 'created_at')

    def save_model(self, request, obj, form, change):
        """
        When an admin manually adds a transaction, update the wallet balance
        and set balance_after as a snapshot.
        """
        wallet = obj.wallet
        if obj.type == WalletTransaction.TYPE_DEPOSIT or obj.type == WalletTransaction.TYPE_REFUND:
            wallet.balance += obj.amount
        elif obj.type == WalletTransaction.TYPE_DEDUCTION:
            wallet.balance -= obj.amount
        wallet.save(update_fields=['balance', 'updated_at'])
        obj.balance_after = wallet.balance
        super().save_model(request, obj, form, change)
