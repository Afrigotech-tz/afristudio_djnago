"""
notifications/tasks.py
Async notification delivery via Celery, with a threading fallback.

Usage — replace every synchronous notify() call with:

    from apps.notifications.tasks import notify_async

    notify_async(
        user_id=user.pk,
        subject='Verify your account',
        message='Your code is 123456',
        template='emails/verify_account.html',
        context={'name': 'Jane', 'code': '123456'},
    )

    # Without a user object
    notify_async(to_email='jane@example.com', subject='Hi', message='Hello')

Behaviour:
  • Celery worker running + Redis up → queued as a proper Celery task.
  • Redis down or broker unavailable     → runs in a daemon thread so the
    HTTP request still returns instantly.
"""

import threading
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification(
    self,
    *,
    user_id: int = None,
    subject: str = '',
    message: str,
    channel: str = 'auto',
    template: str = None,
    context: dict = None,
    to_email: str = None,
    to_phone: str = None,
):
    """
    Celery task. Accepts `user_id` (int PK) because model instances
    cannot be serialised for the broker.
    """
    from django.contrib.auth import get_user_model
    from .service import notify

    user = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return  # user deleted before task ran

    try:
        notify(
            user=user,
            subject=subject,
            message=message,
            channel=channel,
            template=template,
            context=context,
            to_email=to_email,
            to_phone=to_phone,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


def _run_in_thread(**kwargs):
    """Fallback: send synchronously in a daemon thread."""
    from django.contrib.auth import get_user_model
    from .service import notify

    user_id = kwargs.pop('user_id', None)
    user = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return

    try:
        notify(user=user, **kwargs)
    except Exception as exc:
        logger.warning('notify thread fallback failed: %s', exc)


def notify_async(**kwargs):
    """
    Queue send_notification via Celery.
    Falls back to a daemon thread if the broker is unreachable,
    so the calling view always returns immediately.
    """
    try:
        send_notification.delay(**kwargs)
    except Exception as exc:
        logger.warning('Celery broker unavailable (%s) — falling back to thread', exc)
        t = threading.Thread(target=_run_in_thread, kwargs=kwargs, daemon=True)
        t.start()
