"""
notifications/views.py

GET  /api/notifications/          — list logs (staff/admin only), supports ?status=&channel=&search=
POST /api/notifications/<id>/resend/ — resend a specific notification (staff/admin only)
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import NotificationLog
from apps.accounts.permissions import IsAdminOrStaff


class NotificationLogListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(
        tags=['Notifications'],
        summary='List notification logs (admin/staff only)',
        parameters=[
            OpenApiParameter('status',  str, description='Filter: sent | failed'),
            OpenApiParameter('channel', str, description='Filter: email | sms'),
            OpenApiParameter('search',  str, description='Search recipient or subject'),
        ],
    )
    def get(self, request):
        qs = NotificationLog.objects.select_related('causer').all()

        status_filter = request.query_params.get('status')
        if status_filter in (NotificationLog.STATUS_SENT, NotificationLog.STATUS_FAILED):
            qs = qs.filter(status=status_filter)

        channel_filter = request.query_params.get('channel')
        if channel_filter in (NotificationLog.CHANNEL_EMAIL, NotificationLog.CHANNEL_SMS):
            qs = qs.filter(channel=channel_filter)

        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(recipient__icontains=search) | Q(subject__icontains=search))

        qs = qs[:500]

        data = [
            {
                'id':         log.id,
                'channel':    log.channel,
                'recipient':  log.recipient,
                'subject':    log.subject,
                'message':    log.message,
                'status':     log.status,
                'error':      log.error,
                'causer_name': log.causer.name if log.causer else None,
                'sent_at':    log.sent_at.isoformat(),
            }
            for log in qs
        ]
        return Response(data)


class NotificationResendView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(
        tags=['Notifications'],
        summary='Resend a notification (admin/staff only)',
    )
    def post(self, request, pk):
        log = get_object_or_404(NotificationLog, pk=pk)

        from .service import notify
        success = notify(
            to_email=log.recipient if log.channel == NotificationLog.CHANNEL_EMAIL else None,
            to_phone=log.recipient if log.channel == NotificationLog.CHANNEL_SMS else None,
            subject=log.subject or '',
            message=log.message,
            channel=log.channel,
            causer=request.user,
        )

        if success:
            return Response({'detail': 'Notification resent successfully.'})
        return Response(
            {'detail': 'Resend attempt failed. Check the new log entry for details.'},
            status=http_status.HTTP_502_BAD_GATEWAY,
        )
