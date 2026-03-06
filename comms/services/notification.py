import logging
from smtplib import SMTPException
from time import sleep
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from comms.models import Broadcast, BroadcastLog, Notification
from comms.services.kudi_sms import KudiSmsService
from comms.utils import (
    _normalize_phone,
    format_sms_body,
    is_placeholder_phone as _is_placeholder_phone,
)
from vmlc.utils.exceptions import (
    InvalidMediumError,
    NoRecipientsFoundError,
    ServerError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Nigerian local number pattern (e.g. 08012345678)
# _LOCAL_PHONE_RE = re.compile(r"^(0[789][01]\d{8})$")
_PLACEHOLDER_PHONE = "2349123456789"


class NotificationService:
    """
    Central service for dispatching notifications and broadcasts across all
    supported mediums: Platform (WebSocket), Email, SMS, and WhatsApp.

    Intended to be used directly or via Celery tasks for async execution.
    """

    def __init__(self) -> None:
        self.kudi_sms_service = KudiSmsService()
        self.twilio_client: Optional[TwilioClient] = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def notify_user(
        self,
        user,
        subject: str,
        message: str,
        mediums: Optional[List[str]] = None,
        notification_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[timezone.datetime] = None,
    ) -> Dict[str, bool]:
        """
        Send a notification to a single user across one or more mediums.

        Returns a dict mapping each medium name to a boolean indicating
        whether dispatch succeeded.
        """
        if mediums is None:
            mediums = [Broadcast.Mediums.PLATFORM]

        results: Dict[str, bool] = {}

        # Flag for centralized email delivery if both platform and email are requested
        has_platform = Broadcast.Mediums.PLATFORM in mediums
        has_email = Broadcast.Mediums.EMAIL in mediums

        if has_platform and has_email:
            metadata = metadata or {}
            metadata["send_email"] = True

        for medium in mediums:
            if medium == Broadcast.Mediums.SMS:
                body_to_send = format_sms_body(subject, message)
            else:
                body_to_send = f"{subject}:\n\n{message}" if subject else message

            try:
                if medium == Broadcast.Mediums.PLATFORM:
                    results["platform"] = self._send_platform_notification(
                        user=user,
                        subject=subject,
                        full_body=body_to_send,
                        notification_type=notification_type,
                        metadata=metadata,
                        expires_at=expires_at,
                    )

                elif medium == Broadcast.Mediums.EMAIL:
                    if has_platform:
                        # Skip explicit email send; handled by Notification signal
                        results["email"] = True
                        continue

                    from comms.tasks import send_mail_task

                    html_message = metadata.get("html_message") if metadata else None
                    send_mail_task.delay(
                        subject=subject,
                        message=message,
                        recipient_list=[user.email],
                        html_message=html_message,
                    )
                    results["email"] = True

                elif medium == Broadcast.Mediums.SMS:
                    results["sms"] = self._dispatch_phone_notification(
                        user=user, body=body_to_send, medium="sms"
                    )

                elif medium == Broadcast.Mediums.WHATSAPP:
                    results["whatsapp"] = self._dispatch_phone_notification(
                        user=user, body=body_to_send, medium="whatsapp"
                    )

            except Exception as e:
                logger.error(
                    "Failed to send %s notification to user %s: %s",
                    medium,
                    user.id,
                    e,
                )
                results[medium] = False

        return results

    def send_broadcast(self, broadcast_id: int) -> Dict[str, Any]:
        """
        Execute a broadcast: resolve recipients, dispatch per medium/role, and
        update the broadcast's status and associated ``BroadcastLog`` records.

        Returns a summary dict with counts and final status.
        """
        from identity.models import Candidate, Staff

        try:
            broadcast = Broadcast.objects.select_related("created_by__user").get(
                id=broadcast_id
            )
        except Broadcast.DoesNotExist:
            logger.error("Broadcast not found (id=%s)", broadcast_id)
            return {"error": "Broadcast not found", "broadcast_id": broadcast_id}

        # Handle retry logic and initial status
        if broadcast.status in [Broadcast.Status.FAILED, Broadcast.Status.PARTIAL]:
            broadcast.retry_count += 1

        broadcast.status = Broadcast.Status.IN_PROGRESS
        broadcast.last_attempt = timezone.now()
        broadcast.save(update_fields=["status", "last_attempt", "retry_count"])

        logger.info(
            "Starting broadcast %s (retry #%d): '%s'",
            broadcast_id,
            broadcast.retry_count,
            broadcast.subject,
        )

        total_attempts = 0
        successful_attempts = 0
        total_recipients_reached = 0

        recipients_by_key = self._resolve_recipients(broadcast, Staff, Candidate)

        for medium in broadcast.mediums:
            for user_type, roles in broadcast.target_roles.items():
                for role in roles:
                    total_attempts += 1
                    key = f"{user_type}_{role}"
                    recipients = recipients_by_key.get(key, [])
                    count = len(recipients)

                    log = BroadcastLog.objects.create(
                        broadcast=broadcast,
                        medium=medium,
                        target_role=role,
                        role_type=user_type,
                        status=BroadcastLog.MediumStatus.PENDING,
                        recipient_count=count,
                    )

                    try:
                        if not recipients:
                            raise NoRecipientsFoundError(
                                "No active %s found for role '%s'" % (user_type, role)
                            )

                        if medium == Broadcast.Mediums.EMAIL:
                            self._send_email_broadcast(broadcast, recipients, role)
                        elif medium == Broadcast.Mediums.PLATFORM:
                            self._send_platform_broadcast(broadcast, recipients, role)
                        elif medium == Broadcast.Mediums.SMS:
                            # Note: Bulk SMS task might update this log asynchronously
                            self._send_sms_broadcast(broadcast, recipients, log)
                        elif medium == Broadcast.Mediums.WHATSAPP:
                            pass  # Not yet implemented
                        else:
                            raise InvalidMediumError(
                                "Unknown medium specified: %s" % medium
                            )

                        # For synchronous mediums (Email, Platform), we mark as sent here
                        if medium in [
                            Broadcast.Mediums.EMAIL,
                            Broadcast.Mediums.PLATFORM,
                        ]:
                            log.status = BroadcastLog.MediumStatus.SENT
                            log.sent_at = timezone.now()
                            log.message = "Successfully sent to %d recipients" % count
                            log.save(update_fields=["status", "sent_at", "message"])
                            successful_attempts += 1
                            total_recipients_reached += count

                    except (
                        SMTPException,
                        ValidationError,
                        NotImplementedError,
                        NoRecipientsFoundError,
                        InvalidMediumError,
                        ServerError,
                        DatabaseError,
                    ) as e:
                        log.status = BroadcastLog.MediumStatus.FAILED
                        log.message = "Error: %s" % e
                        log.save(update_fields=["status", "message"])
                        logger.error(
                            "Error for broadcast %s (%s -> %s:%s): %s",
                            broadcast_id,
                            medium,
                            user_type,
                            role,
                            e,
                        )

        # Final status resolution: only if no logs are still PENDING
        if not broadcast.logs.filter(status=BroadcastLog.MediumStatus.PENDING).exists():
            final_status = self._resolve_broadcast_status(
                total_attempts, successful_attempts
            )
            broadcast.status = final_status
            if final_status == Broadcast.Status.SENT:
                broadcast.sent_at = timezone.now()

        # Atomically increment total_recipients
        if total_recipients_reached > 0:
            broadcast.total_recipients = (
                F("total_recipients") + total_recipients_reached
            )

        broadcast.save(update_fields=["status", "total_recipients", "sent_at"])

        cache.delete("broadcast_detail_%s" % broadcast_id)
        cache.delete("broadcast_summary_data")

        return {
            "broadcast_id": broadcast_id,
            "status": broadcast.status,
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "total_recipients_reached_now": total_recipients_reached,
            "subject": broadcast.subject,
            "completed_at": timezone.now().isoformat(),
        }

    def notify_candidates_about_exam(self, exam, event_type: str) -> None:
        """
        Send scheduled, reminder, or started notifications to all candidates enrolled in
        the stage associated with the given exam.

        ``event_type`` must be ``'scheduled'``, ``'reminder'``, or ``'started'``.
        """
        from competition.models import Enrollment

        if event_type not in ("scheduled", "started", "reminder"):
            logger.warning(
                "Invalid event_type: '%s'. Must be 'scheduled', 'started', or 'reminder'.",
                event_type,
            )
            return

        if exam.competition_slot is None:
            logger.warning(
                "Exam %s has no competition_slot; skipping '%s' notifications.",
                exam.id,
                event_type,
            )
            return

        stage = exam.competition_slot.competition_stage
        eligible_enrollments = Enrollment.objects.filter(
            current_stage=stage,
            status=Enrollment.Status.ACTIVE,
        ).select_related("candidate__user")

        if not eligible_enrollments.exists():
            logger.info(
                "No candidates to notify for exam %s (%s).", exam.id, event_type
            )
            return

        subject, message_template, sms_template, template_kwargs = (
            self._build_exam_notification_content(exam, event_type)
        )

        from comms.services.email import create_email_html

        phone_grouped_users: Dict[str, list] = {}
        notification_count = 0

        for enrollment in eligible_enrollments:
            user = enrollment.candidate.user
            notification_count += 1

            personalized_message = message_template.format(
                candidate_name=user.first_name or "Candidate",
                exam_title=exam.get_title(),
                **template_kwargs,
            )
            html_message = create_email_html(
                subject=subject, message=personalized_message
            )

            self.notify_user(
                user=user,
                subject=subject,
                message=personalized_message,
                mediums=[Broadcast.Mediums.EMAIL],
                # mediums=[Broadcast.Mediums.PLATFORM, Broadcast.Mediums.EMAIL],
                notification_type="info",
                metadata={"html_message": html_message},
            )

            if not user.phone:
                continue

            phone = _normalize_phone(user.phone)
            if _is_placeholder_phone(phone):
                continue

            phone_grouped_users.setdefault(phone, []).append(user)

        # phone_mediums = [Broadcast.Mediums.SMS, Broadcast.Mediums.WHATSAPP]
        for phone, users in phone_grouped_users.items():
            candidate_name = self._format_grouped_names(users)
            personalized_sms = sms_template.format(
                candidate_name=candidate_name,
                exam_title=exam.get_title(),
                **template_kwargs,
            )
            # Use send_bulk_phone_msg to ensure it's queued if using Kudi
            self.send_bulk_phone_msg(
                body=personalized_sms,
                recipients=[phone],
                medium=Broadcast.Mediums.SMS,
            )

        logger.info(
            "Queued '%s' notifications for exam %s to %d candidate(s).",
            event_type,
            exam.id,
            notification_count,
        )

    def notify_ranking_published(self, ranking) -> None:
        """
        Notify candidates that exam results are available, and alert staff via Slack/Email.
        """
        from identity.models import Staff
        from comms.services.slack import SlackService

        ENV = settings.APP_ENVIRONMENT
        exam = ranking.exam

        # Environment-aware subject prefix
        env_prefix = f"{ENV.title()} " if ENV != "production" else ""
        subject = f"{env_prefix}Results Published: {exam.get_title()}"

        # 1. Notify Candidates (via Broadcast)
        candidate_message = (
            f"Dear Candidate,\n\n"
            f"The results for '{exam.get_title()}' have been published and are now available on your dashboard.\n\n"
            f"Log in now to view your performance:\n\n"
            f"{settings.FRONTEND_BASE_URL}/login\n\n"
            f"Regards,\n"
            f"VMLC Team."
        )

        candidate_broadcast = Broadcast.objects.create(
            subject=subject,
            message=candidate_message,
            mediums=[Broadcast.Mediums.EMAIL],
            target_roles={"candidate": [ranking.stage]},
            status=Broadcast.Status.PENDING,
        )
        self.send_broadcast(candidate_broadcast.id)

        # 2. Notify Staff (Managers, Admins) (via Broadcast)
        staff_subject = f"{env_prefix}System Update: Results Published for {exam.get_title()}"
        ignore_message = f"You may ignore this alert, as testing is ongoing.\n\n" if ENV != 'production' else ""
        staff_message = (
            f"The ranking table for '{exam.get_title()}' has been published "
            f"for {ranking.entries.count()} candidates.\n\n"
            f"This is an automated message for the {ENV.title()} environment.\n\n"
            f"{ignore_message}"
            "Regards,\n"
            "VMLC Bot."
        )

        staff_broadcast = Broadcast.objects.create(
            subject=staff_subject,
            message=staff_message,
            mediums=[Broadcast.Mediums.EMAIL],
            target_roles={
                "staff": [Staff.Roles.ADMIN, Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]
            },
            status=Broadcast.Status.PENDING,
        )
        self.send_broadcast(staff_broadcast.id)

        # 3. Slack Notification
        slack = SlackService()
        slack.send_ranking_published_notification(ranking)

        logger.info(
            f"Triggered 'Results Published' broadcasts for {exam.get_title()} to "
            f"candidates ({ranking.stage}) and management staff."
        )

    def send_phone_msg(self, body: str, recipient: str, medium: str) -> Dict[str, Any]:
        """
        Send a single SMS or WhatsApp message to one recipient.

        Returns a dict with keys: ``success``, ``recipient``, ``error``, ``sid``.
        """
        if medium not in ("sms", "whatsapp"):
            raise InvalidMediumError(
                "Invalid medium: '%s'. Must be 'sms' or 'whatsapp'." % medium
            )

        try:
            if medium == "sms":
                return self._send_via_sms(body=body, recipient=recipient)
            if medium == "whatsapp":
                return self._send_via_whatsapp(body=body, recipient=recipient)

        except TwilioRestException as e:
            logger.error(
                "Failed to send %s to %s: [%s] %s",
                medium.upper(),
                recipient[:8] + "***",
                e.code,
                e.msg,
            )
            return {
                "success": False,
                "recipient": recipient,
                "error": "[%s] %s" % (e.code, e.msg),
                "sid": None,
            }

        return {
            "success": False,
            "recipient": recipient,
            "error": "Unknown error",
            "sid": None,
        }

    def send_bulk_phone_msg(
        self,
        body: str,
        recipients: List[str],
        medium: str,
        delay: float = 0.1,
        broadcast_log_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch a message to multiple phone recipients.

        For Kudi SMS, enqueues a Celery task and returns immediately with
        ``status: "QUEUED"``. For all other providers/mediums, sends
        sequentially with an optional inter-message ``delay`` (in seconds).
        """
        if not recipients:
            logger.warning("No recipients provided for bulk %s.", medium)
            return {
                "success_count": 0,
                "failure_count": 0,
                "failed_recipients": [],
                "total": 0,
            }

        logger.info(
            "Processing bulk %s to %d recipients.", medium.upper(), len(recipients)
        )

        sms_provider = getattr(settings, "SMS_PROVIDER", "kudi").lower()
        if medium == "sms" and sms_provider == "kudi":
            from comms.tasks import send_bulk_sms_task

            send_bulk_sms_task.delay(
                body=body, recipients=recipients, broadcast_log_id=broadcast_log_id
            )
            logger.info(
                "Queued bulk SMS task for %d recipients (log: %s).",
                len(recipients),
                broadcast_log_id,
            )
            return {
                "status": "QUEUED",
                "message": "Task queued to send SMS to %d recipients."
                % len(recipients),
                "total": len(recipients),
            }

        results = []
        for i, recipient in enumerate(recipients, 1):
            result = self.send_phone_msg(body=body, recipient=recipient, medium=medium)
            results.append(result)
            if i < len(recipients) and delay > 0:
                sleep(delay)

        success_count = sum(1 for r in results if r["success"])
        failure_count = len(results) - success_count
        failed_recipients = [r["recipient"] for r in results if not r["success"]]

        logger.info(
            "Bulk %s complete: %d succeeded, %d failed out of %d total.",
            medium.upper(),
            success_count,
            failure_count,
            len(recipients),
        )

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "failed_recipients": failed_recipients,
            "total": len(recipients),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _send_platform_notification(
        self,
        user,
        subject: str,
        full_body: str,
        notification_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[timezone.datetime] = None,
    ) -> bool:
        """Create a platform ``Notification`` record (delivery is handled by signal)."""
        Notification.objects.create(
            recipient=user,
            subject=subject,
            message=full_body,
            type=notification_type,
            metadata=metadata or {},
            expires_at=expires_at,
            created_at=timezone.now(),
        )
        return True

    def _dispatch_phone_notification(self, user, body: str, medium: str) -> bool:
        """Normalize the user's phone number and dispatch an SMS or WhatsApp message."""
        if not (hasattr(user, "phone") and user.phone):
            logger.warning(
                "User %s has no phone number for %s notification.", user.id, medium
            )
            return False

        phone = _normalize_phone(user.phone)
        self.send_phone_msg(body=body, recipient=phone, medium=medium)
        return True

    def _resolve_recipients(
        self, broadcast: Broadcast, Staff, Candidate
    ) -> Dict[str, list]:
        """
        Query and return all active recipients grouped by ``{user_type}_{role}`` keys.
        """
        recipients_by_key: Dict[str, list] = {}

        for user_type, roles in broadcast.target_roles.items():
            for role in roles:
                key = "%s_%s" % (user_type, role)
                if user_type == "staff":
                    queryset = Staff.objects.select_related("user").filter(
                        role=role, user__is_active=True
                    )
                else:
                    queryset = Candidate.objects.select_related("user").filter(
                        role=role, user__is_active=True
                    )
                recipients_by_key[key] = list(
                    queryset.values("user__id", "user__email", "user__phone")
                )
                logger.info(
                    "Found %d active %s users for role '%s'.",
                    len(recipients_by_key[key]),
                    user_type,
                    role,
                )

        return recipients_by_key

    @staticmethod
    def _resolve_broadcast_status(total_attempts: int, successful_attempts: int) -> str:
        """Derive the overall broadcast status from attempt counts."""
        if successful_attempts == total_attempts:
            return Broadcast.Status.SENT
        if successful_attempts > 0:
            return Broadcast.Status.PARTIAL
        return Broadcast.Status.FAILED

    def _send_sms_broadcast(
        self, broadcast: Broadcast, recipients: list, log: BroadcastLog
    ) -> None:
        phones = [r["user__phone"] for r in recipients if r.get("user__phone")]
        if not phones:
            raise NoRecipientsFoundError("No phone numbers found for recipients.")

        valid_phones = [
            _normalize_phone(p)
            for p in phones
            if not _is_placeholder_phone(_normalize_phone(p))
        ]
        if not valid_phones:
            raise NoRecipientsFoundError(
                "No valid, non-placeholder phone numbers found."
            )

        if broadcast.sms_message:
            full_body = broadcast.sms_message
        else:
            full_body = format_sms_body(broadcast.subject, broadcast.message)

        try:
            self.send_bulk_phone_msg(
                body=full_body,
                recipients=valid_phones,
                medium="sms",
                broadcast_log_id=log.id,
            )
            logger.info(
                "SMS broadcast %s queued for %d recipients.",
                broadcast.id,
                len(valid_phones),
            )
        except Exception as e:
            logger.error(
                "Failed to queue SMS broadcast task for broadcast %s: %s",
                broadcast.id,
                e,
            )
            raise ValidationError("SMS task queuing error: %s" % e) from e

    def _send_email_broadcast(
        self, broadcast: Broadcast, recipients: list, role: str
    ) -> None:
        valid_emails = [r["user__email"] for r in recipients if r.get("user__email")]
        if not valid_emails:
            raise NoRecipientsFoundError(
                "No valid email addresses found for role '%s'." % role
            )

        from comms.tasks import send_mail_task
        from comms.services.email import create_email_html

        html_message = create_email_html(
            subject=broadcast.subject, message=broadcast.message
        )

        # send_mass_mail is synchronous. Since send_broadcast is often called
        # from a celery task (send_broadcast_task), we can offload each email
        # to a separate task or just loop here. Offloading is better for scaling.
        for email in valid_emails:
            send_mail_task.delay(
                subject=broadcast.subject,
                message=broadcast.message,
                recipient_list=[email],
                html_message=html_message,
            )

        logger.info(
            "Email tasks queued for broadcast %s to %d recipients (role: %s).",
            broadcast.id,
            len(valid_emails),
            role,
        )

    def _send_platform_broadcast(
        self, broadcast: Broadcast, recipients: list, role: str
    ) -> None:
        from comms.signals import notifications_created

        user_ids = [r["user__id"] for r in recipients if r.get("user__id")]
        if not user_ids:
            raise NoRecipientsFoundError("No user IDs found for role '%s'." % role)

        full_body = (
            "%s:\n\n%s" % (broadcast.subject, broadcast.message)
            if broadcast.subject
            else broadcast.message
        )

        notifications_to_create = [
            Notification(
                recipient_id=user_id,
                subject=broadcast.subject,
                message=full_body,
                type=Notification.Type.INFO,
                created_at=timezone.now(),
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
            raise ServerError("Failed to save notifications to the database.") from e

        notifications_created.send(
            sender=self.send_broadcast, notifications=created_notifications
        )
        logger.info(
            "Platform notifications created for %d users (role: %s).",
            len(user_ids),
            role,
        )

    def _send_via_sms(self, body: str, recipient: str) -> Dict[str, Any]:
        """Send a single SMS, routing through the configured provider."""
        sms_provider = getattr(settings, "SMS_PROVIDER", "kudi").lower()
        if sms_provider == "kudi":
            kudi_recipient = recipient.lstrip("+")
            response = self.kudi_sms_service.send_bulk_sms(
                message=body, recipients=kudi_recipient
            )
            is_success = (
                response.get("status") == "success" or response.get("error") == 0
            )
            error_msg = response.get("message") if not is_success else None
            if is_success:
                logger.info("Sent SMS via Kudi to %s", recipient[:8] + "***")
            else:
                logger.error("Failed to send SMS via Kudi: %s", error_msg)
            return {
                "success": is_success,
                "recipient": recipient,
                "error": error_msg,
                "sid": response.get("request_id") or response.get("msgid"),
            }
        # Fallback: unsupported provider
        return {
            "success": False,
            "recipient": recipient,
            "error": "Unsupported SMS provider: %s" % sms_provider,
            "sid": None,
        }

    def _send_via_whatsapp(self, body: str, recipient: str) -> Dict[str, Any]:
        """Send a single WhatsApp message via Twilio."""
        if not self.twilio_client:
            logger.error("Twilio client is not configured.")
            return {
                "success": False,
                "recipient": recipient,
                "error": "Twilio client not configured.",
                "sid": None,
            }
        message = self.twilio_client.messages.create(
            body=body,
            from_="whatsapp:%s" % settings.TWILIO_FROM_PHONE,
            to="whatsapp:%s" % recipient,
        )
        logger.info("Sent WhatsApp to %s (SID: %s)", recipient[:8] + "***", message.sid)
        return {
            "success": True,
            "recipient": recipient,
            "error": None,
            "sid": message.sid,
        }

    @staticmethod
    def _build_exam_notification_content(exam, event_type: str):
        """
        Return (subject, message_template, sms_template, template_kwargs) for the given
        exam event type.
        """
        if event_type == "scheduled":
            subject = "New Exam Scheduled: %s" % exam.get_title()
            message_template = (
                "Dear {candidate_name},\n\n"
                "A new exam '{exam_title}' has been scheduled for your stage.\n"
                "Start Time: {start_time}\n\n"
                "Please log in to your dashboard for more details.\n\n"
                "Regards,\n"
                "VMLC Team"
            )
            sms_template = "Hi {candidate_name}. New exam '{exam_title}' scheduled for {start_time}. Check email or log in for details. -VMLC Team"
            template_kwargs = {
                "start_time": (
                    timezone.localtime(exam.scheduled_date).strftime(
                        "%a, %b %d, %I:%M %p"
                    )
                    if exam.scheduled_date
                    else "N/A"
                )
            }
        elif event_type == "reminder":
            subject = "Exam Reminder: %s starts in 1 hour" % exam.get_title()
            message_template = (
                "Dear {candidate_name},\n\n"
                "This is a reminder that your exam '{exam_title}' will start in approximately one hour.\n"
                "Start Time: {start_time}\n\n"
                "Please ensure you have a stable internet connection and are ready to begin.\n\n"
                "Regards,\n"
                "VMLC Team"
            )
            sms_template = "Reminder: Your exam '{exam_title}' starts in 1 hour ({start_time}). Get ready! -VMLC Team"
            template_kwargs = {
                "start_time": (
                    timezone.localtime(exam.scheduled_date).strftime(
                        "%a, %b %d, %I:%M %p"
                    )
                    if exam.scheduled_date
                    else "N/A"
                )
            }
        else:  # started
            from datetime import timedelta

            conclusion_time = exam.scheduled_date + timedelta(
                hours=exam.open_duration_hours
            )
            subject = "Exam Started: %s" % exam.get_title()
            message_template = (
                "Dear {candidate_name},\n\n"
                "The exam '{exam_title}' has started and is now open for taking.\n"
                "It will remain open until {conclusion_time}.\n\n"
                "Good luck,\n"
                "VMLC Team"
            )
            sms_template = "Exam '{exam_title}' has started! It closes at {conclusion_time}. Good luck! -VMLC Team"
            template_kwargs = {
                "conclusion_time": timezone.localtime(conclusion_time).strftime(
                    "%a, %b %d, %I:%M %p"
                )
            }

        return subject, message_template, sms_template, template_kwargs

    @staticmethod
    def _format_grouped_names(users: list) -> str:
        """
        Return a natural-language name string for a group of users sharing
        the same phone number (e.g. ``"Alice, Bob, and Carol"``).
        """
        seen = []
        for u in users:
            name = u.first_name or "Candidate"
            if name not in seen:
                seen.append(name)

        if len(seen) == 1:
            return seen[0]
        if len(seen) == 2:
            return " and ".join(seen)
        return ", ".join(seen[:-1]) + ", and " + seen[-1]
