"""
artworks/models.py
Equivalent to Laravel's Category + Artwork models.
"""

import uuid
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Artwork(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='artworks')
    name = models.CharField(max_length=255)
    dimensions = models.CharField(max_length=100)   # e.g. "100x100"
    base_price = models.DecimalField(max_digits=15, decimal_places=2)
    base_currency = models.CharField(max_length=3, default='USD')
    image = models.ImageField(upload_to='artworks/', null=True, blank=True)
    is_sold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'artworks'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_price_in(self, currency_code: str) -> dict:
        """
        Calculate price converted to a given currency.
        Equivalent to Artwork::getPriceIn() in Laravel.
        """
        from apps.currencies.models import Currency
        currency = Currency.objects.filter(code=currency_code).first()
        rate = float(currency.exchange_rate) if currency else 1.0
        symbol = currency.symbol if currency else '$'
        amount = round(float(self.base_price) * rate, 2)
        return {
            'amount': amount,
            'currency': currency_code,
            'symbol': symbol,
        }


class ArtworkImage(models.Model):
    artwork    = models.ForeignKey(Artwork, on_delete=models.CASCADE, related_name='images')
    image      = models.ImageField(upload_to='artwork_images/')
    is_primary = models.BooleanField(default=False, db_index=True)
    order      = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'artwork_images'
        ordering = ['-is_primary', 'order', 'created_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            ArtworkImage.objects.filter(
                artwork=self.artwork, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
