"""
cart/models.py
Each user has one Cart. Items can be added manually or automatically
when a user wins an auction.

Artwork in a LIVE auction cannot be added to the cart manually.
"""

import uuid
from django.db import models
from django.conf import settings


class Cart(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'

    def __str__(self):
        return f"Cart of {self.user}"


class CartItem(models.Model):
    SOURCE_MANUAL = 'manual'
    SOURCE_AUCTION_WIN = 'auction_win'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_AUCTION_WIN, 'Auction Win'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    artwork = models.ForeignKey('artworks.Artwork', on_delete=models.CASCADE, related_name='cart_items')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    auction = models.ForeignKey(
        'auctions.Auction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cart_items',
    )
    price = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cart_items'
        unique_together = [['cart', 'artwork']]

    def __str__(self):
        return f"{self.artwork.name} in {self.cart}"
