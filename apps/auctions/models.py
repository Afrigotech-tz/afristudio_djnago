"""
auctions/models.py
Auction — tied to a single Artwork.
Bid     — each bid placed by a user during a live auction.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Auction(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_LIVE = 'live'
    STATUS_ENDED = 'ended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_LIVE, 'Live'),
        (STATUS_ENDED, 'Ended'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    artwork = models.OneToOneField(
        'artworks.Artwork',
        on_delete=models.CASCADE,
        related_name='auction',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_auctions',
    )
    start_price = models.DecimalField(max_digits=15, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                        help_text='Minimum price to complete the sale. Optional.')
    current_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    bid_increment = models.DecimalField(max_digits=15, decimal_places=2, default=1.00,
                                        help_text='Minimum amount each new bid must exceed the current price by.')
    currency = models.CharField(max_length=3, default='USD')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_auctions',
    )
    total_bids = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auctions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Auction: {self.artwork.name} [{self.status}]"

    @property
    def is_live(self) -> bool:
        return self.status == self.STATUS_LIVE

    @property
    def minimum_next_bid(self):
        price = self.current_price or self.start_price
        return price + self.bid_increment

    def check_and_auto_close(self):
        """Close the auction if end_time has passed. Returns True if closed."""
        if self.status == self.STATUS_LIVE and timezone.now() >= self.end_time:
            close_auction(self)
            return True
        return False


class Bid(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_winning = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'auction_bids'
        ordering = ['-amount', '-created_at']

    def __str__(self):
        return f"Bid {self.amount} on {self.auction} by {self.bidder}"


# ─── Auction lifecycle helper ─────────────────────────────────────────────────

def close_auction(auction: Auction):
    """
    Finalise a live or pending auction:
    1. Pick the winning bid.
    2. Mark artwork as sold.
    3. Add artwork to winner's cart.
    4. Auto-create a confirmed Order for the winner.
    5. Send win email + order confirmation email.
    6. Log the event.

    DB work runs inside transaction.atomic() so state is always consistent.
    Notifications are outside the transaction so email/SMS failure never
    prevents the winner from being saved.
    """
    from django.db import transaction
    from apps.cart.models import Cart, CartItem
    from apps.orders.models import Order, OrderItem
    from apps.notifications.service import notify
    from apps.activity_logs.utils import log_activity

    # Pick winner: is_winning=True first, fall back to highest bid overall
    winning_bid = (
        auction.bids.filter(is_winning=True).order_by('-amount').first()
        or auction.bids.order_by('-amount').first()
    )

    order = None

    with transaction.atomic():
        auction.status = Auction.STATUS_ENDED

        if winning_bid:
            winner = winning_bid.bidder
            auction.winner = winner
            auction.current_price = winning_bid.amount

            # Mark artwork as sold
            auction.artwork.is_sold = True
            auction.artwork.save(update_fields=['is_sold'])

            # Ensure bid flags are consistent
            auction.bids.exclude(pk=winning_bid.pk).update(is_winning=False)
            if not winning_bid.is_winning:
                winning_bid.is_winning = True
                winning_bid.save(update_fields=['is_winning'])

            # Add artwork to winner's cart (so they can still navigate to it)
            cart, _ = Cart.objects.get_or_create(user=winner)
            CartItem.objects.update_or_create(
                cart=cart,
                artwork=auction.artwork,
                defaults={
                    'source': CartItem.SOURCE_AUCTION_WIN,
                    'auction': auction,
                    'price': winning_bid.amount,
                    'currency': auction.currency,
                },
            )

            # Pull delivery details from user profile (if available)
            profile = getattr(winner, 'profile', None)
            order = Order.objects.create(
                user=winner,
                auction=auction,
                status=Order.STATUS_CONFIRMED,
                total=winning_bid.amount,
                currency=auction.currency,
                delivery_name=winner.name or '',
                delivery_phone=getattr(winner, 'phone', '') or '',
                delivery_address=getattr(profile, 'address', '') or '',
                delivery_city=getattr(profile, 'city', '') or '',
                delivery_country='Tanzania',
                notes=f'Auto-created from auction win — Auction #{auction.uuid}',
            )
            OrderItem.objects.create(
                order=order,
                artwork=auction.artwork,
                artwork_name=auction.artwork.name,
                price=winning_bid.amount,
                currency=auction.currency,
                auction=auction,
            )

        auction.save(update_fields=['status', 'winner', 'current_price', 'updated_at'])

    # ── Post-transaction: notifications & logs ────────────────────────────────
    if winning_bid and order:
        winner = winning_bid.bidder

        # 1 — Auction win notification
        try:
            notify(
                user=winner,
                subject=f'Congratulations! You won the auction for "{auction.artwork.name}"',
                message=(
                    f'Hi {winner.name}, you won the auction for '
                    f'"{auction.artwork.name}" with a bid of '
                    f'{winning_bid.amount} {auction.currency}. '
                    f'Your order #{order.id} has been confirmed.'
                ),
                template='emails/auction_won.html',
                context={
                    'name': winner.name,
                    'artwork_name': auction.artwork.name,
                    'amount': str(winning_bid.amount),
                    'currency': auction.currency,
                    'order_id': order.id,
                },
            )
        except Exception:
            pass

        # 2 — Order confirmation notification
        try:
            notify(
                user=winner,
                subject=f'Order #{order.id} Confirmed — Afristudio',
                message=(
                    f'Hi {winner.name}, your order #{order.id} for '
                    f'"{auction.artwork.name}" has been confirmed. '
                    f'Total: {order.total} {order.currency}. '
                    f'Please update your delivery address if not already set.'
                ),
                template='emails/order_placed.html',
                context={
                    'name': winner.name,
                    'order_id': order.id,
                    'total': str(order.total),
                    'currency': order.currency,
                    'delivery_city': order.delivery_city or 'Not set — please update',
                },
            )
        except Exception:
            pass

        log_activity(
            user=winner,
            subject=auction,
            description=f'Won auction for "{auction.artwork.name}" at {winning_bid.amount} {auction.currency} — Order #{order.id} created',
            log_name='auctions',
            event='auction_won',
        )
        log_activity(
            user=winner,
            subject=order,
            description=f'Order #{order.id} auto-created from auction win',
            log_name='orders',
            event='order_placed',
        )

    log_activity(
        user=auction.created_by,
        subject=auction,
        description=f'Auction ended for "{auction.artwork.name}"',
        log_name='auctions',
        event='auction_ended',
    )
