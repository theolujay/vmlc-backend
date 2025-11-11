import logging
from django.conf import settings
from django.dispatch import Signal
from django.core.mail import mail_admins
from celery.signals import task_success, task_failure

from vmlc.utils.exceptions import ValidationError

logger = logging.getLogger(__name__)
notifications_created = Signal()


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Handle successful task completion"""
    if sender and sender.name == "send_broadcast_task":
        if result and isinstance(result, dict):
            success_rate = (
                result.get("successful_attempts", 0)
                / max(result.get("total_attempts", 1), 1)
                * 100
            )

            # Log summary
            logger.info(
                "Broadcast %s completed: %d/%d attempts successful (%.1f%%)",
                result.get("broadcast_id"),
                result.get("successful_attempts", 0),
                result.get("total_attempts", 0),
                success_rate,
            )

            # Alert on low success rate
            if success_rate < 50:
                mail_admins(
                    subject=f"Low Broadcast Success Rate: {success_rate:.1f}%",
                    message=f"Broadcast {result.get('broadcast_id')} had low success rate: {result}",
                )


@task_failure.connect
def task_failure_handler(
    sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs
):
    """Handle failed tasks"""
    if sender and sender.name == "send_broadcast_task":
        logger.error(
            "Broadcast task %s failed with exception: %s", task_id, repr(exception)
        )

        # Only alert admins for critical, unexpected errors, not for simple validation issues.
        if not isinstance(exception, ValidationError):
            mail_admins(
                subject=f"CRITICAL: Broadcast Task Failed - {type(exception).__name__}",
                message=(
                    f"Task {task_id} failed with a critical error.\n\n"
                    f"Exception: {repr(exception)}\n\n"
                    f"Traceback:\n{einfo.traceback if einfo else 'Not available'}"
                ),
            )


# You could even create webhooks to notify external systems
@task_success.connect
def broadcast_webhook_notification(sender=None, result=None, **kwargs):
    if sender and sender.name == "send_broadcast_task" and result:
        import requests

        webhook_url = settings.BROADCAST_WEBHOOK_URL
        if webhook_url:
            try:
                requests.post(
                    webhook_url,
                    json={"event": "broadcast_completed", "data": result},
                    timeout=5,
                )
            except Exception as e:
                logger.warning("Failed to send webhook: %s", str(e))
