"""
Master seed command — runs all seeders in dependency order.
Usage:
    python manage.py seed
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run all seeders in order'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding countries ...')
        call_command('seed_countries')

        self.stdout.write('Seeding currencies ...')
        call_command('seed_currencies')

        self.stdout.write('Seeding roles & permissions ...')
        call_command('seed_roles_permissions')

        self.stdout.write('Seeding users ...')
        call_command('seed_users')

        self.stdout.write('Seeding payment methods ...')
        call_command('seed_payment_methods')

        self.stdout.write(self.style.SUCCESS('\nAll seeders completed successfully.'))
