"""
site_config/serializers.py
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import LandingHero, HeroContent, ContactInfo, ContactMessage, ArtistProfile, Exhibition



class LandingHeroSerializer(serializers.ModelSerializer):
    image_url   = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()

    class Meta:
        model = LandingHero
        fields = ['image_url', 'favicon_url', 'updated_at']

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    @extend_schema_field(OpenApiTypes.URI)
    def get_favicon_url(self, obj):
        request = self.context.get('request')
        if obj.favicon and request:
            return request.build_absolute_uri(obj.favicon.url)
        return None


class LandingHeroUpdateSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=True)

    class Meta:
        model = LandingHero
        fields = ['image']


class LandingFaviconUpdateSerializer(serializers.ModelSerializer):
    favicon = serializers.ImageField(required=True)

    class Meta:
        model = LandingHero
        fields = ['favicon']


class HeroContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroContent
        fields = ['tagline', 'title', 'subtitle', 'cta_text', 'cta_link', 'updated_at']


class HeroContentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroContent
        fields = ['tagline', 'title', 'subtitle', 'cta_text', 'cta_link']
        extra_kwargs = {f: {'required': False} for f in ['tagline', 'title', 'subtitle', 'cta_text', 'cta_link']}


class ContactInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInfo
        fields = ['email', 'phone', 'location', 'updated_at']


class ContactInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInfo
        fields = ['email', 'phone', 'location']
        extra_kwargs = {f: {'required': False} for f in ['email', 'phone', 'location']}


class ContactMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'name', 'email', 'subject', 'message', 'created_at', 'updated_at']


class ContactMessageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['status']

    def validate_status(self, value):
        valid = [s for s, _ in ContactMessage.STATUS_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(f'Status must be one of: {", ".join(valid)}')
        return value


class ArtistProfileSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = ArtistProfile
        fields = ['name', 'location', 'photo_url', 'biography', 'story', 'philosophy', 'statement', 'updated_at']

    @extend_schema_field(OpenApiTypes.URI)
    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None


class ArtistProfileUpdateSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(required=False)

    class Meta:
        model = ArtistProfile
        fields = ['name', 'location', 'photo', 'biography', 'story', 'philosophy', 'statement']
        extra_kwargs = {f: {'required': False} for f in ['name', 'location', 'photo', 'biography', 'story', 'philosophy', 'statement']}


class ExhibitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exhibition
        fields = ['id', 'date_label', 'title', 'location', 'order']


class ExhibitionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exhibition
        fields = ['date_label', 'title', 'location', 'order']
        extra_kwargs = {'order': {'required': False}}
