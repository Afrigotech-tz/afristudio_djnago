"""
accounts/admin_serializers.py
Serializers for the admin role/permission management API.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    content_type = serializers.StringRelatedField()

    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'content_type']


class RoleSerializer(serializers.ModelSerializer):
    """Read serializer — includes all permissions assigned to this role."""
    permissions = PermissionSerializer(many=True, read_only=True)
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'users_count']

    @extend_schema_field(serializers.IntegerField())
    def get_users_count(self, obj):
        return obj.user_set.count()


class RoleWriteSerializer(serializers.ModelSerializer):
    """Write serializer — accepts permission IDs."""
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source='permissions',
    )

    class Meta:
        model = Group
        fields = ['name', 'permission_ids']

    def validate_name(self, value):
        qs = Group.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A role with this name already exists.')
        return value

    def create(self, validated_data):
        permissions = validated_data.pop('permissions', [])
        group = Group.objects.create(**validated_data)
        if permissions:
            group.permissions.set(permissions)
        return group

    def update(self, instance, validated_data):
        permissions = validated_data.pop('permissions', None)
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance


class AssignRoleSerializer(serializers.Serializer):
    """Assign or remove a role from a user."""
    role_name = serializers.CharField()


class AdminUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    direct_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'uuid', 'name', 'email', 'phone', 'is_staff', 'is_active',
            'verified_at', 'bidding_banned_until',
            'roles', 'permissions', 'direct_permissions', 'created_at',
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, obj):
        return obj.get_role_names()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, obj):
        return obj.get_all_permissions_list()

    @extend_schema_field(PermissionSerializer(many=True))
    def get_direct_permissions(self, obj):
        return PermissionSerializer(
            obj.user_permissions.select_related('content_type').all(),
            many=True,
        ).data


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer for admin full user update.
    Allows updating name, email, phone, is_staff, is_active.
    Validates uniqueness excluding the current instance.
    """
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = ['name', 'email', 'phone', 'is_staff', 'is_active']

    def validate_email(self, value):
        value = value or None
        if value:
            qs = User.objects.filter(email=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('This email is already in use by another account.')
        return value

    def validate_phone(self, value):
        value = value or None
        if value:
            qs = User.objects.filter(phone=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('This phone number is already in use by another account.')
        return value

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save(update_fields=list(validated_data.keys()) + ['updated_at'])
        return instance
