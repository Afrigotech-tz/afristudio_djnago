"""
notifications/channels/email.py
Handles email delivery via Django's built-in email backend.
"""

from django.core.mail import send_mail
from django.conf import settings


def send_email(to: str, subject: str, message: str) -> tuple[bool, str | None]:
    """
    Send a plain-text email.

    Returns:
        (True, None)          on success
        (False, error_str)    on failure
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        return True, None
    except Exception as exc:
        return False, str(exc)
