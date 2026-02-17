import logging
import re
from smtplib import SMTPException

from django.db import DatabaseError
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mass_mail
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from vmlc.utils.exceptions import (
    ServerError,
    ValidationError,
    NoRecipientsFoundError,
    InvalidMediumError,
)
from comms.utils import send_bulk_phone_msg, send_phone_msg

logger = logging.getLogger(__name__)

def notify_user(
    user,
    subject,
    message,
    mediums=None,
    notification_type="info",
):
    """
    Sends a notification to a single user via specified mediums.

    Args:
        user: User instance
        subject: Notification subject
        message: Notification message
        mediums: List of mediums (email, platform, sms, whatsapp). Defaults to ["platform"]
        notification_type: Type of notification (alert, info, success, warning, error)
    """
    from comms.models import Notification, Broadcast

    if mediums is None:
        mediums = [Broadcast.Mediums.PLATFORM]

    results = {}

    for medium in mediums:
        try:
            # Combine subject and message for mediums that only handle a single body
            full_body = f"{subject}:\n\n{message}" if subject else message

            if medium == Broadcast.Mediums.PLATFORM:
                notification = Notification.objects.create(
                    recipient=user,
                    subject=subject,
                    message=full_body,  # Use full body for platform UI
                    type=notification_type,
                )
                # Push to channel layer
                channel_layer = get_channel_layer()
                if channel_layer:
                    group_name = f"user__{user.id}"
                    message_payload = {
                        "type": "notification_activity",
                        "message": {
                            "id": notification.id,
                            "subject": notification.subject,
                            "message": notification.message,
                            "type": notification.type,
                            "is_read_by_recipient": notification.is_read_by_recipient,
                            "created_at": notification.created_at.isoformat(),
                        },
                    }
                    async_to_sync(channel_layer.group_send)(group_name, message_payload)
                results["platform"] = True

            elif medium == Broadcast.Mediums.EMAIL:
                from vmlc.tasks import send_mail_task

                send_mail_task.delay(
                    subject=subject, message=message, recipient_list=[user.email]
                )
                results["email"] = True

            elif medium == Broadcast.Mediums.SMS:
                if hasattr(user, "phone") and user.phone:
                    # Clean phone number for Nigerian format if necessary
                    phone = user.phone
                    if re.match(r"^(0[789][01]\d{8})$", phone):
                        phone = "+234" + phone[1:]

                    send_phone_msg(body=full_body, recipient=phone, medium="sms")
                    results["sms"] = True
                else:
                    logger.warning(f"User {user.id} has no phone number for SMS notification")
                    results["sms"] = False

            elif medium == Broadcast.Mediums.WHATSAPP:
                if hasattr(user, "phone") and user.phone:
                    phone = user.phone
                    if re.match(r"^(0[789][01]\d{8})$", phone):
                        phone = "+234" + phone[1:]

                    send_phone_msg(body=full_body, recipient=phone, medium="whatsapp")
                    results["whatsapp"] = True
                else:
                    logger.warning(f"User {user.id} has no phone number for WhatsApp notification")
                    results["whatsapp"] = False

        except Exception as e:
            logger.error(f"Failed to send {medium} notification to user {user.id}: {e}")
            results[medium] = False

    return results


# TODO: handle emitted events to send notifications


