from django.db import models
from django.conf import settings
from django.utils import timezone


class BlockedIP(models.Model):
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


class RateLimitViolation(models.Model):
    ip = models.GenericIPAddressField(unique=True, db_index=True)
    violation_count = models.PositiveIntegerField(default=1)
    first_violation = models.DateTimeField()
    last_violation = models.DateTimeField()

    class Meta:
        ordering = ['-last_violation']
        verbose_name = 'Rate Limit Violation'

    def __str__(self):
        return f'{self.ip} — {self.violation_count} violations'


class RequestLog(models.Model):
    METHOD_CHOICES = [
        ('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'),
        ('PATCH', 'PATCH'), ('DELETE', 'DELETE'), ('OPTIONS', 'OPTIONS'),
    ]

    ip = models.GenericIPAddressField(db_index=True)
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, db_index=True)
    status_code = models.PositiveSmallIntegerField(null=True, db_index=True)
    response_time_ms = models.PositiveIntegerField(null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Request Log'
        indexes = [
            models.Index(fields=['created_at', 'status_code']),
            models.Index(fields=['ip', 'created_at']),
        ]

    def __str__(self):
        return f'{self.method} {self.path} [{self.status_code}] from {self.ip}'
