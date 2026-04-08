"""
currencies/models.py
Equivalent to Laravel's Currency model.
"""

import uuid
from django.db import models


class Currency(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    code = models.CharField(max_length=3, unique=True)
    symbol = models.CharField(max_length=10)
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'currencies'
        verbose_name_plural = 'currencies'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.symbol})"
