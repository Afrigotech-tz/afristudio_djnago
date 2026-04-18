import hashlib

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache


SECURITY_CONFIG_CACHE_KEY = 'security:config'


def compute_device_signature(request) -> str:
    """
    SHA-256 of stable HTTP headers that identify a browser/client.
    Devices behind the same NAT share an IP but differ in UA, language, etc.
    This hash lets us block one device without affecting its neighbours.
    """
    raw = '|'.join([
        request.META.get('HTTP_USER_AGENT', ''),
        request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
        request.META.get('HTTP_ACCEPT_ENCODING', ''),
        request.META.get('HTTP_ACCEPT', ''),
        request.META.get('HTTP_SEC_CH_UA', ''),           # Chrome client hints
        request.META.get('HTTP_SEC_CH_UA_PLATFORM', ''),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class SecurityConfig(models.Model):
    """Singleton — one row (pk=1). Middleware reads this with a 60s cache."""
    rate_limit_requests  = models.PositiveIntegerField(default=120, help_text='Max requests per device per window')
    rate_limit_window    = models.PositiveIntegerField(default=60,  help_text='Window size in seconds')
    auto_block_threshold = models.PositiveIntegerField(default=10,  help_text='Violations before auto-block')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Security Config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SECURITY_CONFIG_CACHE_KEY)

    @classmethod
    def get(cls):
        cached = cache.get(SECURITY_CONFIG_CACHE_KEY)
        if cached:
            return cached
        obj, _ = cls.objects.get_or_create(pk=1)
        cache.set(SECURITY_CONFIG_CACHE_KEY, obj, 60)
        return obj


class BlockedIP(models.Model):
    """Network-level block — stops every device behind this IP."""
    ip = models.GenericIPAddressField(unique=True, db_index=True)
    reason = models.TextField(blank=True)
    is_permanent = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='blocked_ips',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blocked IP'
        verbose_name_plural = 'Blocked IPs'

    def __str__(self):
        return f'{self.ip} ({"permanent" if self.is_permanent else "temporary"})'

    @property
    def is_active(self):
        if self.is_permanent:
            return True
        return self.expires_at and self.expires_at > timezone.now()


class BlockedDevice(models.Model):
    """
    Device-level block — stops one specific browser/client identified by its
    header fingerprint while leaving other devices on the same IP unaffected.
    """
    device_signature = models.CharField(max_length=64, unique=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)   # recorded at block time, informational only
    user_agent = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    is_permanent = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='blocked_devices',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blocked Device'

    def __str__(self):
        return f'Device {self.device_signature[:8]}… from {self.ip}'

    @property
    def is_active(self):
        if self.is_permanent:
            return True
        return self.expires_at and self.expires_at > timezone.now()


class RateLimitViolation(models.Model):
    """Tracks per-device rate-limit violations (keyed on device_signature)."""
    device_signature = models.CharField(max_length=64, unique=True, db_index=True, default='')
    ip = models.GenericIPAddressField(null=True, blank=True)   # last-seen IP for display
    user_agent = models.TextField(blank=True)
    violation_count = models.PositiveIntegerField(default=1)
    first_violation = models.DateTimeField()
    last_violation = models.DateTimeField()

    class Meta:
        ordering = ['-last_violation']
        verbose_name = 'Rate Limit Violation'

    def __str__(self):
        return f'{self.ip or self.device_signature[:8]} — {self.violation_count} violations'


class RequestLog(models.Model):
    METHOD_CHOICES = [
        ('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'),
        ('PATCH', 'PATCH'), ('DELETE', 'DELETE'), ('OPTIONS', 'OPTIONS'),
    ]

    ip               = models.GenericIPAddressField(db_index=True)
    device_signature = models.CharField(max_length=64, blank=True, db_index=True)
    path             = models.CharField(max_length=500)
    method           = models.CharField(max_length=10, choices=METHOD_CHOICES, db_index=True)
    status_code      = models.PositiveSmallIntegerField(null=True, db_index=True)
    response_time_ms = models.PositiveIntegerField(null=True)
    user_agent       = models.CharField(max_length=500, blank=True)
    country_code     = models.CharField(max_length=2, blank=True, db_index=True)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Request Log'
        indexes = [
            models.Index(fields=['created_at', 'status_code']),
            models.Index(fields=['ip', 'created_at']),
            models.Index(fields=['device_signature', 'created_at']),
        ]

    def __str__(self):
        return f'{self.method} {self.path} [{self.status_code}] from {self.ip}'
