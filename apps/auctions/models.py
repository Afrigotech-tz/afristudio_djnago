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
    current_price = models.DecimalField(max_digits=15, decimal_places=2)
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
        return self.current_price + self.bid_increment

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
    Finalise a live auction:
    - Determine the winner (highest bid).
    - Mark artwork as sold.
    - Add artwork to winner's cart.
    - Send notification to winner.
    - Log the event.
    """
    from apps.cart.models import Cart, CartItem
    from apps.notifications.service import notify
    from apps.activity_logs.utils import log_activity

    winning_bid = auction.bids.filter(is_winning=True).first()
    auction.status = Auction.STATUS_ENDED

    if winning_bid:
        auction.winner = winning_bid.bidder
        auction.artwork.is_sold = True
        auction.artwork.save(update_fields=['is_sold'])

        # Add to winner's cart
        cart, _ = Cart.objects.get_or_create(user=winning_bid.bidder)
        CartItem.objects.get_or_create(
            cart=cart,
            artwork=auction.artwork,
            defaults={
                'source': CartItem.SOURCE_AUCTION_WIN,
                'auction': auction,
                'price': winning_bid.amount,
                'currency': auction.currency,
            },
        )

        # Notify winner
        notify(
            user=winning_bid.bidder,
            subject='Congratulations! You won the auction',
            message=(
                f'Hi {winning_bid.bidder.name}, you won the auction for '
                f'"{auction.artwork.name}" with a bid of '
                f'{winning_bid.amount} {auction.currency}. '
                f'The artwork has been added to your cart.'
            ),
            template='emails/auction_won.html',
            context={
                'name': winning_bid.bidder.name,
                'artwork_name': auction.artwork.name,
                'amount': str(winning_bid.amount),
                'currency': auction.currency,
            },
        )

        log_activity(
            user=winning_bid.bidder,
            subject=auction,
            description=f'Won auction for "{auction.artwork.name}" at {winning_bid.amount} {auction.currency}',
            log_name='auctions',
            event='auction_won',
        )

    auction.save(update_fields=['status', 'winner', 'updated_at'])

    log_activity(
        user=auction.created_by,
        subject=auction,
        description=f'Auction ended for "{auction.artwork.name}"',
        log_name='auctions',
        event='auction_ended',
    )
