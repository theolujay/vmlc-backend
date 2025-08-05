"""
Celery tasks for the API application.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="send_mail_task", max_retries=3, default_retry_delay=60)
def send_mail_task(self, subject, message, recipient_list):
    """
    Celery task to send an email asynchronously.

    It will automatically retry up to 3 times if it fails,
    with a 60-second delay between retries.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Successfully sent email to {recipient_list}")
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}: {exc}")
        # The `self.retry` call will re-queue the task.
        # The `bind=True` and `max_retries` arguments in the decorator handle this automatically.
        raise self.retry(exc=exc)