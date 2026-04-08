from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    subject = serializers.SerializerMethodField()
    causer_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'log_name', 'description', 'event',
            'subject_type', 'subject_id', 'subject',
            'causer', 'causer_name',
            'properties',
            'created_at', 'updated_at',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_subject(self, obj):
        if obj.subject:
            return getattr(obj.subject, 'name', None) or getattr(obj.subject, 'email', None)
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_causer_name(self, obj):
        if obj.causer:
            return obj.causer.name or obj.causer.email
        return None
