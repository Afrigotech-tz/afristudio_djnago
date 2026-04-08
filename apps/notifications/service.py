"""
notifications/service.py
Single entry-point for sending notifications across the whole project.

Usage examples:

    from apps.notifications.service import notify

    # Auto-detect channel from user (email if available, else SMS)
    notify(user=user, subject='Verify account', message='Your OTP is 123456')

    # Force a specific channel
    notify(user=user, subject='Welcome', message='Hello!', channel='email')
    notify(user=user, message='Your OTP is 123456', channel='sms')

    # Without a user object (raw recipient)
    notify(to_email='jane@example.com', subject='Hello', message='Hi Jane')
    notify(to_phone='+255712345678', message='Your OTP is 123456')
"""

from .channels.email import send_email
from .channels.sms import send_sms


def notify(
    *,
    user=None,
    subject: str = '',
    message: str,
    channel: str = 'auto',
    to_email: str = None,
    to_phone: str = None,
    causer=None,
) -> bool:
    """
    Send a notification and persist a log entry.

    Args:
        user:       Django user instance — used to resolve recipient & causer.
        subject:    Email subject (ignored for SMS).
        message:    Body of the notification.
        channel:    'auto' | 'email' | 'sms'.
                    'auto' picks email when the user has one, otherwise sms.
        to_email:   Override recipient email (use without `user`).
        to_phone:   Override recipient phone (use without `user`).
        causer:     User who triggered this notification (defaults to `user`).

    Returns:
        True if delivered successfully, False otherwise.
    """
    from .models import NotificationLog  # late import — avoid circular imports

    # ── Resolve recipient & channel ───────────────────────────────────────────
    resolved_channel = channel
    recipient = None

    if to_email:
        recipient = to_email
        resolved_channel = NotificationLog.CHANNEL_EMAIL
    elif to_phone:
        recipient = to_phone
        resolved_channel = NotificationLog.CHANNEL_SMS
    elif user:
        if channel == 'auto':
            if user.email:
                recipient = user.email
                resolved_channel = NotificationLog.CHANNEL_EMAIL
            elif hasattr(user, 'phone') and user.phone:
                recipient = user.phone
                resolved_channel = NotificationLog.CHANNEL_SMS
        elif channel == NotificationLog.CHANNEL_EMAIL:
            recipient = user.email
        elif channel == NotificationLog.CHANNEL_SMS:
            recipient = getattr(user, 'phone', None)

    if not recipient:
        return False

    # ── Deliver ───────────────────────────────────────────────────────────────
    if resolved_channel == NotificationLog.CHANNEL_EMAIL:
        success, error = send_email(to=recipient, subject=subject, message=message)
    else:
        success, error = send_sms(to=recipient, message=message)

    # ── Log ───────────────────────────────────────────────────────────────────
    NotificationLog.objects.create(
        causer=causer or user,
        channel=resolved_channel,
        recipient=recipient,
        subject=subject or None,
        message=message,
        status=NotificationLog.STATUS_SENT if success else NotificationLog.STATUS_FAILED,
        error=error,
    )

    return success
