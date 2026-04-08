from django.core.management.base import BaseCommand
from apps.accounts.models import Country


COUNTRIES = [
    {'name': 'Tanzania',       'iso_code': 'TZ', 'phone_code': '+255', 'currency_code': 'TZS'},
    {'name': 'Kenya',          'iso_code': 'KE', 'phone_code': '+254', 'currency_code': 'KES'},
    {'name': 'Uganda',         'iso_code': 'UG', 'phone_code': '+256', 'currency_code': 'UGX'},
    {'name': 'Rwanda',         'iso_code': 'RW', 'phone_code': '+250', 'currency_code': 'RWF'},
    {'name': 'United States',  'iso_code': 'US', 'phone_code': '+1',   'currency_code': 'USD'},
    {'name': 'United Kingdom', 'iso_code': 'GB', 'phone_code': '+44',  'currency_code': 'GBP'},
]


class Command(BaseCommand):
    help = 'Seed countries'

    def handle(self, *args, **kwargs):
        for data in COUNTRIES:
            Country.objects.update_or_create(
                iso_code=data['iso_code'],
                defaults={
                    'name':          data['name'],
                    'phone_code':    data['phone_code'],
                    'currency_code': data['currency_code'],
                },
            )
        self.stdout.write(self.style.SUCCESS(f'Countries seeded successfully ({len(COUNTRIES)} records).'))
