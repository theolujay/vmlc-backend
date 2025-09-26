import logging
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, send_mass_mail
from django.core.mail.backends.smtp import EmailBackend
from django.utils import timezone
from smtplib import SMTPException
from django.db import DatabaseError
from vmlc.utils.exceptions import (
    ServerError,
    ValidationError,
    NoRecipientsFoundError,
    InvalidMediumError,
)

logger = logging.getLogger(__name__)

def _send_email_broadcast(broadcast, recipients):
    """Helper function to handle email sending logic."""
    valid_emails = [r['user__email'] for r in recipients if r.get('user__email')]
    if not valid_emails:
        raise NoRecipientsFoundError(f"No valid email addresses found for role '{broadcast.target_roles}'")
    
    mail_details = (
        broadcast.subject,
        broadcast.message,
        settings.DEFAULT_FROM_EMAIL,
        valid_emails,
    )
    # This can raise SMTPException, which will be caught by the main task loop
    send_mass_mail((mail_details,), fail_silently=False)
    
    logger.info(
        "Email queued successfully for broadcast %s to %d recipients (roles: %s)",
        broadcast.id, len(valid_emails), ", ".join(broadcast.target_roles)
    )

def _send_platform_broadcast(broadcast, recipients):
    """Helper function to handle platform notification logic."""
    from comms.models import Notification
    from comms.signals import notifications_created

    user_ids = [r['user__id'] for r in recipients if r.get('user__id')]
    if not user_ids:
        raise NoRecipientsFoundError(f"No user IDs found for role '{broadcast.target_roles}'")

    notifications_to_create = [
        Notification(
            recipient_id=user_id,
            subject=broadcast.subject,
            message=broadcast.message
        )
        for user_id in user_ids
    ]
    
    try:
        created_notifications = Notification.objects.bulk_create(notifications_to_create)
    except DatabaseError as e:
        logger.error("Database error during notification bulk_create for broadcast %s: %s", broadcast.id, e)
        # Re-raise as a ServerError to be handled by the main loop
        raise ServerError("Failed to save notifications to the database.") from e

    # Manually send messages to the channel layer
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.error("Could not get channel layer. Real-time notifications will not be sent for broadcast %s.", broadcast.id)
        # This is a critical configuration error, but we don't want to fail the whole task.
        # The notifications are saved, but not pushed in real-time.
        return

    for notification in created_notifications:
        group_name = f"user__{notification.recipient_id}"
        message_payload = {
            "type": "notification_activity",
            "message": {
                "id": notification.id,
                "subject": notification.subject,
                "message": notification.message,
                "read": notification.read,
                "created_at": notification.created_at.isoformat(),
            }
        }
        try:
            async_to_sync(channel_layer.group_send)(group_name, message_payload)
        except Exception as e:
            # Log if a single group_send fails, but don't stop the others
            logger.error("Failed to send notification to group %s for broadcast %s: %s", group_name, broadcast.id, e)

    # Send our custom signal for other potential listeners
    notifications_created.send(sender=send_broadcast_task, notifications=created_notifications)
    logger.info("Platform notifications created and pushed for %d users (roles: %s)", len(user_ids), ", ".join(broadcast.target_roles))


