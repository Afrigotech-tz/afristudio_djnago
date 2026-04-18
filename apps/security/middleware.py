import time
import threading
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class IPSecurityMiddleware:
    """
    1. Blocks IPs in the BlockedIP table (cached 30s per IP).
    2. Rate-limits per IP using a fixed-window counter in Django cache.
    3. Auto-blocks IPs that exceed SECURITY_AUTO_BLOCK_THRESHOLD violations.
    4. Logs every API request asynchronously to RequestLog.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = getattr(settings, 'SECURITY_RATE_LIMIT_REQUESTS', 120)
        self.window = getattr(settings, 'SECURITY_RATE_LIMIT_WINDOW', 60)
        self.auto_block_threshold = getattr(settings, 'SECURITY_AUTO_BLOCK_THRESHOLD', 10)

    def __call__(self, request):
        ip = _get_client_ip(request)
        request.client_ip = ip

        # Skip static/media files — only police API and frontend paths
        path = request.path
        skip = path.startswith('/static/') or path.startswith('/media/')
        if not skip:
            if self._is_blocked(ip):
                return JsonResponse(
                    {'detail': 'Access denied. Your IP address has been blocked.'},
                    status=403,
                )
            if not self._check_rate_limit(ip):
                self._record_violation_async(ip)
                return JsonResponse(
                    {'detail': 'Too many requests. Please slow down and try again.'},
                    status=429,
                )

        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Only log /api/ requests to keep DB manageable
        if path.startswith('/api/'):
            self._log_async(ip, request, response.status_code, elapsed_ms,
                            request.META.get('HTTP_USER_AGENT', '')[:500])

        return response

    # ── helpers ──────────────────────────────────────────────────────────────

    def _is_blocked(self, ip):
        cache_key = f'ip_blocked:{ip}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        from .models import BlockedIP
        from django.db.models import Q
        blocked = BlockedIP.objects.filter(ip=ip).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).exists()
        cache.set(cache_key, blocked, 30)  # cache result 30s
        return blocked

    def _check_rate_limit(self, ip):
        window_slot = int(time.time() / self.window)
        key = f'rl:{ip}:{window_slot}'
        count = cache.get(key, 0)
        if count >= self.rate_limit:
            return False
        cache.set(key, count + 1, self.window * 2)
        return True

    def _record_violation_async(self, ip):
        def run():
            try:
                from .models import RateLimitViolation, BlockedIP
                now = timezone.now()
                obj, created = RateLimitViolation.objects.get_or_create(
                    ip=ip,
                    defaults={'first_violation': now, 'last_violation': now, 'violation_count': 1},
                )
                if not created:
                    RateLimitViolation.objects.filter(pk=obj.pk).update(
                        violation_count=obj.violation_count + 1,
                        last_violation=now,
                    )
                    obj.refresh_from_db()

                if obj.violation_count >= self.auto_block_threshold:
                    _, new_block = BlockedIP.objects.get_or_create(
                        ip=ip,
                        defaults={
                            'reason': (
                                f'Auto-blocked after {obj.violation_count} '
                                f'rate-limit violations.'
                            ),
                            'is_permanent': True,
                        },
                    )
                    if new_block:
                        # Invalidate the blocked-IP cache immediately
                        cache.set(f'ip_blocked:{ip}', True, 30)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _log_async(self, ip, request, status_code, elapsed_ms, user_agent):
        method = request.method
        path = request.path[:500]

        def run():
            try:
                from .models import RequestLog
                RequestLog.objects.create(
                    ip=ip,
                    path=path,
                    method=method,
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                    user_agent=user_agent,
                )
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()
