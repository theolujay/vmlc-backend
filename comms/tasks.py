import logging
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, send_mass_mail
from django.core.mail.backends.smtp import EmailBackend
from django.utils import timezone
from smtplib import SMTPException
from django.db import DatabaseError

from vmlc.utils.exceptions import ServerError

logger = logging.getLogger(__name__)


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
    from comms.models import Broadcast, BroadcastLog

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
                ).values_list("user__email", flat=True)
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
                    raise ValueError(f"No active candidates found for role '{role}'")

                if medium == Broadcast.Mediums.EMAIL:
                    valid_emails = [email for email in recipients if email and email.strip()]
                    
                    if not valid_emails:
                        raise ValueError(f"No valid email addresses found for role '{role}'")
                    
                    mail_details = (
                        broadcast.subject,
                        broadcast.message,
                        settings.DEFAULT_FROM_EMAIL,
                        valid_emails,
                    )
                    send_mass_mail((mail_details,), fail_silently=False)
                    
                    logger.info(
                        "Email sent successfully for broadcast %s to %d recipients (role: %s)",
                        broadcast_id, len(valid_emails), role
                    )

                elif medium == Broadcast.Mediums.PLATFORM:
                    # TODO: Implement WebSocket push via Django Channels
                    # For now, we'll mark it as sent but log that it's not implemented
                    logger.warning(
                        "Platform notifications not yet implemented for broadcast %s (role: %s)",
                        broadcast_id, role
                    )
                    # Consider raising NotImplementedError here instead
                    
                elif medium == Broadcast.Mediums.SMS:
                    # TODO: Integrate SMS provider (Twilio, AWS SNS, etc.)
                    logger.warning(
                        "SMS notifications not yet implemented for broadcast %s (role: %s)",
                        broadcast_id, role
                    )
                    # Consider raising NotImplementedError here instead

                elif medium == Broadcast.Mediums.WHATSAPP:
                    # TODO: Integrate WhatsApp Business API
                    logger.warning(
                        "WhatsApp notifications not yet implemented for broadcast %s (role: %s)",
                        broadcast_id, role
                    )
                    # Consider raising NotImplementedError here instead
                
                else:
                    raise ValueError(f"Unknown medium: {medium}")

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
                
            except ValueError as e:
                overall_success = False
                partial_success = True
                log.status = BroadcastLog.MediumStatus.FAILED
                log.message = f"Validation Error: {str(e)}"
                log.save(update_fields=["status", "message"])
                logger.warning(
                    "Validation error for broadcast %s (%s -> %s): %s",
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
                raise self.retry(exc=e)

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
    
    # Return summary for monitoring/debugging
    return {
        "broadcast_id": broadcast_id,
        "status": broadcast.status,
        "total_attempts": total_attempts,
        "successful_attempts": successful_attempts,
        "subject": broadcast.subject,
        "completed_at": timezone.now().isoformat()
    }