@shared_task(
    bind=True, name="send_broadcast_task", max_retries=3, default_retry_delay=60, queue="comms"
)
def send_broadcast_task(self, broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    
    This task:
    1. Updates broadcast status to IN_PROGRESS
    2. Iterates through each medium and target role combination
    3. Creates logs for each attempt
    4. Updates final broadcast status based on results
    
    Args:
        broadcast_id (int): The ID of the broadcast to send
        self: The Celery task instance (automatically passed due to bind=True)
        
    Returns:
        dict: Summary of the broadcast attempt
    """
    from vmlc.models import Candidate
    from comms.models import Broadcast, BroadcastLog, Notification
    from comms.signals import notifications_created

    try:
        broadcast = Broadcast.objects.select_related("created_by__user").get(id=broadcast_id)
    except Broadcast.DoesNotExist:
        logger.error("Broadcast not found (id=%s)", broadcast_id)
        return {"error": "Broadcast not found", "broadcast_id": broadcast_id}

    broadcast.status = Broadcast.Status.IN_PROGRESS
    broadcast.last_attempt = timezone.now()
    broadcast.save(update_fields=["status", "last_attempt"])
    
    logger.info("Starting broadcast %s: '%s'", broadcast_id, broadcast.subject)

    overall_success = True
    partial_success = False
    total_attempts = 0
    successful_attempts = 0

    recipients_by_role = {}
    for role in broadcast.target_roles:
        try:
            recipients_by_role[role] = list(
                Candidate.objects.select_related('user').filter(
                    role=role, 
                    user__is_active=True
                ).values('user__id', 'user__email')
            )
            logger.info(
                "Found %d active candidates for role '%s'", 
                len(recipients_by_role[role]), 
                role
            )
        except (DatabaseError, ServerError) as e:
            logger.error("Database error fetching candidates for role '%s': %s", role, str(e))
            raise self.retry(exc=e, countdown=60)
            
    for medium in broadcast.mediums:
        for role in broadcast.target_roles:
            total_attempts += 1
            
            log = BroadcastLog.objects.create(
                broadcast=broadcast,
                medium=medium,
                target_role=role,
                status=BroadcastLog.MediumStatus.PENDING
            )
            
            try:
                recipients = recipients_by_role[role]
                
                if not recipients:
                    raise NoRecipientsFoundError(f"No active candidates found for role '{role}'")

                # --- Delegate sending to helper functions ---
                if medium == Broadcast.Mediums.EMAIL:
                    _send_email_broadcast(broadcast, recipients)
                elif medium == Broadcast.Mediums.PLATFORM:
                    _send_platform_broadcast(broadcast, recipients)
                elif medium == Broadcast.Mediums.SMS:
                    raise NotImplementedError("SMS medium is not implemented.")
                elif medium == Broadcast.Mediums.WHATSAPP:
                    raise NotImplementedError("WhatsApp medium is not implemented.")
                else:
                    raise InvalidMediumError(f"Unknown medium specified: {medium}")

                # If we get here, the sending was successful
                log.status = BroadcastLog.MediumStatus.SENT
                log.message = f"Successfully sent to {len(recipients)} recipients"
                log.save(update_fields=["status", "message"])
                successful_attempts += 1

            except SMTPException as e:
                overall_success = False
                partial_success = True
                log.status = BroadcastLog.MediumStatus.FAILED
                log.message = f"SMTP Error: {str(e)}"
                log.save(update_fields=["status", "message"])
                logger.error(
                    "SMTP error for broadcast %s (%s -> %s): %s",
                    broadcast_id, medium, role, str(e)
                )
                
            except ValidationError as e: # Catch specific validation errors
                overall_success = False
                partial_success = True
                log.status = BroadcastLog.MediumStatus.FAILED
                log.message = f"Validation Error: {str(e)}"
                log.save(update_fields=["status", "message"])
                logger.warning(
                    "Validation error for broadcast %s (%s -> %s): %s",
                    broadcast_id, medium, role, str(e)
                )

            except NotImplementedError as e:
                overall_success = False
                partial_success = True
                log.status = BroadcastLog.MediumStatus.FAILED
                log.message = f"Not Implemented: {str(e)}"
                log.save(update_fields=["status", "message"])
                logger.warning(
                    "Not implemented for broadcast %s (%s -> %s): %s",
                    broadcast_id, medium, role, str(e)
                )
                
            except Exception as e:
                overall_success = False
                partial_success = True
                log.status = BroadcastLog.MediumStatus.FAILED
                log.message = f"Unexpected Error: {str(e)}"
                log.save(update_fields=["status", "message"])
                logger.error(
                    "Unexpected error for broadcast %s (%s -> %s): %s",
                    broadcast_id, medium, role, str(e)
                )
    if overall_success:
        broadcast.status = Broadcast.Status.SENT
        logger.info("Broadcast %s completed successfully", broadcast_id)
    elif partial_success:
        broadcast.status = Broadcast.Status.PARTIAL
        logger.warning(
            "Broadcast %s completed with partial success (%d/%d attempts successful)",
            broadcast_id, successful_attempts, total_attempts
        )
    else:
        broadcast.status = Broadcast.Status.FAILED
        logger.error("Broadcast %s failed completely", broadcast_id)
    
    broadcast.save(update_fields=["status"])
    
    # Invalidate the cache for this broadcast's detail view
    cache.delete(f"broadcast_detail_{broadcast_id}")
    
    # Return summary for monitoring/debugging
    return {
        "broadcast_id": broadcast_id,
        "status": broadcast.status,
        "total_attempts": total_attempts,
        "successful_attempts": successful_attempts,
        "subject": broadcast.subject,
        "completed_at": timezone.now().isoformat()
    }