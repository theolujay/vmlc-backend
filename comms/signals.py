import logging
from django.conf import settings
from django.dispatch import Signal
from django.core.mail import mail_admins
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from celery.signals import task_success, task_failure

from vmlc.utils.exceptions import ValidationError
from vmlc.v2.utils import CacheKeys, invalidate_notifications
from .models import Notification, Broadcast, HelpdeskThread, ThreadMessage

logger = logging.getLogger(__name__)
notifications_created = Signal()


def invalidate_notification_cache(sender, instance, **kwargs):
    """Invalidates the notification cache for a user and their dashboard."""
    user_id = instance.recipient_id
    invalidate_notifications(user_id)

    # Also invalidate candidate dashboard if they have one
    from vmlc.v2.utils import invalidate_candidate_cache
    from identity.models import Candidate

    try:
        candidate = Candidate.objects.get(user_id=user_id)
        invalidate_candidate_cache(candidate.pk, user_id=user_id)
    except Candidate.DoesNotExist:
        pass

    logger.info(f"Invalidated notification and dashboard cache for user {user_id}")


def handle_notification_delivery(sender, instance, created, **kwargs):
    """Triggers background delivery task for a single notification."""
    if created:
        from .tasks import deliver_notifications_task

        transaction.on_commit(lambda: deliver_notifications_task.delay([instance.pk]))


def handle_bulk_notification_delivery(sender, notifications, **kwargs):
    """Triggers background delivery task for a list of notifications."""
    from .tasks import deliver_notifications_task

    notification_ids = [n.id for n in notifications if n.id]
    if notification_ids:
        transaction.on_commit(
            lambda: deliver_notifications_task.delay(notification_ids)
        )


post_save.connect(invalidate_notification_cache, sender=Notification)
post_delete.connect(invalidate_notification_cache, sender=Notification)
post_save.connect(handle_notification_delivery, sender=Notification)
notifications_created.connect(handle_bulk_notification_delivery)


def invalidate_broadcast_cache(sender, instance, **kwargs):
    """Invalidates broadcast detail and summary caches."""
    cache.delete(CacheKeys.BROADCAST_DETAIL.format(broadcast_id=instance.pk))
    cache.delete(CacheKeys.BROADCAST_SUMMARY)
    logger.info(f"Invalidated broadcast cache for broadcast {instance.pk}")


post_save.connect(invalidate_broadcast_cache, sender=Broadcast)
post_delete.connect(invalidate_broadcast_cache, sender=Broadcast)


def invalidate_helpdesk_cache(sender, instance, **kwargs):
    """Invalidates helpdesk thread detail and staff list caches."""
    if isinstance(instance, HelpdeskThread):
        thread_id = instance.pk
    elif isinstance(instance, ThreadMessage):
        thread_id = instance.thread_id
    else:
        return

    cache.delete(CacheKeys.HELPDESK_THREAD_DETAIL.format(thread_id=thread_id))

    # Invalidate staff list version to force reload for all staff
    try:
        cache.incr(CacheKeys.HELPDESK_THREADS_VERSION_STAFF)
    except ValueError:
        cache.set(CacheKeys.HELPDESK_THREADS_VERSION_STAFF, 1, timeout=86400)

    # Trigger real-time broadcast to staff dashboard
    from .tasks import broadcast_staff_helpdesk_update_task

    broadcast_staff_helpdesk_update_task.delay()

    logger.info(
        f"Invalidated helpdesk cache and triggered broadcast for thread {thread_id}"
    )


post_save.connect(invalidate_helpdesk_cache, sender=HelpdeskThread)
post_save.connect(invalidate_helpdesk_cache, sender=ThreadMessage)
post_delete.connect(invalidate_helpdesk_cache, sender=HelpdeskThread)
post_delete.connect(invalidate_helpdesk_cache, sender=ThreadMessage)


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
