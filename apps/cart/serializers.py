from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    artwork_name = serializers.CharField(source='artwork.name', read_only=True)
    artwork_uuid = serializers.UUIDField(source='artwork.uuid', read_only=True)
    artwork_image = serializers.ImageField(source='artwork.image', read_only=True)

    class Meta:
        model = CartItem
        fields = ['uuid', 'artwork_uuid', 'artwork_name', 'artwork_image',
                  'source', 'price', 'currency', 'created_at']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['uuid', 'items', 'total', 'updated_at']

    @extend_schema_field(serializers.DecimalField(max_digits=15, decimal_places=2))
    def get_total(self, obj):
        return sum(item.price for item in obj.items.all())


class AddToCartSerializer(serializers.Serializer):
    artwork_uuid = serializers.UUIDField()
