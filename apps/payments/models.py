"""
payments/models.py

PaymentMethod  — one record per channel; admin enables/disables & configures.
PaymentTransaction — one record per payment attempt on an Order.
"""

from django.db import models
from django.conf import settings


# ── Payment channels ───────────────────────────────────────────────────────────

class PaymentMethod(models.Model):
    CHANNEL_BANK    = 'bank_transfer'
    CHANNEL_STRIPE  = 'stripe'
    CHANNEL_SELCOM  = 'selcom'
    CHANNEL_CHOICES = [
        (CHANNEL_BANK,   'Bank Transfer (Manual)'),
        (CHANNEL_STRIPE, 'Stripe (International Cards)'),
        (CHANNEL_SELCOM, 'Selcom (Mobile Money)'),
    ]

    channel      = models.CharField(max_length=30, choices=CHANNEL_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    is_active    = models.BooleanField(default=False)
    sort_order   = models.PositiveSmallIntegerField(default=0)

    # Channel-specific configuration stored as JSON:
    #   bank_transfer: { bank_name, account_number, account_name,
    #                    branch, swift_code, instructions }
    #   stripe:        { publishable_key, secret_key, webhook_secret }
    #   selcom:        { vendor_id, vendor_pass, api_url, api_key }
    config = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_methods'
        ordering = ['sort_order', 'channel']
        verbose_name = 'Payment Method'

    def __str__(self):
        return f'{self.display_name} [{"active" if self.is_active else "inactive"}]'


# ── Payment transactions ───────────────────────────────────────────────────────

class PaymentTransaction(models.Model):
    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED  = 'completed'
    STATUS_FAILED     = 'failed'
    STATUS_REFUNDED   = 'refunded'
    STATUS_CANCELLED  = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED,  'Completed'),
        (STATUS_FAILED,     'Failed'),
        (STATUS_REFUNDED,   'Refunded'),
        (STATUS_CANCELLED,  'Cancelled'),
    ]

    order    = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    user     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
    )
    channel  = models.CharField(max_length=30)          # snapshot of channel at time of payment
    amount   = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3)
    status   = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    # Bank transfer: user-provided reference / proof image
    reference   = models.CharField(max_length=255, blank=True)
    proof_image = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)

    # Stripe / Selcom: external IDs returned by the gateway
    external_id   = models.CharField(max_length=255, blank=True, db_index=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    # Admin notes (e.g. "manually verified bank receipt")
    admin_notes = models.TextField(blank=True)

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_payments',
    )

    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at      = models.DateTimeField(null=True, blank=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f'PaymentTransaction #{self.id} [{self.channel}] {self.status} — Order #{self.order_id}'
