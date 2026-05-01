from django.core.management.base import BaseCommand

from apps.payments.models import PaymentMethod


PAYMENT_METHODS = [
    {
        'channel': PaymentMethod.CHANNEL_BANK,
        'display_name': 'Bank Transfer',
        'description': 'Pay by direct bank transfer and upload your payment reference.',
        'is_active': True,
        'sort_order': 10,
        'config': {
            'bank_name': 'CRDB Bank',
            'account_number': '000000000000',
            'account_name': 'AfriStudio',
            'branch': 'Dar es Salaam',
            'swift_code': '',
            'instructions': 'Use your order number as the payment reference. Your order will be confirmed after admin verification.',
        },
    },
]


class Command(BaseCommand):
    help = 'Seed default checkout payment methods'

    def handle(self, *args, **kwargs):
        for data in PAYMENT_METHODS:
            PaymentMethod.objects.update_or_create(
                channel=data['channel'],
                defaults={
                    'display_name': data['display_name'],
                    'description': data['description'],
                    'is_active': data['is_active'],
                    'sort_order': data['sort_order'],
                    'config': data['config'],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(f'Payment methods seeded successfully ({len(PAYMENT_METHODS)} records).')
        )
