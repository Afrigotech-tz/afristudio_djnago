from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'artwork_name', 'price', 'currency']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_name  = serializers.SerializerMethodField()
    buyer_email = serializers.SerializerMethodField()
    buyer_uuid  = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'uuid', 'status', 'total', 'currency', 'items',
            'delivery_name', 'delivery_phone', 'delivery_address',
            'delivery_city', 'delivery_country', 'notes',
            'buyer_name', 'buyer_email', 'buyer_uuid',
            'created_at',
        ]

    def get_buyer_name(self, obj):
        return obj.user.name if obj.user_id else None

    def get_buyer_email(self, obj):
        return obj.user.email if obj.user_id else None

    def get_buyer_uuid(self, obj):
        return str(obj.user.uuid) if obj.user_id else None


class CheckoutSerializer(serializers.Serializer):
    delivery_name    = serializers.CharField(max_length=255)
    delivery_phone   = serializers.CharField(max_length=30)
    delivery_address = serializers.CharField()
    delivery_city    = serializers.CharField(max_length=100)
    delivery_country = serializers.CharField(max_length=100, default='Tanzania')
    notes            = serializers.CharField(required=False, allow_blank=True, default='')


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
