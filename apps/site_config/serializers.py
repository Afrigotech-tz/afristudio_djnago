"""
site_config/serializers.py
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import LandingHero, HeroContent, ContactInfo, ContactMessage, LanguageConfig, ArtistProfile, Exhibition



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


class LanguageConfigSerializer(serializers.ModelSerializer):
    available_languages = serializers.SerializerMethodField()

    class Meta:
        model = LanguageConfig
        fields = ['available_languages', 'enabled_languages', 'default_language', 'updated_at']

    def get_available_languages(self, _obj):
        return LanguageConfig.options()


class LanguageConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageConfig
        fields = ['enabled_languages', 'default_language']
        extra_kwargs = {f: {'required': False} for f in ['enabled_languages', 'default_language']}

    def validate_enabled_languages(self, value):
        valid = {code for code, _ in LanguageConfig.LANGUAGE_CHOICES}
        clean = []
        for code in value:
            normalized = str(code).upper()
            if normalized not in valid:
                raise serializers.ValidationError(f'Unsupported language code: {code}')
            if normalized not in clean:
                clean.append(normalized)
        if not clean:
            raise serializers.ValidationError('At least one language must be enabled.')
        return clean

    def validate_default_language(self, value):
        normalized = str(value).upper()
        valid = {code for code, _ in LanguageConfig.LANGUAGE_CHOICES}
        if normalized not in valid:
            raise serializers.ValidationError(f'Unsupported language code: {value}')
        return normalized

    def validate(self, attrs):
        enabled = attrs.get('enabled_languages', getattr(self.instance, 'enabled_languages', []))
        default = attrs.get('default_language', getattr(self.instance, 'default_language', LanguageConfig.ENGLISH))
        if enabled and default not in enabled:
            raise serializers.ValidationError({'default_language': 'Default language must be enabled.'})
        return attrs


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
