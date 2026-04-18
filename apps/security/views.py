from datetime import timedelta

from django.db.models import Count, Avg, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import BlockedIP, RateLimitViolation, RequestLog
from .serializers import BlockedIPSerializer, RateLimitViolationSerializer


def _require_admin(request):
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


class BlockedIPListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = BlockedIP.objects.select_related('blocked_by').order_by('-created_at')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(ip__icontains=search)
        return Response(BlockedIPSerializer(qs, many=True).data)

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
        # Bust cache
        from django.core.cache import cache
        cache.set(f'ip_blocked:{ip}', True, 30)
        return Response(BlockedIPSerializer(obj).data, status=status.HTTP_201_CREATED)


class BlockedIPDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = BlockedIP.objects.get(pk=pk)
        except BlockedIP.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BlockedIPSerializer(obj).data)

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


class RateLimitViolationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = RateLimitViolation.objects.order_by('-last_violation')[:100]
        return Response(RateLimitViolationSerializer(qs, many=True).data)

    def delete(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        RateLimitViolation.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SecurityStatsView(APIView):
    """Aggregated performance and security stats for the admin performance dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        day_ago = now - timedelta(hours=24)

        # ── totals ────────────────────────────────────────────────────────────
        total_today = RequestLog.objects.filter(created_at__gte=today_start).count()
        total_week = RequestLog.objects.filter(created_at__gte=week_start).count()

        # ── response time ─────────────────────────────────────────────────────
        avg_rt = (
            RequestLog.objects.filter(created_at__gte=today_start)
            .aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        )

        # ── error rate ────────────────────────────────────────────────────────
        errors_today = RequestLog.objects.filter(
            created_at__gte=today_start, status_code__gte=400
        ).count()
        error_rate = round((errors_today / total_today * 100) if total_today else 0, 1)

        # ── status code distribution ─────────────────────────────────────────
        status_dist = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('status_code')
            .annotate(count=Count('id'))
            .order_by('status_code')
        )

        # ── requests by method ────────────────────────────────────────────────
        by_method = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('method')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # ── requests per hour (last 24h) ──────────────────────────────────────
        # Build 24 buckets
        hourly = []
        for h in range(23, -1, -1):
            bucket_start = now - timedelta(hours=h + 1)
            bucket_end = now - timedelta(hours=h)
            cnt = RequestLog.objects.filter(
                created_at__gte=bucket_start,
                created_at__lt=bucket_end,
            ).count()
            hourly.append({
                'hour': bucket_start.strftime('%H:00'),
                'count': cnt,
            })

        # ── top paths ─────────────────────────────────────────────────────────
        top_paths = list(
            RequestLog.objects.filter(created_at__gte=today_start)
            .values('path', 'method')
            .annotate(count=Count('id'), avg_ms=Avg('response_time_ms'))
            .order_by('-count')[:15]
        )

        # ── security ─────────────────────────────────────────────────────────
        blocked_count = BlockedIP.objects.filter(
            Q(is_permanent=True) | Q(expires_at__gt=now)
        ).count()
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
                'total_requests_week': total_week,
                'avg_response_time_ms': round(avg_rt, 1),
                'error_rate_percent': error_rate,
                'blocked_ips': blocked_count,
                'violations': violations_count,
            },
            'requests_by_method': by_method,
            'requests_hourly': hourly,
            'status_distribution': status_dist,
            'top_paths': top_paths,
            'recent_violations': recent_violations,
            'recent_blocked': recent_blocked,
        })
