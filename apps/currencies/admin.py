from django.contrib import admin
from .models import Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'code', 'symbol', 'exchange_rate', 'updated_at']
    search_fields = ['code', 'symbol']
