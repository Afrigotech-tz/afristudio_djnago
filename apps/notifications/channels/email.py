"""
notifications/channels/email.py
Handles email delivery via Django's built-in email backend.
Supports plain-text and HTML template emails.
"""

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone


def send_email(
    to: str,
    subject: str,
    message: str,
    template: str = None,
    context: dict = None,
) -> tuple[bool, str | None]:
    """
    Send an email, optionally using an HTML template.

    Args:
        to:        Recipient email address.
        subject:   Email subject line.
        message:   Plain-text fallback body (always required for non-HTML clients).
        template:  Optional Django template path, e.g. 'emails/verify_account.html'.
                   When provided, an HTML version is attached alongside the plain text.
        context:   Template context variables. 'year' is injected automatically.

    Returns:
        (True, None)       on success
        (False, error_str) on failure
    """
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )

        if template:
            ctx = {'year': timezone.now().year}
            if context:
                ctx.update(context)
            html_body = render_to_string(template, ctx)
            email.attach_alternative(html_body, 'text/html')

        email.send(fail_silently=False)
        return True, None
    except Exception as exc:
        return False, str(exc)