def send_broadcast(broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    """
    from identity.models import Candidate, Staff
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
                        .values("user__id", "user__email", "user__phone")
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
                        _send_sms_broadcast(broadcast, recipients, log)
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
    cache.delete("broadcast_summary_data")

    # Return summary for monitoring/debugging
    return {
        "broadcast_id": broadcast_id,
        "status": broadcast.status,
        "total_attempts": total_attempts,
        "successful_attempts": successful_attempts,
        "subject": broadcast.subject,
        "completed_at": timezone.now().isoformat(),
    }


def _send_sms_broadcast(broadcast, recipients, log):
    """Helper function to handle sending sms"""
    from comms.utils import format_phone, is_placeholder_phone

    phones = [r["user__phone"] for r in recipients if r.get("user__phone")]
    if not phones:
        raise NoRecipientsFoundError("No phone numbers found for recipients")

    valid_phones = []
    for phone in phones:
        clean_phone = format_phone(phone)
        if is_placeholder_phone(clean_phone):
            continue
        valid_phones.append(clean_phone)

    if not valid_phones:
        raise NoRecipientsFoundError("No valid, non-placeholder phone numbers found")

    try:
        full_body = f"{broadcast.subject}:\n\n{broadcast.message}" if broadcast.subject else broadcast.message
        send_bulk_phone_msg(
            body=full_body,
            recipients=valid_phones,
            medium="sms",
            broadcast_log_id=log.id,
        )
        logger.info(
            "SMS broadcast %s queued for %d recipients.", broadcast.id, len(valid_phones)
        )
    except Exception as e:
        # This will catch errors during task queuing, not sending.
        logger.error(
            "Failed to queue SMS broadcast task for broadcast %s: %s",
            broadcast.id,
            str(e),
        )
        # Re-raise to let the main broadcast loop handle it as a failure
        raise ValidationError(f"SMS task queuing error: {str(e)}") from e


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

    full_body = f"{broadcast.subject}:\n\n{broadcast.message}" if broadcast.subject else broadcast.message

    notifications_to_create = [
        Notification(
            recipient_id=user_id,
            subject=broadcast.subject,
            message=full_body,
            type=Notification.Type.INFO
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
                "type": notification.type,
                "is_read_by_recipient": notification.is_read_by_recipient,
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

def notify_candidates_about_exam(exam, event_type):
    """
    Notify all in-progress candidates about exam events.

    Args:
        exam: Exam instance with scheduled_date, open_duration_hours, and competition_slot
        event_type: Type of notification - either 'scheduled' or 'started'
    """
    import logging
    from datetime import timedelta

    from competition.models import EnrollmentStageProgress
    from comms.tasks import notify_user_task
    from comms.models import Broadcast
    from comms.utils import format_phone, is_placeholder_phone

    logger = logging.getLogger(__name__)

    if event_type not in ('scheduled', 'started'):
        logger.warning(f"Invalid event_type: {event_type}. Must be 'scheduled' or 'started'")
        return

    # Early return if exam has no associated competition slot
    if exam.competition_slot is None:
        logger.warning(
            f"Exam {exam.id} has no competition_slot, skipping {event_type} notifications"
        )
        return

    # Fetch candidates who are in progress for this stage
    stage = exam.competition_slot.competition_stage
    enrollment_stage_progresses = EnrollmentStageProgress.objects.filter(
        stage=stage,
        status=EnrollmentStageProgress.Status.IN_PROGRESS
    ).select_related('enrollment__candidate__user')

    if not enrollment_stage_progresses.exists():
        logger.info(f"No candidates to notify for exam {exam.id} ({event_type})")
        return

    # Configure notification content based on event type
    if event_type == 'scheduled':
        subject = f"New Exam Scheduled: {exam.get_title()}"
        message_template = (
            "Dear {candidate_name},\n\n"
            "A new exam '{exam_title}' has been scheduled for your stage.\n"
            "Start Time: {start_time}\n\n"
            "Please log in to your dashboard for more details.\n\n"
            "Regards,\n"
            "VMLC Team"
        )
        template_kwargs = {
            'start_time': exam.scheduled_date.strftime('%Y-%m-%d %H:%M:%S %Z') if exam.scheduled_date else 'N/A'
        }
    else:  # event_type == 'started'
        conclusion_time = exam.scheduled_date + timedelta(hours=exam.open_duration_hours)
        subject = f"Exam Started: {exam.get_title()}"
        message_template = (
            "Dear {candidate_name},\n\n"
            "The exam '{exam_title}' has started and is now open for taking.\n"
            "It will remain open until {conclusion_time}.\n\n"
            "Good luck,\n"
            "VMLC Team"
        )
        template_kwargs = {
            'conclusion_time': conclusion_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        }

    # Send individual notifications (Platform, Email) and group for (SMS, WhatsApp)
    phone_grouped_users = {}  # {phone: [user1, user2, ...]}
    notification_count = 0

    for esp in enrollment_stage_progresses:
        user = esp.enrollment.candidate.user
        notification_count += 1

        # Individual notifications (Platform & Email)
        format_args = {
            'candidate_name': user.first_name or 'Candidate',
            'exam_title': exam.get_title(),
            **template_kwargs
        }
        personalized_message = message_template.format(**format_args)
        notify_user_task.delay(
            user=user,
            subject=subject,
            message=personalized_message,
            mediums=[Broadcast.Mediums.PLATFORM, Broadcast.Mediums.EMAIL],
            notification_type='info',
        )

        # Collect users sharing the same phone number for SMS/WhatsApp
        if user.phone:
            phone = user.phone
            phone = format_phone(phone)

            if is_placeholder_phone(phone):
                continue
            if phone not in phone_grouped_users:
                phone_grouped_users[phone] = []
            phone_grouped_users[phone].append(user)

    # Send grouped notifications (SMS & WhatsApp)
    phone_mediums = [Broadcast.Mediums.SMS, Broadcast.Mediums.WHATSAPP]
    for phone, users in phone_grouped_users.items():
        if len(users) > 1:
            unique_names = []
            for u in users:
                name = u.first_name or 'Candidate'
                if name not in unique_names:
                    unique_names.append(name)

            if len(unique_names) > 2:
                candidate_name = ", ".join(unique_names[:-1]) + f", and {unique_names[-1]}"
            elif len(unique_names) == 2:
                candidate_name = " and ".join(unique_names)
            else:
                candidate_name = unique_names[0]
        else:
            candidate_name = users[0].first_name or 'Candidate'

        format_args = {
            'candidate_name': candidate_name,
            'exam_title': exam.get_title(),
            **template_kwargs
        }
        personalized_message = message_template.format(**format_args)

        notify_user_task.delay(
            user=users[0],
            subject=subject,
            message=personalized_message,
            mediums=phone_mediums,
            notification_type='info',
        )

    logger.info(
        f"Queued '{event_type}' notifications for exam {exam.id} "
        f"to {notification_count} candidate(s)"
    )