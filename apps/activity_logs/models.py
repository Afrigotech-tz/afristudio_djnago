"""
activity_logs/models.py
Simple activity log model — equivalent to Spatie's activity_log table.
Stores who did what, on which object, with optional JSON properties.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


class ActivityLog(models.Model):
    log_name = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    description = models.TextField()
    event = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Subject (the object the action was performed on)
    subject_type = models.ForeignKey(
        ContentType,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='subject_activities',
    )
    subject_id = models.PositiveBigIntegerField(null=True, blank=True)
    subject = GenericForeignKey('subject_type', 'subject_id')

    # Causer (the user who performed the action)
    causer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activities',
    )

    properties = models.JSONField(null=True, blank=True)
    batch_uuid = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.log_name}] {self.description}"
