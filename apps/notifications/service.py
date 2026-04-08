"""
notifications/service.py
Single entry-point for sending notifications across the whole project.

Usage examples:

    from apps.notifications.service import notify

    # Plain-text (auto-detect channel)
    notify(user=user, subject='OTP', message='Your code is 123456')

    # HTML email with a template
    notify(
        user=user,
        subject='Verify your account',
        message='Your OTP is 123456',   # plain-text fallback
        template='emails/verify_account.html',
        context={'name': user.name, 'code': '123456'},
    )

    # Force SMS
    notify(user=user, message='Your code is 123456', channel='sms')

    # Without a user object
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
    template: str = None,
    context: dict = None,
    to_email: str = None,
    to_phone: str = None,
    causer=None,
) -> bool:
    """
    Send a notification and persist a log entry.

    Args:
        user:       Django user instance — used to resolve recipient & causer.
        subject:    Email subject (ignored for SMS).
        message:    Plain-text body (also used as SMS body; email fallback for non-HTML clients).
        channel:    'auto' | 'email' | 'sms'.
                    'auto' picks email when the user has one, otherwise sms.
        template:   Django template path for HTML email, e.g. 'emails/verify_account.html'.
        context:    Template context dict passed to the HTML template.
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
        success, error = send_email(
            to=recipient,
            subject=subject,
            message=message,
            template=template,
            context=context,
        )
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
