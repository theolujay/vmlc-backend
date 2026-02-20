import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from vmlc.models import Exam, ExamAccess, ExamAccessPasscode
from competition.models import Enrollment
from rest_framework_simplejwt.tokens import RefreshToken

from vmlc.utils.exceptions import ServerError

logger = logging.getLogger(__name__)

class ExamAccessService:
    @staticmethod
    def generate_passcodes(exam_id):
        """
        Generates unique passcodes and URLs for all eligible candidates for an exam.
        Eligible candidates are those enrolled in the competition and currently in the
        stage the exam belongs to.
        """
        try:
            exam = Exam.objects.select_related('competition_slot__competition_stage').get(pk=exam_id)
        except Exam.DoesNotExist:
            logger.error(f"Exam {exam_id} not found.")
            return 0

        slot = exam.competition_slot
        if not slot:
            logger.warning(f"Exam {exam_id} is not linked to any competition slot.")
            return 0

        stage = slot.competition_stage
        if not stage:
            logger.warning(f"Competition slot {slot.id} has no competition stage.")
            return 0

        competition = stage.competition

        # Find eligible candidates: Active enrollment in this competition and current_stage matches exam's stage
        eligible_enrollments = Enrollment.objects.filter(
            competition=competition,
            current_stage=stage,
            status=Enrollment.Status.ACTIVE
        ).select_related('candidate')

        if not exam.scheduled_date or not exam.open_duration_hours:
            logger.warning(f"Exam {exam_id} is not fully scheduled.")
            return 0

        expiry_date = exam.scheduled_date + timedelta(hours=exam.open_duration_hours)

        count = 0
        with transaction.atomic():
            for enrollment in eligible_enrollments:
                candidate = enrollment.candidate
                # Get or create ExamAccess
                access, created = ExamAccess.objects.get_or_create(
                    exam=exam,
                    candidate=candidate,
                    defaults={
                        "facilitator_system": ExamAccess.Facilitator.VMLC,
                        "status": ExamAccess.Status.PENDING,
                    }
                )
                if not created and access.submitted_at is not None:
                    logger.warning(f"Generate passcode skipped for an already submitted exam (access {access.id})")
                    continue

                # Get or create ExamAccessPasscode
                passcode_record, p_created = ExamAccessPasscode.objects.get_or_create(
                    exam_access=access,
                    defaults={
                        "status": ExamAccessPasscode.Status.ISSUED,
                        "expiry_date": expiry_date,
                    }
                )

                # Generate passcode if it's new or expired or we want to force a refresh
                if p_created or passcode_record.status == ExamAccessPasscode.Status.EXPIRED or timezone.now() > passcode_record.expiry_date:
                    passcode_record.passcode = secrets.token_urlsafe(32)
                    passcode_record.status = ExamAccessPasscode.Status.ISSUED
                    passcode_record.expiry_date = expiry_date

                    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL")
                    if not frontend_base_url:
                        logger.error("FRONTEND_BASE_URL is not configured")
                        raise ServerError("FRONTEND_BASE_URL is not set")

                    base_url = frontend_base_url.rstrip('/')
                    passcode_record.access_url = f"{base_url}/?passcode={passcode_record.passcode}"
                    passcode_record.is_passcode_sent = False
                    passcode_record.save()
                    count += 1

        logger.info(f"Generated {count} passcodes for exam {exam_id}")
        return count

    @staticmethod
    def send_passcode_emails(exam_id):
        """
        Sends emails with access URLs to all candidates who have an unsent passcode for the exam.
        """
        from comms.tasks import send_mail_task
        from comms.services.email import create_email_html

        passcode_records = ExamAccessPasscode.objects.filter(
            exam_access__exam_id=exam_id,
            passcode__isnull=False,
            status=ExamAccessPasscode.Status.ISSUED,
            is_passcode_sent=False
        ).select_related('exam_access__candidate__user', 'exam_access__exam')

        sent_count = 0
        for p_record in passcode_records:
            user = p_record.exam_access.candidate.user
            exam_title = p_record.exam_access.exam.get_title()

            subject = f"Direct Access to your {exam_title}"
            message = (
                f"Hello {user.first_name},\n\n"
                f"You can access your upcoming exam '{exam_title}' directly by clicking the link below:\n\n"
                f"{p_record.access_url}\n\n"
                "This link is for your use only and will log you in directly to your dashboard. "
                "Note that this link is only valid when the exam is ongoing."
            )

            html_message = create_email_html(
                subject=subject,
                message=message
            )

            send_mail_task.delay(
                subject=subject,
                message=message,
                recipient_list=[user.email],
                html_message=html_message
            )

            # Mark as sent
            p_record.is_passcode_sent = True
            p_record.save(update_fields=['is_passcode_sent'])

            sent_count += 1

        logger.info(f"Queued {sent_count} passcode emails for exam {exam_id}")
        return sent_count

    @staticmethod
    @transaction.atomic
    def authenticate_passcode(passcode):
        """
        Verifies a passcode and returns tokens if valid and exam is ongoing.
        """
        try:
            p_record = ExamAccessPasscode.objects.select_for_update().get(
                passcode=passcode
            )
        except ExamAccessPasscode.DoesNotExist:
            return None, "Invalid passcode."

        now = timezone.now()
        exam_access = p_record.exam_access
        if not exam_access:
            return None, "Access record not found."

        exam = exam_access.exam

        # Check if expired
        if p_record.expiry_date and now > p_record.expiry_date:
            p_record.status = ExamAccessPasscode.Status.EXPIRED
            p_record.save(update_fields=['status'])
            return None, "This access link has expired."

        # Check if exam is active
        if not exam.is_active:
            return None, "This exam is no longer active."

        # Mark as used for tracking, but don't block subsequent logins if not expired
        if p_record.status != ExamAccessPasscode.Status.USED:
            p_record.status = ExamAccessPasscode.Status.USED
            p_record.updated_at = timezone.now()
            p_record.save(update_fields=["status", "updated_at"])

        # Generate tokens
        user = p_record.exam_access.candidate.user
        refresh = RefreshToken.for_user(user)

        from vmlc.v2.utils import invalidate_candidate_cache
        from vmlc.views.user.management import ProfileManager

        # Invalidate cache since status might change
        invalidate_candidate_cache(p_record.exam_access.candidate.pk, user.id)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

        # Add profile information (candidate or staff)
        profile_data = ProfileManager.serialize_profile(user)
        if profile_data:
            # profile_data["is_setup_complete"] = user.is_setup_complete
            data["profile"] = profile_data

        return data, None
