from rest_framework import serializers
from .models import BlockedIP, BlockedDevice, RateLimitViolation, RequestLog, SecurityConfig


class BlockedIPSerializer(serializers.ModelSerializer):
    blocked_by_name = serializers.CharField(source='blocked_by.name', read_only=True, default=None)

    class Meta:
        model = BlockedIP
        fields = [
            'id', 'ip', 'reason', 'is_permanent', 'expires_at',
            'blocked_by', 'blocked_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'blocked_by', 'blocked_by_name', 'created_at']


class BlockedDeviceSerializer(serializers.ModelSerializer):
    blocked_by_name  = serializers.CharField(source='blocked_by.name', read_only=True, default=None)
    signature_short  = serializers.SerializerMethodField()

    class Meta:
        model = BlockedDevice
        fields = [
            'id', 'device_signature', 'signature_short', 'ip', 'user_agent',
            'reason', 'is_permanent', 'expires_at',
            'blocked_by', 'blocked_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'signature_short', 'blocked_by', 'blocked_by_name', 'created_at']

    def get_signature_short(self, obj):
        return obj.device_signature[:8] + '…'


class RateLimitViolationSerializer(serializers.ModelSerializer):
    signature_short = serializers.SerializerMethodField()

    class Meta:
        model = RateLimitViolation
        fields = [
            'id', 'device_signature', 'signature_short', 'ip', 'user_agent',
            'violation_count', 'first_violation', 'last_violation',
        ]

    def get_signature_short(self, obj):
        return obj.device_signature[:8] + '…'


class RequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestLog
        fields = [
            'id', 'ip', 'device_signature', 'path', 'method',
            'status_code', 'response_time_ms', 'user_agent', 'country_code', 'created_at',
        ]


class SecurityConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityConfig
        fields = ['rate_limit_requests', 'rate_limit_window', 'auto_block_threshold', 'updated_at']
        read_only_fields = ['updated_at']
