"""
artworks/serializers.py
Equivalent to Laravel's ArtworkResource + CategoryResource + Form Requests.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import Category, Artwork


# ──────────────────────────────────────────────
# Category  (replaces CategoryResource)
# ──────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    artworks_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['uuid', 'name', 'slug', 'description', 'artworks_count']
        read_only_fields = ['uuid', 'slug', 'artworks_count']


class StoreCategorySerializer(serializers.ModelSerializer):
    """Equivalent to StoreCategoryRequest + UpdateCategoryRequest."""
    class Meta:
        model = Category
        fields = ['name', 'description']
        extra_kwargs = {'description': {'required': False}}

    def validate_name(self, value):
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value


# ──────────────────────────────────────────────
# Artwork  (replaces ArtworkResource)
# ──────────────────────────────────────────────
class ArtworkSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    pricing = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Artwork
        fields = [
            'uuid', 'name', 'dimensions', 'category',
            'pricing', 'image_url', 'is_sold', 'created_at',
        ]

    @extend_schema_field(
        serializers.DictField(child=serializers.CharField())
    )
    def get_pricing(self, obj):
        request = self.context.get('request')
        # Currency from ?currency=TZS query param (mirrors Laravel's ArtworkResource)
        currency_code = 'USD'
        if request:
            currency_code = (
                request.query_params.get('currency')
                or currency_code
            )

        from apps.currencies.models import Currency
        currency = Currency.objects.filter(code=currency_code).first()
        rate = float(currency.exchange_rate) if currency else 1.0
        symbol = currency.symbol if currency else '$'
        base = float(obj.base_price)

        return {
            'base_usd': base,
            'converted_amount': round(base * rate, 2),
            'currency_code': currency_code,
            'currency_symbol': symbol,
            'formatted': f"{symbol} {base * rate:,.2f}",
        }

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class StoreArtworkSerializer(serializers.ModelSerializer):
    """
    Equivalent to StoreArtworkRequest.
    Accepts category UUID (not PK) to match UUID-based routing.
    """
    category_uuid = serializers.UUIDField(write_only=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Artwork
        fields = ['category_uuid', 'name', 'dimensions', 'base_price', 'image', 'is_sold']

    def validate_category_uuid(self, value):
        try:
            return Category.objects.get(uuid=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError('Category not found.')

    def create(self, validated_data):
        category = validated_data.pop('category_uuid')   # already resolved to Category instance
        return Artwork.objects.create(category=category, **validated_data)


class UpdateArtworkSerializer(serializers.ModelSerializer):
    """Equivalent to UpdateArtworkRequest."""
    category_uuid = serializers.UUIDField(write_only=True, required=False)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Artwork
        fields = ['category_uuid', 'name', 'dimensions', 'base_price', 'image', 'is_sold']
        extra_kwargs = {f: {'required': False} for f in ['name', 'dimensions', 'base_price', 'is_sold']}

    def validate_category_uuid(self, value):
        try:
            return Category.objects.get(uuid=value)
        except Category.DoesNotExist:
            raise serializers.ValidationError('Category not found.')

    def update(self, instance, validated_data):
        category = validated_data.pop('category_uuid', None)
        if category:
            instance.category = category
        image = validated_data.pop('image', None)
        if image:
            if instance.image:
                instance.image.delete(save=False)
            instance.image = image
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance
