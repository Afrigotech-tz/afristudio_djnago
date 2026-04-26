"""
orders/models.py
An Order is created when the user checks out their cart.
OrderItem snapshots the artwork name and price at purchase time.
"""

import uuid
from django.db import models
from django.conf import settings


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    total = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    # Auction that generated this order (set when order is created from auction win)
    auction = models.OneToOneField(
        'auctions.Auction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='order',
    )

    # Delivery details — blank/null allowed so auction-won orders can be created
    # before the winner fills in their shipping address.
    payment_channel = models.CharField(max_length=30, blank=True, default='')

    delivery_name = models.CharField(max_length=255, blank=True, default='')
    delivery_phone = models.CharField(max_length=30, blank=True, default='')
    delivery_address = models.TextField(blank=True, default='')
    delivery_city = models.CharField(max_length=100, blank=True, default='')
    delivery_country = models.CharField(max_length=100, blank=True, default='Tanzania')
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} by {self.user} [{self.status}]"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    artwork = models.ForeignKey(
        'artworks.Artwork',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items',
    )
    # Snapshots — preserved even if artwork is deleted
    artwork_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    auction = models.ForeignKey(
        'auctions.Auction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='order_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_items'

    def __str__(self):
        return f"{self.artwork_name} in Order #{self.order_id}"
