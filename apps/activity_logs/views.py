"""
activity_logs/views.py
Equivalent to Laravel's ActivityLogController::index
GET /api/activity-logs/  (auth required)
Supports: search, log_name, event, causer_email filters + pagination
"""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import ActivityLog
from .serializers import ActivityLogSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Activity Logs'],
        summary='List activity logs',
        description=(
            'Returns a paginated, reverse-chronological list of all system activity events. '
            'Supports filtering by keyword search, log channel, event type, and causer email. '
            '**Requires authentication.**'
        ),
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Full-text search across `description` and `log_name`.',
                required=False,
            ),
            OpenApiParameter(
                name='log_name',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by log channel name (e.g. `auth`, `artworks`, `categories`, `currencies`).',
                required=False,
            ),
            OpenApiParameter(
                name='event',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by event type (e.g. `login`, `created`, `updated`, `deleted`, `verified`).',
                required=False,
            ),
            OpenApiParameter(
                name='causer_email',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by partial email of the user who triggered the event.',
                required=False,
            ),
            OpenApiParameter(
                name='page',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Page number (default: 1).',
                required=False,
            ),
            OpenApiParameter(
                name='page_size',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results per page (default: 20).',
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(response=ActivityLogSerializer(many=True), description='Paginated activity logs.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
    ),
)
class ActivityLogListView(generics.ListAPIView):
    """
    GET /api/activity-logs/
    Query params: search, log_name, event, causer_email, page, page_size
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ActivityLog.objects.select_related('causer', 'subject_type').order_by('-created_at')

        search = self.request.query_params.get('search')
        log_name = self.request.query_params.get('log_name')
        event = self.request.query_params.get('event')
        causer_email = self.request.query_params.get('causer_email')

        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(log_name__icontains=search)
            )

        if log_name:
            qs = qs.filter(log_name=log_name)

        if event:
            qs = qs.filter(event=event)

        if causer_email:
            qs = qs.filter(causer__email__icontains=causer_email)

        return qs
