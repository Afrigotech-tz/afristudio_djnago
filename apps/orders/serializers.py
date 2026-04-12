from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'artwork_name', 'price', 'currency']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'uuid', 'status', 'total', 'currency', 'items',
            'delivery_name', 'delivery_phone', 'delivery_address',
            'delivery_city', 'delivery_country', 'notes', 'created_at',
        ]


class CheckoutSerializer(serializers.Serializer):
    delivery_name = serializers.CharField(max_length=255)
    delivery_phone = serializers.CharField(max_length=30)
    delivery_address = serializers.CharField()
    delivery_city = serializers.CharField(max_length=100)
    delivery_country = serializers.CharField(max_length=100, default='Tanzania')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
