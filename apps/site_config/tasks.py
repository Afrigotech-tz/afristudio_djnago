"""
site_config/tasks.py
Celery tasks for processing incoming contact messages.
"""

from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_new_contact_message(self, message_id: int):
    """
    Send an email notification to the site admin whenever a new contact
    message is submitted via the public contact form.
    Retries up to 3 times with a 60-second delay on failure.
    """
    try:
        from apps.site_config.models import ContactMessage, ContactInfo
        from apps.notifications.service import notify

        msg = ContactMessage.objects.get(pk=message_id)
        info = ContactInfo.load()

        notify(
            to_email=info.email,
            subject=f'[AfriStudio] New contact message: {msg.subject}',
            message=(
                f'From: {msg.name} <{msg.email}>\n'
                f'Subject: {msg.subject}\n\n'
                f'{msg.message}'
            ),
            template='site_config/email/new_contact_message.html',
            context={
                'sender_name': msg.name,
                'sender_email': msg.email,
                'subject': msg.subject,
                'message_body': msg.message,
            },
        )
    except Exception as exc:
        raise self.retry(exc=exc)
