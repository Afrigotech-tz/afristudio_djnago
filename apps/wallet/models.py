"""
wallet/models.py
Each user has one Wallet. Every credit/debit is recorded in WalletTransaction.
"""

import uuid
from django.db import models
from django.conf import settings


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'

    def __str__(self):
        return f"{self.user} — {self.balance} {self.currency}"

    def can_afford(self, amount) -> bool:
        return self.balance >= amount

    def deduct(self, amount, description='', reference=''):
        """Deduct amount and record transaction. Raises ValueError if insufficient funds."""
        if not self.can_afford(amount):
            raise ValueError('Insufficient wallet balance.')
        self.balance -= amount
        self.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=self,
            type=WalletTransaction.TYPE_DEDUCTION,
            amount=amount,
            balance_after=self.balance,
            description=description,
            reference=reference,
        )

    def credit(self, amount, description='', reference='', tx_type=None):
        """Credit amount and record transaction."""
        self.balance += amount
        self.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=self,
            type=tx_type or WalletTransaction.TYPE_DEPOSIT,
            amount=amount,
            balance_after=self.balance,
            description=description,
            reference=reference,
        )


class WalletTransaction(models.Model):
    TYPE_DEPOSIT = 'deposit'
    TYPE_DEDUCTION = 'deduction'
    TYPE_REFUND = 'refund'
    TYPE_CHOICES = [
        (TYPE_DEPOSIT, 'Deposit'),
        (TYPE_DEDUCTION, 'Deduction'),
        (TYPE_REFUND, 'Refund'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.amount} — {self.wallet.user}"
