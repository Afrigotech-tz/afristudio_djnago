"""
activity_logs/utils.py
Helper function used across all apps to log activity.
Mirrors Laravel's  activity()->performedOn($model)->log('...')
"""

from django.contrib.contenttypes.models import ContentType


def log_activity(description: str, user=None, subject=None, log_name: str = 'default',
                 event: str = None, properties: dict = None):
    """
    Record an activity log entry.

    Usage:
        log_activity(user=request.user, subject=artwork,
                     description='Created new artwork: Sunset',
                     log_name='artworks', event='created')
    """
    from .models import ActivityLog  # late import to avoid circular imports

    subject_type = None
    subject_id = None

    if subject is not None:
        subject_type = ContentType.objects.get_for_model(subject)
        subject_id = subject.pk

    ActivityLog.objects.create(
        log_name=log_name,
        description=description,
        event=event,
        subject_type=subject_type,
        subject_id=subject_id,
        causer=user,
        properties=properties,
    )
