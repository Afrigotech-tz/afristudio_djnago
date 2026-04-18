from rest_framework import serializers
from .models import BlockedIP, RateLimitViolation, RequestLog


class BlockedIPSerializer(serializers.ModelSerializer):
    blocked_by_name = serializers.CharField(source='blocked_by.name', read_only=True, default=None)

    class Meta:
        model = BlockedIP
        fields = [
            'id', 'ip', 'reason', 'is_permanent', 'expires_at',
            'blocked_by', 'blocked_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'blocked_by', 'blocked_by_name', 'created_at']


class RateLimitViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimitViolation
        fields = ['id', 'ip', 'violation_count', 'first_violation', 'last_violation']


class RequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestLog
        fields = ['id', 'ip', 'path', 'method', 'status_code',
                  'response_time_ms', 'user_agent', 'country_code', 'created_at']
