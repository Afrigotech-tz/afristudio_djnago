from decimal import Decimal
from rest_framework import serializers
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from .models import Auction, Bid


class BidSerializer(serializers.ModelSerializer):
    bidder_name = serializers.CharField(source='bidder.name', read_only=True)

    class Meta:
        model = Bid
        fields = ['uuid', 'bidder_name', 'amount', 'is_winning', 'created_at']


class AuctionSerializer(serializers.ModelSerializer):
    artwork_name = serializers.CharField(source='artwork.name', read_only=True)
    artwork_uuid = serializers.UUIDField(source='artwork.uuid', read_only=True)
    artwork_image = serializers.ImageField(source='artwork.image', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    winner_name = serializers.CharField(source='winner.name', read_only=True)
    minimum_next_bid = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    top_bids = serializers.SerializerMethodField()
    seconds_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Auction
        fields = [
            'uuid', 'artwork_uuid', 'artwork_name', 'artwork_image',
            'created_by_name', 'start_price', 'reserve_price',
            'current_price', 'bid_increment', 'minimum_next_bid',
            'currency', 'start_time', 'end_time', 'status',
            'winner_name', 'total_bids', 'top_bids', 'seconds_remaining',
            'created_at',
        ]

    @extend_schema_field(BidSerializer(many=True))
    def get_top_bids(self, obj):
        return BidSerializer(obj.bids.order_by('-amount')[:10], many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_seconds_remaining(self, obj):
        if obj.status != Auction.STATUS_LIVE:
            return 0
        delta = obj.end_time - timezone.now()
        return max(int(delta.total_seconds()), 0)


class CreateAuctionSerializer(serializers.Serializer):
    artwork_uuid = serializers.UUIDField()
    start_price = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    reserve_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    bid_increment = serializers.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1.00'), min_value=Decimal('0.01'))
    currency = serializers.CharField(max_length=3, default='USD')
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, data):
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError('end_time must be after start_time.')
        return data


class PlaceBidSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
