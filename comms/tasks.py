import logging
from typing import List

from django.db import DatabaseError
from django.conf import settings
from django.core.mail import send_mail
from celery import shared_task

from identity.models import User
from vmlc.utils.exceptions import ServerError
from comms.services.notification import NotificationService
from comms.services.kudi_sms import KudiSmsService
from comms.services.slack import SlackService

logger = logging.getLogger(__name__)

notification_service = NotificationService()
kudi_sms_service = KudiSmsService()
slack_service = SlackService()


@shared_task(
    bind=True,
    name="send_broadcast_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_broadcast_task(self, broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    """
    try:
        result = notification_service.send_broadcast(broadcast_id)
        return result
    except (DatabaseError, ServerError) as e:
        logger.warning(
            "Retryable error for broadcast %s (attempt %s/%s): %s",
            broadcast_id,
            self.request.retries + 1,
            self.max_retries,
            str(e),
        )
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.exception(
            "Fatal error during broadcast %s: %s",
            broadcast_id,
            str(e),
        )
        raise


@shared_task(name="notify_prereg_users_via_whatsapp_task")
def notify_prereg_users_via_whatsapp_task():
    """
    Notify PreRegUser entities via WhatsApp if registration is open.
    """
    import re
    from django.conf import settings
    from vmlc.models import FeatureFlag
    from identity.models import PreRegUser

    if not FeatureFlag.get_bool("candidate_registration"):
        logger.info("Candidate registration is closed. Skipping WhatsApp notification.")
        return

    candidates = PreRegUser.objects.filter(
        interest_type=PreRegUser.InterestType.CANDIDATE
    )

    if not candidates.exists():
        logger.info("No pre-registered candidates found.")
        return

    phones = []
    for candidate in candidates:
        if not candidate.phone:
            continue

        phone = candidate.phone.strip()
        if re.match(r"^(\+234[789][01]\d{8})$", phone):
            phones.append(phone)
        elif re.match(r"^(0[789][01]\d{8})$", phone):
            phones.append("+234" + phone[1:])

    if not phones:
        logger.info("No valid phone numbers found for pre-registered candidates.")
        return

    phones = list(set(phones))

    registration_url = f"{settings.LANDING_BASE_URL}/register"
    message = (
        f"Hi! Registration for the Verboheit Mathematics League Competition is now open. "
        f"You previously expressed interest. Please complete your registration here: {registration_url}"
    )

    result = notification_service.send_bulk_phone_msg(
        body=message, recipients=phones, medium="whatsapp"
    )

    logger.info(
        f"Pre-reg WhatsApp notification task completed. "
        f"Success: {result.get('success_count', 0)}, Failed: {result.get('failure_count', 0)}"
    )


@shared_task(
    bind=True,
    name="notify_user_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def notify_user_task(
    self,
    user: User,
    subject: str,
    message: str,
    mediums: List[str],
    type: str,
):
    """
    Sends a notification to a single user.
    """
    results = notification_service.notify_user(
        user=user,
        subject=subject,
        message=message,
        mediums=mediums,
        type=type,
    )
    if not results.get("email"):
        raise self.retry(exc="Email medium failed", countdown=60)


@shared_task(name="notify_candidates_about_exam_task")
def notify_candidates_about_exam_task(exam_id, event_type):
    """
    Unified task to notify candidates about exam events (scheduled or started).
    """
    from vmlc.models import Exam

    try:
        exam = Exam.objects.select_related("competition_slot__competition_stage").get(
            id=exam_id
        )
        notification_service.notify_candidates_about_exam(
            exam=exam, event_type=event_type
        )
    except Exam.DoesNotExist:
        logger.error(f"Exam {exam_id} not found for notification task.")


@shared_task(
    bind=True,
    name="send_bulk_sms_task",
    max_retries=12,
    default_retry_delay=3600,  # 1 hour
    queue="comms",
)
def send_bulk_sms_task(
    self, body: str, recipients: List[str], broadcast_log_id: int = None
):
    """
    Sends bulk SMS and retries if the balance is insufficient.
    Updates the BroadcastLog status if broadcast_log_id is provided.
    """
    from comms.models import BroadcastLog

    log = None
    if broadcast_log_id:
        try:
            log = BroadcastLog.objects.get(id=broadcast_log_id)
        except BroadcastLog.DoesNotExist:
            logger.error(f"BroadcastLog with id {broadcast_log_id} not found.")
            return

    try:
        estimated_cost = kudi_sms_service.estimate_cost(body, len(recipients))
        balance_resp = kudi_sms_service.get_balance()
        current_balance = kudi_sms_service.parse_balance(
            balance_resp.get("balance", "0")
        )

        logger.info(
            "Kudi SMS Task: Cost ~%s N, Balance: %s N",
            estimated_cost,
            current_balance,
        )

        if current_balance < estimated_cost:
            logger.warning(
                "Insufficient Kudi balance for bulk SMS (log: %s). Retrying in 1 hour.",
                broadcast_log_id,
            )
            if self.request.retries == 0:
                slack_service.send_low_kudi_balance_alert(
                    current_balance, estimated_cost, len(recipients)
                )
            raise self.retry(countdown=3600)

        kudi_recipients = ",".join([r.lstrip("+") for r in recipients])
        response = kudi_sms_service.send_bulk_sms(
            message=body, recipients=kudi_recipients
        )

        is_success = response.get("status") == "success" or response.get("error") == 0

        if is_success:
            logger.info(
                "Bulk SMS via Kudi sent successfully for log %s.", broadcast_log_id
            )
            if log:
                from django.utils import timezone
                from django.db.models import F

                log.status = BroadcastLog.MediumStatus.SENT
                log.sent_at = timezone.now()
                log.recipient_count = len(recipients)
                log.message = f"Successfully sent to {len(recipients)} recipients."
                log.save(
                    update_fields=["status", "sent_at", "recipient_count", "message"]
                )

                # Update broadcast stats and potentially final status
                broadcast = log.broadcast
                broadcast.total_recipients = F("total_recipients") + len(recipients)
                broadcast.save(update_fields=["total_recipients"])
                broadcast.refresh_from_db()

                # Check if this was the last pending medium/role
                if not broadcast.logs.filter(
                    status=BroadcastLog.MediumStatus.PENDING
                ).exists():
                    from comms.services.notification import NotificationService

                    ns = NotificationService()
                    total = broadcast.logs.count()
                    success = broadcast.logs.filter(
                        status=BroadcastLog.MediumStatus.SENT
                    ).count()
                    broadcast.status = ns._resolve_broadcast_status(total, success)
                    if broadcast.status == broadcast.Status.SENT:
                        broadcast.sent_at = timezone.now()
                    broadcast.save(update_fields=["status", "sent_at"])

                    # Invalidate cache
                    from django.core.cache import cache
                    from vmlc.v2.utils import CacheKeys

                    cache.delete(
                        CacheKeys.BROADCAST_DETAIL.format(broadcast_id=broadcast.pk)
                    )
                    cache.delete(CacheKeys.BROADCAST_SUMMARY)
                    logger.info(
                        f"Invalidated broadcast cache for broadcast {broadcast.pk} from task."
                    )

            return {"status": "SUCCESS", "count": len(recipients)}
        else:
            message = response.get("message", "Unknown error from Kudi")
            logger.error(
                "Bulk SMS via Kudi failed for log %s: %s. Retrying in 5 mins.",
                broadcast_log_id,
                message,
            )
            if log:
                log.message = f"Kudi API Error: {message}. Retrying..."
                log.save(update_fields=["message"])
            raise self.retry(countdown=300)

    except self.retry as e:
        raise e
    except Exception as e:
        logger.exception(
            "Unexpected error in send_bulk_sms_task for log %s.", broadcast_log_id
        )
        if log:
            log.status = BroadcastLog.MediumStatus.FAILED
            log.message = f"Fatal Error: {str(e)}"
            log.save(update_fields=["status", "message"])
        raise


@shared_task(
    bind=True,
    name="send_mail_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_mail_task(self, subject, message, recipient_list, html_message=None):
    """
    Celery task to send an email asynchronously.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=html_message,
        )
        logger.info(f"Successfully sent email to {recipient_list}")
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, name="send_system_email_task", max_retries=20)
def send_system_email_task(
    self,
    obj_id=None,
    generated_password=None,
    is_pre_reg=False,
    is_full_reg=False,
    is_public_support=False,
    is_support_notification=False,
):
    """
    Send system emails for user registration and support inquiries.
    """
    from comms.services.email import (
        send_system_email,
        build_registration_welcome_email,
        build_pre_registration_email,
        build_support_confirmation_email,
        build_support_notification_email,
    )
    from identity.models import User, PreRegUser
    from comms.models import PublicSupportRequest

    if not obj_id:
        logger.error("No object ID provided for email task")
        return

    try:
        # Determine object type and build email content
        if is_pre_reg:
            user = PreRegUser.objects.get(pk=obj_id)
            subject, message = build_pre_registration_email(user=user)
            recipient_email = user.email
            email_type = "pre-registration"

        elif is_full_reg:
            user = User.objects.get(pk=obj_id)
            subject, message = build_registration_welcome_email(
                user=user, generated_password=generated_password
            )
            recipient_email = user.email
            email_type = "full registration"

        elif is_public_support:
            inquiry = PublicSupportRequest.objects.get(pk=obj_id)
            subject, message = build_support_confirmation_email(inquiry=inquiry)
            recipient_email = inquiry.email
            email_type = "support inquiry"

        elif is_support_notification:
            inquiry = PublicSupportRequest.objects.get(pk=obj_id)
            subject, message = build_support_notification_email(inquiry=inquiry)
            recipient_email = settings.SUPPORT_EMAIL
            email_type = "support notification"

        else:
            logger.error(f"No valid email type specified for object ID {obj_id}")
            return

    except (
        User.DoesNotExist,
        PreRegUser.DoesNotExist,
        PublicSupportRequest.DoesNotExist,
    ) as e:
        logger.error(f"Object not found for email task: {e}")
        return

    # Send email with retry logic
    try:
        send_system_email(subject, message, recipient_email)
        logger.info(
            f"{email_type.capitalize()} email sent successfully to {recipient_email}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send {email_type} email to {recipient_email} "
            f"(attempt {self.request.retries + 1}/{self.max_retries}): {e}"
        )

        if self.request.retries >= self.max_retries - 1:
            logger.error(
                f"Max retries reached for {email_type} email to {recipient_email}. "
                f"Object ID: {obj_id}"
            )


@shared_task(bind=True, name="send_welcome_mail_task", max_retries=20)
def send_welcome_mail_task(
    self, user_id=None, generated_password=None, is_pre_reg=False
):
    """Send welcome email to newly registered user."""
    from comms.services.email import send_welcome_email
    from identity.models import User, PreRegUser
    from celery.exceptions import Retry

    if is_pre_reg:
        user = PreRegUser.objects.get(pk=user_id)
    else:
        user = User.objects.get(pk=user_id)

    try:
        send_welcome_email(user, generated_password)
        logger.info(f"Welcome email sent to {user.email}")
    except Retry:
        raise
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")
        if self.request.retries >= 3:
            logger.error(f"Max retries reached for user {user_id}. Giving up.")
            return

        raise self.retry(exc=e, countdown=60)


@shared_task(
    bind=True,
    name="send_otp_on_registration_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_otp_on_registration_task(self, user_id):
    """
    Celery task to send OTP to user on registration.
    """
    from identity.models import User
    from vmlc.utils.auth import send_otp_to_email
    from celery.exceptions import Retry

    try:
        user = User.objects.get(pk=user_id)
        send_otp_to_email(user)
        logger.info(f"Successfully sent OTP to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
    except Retry:
        raise
    except Exception as exc:
        logger.error(f"Failed to send OTP to user with id {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="helpdesk_escalation_task", queue="comms")
def helpdesk_escalation_task(message_id):
    """
    Check if a support message from a candidate has been replied to within 2 minutes.
    If not, escalate to admins and managers.
    """
    from comms.models import ThreadMessage, HelpdeskThread
    from identity.models import Staff
    from vmlc.models import ExamAccess, Exam
    from django.db.models import Q
    from django.utils import timezone

    try:
        message = ThreadMessage.objects.select_related("thread__candidate").get(
            id=message_id
        )
        thread = message.thread
        candidate = thread.candidate

        # Get the absolute latest message in this thread
        latest_message = thread.messages.order_by("-created_at").first()
        exam_title = None
        # Only proceed if the latest message is still from a candidate
        if (
            latest_message
            and latest_message.sender_type == ThreadMessage.SenderType.CANDIDATE
        ):
            exam_id = message.metadata.get("exam_id") if message.metadata else None
            is_ongoing_exam = False

            if exam_id:
                try:
                    # Check for an active ExamAccess record for this candidate and exam
                    exam_access = ExamAccess.objects.get(
                        candidate=candidate,
                        exam_id=exam_id,
                        status=ExamAccess.Status.STARTED,
                        deadline__gt=timezone.now(),
                    )
                    # Additionally, check if the parent Exam itself is considered 'ONGOING'
                    # The Exam.status property handles scheduled_date and open_duration_hours logic
                    exam = exam_access.exam
                    exam_title = exam.get_title()
                    if exam.status == Exam.Status.ONGOING:
                        is_ongoing_exam = True
                        logger.info(
                            f"Exam {exam_id} is ongoing for candidate {candidate.user.email}."
                        )
                    else:
                        logger.info(
                            f"Exam {exam_id} is NOT ongoing for candidate {candidate.user.email} (status: {exam.status})."
                        )

                except ExamAccess.DoesNotExist:
                    logger.info(
                        f"No active ExamAccess found for candidate {candidate.user.email} for exam {exam_id}."
                    )
                except Exam.DoesNotExist:
                    logger.warning(
                        f"Exam {exam_id} referenced in metadata not found for candidate {candidate.user.email}."
                    )
                except Exception as e:
                    logger.exception(
                        f"Error checking ongoing exam status for candidate {candidate.user.email}, exam {exam_id}: {e}"
                    )

            if not exam_id or not is_ongoing_exam:
                logger.info(
                    f"Skipping helpdesk escalation for thread {thread.id}. No exam_id in metadata or exam not ongoing."
                )
                return

            # If we reach here, it means the candidate is in an ongoing exam and
            # the latest message is still from them. Proceed with escalation.
            logger.info(
                f"Escalating helpdesk thread {thread.id} - candidate in ongoing exam, no staff reply after 2 minutes."
            )

            # 1. Send Slack Alert
            slack_service.send_support_escalation_alert(thread, latest_message)

            # 2. Get admins and managers for Email/SMS
            escalation_targets = Staff.objects.filter(
                Q(role=Staff.Roles.MANAGER) | Q(role=Staff.Roles.ADMIN),
                user__is_active=True,
            ).select_related("user")

            subject = f"URGENT: Helpdesk Escalation - {thread.candidate.user.get_full_name()} - {exam_title}"
            body = (
                f"Helpdesk thread for {thread.candidate.user.get_full_name()} ({thread.candidate.user.email}) "
                f"has a new message during an ongoing exam and has been waiting for a reply for over 2 minutes.\\n\\n"
                f"Exam ID: {exam_id}\\n"
                f"Latest Message: {latest_message.text}\\n\\n"
                f"Please review and respond immediately."
            )

            for staff in escalation_targets:
                # Send Email
                notification_service.notify_user(
                    user=staff.user,
                    subject=subject,
                    message=body,
                    mediums=["email", "platform"],
                    type="alert",
                )
                # Send SMS
                if staff.user.phone:
                    notification_service.notify_user(
                        user=staff.user,
                        subject=subject,
                        message=body,
                        mediums=["sms"],
                        type="alert",
                    )

    except ThreadMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found for escalation task.")
    except Exception as e:
        logger.exception(f"Error in helpdesk_escalation_task: {e}")
