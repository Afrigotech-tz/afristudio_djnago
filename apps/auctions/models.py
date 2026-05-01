"""
auctions/models.py

Auction   — tied to a single Artwork.
Bid       — each bid placed during a live auction.
AuctionConfig — singleton payment-rules configuration.
AuctionWinner — winner record with payment deadline and status.
AuctionPaymentViolation — one record per unpaid win.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


# ─── Auction ──────────────────────────────────────────────────────────────────

class Auction(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_LIVE      = 'live'
    STATUS_ENDED     = 'ended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_LIVE,      'Live'),
        (STATUS_ENDED,     'Ended'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    uuid        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    artwork     = models.OneToOneField(
        'artworks.Artwork',
        on_delete=models.CASCADE,
        related_name='auction',
    )
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_auctions',
    )
    start_price   = models.DecimalField(max_digits=15, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    bid_increment = models.DecimalField(max_digits=15, decimal_places=2, default=1.00)
    currency      = models.CharField(max_length=3, default='USD')
    start_time    = models.DateTimeField()
    end_time      = models.DateTimeField()
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    winner        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_auctions',
    )
    total_bids  = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

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
        if self.status == self.STATUS_LIVE and timezone.now() >= self.end_time:
            close_auction(self)
            return True
        return False


# ─── AuctionImage ─────────────────────────────────────────────────────────────

class AuctionImage(models.Model):
    auction    = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='images')
    image      = models.ImageField(upload_to='auction_images/')
    is_primary = models.BooleanField(default=False, db_index=True)
    order      = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auction_images'
        ordering = ['-is_primary', 'order', 'created_at']

    def __str__(self):
        return f"Image for {self.auction} (primary={self.is_primary})"

    def save(self, *args, **kwargs):
        # If this image is being set as primary, demote all others
        if self.is_primary:
            AuctionImage.objects.filter(auction=self.auction, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


# ─── Bid ──────────────────────────────────────────────────────────────────────

class Bid(models.Model):
    uuid     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    auction  = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    amount     = models.DecimalField(max_digits=15, decimal_places=2)
    is_winning = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'auction_bids'
        ordering = ['-amount', '-created_at']

    def __str__(self):
        return f"Bid {self.amount} on {self.auction} by {self.bidder}"


# ─── AuctionConfig (singleton) ────────────────────────────────────────────────

class AuctionConfig(models.Model):
    MODE_FREE_BID          = 'free_bid'
    MODE_BALANCE_REQUIRED  = 'balance_required'
    MODE_AUTO_DEDUCT       = 'auto_deduct'
    MODE_CHOICES = [
        (MODE_FREE_BID,         'Free Bid — no balance required; winner pays after auction ends'),
        (MODE_BALANCE_REQUIRED, 'Balance Required — must have funds; winner pays after auction ends'),
        (MODE_AUTO_DEDUCT,      'Auto Deduct — funds held during bidding; order auto-confirmed on win'),
    ]

    payment_mode           = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_AUTO_DEDUCT)
    payment_deadline_hours = models.PositiveIntegerField(
        default=24,
        help_text='Hours the winner has to complete payment before the auction is relisted.',
    )
    max_violations         = models.PositiveIntegerField(
        default=3,
        help_text='Unpaid-win violations before the user is automatically banned.',
    )
    ban_duration_days      = models.PositiveIntegerField(
        default=30,
        help_text='Ban duration in days for repeat non-payers.',
    )
    relist_on_expired      = models.BooleanField(
        default=True,
        help_text='Reset the auction and open fresh bidding if payment deadline expires.',
    )
    relist_duration_hours  = models.PositiveIntegerField(
        default=48,
        help_text='Duration (hours) of the relisted auction.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auction_config'
        verbose_name = 'Auction Configuration'

    def __str__(self):
        return f'Auction Config [{self.payment_mode}]'

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ─── AuctionWinner ────────────────────────────────────────────────────────────

class AuctionWinner(models.Model):
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID    = 'paid'
    PAYMENT_EXPIRED = 'expired'
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, 'Pending Payment'),
        (PAYMENT_PAID,    'Paid'),
        (PAYMENT_EXPIRED, 'Expired — Auction Relisted'),
    ]

    auction        = models.OneToOneField(Auction, on_delete=models.CASCADE, related_name='winner_record')
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='auction_wins',
    )
    bid_amount     = models.DecimalField(max_digits=15, decimal_places=2)
    currency       = models.CharField(max_length=3)
    payment_mode   = models.CharField(max_length=20)  # snapshot at win time
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    payment_deadline = models.DateTimeField(null=True, blank=True)
    paid_at        = models.DateTimeField(null=True, blank=True)
    order          = models.OneToOneField(
        'orders.Order',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='auction_win',
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auction_winners'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} won "{self.auction.artwork.name}" — {self.payment_status}'

    @property
    def is_overdue(self) -> bool:
        return (
            self.payment_status == self.PAYMENT_PENDING
            and self.payment_deadline is not None
            and timezone.now() > self.payment_deadline
        )

    @property
    def hours_remaining(self):
        if not self.payment_deadline or self.payment_status != self.PAYMENT_PENDING:
            return None
        delta = self.payment_deadline - timezone.now()
        return max(round(delta.total_seconds() / 3600, 1), 0)


# ─── AuctionPaymentViolation ──────────────────────────────────────────────────

class AuctionPaymentViolation(models.Model):
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='auction_violations',
    )
    auction_winner = models.OneToOneField(
        AuctionWinner,
        on_delete=models.CASCADE,
        related_name='violation',
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auction_payment_violations'
        ordering = ['-created_at']

    def __str__(self):
        return f'Violation: {self.user} — {self.auction_winner}'


# ─── Auction lifecycle helpers ────────────────────────────────────────────────

def _notify_winner_pending_payment(auction: Auction, winner, bid_amount, deadline):
    """Send payment-pending notification (modes: free_bid, balance_required)."""
    from apps.notifications.tasks import notify_async
    deadline_str = deadline.strftime('%Y-%m-%d %H:%M UTC') if deadline else 'N/A'
    notify_async(
        user_id=winner.pk,
        subject=f'You won the auction for "{auction.artwork.name}" — complete payment',
        message=(
            f'Congratulations {winner.name}! You won the auction for '
            f'"{auction.artwork.name}" with a bid of {bid_amount} {auction.currency}. '
            f'Please complete your payment by {deadline_str}. '
            f'The item has been added to your cart.'
        ),
        template='emails/auction_won_pending.html',
        context={
            'name': winner.name,
            'artwork_name': auction.artwork.name,
            'amount': str(bid_amount),
            'currency': auction.currency,
            'deadline': deadline_str,
        },
    )


def _notify_winner_auto_order(auction: Auction, winner, order):
    """Send win + order confirmation (mode: auto_deduct)."""
    from apps.notifications.tasks import notify_async
    notify_async(
        user_id=winner.pk,
        subject=f'Congratulations! You won the auction for "{auction.artwork.name}"',
        message=(
            f'Hi {winner.name}, you won the auction for '
            f'"{auction.artwork.name}" with a bid of '
            f'{auction.current_price} {auction.currency}. '
            f'Your order #{order.id} has been confirmed.'
        ),
        template='emails/auction_won.html',
        context={
            'name': winner.name,
            'artwork_name': auction.artwork.name,
            'amount': str(auction.current_price),
            'currency': auction.currency,
            'order_id': order.id,
        },
    )
    notify_async(
        user_id=winner.pk,
        subject=f'Order #{order.id} Confirmed — Afristudio',
        message=(
            f'Hi {winner.name}, your order #{order.id} for '
            f'"{auction.artwork.name}" has been confirmed. '
            f'Total: {order.total} {order.currency}.'
        ),
        template='emails/order_placed.html',
        context={
            'name': winner.name,
            'order_id': order.id,
            'total': str(order.total),
            'currency': order.currency,
            'delivery_city': order.delivery_city or 'Not set',
        },
    )


def close_auction(auction: Auction):
    """
    Finalise a live or pending auction.

    Behaviour depends on the active AuctionConfig.payment_mode:

    • auto_deduct      — funds already held during bidding; create a confirmed
                         Order immediately (legacy / default behaviour).
    • free_bid         — no balance was required; add artwork to cart, set a
                         payment deadline, notify winner to check out.
    • balance_required — winner had funds validated but NOT deducted; same
                         cart + deadline flow as free_bid.

    DB writes are inside transaction.atomic() so state is always consistent.
    Notifications run outside the transaction.
    """
    from django.db import transaction
    from apps.cart.models import Cart, CartItem
    from apps.orders.models import Order, OrderItem
    from apps.activity_logs.utils import log_activity

    config = AuctionConfig.get_config()

    winning_bid = (
        auction.bids.filter(is_winning=True).order_by('-amount').first()
        or auction.bids.order_by('-amount').first()
    )

    order       = None
    winner_rec  = None

    with transaction.atomic():
        auction.status = Auction.STATUS_ENDED

        if winning_bid:
            winner = winning_bid.bidder
            auction.winner = winner
            auction.current_price = winning_bid.amount

            # Mark artwork sold
            auction.artwork.is_sold = True
            auction.artwork.save(update_fields=['is_sold'])

            # Ensure bid flags consistent
            auction.bids.exclude(pk=winning_bid.pk).update(is_winning=False)
            if not winning_bid.is_winning:
                winning_bid.is_winning = True
                winning_bid.save(update_fields=['is_winning'])

            # Add to cart (all modes)
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

            if config.payment_mode == AuctionConfig.MODE_AUTO_DEDUCT:
                # Create confirmed order immediately
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
                winner_rec = AuctionWinner.objects.create(
                    auction=auction,
                    user=winner,
                    bid_amount=winning_bid.amount,
                    currency=auction.currency,
                    payment_mode=config.payment_mode,
                    payment_status=AuctionWinner.PAYMENT_PAID,
                    paid_at=timezone.now(),
                    order=order,
                )

            else:
                # free_bid / balance_required — winner pays later
                deadline = (
                    timezone.now() + timedelta(hours=config.payment_deadline_hours)
                    if config.payment_deadline_hours
                    else None
                )
                winner_rec = AuctionWinner.objects.create(
                    auction=auction,
                    user=winner,
                    bid_amount=winning_bid.amount,
                    currency=auction.currency,
                    payment_mode=config.payment_mode,
                    payment_status=AuctionWinner.PAYMENT_PENDING,
                    payment_deadline=deadline,
                )

        auction.save(update_fields=['status', 'winner', 'current_price', 'updated_at'])

    # ── Post-transaction: notifications & logs ────────────────────────────────
    if winning_bid:
        winner = winning_bid.bidder

        if config.payment_mode == AuctionConfig.MODE_AUTO_DEDUCT and order:
            _notify_winner_auto_order(auction, winner, order)
            log_activity(
                user=winner, subject=order,
                description=f'Order #{order.id} auto-created from auction win',
                log_name='orders', event='order_placed',
            )
        elif winner_rec:
            _notify_winner_pending_payment(
                auction, winner, winning_bid.amount, winner_rec.payment_deadline
            )

        log_activity(
            user=winner, subject=auction,
            description=(
                f'Won auction for "{auction.artwork.name}" at '
                f'{winning_bid.amount} {auction.currency}'
            ),
            log_name='auctions', event='auction_won',
        )

    log_activity(
        user=auction.created_by, subject=auction,
        description=f'Auction ended for "{auction.artwork.name}"',
        log_name='auctions', event='auction_ended',
    )


def relist_auction(auction: Auction, config: AuctionConfig):
    """
    Reset an ended auction back to pending with a fresh time window.
    Called by check_auction_deadlines when payment deadline expires.
    """
    from apps.cart.models import CartItem
    from apps.activity_logs.utils import log_activity

    now = timezone.now()
    new_end = now + timedelta(hours=config.relist_duration_hours)

    auction.status        = Auction.STATUS_PENDING
    auction.winner        = None
    auction.current_price = auction.start_price
    auction.total_bids    = 0
    auction.start_time    = now
    auction.end_time      = new_end
    auction.save(update_fields=[
        'status', 'winner', 'current_price', 'total_bids',
        'start_time', 'end_time', 'updated_at',
    ])

    # Delete old bids so fresh auction starts clean
    auction.bids.all().delete()

    # Mark artwork as not sold
    auction.artwork.is_sold = False
    auction.artwork.save(update_fields=['is_sold'])

    # Remove from winner's cart
    CartItem.objects.filter(artwork=auction.artwork).delete()

    log_activity(
        user=None, subject=auction,
        description=(
            f'Auction relisted for "{auction.artwork.name}" after payment deadline expired. '
            f'New end time: {new_end.strftime("%Y-%m-%d %H:%M UTC")}'
        ),
        log_name='auctions', event='auction_relisted',
    )
