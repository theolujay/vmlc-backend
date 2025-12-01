import logging
import re
from smtplib import SMTPException

from django.db import DatabaseError
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mass_mail
from django.utils import timezone

from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from vmlc.utils.exceptions import (
    ServerError,
    ValidationError,
    NoRecipientsFoundError,
    InvalidMediumError,
)
from comms.utils import send_bulk_sms

logger = logging.getLogger(__name__)


def send_broadcast(broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    """
    from vmlc.models import Candidate, Staff
    from comms.models import Broadcast, BroadcastLog

    try:
        broadcast = Broadcast.objects.select_related("created_by__user").get(
            id=broadcast_id
        )
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

    # Build recipients dictionary
    recipients_by_type_and_role = {}

    for user_type, roles in broadcast.target_roles.items():
        try:
            if user_type == "staff":
                for role in roles:
                    key = f"staff_{role}"
                    recipients_by_type_and_role[key] = list(
                        Staff.objects.select_related("user")
                        .filter(role=role, user__is_active=True)
                        .values("user__id", "user__email", "user__phone")
                    )
                    logger.info(
                        "Found %d active staff users for role '%s'",
                        len(recipients_by_type_and_role[key]),
                        role,
                    )

            elif user_type == "candidate":
                for role in roles:
                    key = f"candidate_{role}"
                    recipients_by_type_and_role[key] = list(
                        Candidate.objects.select_related("user")
                        .filter(role=role, user__is_active=True)
                        .values("user__id", "user__email")
                    )
                    logger.info(
                        "Found %d active candidate users for role '%s'",
                        len(recipients_by_type_and_role[key]),
                        role,
                    )

        except (Staff.DoesNotExist, Candidate.DoesNotExist) as e:
            logger.error(
                "User not found during broadcast",
                str(e),
            )
            raise

    for medium in broadcast.mediums:
        for user_type, roles in broadcast.target_roles.items():
            for role in roles:
                total_attempts += 1
                key = f"{user_type}_{role}"

                log = BroadcastLog.objects.create(
                    broadcast=broadcast,
                    medium=medium,
                    target_role=role,
                    role_type=user_type,
                    status=BroadcastLog.MediumStatus.PENDING,
                )

                try:
                    recipients = recipients_by_type_and_role.get(key, [])

                    if not recipients:
                        raise NoRecipientsFoundError(
                            f"No active {user_type} found for role '{role}'"
                        )

                    # --- Delegate sending to helper functions ---
                    if medium == Broadcast.Mediums.EMAIL:
                        _send_email_broadcast(broadcast, recipients)
                    elif medium == Broadcast.Mediums.PLATFORM:
                        _send_platform_broadcast(broadcast, recipients)
                    elif medium == Broadcast.Mediums.SMS:
                        _send_sms_broadcast(broadcast, recipients)
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
                        "SMTP error for broadcast %s (%s -> %s:%s): %s",
                        broadcast_id,
                        medium,
                        user_type,
                        role,
                        str(e),
                    )

                except ValidationError as e:
                    overall_success = False
                    partial_success = True
                    log.status = BroadcastLog.MediumStatus.FAILED
                    log.message = f"Validation Error: {str(e)}"
                    log.save(update_fields=["status", "message"])
                    logger.warning(
                        "Validation error for broadcast %s (%s -> %s:%s): %s",
                        broadcast_id,
                        medium,
                        user_type,
                        role,
                        str(e),
                    )

                except NotImplementedError as e:
                    overall_success = False
                    partial_success = True
                    log.status = BroadcastLog.MediumStatus.FAILED
                    log.message = f"Not Implemented: {str(e)}"
                    log.save(update_fields=["status", "message"])
                    logger.warning(
                        "Not implemented for broadcast %s (%s -> %s:%s): %s",
                        broadcast_id,
                        medium,
                        user_type,
                        role,
                        str(e),
                    )

                except Exception as e:
                    overall_success = False
                    partial_success = True
                    log.status = BroadcastLog.MediumStatus.FAILED
                    log.message = f"Unexpected Error: {str(e)}"
                    log.save(update_fields=["status", "message"])
                    logger.error(
                        "Unexpected error for broadcast %s (%s -> %s:%s): %s",
                        broadcast_id,
                        medium,
                        user_type,
                        role,
                        str(e),
                    )

    if overall_success:
        broadcast.status = Broadcast.Status.SENT
        logger.info("Broadcast %s completed successfully", broadcast_id)
    elif partial_success:
        broadcast.status = Broadcast.Status.PARTIAL
        logger.warning(
            "Broadcast %s completed with partial success (%d/%d attempts successful)",
            broadcast_id,
            successful_attempts,
            total_attempts,
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
        "completed_at": timezone.now().isoformat(),
    }


def _send_sms_broadcast(broadcast, recipients):
    """Helper function to handle sending sms"""
    from twilio.base.exceptions import TwilioRestException

    phones = [r["user__phone"] for r in recipients if r.get("user__phone")]
    if not phones:
        raise NoRecipientsFoundError("No phone numbers found for recipients")

    valid_phones = []
    invalid_phones = []
    for phone in phones:
        if re.match(r"^(\+234[789][01]\d{8})$", phone):
            valid_phones.append(phone)
        elif re.match(r"^(0[789][01]\d{8})$", phone):
            clean_phone = "+234" + phone[1:]
            valid_phones.append(clean_phone)
        else:
            invalid_phones.append(phone)

    if invalid_phones:
        logger.warning(
            "Broadcast %s: Skipping %d invalid phone numbers: %s",
            broadcast.id,
            len(invalid_phones),
            invalid_phones[:5],
        )

    if not valid_phones:
        raise ValidationError(
            f"No valid Nigerian phone numbers found. "
            f"Expected format: +2347xxxxxxxx or 07xxxxxxxxx"
        )

    try:
        result = send_bulk_sms(body=broadcast.message, recipients=valid_phones)

        logger.info(
            "SMS broadcast %s: Sent to %d/%d recipients (%d failed)",
            broadcast.id,
            result["success_count"],
            len(valid_phones),
            result["failure_count"],
        )
        if result["failure_count"] > 0:
            logger.warning(
                "SMS broadcast %s: Failed recipients: %s",
                broadcast.id,
                result["failed_recipients"][:5],
            )

    except TwilioRestException as e:
        logger.error(
            "Twilio API error for broadcast %s: %s",
            broadcast.id,
            str(e),
        )
        raise ValidationError(f"SMS service error: {str(e)}") from e


def _send_email_broadcast(broadcast, recipients):
    """Helper function to handle email sending logic."""
    valid_emails = [r["user__email"] for r in recipients if r.get("user__email")]
    if not valid_emails:
        raise NoRecipientsFoundError(
            f"No valid email addresses found for role '{broadcast.target_roles}'"
        )

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
        broadcast.id,
        len(valid_emails),
        ", ".join(broadcast.target_roles),
    )


def _send_platform_broadcast(broadcast, recipients):
    """Helper function to handle platform notification logic."""
    from comms.models import Notification
    from comms.signals import notifications_created

    user_ids = [r["user__id"] for r in recipients if r.get("user__id")]
    if not user_ids:
        raise NoRecipientsFoundError(
            f"No user IDs found for role '{broadcast.target_roles}'"
        )

    notifications_to_create = [
        Notification(
            recipient_id=user_id, subject=broadcast.subject, message=broadcast.message
        )
        for user_id in user_ids
    ]

    try:
        created_notifications = Notification.objects.bulk_create(
            notifications_to_create
        )
    except DatabaseError as e:
        logger.error(
            "Database error during notification bulk_create for broadcast %s: %s",
            broadcast.id,
            e,
        )
        # Re-raise as a ServerError to be handled by the main loop
        raise ServerError("Failed to save notifications to the database.") from e

    # Manually send messages to the channel layer
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.error(
            "Could not get channel layer. Real-time notifications will not be sent for broadcast %s.",
            broadcast.id,
        )
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
            },
        }
        try:
            async_to_sync(channel_layer.group_send)(group_name, message_payload)
        except Exception as e:
            # Log if a single group_send fails, but don't stop the others
            logger.error(
                "Failed to send notification to group %s for broadcast %s: %s",
                group_name,
                broadcast.id,
                e,
            )

    # Send our custom signal for other potential listeners
    notifications_created.send(
        sender=send_broadcast, notifications=created_notifications
    )
    logger.info(
        "Platform notifications created and pushed for %d users (roles: %s)",
        len(user_ids),
        ", ".join(broadcast.target_roles),
    )
