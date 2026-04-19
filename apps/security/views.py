from datetime import timedelta

from django.db.models import Count, Avg, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, inline_serializer
import rest_framework.serializers as s

from .models import BlockedIP, BlockedDevice, RateLimitViolation, RequestLog, SecurityConfig
from .serializers import (
    BlockedIPSerializer, BlockedDeviceSerializer,
    RateLimitViolationSerializer, SecurityConfigSerializer,
)


def _require_admin(request):
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


# ── Blocked IPs ───────────────────────────────────────────────────────────────

class BlockedIPListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='List blocked IPs', responses={200: BlockedIPSerializer(many=True)})
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = BlockedIP.objects.select_related('blocked_by').order_by('-created_at')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(ip__icontains=search)
        return Response(BlockedIPSerializer(qs, many=True).data)

    @extend_schema(tags=['Security'], summary='Block an IP address',
                   request=BlockedIPSerializer, responses={201: BlockedIPSerializer})
    def post(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ser = BlockedIPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ip = ser.validated_data['ip']
        obj, created = BlockedIP.objects.get_or_create(
            ip=ip,
            defaults={
                'reason': ser.validated_data.get('reason', ''),
                'is_permanent': ser.validated_data.get('is_permanent', True),
                'expires_at': ser.validated_data.get('expires_at'),
                'blocked_by': request.user,
            },
        )
        if not created:
            return Response(
                {'detail': f'IP {ip} is already blocked.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        from django.core.cache import cache
        cache.set(f'ip_blocked:{ip}', True, 30)
        return Response(BlockedIPSerializer(obj).data, status=status.HTTP_201_CREATED)


class BlockedIPBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Bulk-delete blocked IPs',
                   request=inline_serializer('BulkDeleteIds', {'ids': s.ListField(child=s.IntegerField())}),
                   responses={204: None})
    def delete(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'detail': 'No ids provided.'}, status=status.HTTP_400_BAD_REQUEST)
        ips = list(BlockedIP.objects.filter(pk__in=ids).values_list('ip', flat=True))
        BlockedIP.objects.filter(pk__in=ids).delete()
        from django.core.cache import cache
        for ip in ips:
            cache.delete(f'ip_blocked:{ip}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockedIPDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Get a blocked IP', responses={200: BlockedIPSerializer})
    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = BlockedIP.objects.get(pk=pk)
        except BlockedIP.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BlockedIPSerializer(obj).data)

    @extend_schema(tags=['Security'], summary='Unblock an IP', responses={204: None})
    def delete(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = BlockedIP.objects.get(pk=pk)
        except BlockedIP.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ip = obj.ip
        obj.delete()
        from django.core.cache import cache
        cache.delete(f'ip_blocked:{ip}')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Blocked Devices ──────────────────────────────────────────────────────────

class BlockedDeviceListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='List blocked devices',
                   responses={200: BlockedDeviceSerializer(many=True)})
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = BlockedDevice.objects.select_related('blocked_by').order_by('-created_at')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(ip__icontains=search) | qs.filter(device_signature__icontains=search)
        return Response(BlockedDeviceSerializer(qs, many=True).data)


class BlockedDeviceBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Bulk-delete blocked devices',
                   request=inline_serializer('BulkDeleteDeviceIds', {'ids': s.ListField(child=s.IntegerField())}),
                   responses={204: None})
    def delete(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'detail': 'No ids provided.'}, status=status.HTTP_400_BAD_REQUEST)
        sigs = list(BlockedDevice.objects.filter(pk__in=ids).values_list('device_signature', flat=True))
        BlockedDevice.objects.filter(pk__in=ids).delete()
        from django.core.cache import cache
        for sig in sigs:
            cache.delete(f'dev_blocked:{sig}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockedDeviceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Unblock a device', responses={204: None})
    def delete(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = BlockedDevice.objects.get(pk=pk)
        except BlockedDevice.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        sig = obj.device_signature
        obj.delete()
        from django.core.cache import cache
        cache.delete(f'dev_blocked:{sig}')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Rate-Limit Violations ─────────────────────────────────────────────────────

class RateLimitViolationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='List rate-limit violations',
                   responses={200: RateLimitViolationSerializer(many=True)})
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = RateLimitViolation.objects.order_by('-last_violation')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(ip__icontains=search)
        return Response(RateLimitViolationSerializer(qs[:200], many=True).data)


class RateLimitViolationBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Bulk-delete rate-limit violations',
                   request=inline_serializer('BulkDeleteViolationIds', {'ids': s.ListField(child=s.IntegerField())}),
                   responses={204: None})
    def delete(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'detail': 'No ids provided.'}, status=status.HTTP_400_BAD_REQUEST)
        RateLimitViolation.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RateLimitViolationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Delete a violation record', responses={204: None})
    def delete(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        RateLimitViolation.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=['Security'],
        summary='Block the specific device behind this violation (not the whole IP)',
        responses={200: BlockedDeviceSerializer, 201: BlockedDeviceSerializer},
    )
    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            v = RateLimitViolation.objects.get(pk=pk)
        except RateLimitViolation.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj, created = BlockedDevice.objects.get_or_create(
            device_signature=v.device_signature,
            defaults={
                'ip':         v.ip,
                'user_agent': v.user_agent,
                'reason':     f'Blocked from violation record ({v.violation_count} violations).',
                'is_permanent': True,
                'blocked_by': request.user,
            },
        )
        from django.core.cache import cache
        cache.set(f'dev_blocked:{v.device_signature}', True, 30)
        return Response(
            BlockedDeviceSerializer(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ── Security Config ───────────────────────────────────────────────────────────

class SecurityConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Get rate-limit config', responses={200: SecurityConfigSerializer})
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        obj, _ = SecurityConfig.objects.get_or_create(pk=1)
        return Response(SecurityConfigSerializer(obj).data)

    @extend_schema(tags=['Security'], summary='Update rate-limit config',
                   request=SecurityConfigSerializer, responses={200: SecurityConfigSerializer})
    def patch(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        obj, _ = SecurityConfig.objects.get_or_create(pk=1)
        ser = SecurityConfigSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ── Stats ─────────────────────────────────────────────────────────────────────

_StatsSerializer = inline_serializer(
    name='SecurityStatsResponse',
    fields={
        'summary': inline_serializer(name='SecurityStatsSummary', fields={
            'total_requests_today': s.IntegerField(),
            'total_requests_week':  s.IntegerField(),
            'avg_response_time_ms': s.FloatField(),
            'error_rate_percent':   s.FloatField(),
            'blocked_ips':          s.IntegerField(),
            'violations':           s.IntegerField(),
        }),
        'requests_by_method': inline_serializer(name='MethodCount', fields={
            'method': s.CharField(), 'count': s.IntegerField(),
        }, many=True),
        'requests_hourly': inline_serializer(name='HourlyCount', fields={
            'hour': s.CharField(), 'count': s.IntegerField(),
        }, many=True),
        'status_distribution': inline_serializer(name='StatusCount', fields={
            'status_code': s.IntegerField(allow_null=True), 'count': s.IntegerField(),
        }, many=True),
        'top_paths': inline_serializer(name='TopPath', fields={
            'path': s.CharField(), 'method': s.CharField(),
            'count': s.IntegerField(), 'avg_ms': s.FloatField(allow_null=True),
        }, many=True),
        'top_ips': inline_serializer(name='TopIP', fields={
            'ip': s.CharField(), 'count': s.IntegerField(),
            'avg_ms': s.FloatField(allow_null=True), 'is_blocked': s.BooleanField(),
        }, many=True),
        'recent_violations': inline_serializer(name='RecentViolation', fields={
            'ip': s.CharField(), 'violation_count': s.IntegerField(),
            'last_violation': s.DateTimeField(),
        }, many=True),
        'recent_blocked': inline_serializer(name='RecentBlocked', fields={
            'ip': s.CharField(), 'reason': s.CharField(),
            'is_permanent': s.BooleanField(), 'created_at': s.DateTimeField(),
        }, many=True),
    },
)


class SecurityStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Security'], summary='Performance & security stats', responses={200: _StatsSerializer})
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)

        total_today = RequestLog.objects.filter(created_at__gte=today_start).count()
        total_week  = RequestLog.objects.filter(created_at__gte=week_start).count()

        avg_rt = (
            RequestLog.objects.filter(created_at__gte=today_start)
            .aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        )

        errors_today = RequestLog.objects.filter(
            created_at__gte=today_start, status_code__gte=400
        ).count()
        error_rate = round((errors_today / total_today * 100) if total_today else 0, 1)

        status_dist = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('status_code')
            .annotate(count=Count('id'))
            .order_by('status_code')
        )

        by_method = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('method')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        hourly = []
        for h in range(23, -1, -1):
            bucket_start = now - timedelta(hours=h + 1)
            bucket_end   = now - timedelta(hours=h)
            cnt = RequestLog.objects.filter(
                created_at__gte=bucket_start,
                created_at__lt=bucket_end,
            ).count()
            hourly.append({'hour': bucket_start.strftime('%H:00'), 'count': cnt})

        top_paths = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('path', 'method')
            .annotate(count=Count('id'), avg_ms=Avg('response_time_ms'))
            .order_by('-count')[:15]
        )

        top_ips = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('ip')
            .annotate(count=Count('id'), avg_ms=Avg('response_time_ms'))
            .order_by('-count')[:20]
        )
        blocked_set = set(
            BlockedIP.objects.filter(ip__in=[r['ip'] for r in top_ips]).values_list('ip', flat=True)
        )
        for row in top_ips:
            row['is_blocked'] = row['ip'] in blocked_set

        blocked_count    = BlockedIP.objects.filter(Q(is_permanent=True) | Q(expires_at__gt=now)).count()
        blocked_devices  = BlockedDevice.objects.filter(Q(is_permanent=True) | Q(expires_at__gt=now)).count()
        violations_count = RateLimitViolation.objects.count()
        recent_violations = list(
            RateLimitViolation.objects.order_by('-last_violation')
            .values('ip', 'violation_count', 'last_violation')[:10]
        )
        recent_blocked = list(
            BlockedIP.objects.order_by('-created_at')
            .values('ip', 'reason', 'is_permanent', 'created_at')[:10]
        )

        return Response({
            'summary': {
                'total_requests_today': total_today,
                'total_requests_week':  total_week,
                'avg_response_time_ms': round(avg_rt, 1),
                'error_rate_percent':   error_rate,
                'blocked_ips':          blocked_count,
                'blocked_devices':      blocked_devices,
                'violations':           violations_count,
            },
            'requests_by_method':  by_method,
            'requests_hourly':     hourly,
            'status_distribution': status_dist,
            'top_paths':           top_paths,
            'top_ips':             top_ips,
            'recent_violations':   recent_violations,
            'recent_blocked':      recent_blocked,
        })


