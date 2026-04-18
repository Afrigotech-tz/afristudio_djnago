import time
import threading
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone

from .models import compute_device_signature


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class IPSecurityMiddleware:
    """
    Two-layer security:

    Layer 1 — IP block  : rejects every device behind a blocked IP (network ban).
    Layer 2 — Device block: rejects a specific browser/client by its header
                            fingerprint, leaving other devices on the same IP free.

    Rate limiting and auto-blocking operate at the DEVICE level so that one
    misbehaving client behind a shared NAT cannot affect others.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _cfg(self):
        try:
            from .models import SecurityConfig
            return SecurityConfig.get()
        except Exception:
            pass

        class _Fallback:
            rate_limit_requests  = getattr(settings, 'SECURITY_RATE_LIMIT_REQUESTS', 120)
            rate_limit_window    = getattr(settings, 'SECURITY_RATE_LIMIT_WINDOW', 60)
            auto_block_threshold = getattr(settings, 'SECURITY_AUTO_BLOCK_THRESHOLD', 10)
        return _Fallback()

    def __call__(self, request):
        path = request.path
        skip = path.startswith('/static/') or path.startswith('/media/')

        if not skip:
            ip  = _get_client_ip(request)
            sig = compute_device_signature(request)
            ua  = request.META.get('HTTP_USER_AGENT', '')[:500]

            request.client_ip        = ip
            request.device_signature = sig

            # ── Layer 1: IP-level block ──────────────────────────────────────
            if self._is_ip_blocked(ip):
                return JsonResponse(
                    {'detail': 'Access denied. Your network has been blocked.'},
                    status=403,
                )

            # ── Layer 2: Device-level block ──────────────────────────────────
            if self._is_device_blocked(sig):
                return JsonResponse(
                    {'detail': 'Access denied. This device has been blocked.'},
                    status=403,
                )

            # ── Rate limiting (per device) ───────────────────────────────────
            if not self._check_rate_limit(sig):
                self._record_violation_async(ip, sig, ua)
                return JsonResponse(
                    {'detail': 'Too many requests. Please slow down and try again.'},
                    status=429,
                )
        else:
            request.client_ip        = _get_client_ip(request)
            request.device_signature = ''

        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if path.startswith('/api/'):
            self._log_async(
                request.client_ip,
                getattr(request, 'device_signature', ''),
                request,
                response.status_code,
                elapsed_ms,
                request.META.get('HTTP_USER_AGENT', '')[:500],
            )

        return response

    # ── blocked-IP check (cached 30s) ────────────────────────────────────────

    def _is_ip_blocked(self, ip):
        key = f'ip_blocked:{ip}'
        cached = cache.get(key)
        if cached is not None:
            return cached
        from .models import BlockedIP
        from django.db.models import Q
        blocked = BlockedIP.objects.filter(ip=ip).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).exists()
        cache.set(key, blocked, 30)
        return blocked

    # ── blocked-device check (cached 30s) ────────────────────────────────────

    def _is_device_blocked(self, sig):
        key = f'dev_blocked:{sig}'
        cached = cache.get(key)
        if cached is not None:
            return cached
        from .models import BlockedDevice
        from django.db.models import Q
        blocked = BlockedDevice.objects.filter(device_signature=sig).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).exists()
        cache.set(key, blocked, 30)
        return blocked

    # ── rate limiting (per device signature) ─────────────────────────────────

    def _check_rate_limit(self, sig):
        cfg = self._cfg()
        slot = int(time.time() / cfg.rate_limit_window)
        key  = f'rl:{sig}:{slot}'
        count = cache.get(key, 0)
        if count >= cfg.rate_limit_requests:
            return False
        cache.set(key, count + 1, cfg.rate_limit_window * 2)
        return True

    # ── violation recording + auto-block (device level) ──────────────────────

    def _record_violation_async(self, ip, sig, ua):
        def run():
            try:
                from .models import RateLimitViolation, BlockedDevice
                cfg = self._cfg()
                now = timezone.now()
                obj, created = RateLimitViolation.objects.get_or_create(
                    device_signature=sig,
                    defaults={
                        'ip': ip, 'user_agent': ua,
                        'first_violation': now, 'last_violation': now,
                        'violation_count': 1,
                    },
                )
                if not created:
                    RateLimitViolation.objects.filter(pk=obj.pk).update(
                        ip=ip,
                        violation_count=obj.violation_count + 1,
                        last_violation=now,
                    )
                    obj.refresh_from_db()

                if obj.violation_count >= cfg.auto_block_threshold:
                    _, new_block = BlockedDevice.objects.get_or_create(
                        device_signature=sig,
                        defaults={
                            'ip': ip,
                            'user_agent': ua,
                            'reason': (
                                f'Auto-blocked: {obj.violation_count} rate-limit '
                                f'violations from {ip}.'
                            ),
                            'is_permanent': True,
                        },
                    )
                    if new_block:
                        cache.set(f'dev_blocked:{sig}', True, 30)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    # ── async request logging ─────────────────────────────────────────────────

    def _log_async(self, ip, sig, request, status_code, elapsed_ms, ua):
        method = request.method
        path   = request.path[:500]

        def run():
            try:
                from .models import RequestLog
                RequestLog.objects.create(
                    ip=ip,
                    device_signature=sig,
                    path=path,
                    method=method,
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                    user_agent=ua,
                )
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()
