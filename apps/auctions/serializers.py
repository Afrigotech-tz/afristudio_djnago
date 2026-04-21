from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone  # noqa: F401 — used in ExtendAuctionSerializer
from drf_spectacular.utils import extend_schema_field
from .models import Auction, Bid, AuctionConfig, AuctionWinner, AuctionPaymentViolation


class BidSerializer(serializers.ModelSerializer):
    bidder_name = serializers.CharField(source='bidder.name', read_only=True)

    class Meta:
        model = Bid
        fields = ['uuid', 'bidder_name', 'amount', 'is_winning', 'created_at']


class AuctionSerializer(serializers.ModelSerializer):
    artwork_name     = serializers.CharField(source='artwork.name', read_only=True)
    artwork_uuid     = serializers.UUIDField(source='artwork.uuid', read_only=True)
    artwork_image    = serializers.ImageField(source='artwork.image', read_only=True)
    created_by_name  = serializers.CharField(source='created_by.name', read_only=True)
    winner_name      = serializers.CharField(source='winner.name', read_only=True)
    minimum_next_bid = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    top_bids         = serializers.SerializerMethodField()
    seconds_remaining = serializers.SerializerMethodField()
    unique_bidders   = serializers.SerializerMethodField()
    payment_status   = serializers.SerializerMethodField()
    payment_deadline = serializers.SerializerMethodField()

    class Meta:
        model = Auction
        fields = [
            'uuid', 'artwork_uuid', 'artwork_name', 'artwork_image',
            'created_by_name', 'start_price', 'reserve_price',
            'current_price', 'bid_increment', 'minimum_next_bid',
            'currency', 'start_time', 'end_time', 'status',
            'winner_name', 'total_bids', 'unique_bidders', 'top_bids',
            'seconds_remaining', 'payment_status', 'payment_deadline',
            'created_at',
        ]

    @extend_schema_field(BidSerializer(many=True))
    def get_top_bids(self, obj):
        return BidSerializer(obj.bids.order_by('-amount')[:10], many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_unique_bidders(self, obj):
        return obj.bids.values('bidder').distinct().count()

    @extend_schema_field(serializers.IntegerField())
    def get_seconds_remaining(self, obj):
        if obj.status != Auction.STATUS_LIVE:
            return 0
        delta = obj.end_time - timezone.now()
        return max(int(delta.total_seconds()), 0)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_payment_status(self, obj):
        try:
            return obj.winner_record.payment_status
        except Exception:
            return None

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_payment_deadline(self, obj):
        try:
            return obj.winner_record.payment_deadline
        except Exception:
            return None


class CreateAuctionSerializer(serializers.Serializer):
    artwork_uuid  = serializers.UUIDField()
    start_price   = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    reserve_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    bid_increment = serializers.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1.00'), min_value=Decimal('0.01'))
    currency      = serializers.CharField(max_length=3, default='USD')
    start_time    = serializers.DateTimeField()
    end_time      = serializers.DateTimeField()

    def validate(self, data):
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError('end_time must be after start_time.')
        return data


class UpdateAuctionSerializer(serializers.Serializer):
    start_price   = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'), required=False)
    reserve_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    bid_increment = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'), required=False)
    currency      = serializers.CharField(max_length=3, required=False)
    start_time    = serializers.DateTimeField(required=False)
    end_time      = serializers.DateTimeField(required=False)

    def validate(self, data):
        st = data.get('start_time', self.instance.start_time if self.instance else None)
        et = data.get('end_time',   self.instance.end_time   if self.instance else None)
        if st and et and et <= st:
            raise serializers.ValidationError('end_time must be after start_time.')
        return data


class ExtendAuctionSerializer(serializers.Serializer):
    end_time      = serializers.DateTimeField()
    bid_increment = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'), required=False)

    def validate_end_time(self, value):
        if self.instance and value <= timezone.now():
            raise serializers.ValidationError('New end time must be in the future.')
        return value


class PlaceBidSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))


# ── AuctionConfig ─────────────────────────────────────────────────────────────

class AuctionConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuctionConfig
        fields = [
            'payment_mode',
            'payment_deadline_hours',
            'max_violations',
            'ban_duration_days',
            'relist_on_expired',
            'relist_duration_hours',
            'updated_at',
        ]
        read_only_fields = ['updated_at']


# ── AuctionWinner ─────────────────────────────────────────────────────────────

class AuctionWinnerSerializer(serializers.ModelSerializer):
    user_name      = serializers.CharField(source='user.name', read_only=True)
    user_email     = serializers.CharField(source='user.email', read_only=True)
    artwork_name   = serializers.CharField(source='auction.artwork.name', read_only=True)
    auction_uuid   = serializers.UUIDField(source='auction.uuid', read_only=True)
    is_overdue     = serializers.BooleanField(read_only=True)
    hours_remaining = serializers.FloatField(read_only=True)

    class Meta:
        model = AuctionWinner
        fields = [
            'id', 'auction_uuid', 'artwork_name',
            'user_name', 'user_email',
            'bid_amount', 'currency', 'payment_mode',
            'payment_status', 'payment_deadline', 'paid_at',
            'is_overdue', 'hours_remaining',
            'created_at',
        ]


# ── AuctionPaymentViolation ───────────────────────────────────────────────────

class AuctionPaymentViolationSerializer(serializers.ModelSerializer):
    user_name    = serializers.CharField(source='user.name', read_only=True)
    user_email   = serializers.CharField(source='user.email', read_only=True)
    artwork_name = serializers.CharField(source='auction_winner.auction.artwork.name', read_only=True)
    auction_uuid = serializers.UUIDField(source='auction_winner.auction.uuid', read_only=True)
    bid_amount   = serializers.DecimalField(source='auction_winner.bid_amount', max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = AuctionPaymentViolation
        fields = [
            'id', 'user_name', 'user_email',
            'artwork_name', 'auction_uuid', 'bid_amount',
            'created_at',
        ]
