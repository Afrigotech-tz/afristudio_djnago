"""
accounts/tasks.py
Celery tasks for OTP delivery — registration verification and password reset.
Retries up to 3 times with a 60-second back-off on transient failures.
"""

import logging
import threading
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_otp(self, user_id: int, code: str):
    """
    Send the 6-digit account verification OTP to a newly registered user.
    Accepts the user PK (not the instance) so it is JSON-serialisable for the broker.
    """
    from django.contrib.auth import get_user_model
    from apps.notifications.service import notify

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('send_verification_otp: user %s not found — skipping', user_id)
        return

    try:
        notify(
            user=user,
            subject='Verify your AfriStudio Account',
            message=f'Hi {user.name}, your verification code is: {code}',
            template='emails/verify_account.html',
            context={'name': user.name, 'code': code},
        )
        logger.info('Verification OTP sent to user %s', user_id)
    except Exception as exc:
        logger.warning('send_verification_otp failed for user %s: %s', user_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_otp(self, user_id: int, code: str):
    """
    Send the 6-digit password-reset OTP to the requesting user.
    """
    from django.contrib.auth import get_user_model
    from apps.notifications.service import notify

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('send_password_reset_otp: user %s not found — skipping', user_id)
        return

    try:
        notify(
            user=user,
            subject='Password Reset Code – AfriStudio',
            message=f'Hi {user.name}, your password reset code is: {code}',
            template='emails/forgot_password.html',
            context={'name': user.name, 'code': code},
        )
        logger.info('Password reset OTP sent to user %s', user_id)
    except Exception as exc:
        logger.warning('send_password_reset_otp failed for user %s: %s', user_id, exc)
        raise self.retry(exc=exc)


# ─── Fire-and-forget dispatch ─────────────────────────────────────────────────
# The view spawns a daemon thread immediately and returns — zero broker wait
# on the request path. Inside the thread we try Celery first; if the broker
# is unavailable we run the task body directly in that same thread.

def _fire(task_func, *args):
    """Spawn a daemon thread that tries Celery then falls back to direct run."""
    def run():
        try:
            task_func.delay(*args)
        except Exception as exc:
            logger.warning('Celery unavailable (%s) — running %s directly in thread', exc, task_func.__name__)
            try:
                task_func(*args)
            except Exception as inner:
                logger.error('%s direct execution failed: %s', task_func.__name__, inner)

    threading.Thread(target=run, daemon=True).start()


def dispatch_verification_otp(user_id: int, code: str):
    _fire(send_verification_otp, user_id, code)


def dispatch_password_reset_otp(user_id: int, code: str):
    _fire(send_password_reset_otp, user_id, code)
