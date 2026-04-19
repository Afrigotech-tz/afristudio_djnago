"""
accounts/serializers.py
Equivalent to Laravel's Form Requests + API Resources for auth & profile.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from .models import Profile

User = get_user_model()


# ──────────────────────────────────────────────
# User serializer  (read — replaces UserResource)
# ──────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['uuid', 'name', 'email', 'phone', 'verified_at', 'roles', 'permissions']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, obj):
        return obj.get_role_names()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, obj):
        return obj.get_all_permissions_list()


# ──────────────────────────────────────────────
# Register  (replaces validation in AuthController::register)
# ──────────────────────────────────────────────
class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email') or None
        phone = attrs.get('phone') or None

        if not email and not phone:
            raise serializers.ValidationError(
                'We need an email if no phone is provided.'
            )
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'Oops! This email is already in our auction system.'})
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({'phone': 'This phone number is already in use to an account.'})

        attrs['email'] = email
        attrs['phone'] = phone
        return attrs


# ──────────────────────────────────────────────
# Verify Account
# ──────────────────────────────────────────────
class VerifyAccountSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)


# ──────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────
class LoginSerializer(serializers.Serializer):
    login = serializers.CharField()   # email or phone
    password = serializers.CharField(write_only=True)


# ──────────────────────────────────────────────
# Forgot / Reset Password
# ──────────────────────────────────────────────
class ForgotPasswordSerializer(serializers.Serializer):
    login = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    login = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(min_length=8, write_only=True)
    password_confirmation = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs


# ──────────────────────────────────────────────
# Profile serializers  (replaces ProfileResource + UpdateProfileRequest)
# ──────────────────────────────────────────────
class ProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['uuid', 'bio', 'avatar_url', 'address', 'city', 'created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.URI)
    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class UpdateProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ['bio', 'address', 'city', 'avatar']


class UpdateUserSerializer(serializers.ModelSerializer):
    """Allows an authenticated user to update their own name, email, and phone."""
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = ['name', 'email', 'phone']

    def validate_email(self, value):
        value = value or None
        if value:
            qs = User.objects.filter(email=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('This email is already taken.')
        return value

    def validate_phone(self, value):
        value = value or None
        if value:
            qs = User.objects.filter(phone=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('This phone number is already taken.')
        return value

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save(update_fields=list(validated_data.keys()) + ['updated_at'])
        return instance


# ──────────────────────────────────────────────
# Address serializers
# ──────────────────────────────────────────────
from .models import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'label', 'full_name', 'phone', 'address', 'city', 'country', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_default', 'created_at', 'updated_at']


class AddressWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['label', 'full_name', 'phone', 'address', 'city', 'country']