# ── Error Requests ────────────────────────────────────────────────────────────

_ErrorLogSerializer = inline_serializer(
    name='ErrorRequestLog',
    many=True,
    fields={
        'id':               s.IntegerField(),
        'ip':               s.CharField(),
        'method':           s.CharField(),
        'path':             s.CharField(),
        'status_code':      s.IntegerField(allow_null=True),
        'response_time_ms': s.IntegerField(allow_null=True),
        'user_agent':       s.CharField(),
        'created_at':       s.DateTimeField(),
    },
)


class ErrorRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Security'],
        summary='Recent requests with 4xx / 5xx status codes',
        responses={200: _ErrorLogSerializer},
    )
    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        now        = timezone.now()
        since_days = int(request.query_params.get('days', 1))
        since      = now - timedelta(days=since_days)
        min_status = int(request.query_params.get('min_status', 400))
        search     = request.query_params.get('search', '').strip()
        limit      = min(int(request.query_params.get('limit', 200)), 500)

        qs = RequestLog.objects.filter(
            created_at__gte=since,
            status_code__gte=min_status,
        ).order_by('-created_at')

        if search:
            qs = qs.filter(
                Q(ip__icontains=search) |
                Q(path__icontains=search) |
                Q(method__icontains=search)
            )

        rows = list(
            qs.values('id', 'ip', 'method', 'path', 'status_code', 'response_time_ms', 'user_agent', 'created_at')[:limit]
        )
        return Response(rows)
