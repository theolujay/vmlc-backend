import logging
from django.conf import settings
from django.core.mail import mail_admins
from celery.signals import task_success, task_failure

logger = logging.getLogger(__name__)

@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Handle successful task completion"""
    if sender and sender.name == 'send_broadcast_task':
        if result and isinstance(result, dict):
            success_rate = (
                result.get('successful_attempts', 0) / 
                max(result.get('total_attempts', 1), 1) * 100
            )
            
            # Log summary
            logger.info(
                "Broadcast %s completed: %d/%d attempts successful (%.1f%%)",
                result.get('broadcast_id'),
                result.get('successful_attempts', 0),
                result.get('total_attempts', 0),
                success_rate
            )
            
            # Alert on low success rate
            if success_rate < 50:
                mail_admins(
                    subject=f"Low Broadcast Success Rate: {success_rate:.1f}%",
                    message=f"Broadcast {result.get('broadcast_id')} had low success rate: {result}"
                )

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs):
    """Handle failed tasks"""
    if sender and sender.name == 'send_broadcast_task':
        logger.error(
            "Broadcast task %s failed: %s",
            task_id, str(exception)
        )

        mail_admins(
            subject="Broadcast Task Failed",
            message=f"Task {task_id} failed with error: {exception}\n\nTraceback:\n{traceback}"
        )
        
# You could even create webhooks to notify external systems
@task_success.connect
def broadcast_webhook_notification(sender=None, result=None, **kwargs):
    if sender and sender.name == 'send_broadcast_task' and result:
        import requests
        
        webhook_url = settings.BROADCAST_WEBHOOK_URL
        if webhook_url:
            try:
                requests.post(webhook_url, json={
                    "event": "broadcast_completed",
                    "data": result
                }, timeout=5)
            except Exception as e:
                logger.warning("Failed to send webhook: %s", str(e))