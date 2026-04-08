from django.core.management.base import BaseCommand
from apps.currencies.models import Currency


CURRENCIES = [
    {'code': 'USD', 'symbol': '$',   'exchange_rate': '1.00000000'},
    {'code': 'TZS', 'symbol': 'TSh', 'exchange_rate': '2580.50000000'},
    {'code': 'EUR', 'symbol': '€',   'exchange_rate': '0.92000000'},
    {'code': 'GBP', 'symbol': '£',   'exchange_rate': '0.79000000'},
    {'code': 'KES', 'symbol': 'KSh', 'exchange_rate': '132.50000000'},
]


class Command(BaseCommand):
    help = 'Seed currencies'

    def handle(self, *args, **kwargs):
        for data in CURRENCIES:
            Currency.objects.update_or_create(
                code=data['code'],
                defaults={
                    'symbol':        data['symbol'],
                    'exchange_rate': data['exchange_rate'],
                },
            )
        self.stdout.write(self.style.SUCCESS(f'Currencies seeded successfully ({len(CURRENCIES)} records).'))
