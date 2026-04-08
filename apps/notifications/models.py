"""
notifications/models.py
Tracks every notification sent through the system (email or SMS).
"""

from django.db import models
from django.conf import settings


class NotificationLog(models.Model):
    CHANNEL_EMAIL = 'email'
    CHANNEL_SMS = 'sms'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
    ]

    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    # Who triggered this (optional — system notifications may have no user)
    causer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='sent_notifications',
    )

    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, db_index=True)
    recipient = models.CharField(max_length=255, help_text='Email address or phone number')
    subject = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SENT, db_index=True)
    error = models.TextField(null=True, blank=True, help_text='Error detail if delivery failed')

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notification_logs'
        ordering = ['-sent_at']

    def __str__(self):
        return f"[{self.channel}] {self.recipient} — {self.status}"
