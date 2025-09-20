import logging
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from PIL import Image
import magic


logger = logging.getLogger(__name__)


@shared_task(bind=True, name="send_mail_task", max_retries=3, default_retry_delay=60)
def send_mail_task(self, subject, message, recipient_list):
    """
    Celery task to send an email asynchronously.

    It will automatically retry up to 3 times if it fails,
    with a 60-second delay between retries.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Successfully sent email to {recipient_list}")
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}: {exc}")
        # The `self.retry` call will re-queue the task.
        # The `bind=True` and `max_retries` arguments in the decorator handle this automatically.
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    bind=True,
    name="send_otp_on_registration_task",
    max_retries=3,
    default_retry_delay=60,
)
def send_otp_on_registration_task(self, user_id):
    """
    Celery task to send OTP to user on registration.
    """
    from .models import User
    from .utils.auth import send_otp_to_email

    try:
        user = User.objects.get(pk=user_id)
        send_otp_to_email(user)
        logger.info(f"Successfully sent OTP to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
    except Exception as exc:
        logger.error(f"Failed to send OTP to user with id {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="calculate_and_save_auto_score_task")
def calculate_and_save_auto_score_task(candidate_score_id):
    """
    Celery task to calculate and save the auto score for a candidate's exam submission.
    """
    from .models import CandidateScore, CandidateAnswer

    try:
        candidate_score = CandidateScore.objects.get(pk=candidate_score_id)
        submitted_answers = CandidateAnswer.objects.filter(
            candidate_score=candidate_score
        )

        total_questions = candidate_score.exam.questions.count()
        if not total_questions:
            candidate_score.score = 0
        else:
            correct_count = sum(
                1
                for answer in submitted_answers
                if answer.selected_option == answer.question.correct_answer
            )
            score = (correct_count / total_questions) * 100
            candidate_score.score = round(score, 2)

        candidate_score.auto_score = True
        candidate_score.date_recorded = timezone.now()
        candidate_score.save()

        logger.info(
            f"Successfully calculated score for CandidateScore {candidate_score_id}"
        )
    except CandidateScore.DoesNotExist:
        logger.error(f"CandidateScore with id {candidate_score_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Failed to calculate score for CandidateScore {candidate_score_id}: {e}"
        )


@shared_task(name="generate_leaderboard_snapshot_task")
def generate_leaderboard_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the leaderboard snapshot.
    """
    from .models import Candidate, LeaderboardSnapshot, Staff, User
    from .serializers import MinimalCandidateSerializer

    try:
        if staff_id:
            staff = Staff.objects.get(pk=staff_id)
        else:
            # If no staff_id is provided, use the first superadmin
            superadmin_user = User.objects.filter(is_superuser=True).first()
            if not superadmin_user:
                logger.error("No superadmin user found to publish the leaderboard.")
                return
            staff = superadmin_user.staff_profile

        league_candidates = (
            Candidate.objects.with_scores()
            .filter(role=Candidate.Roles.LEAGUE, is_active=True)
            .order_by("-total_score")
        )

        leaderboard_data = [
            {
                "rank": index + 1,
                "candidate": MinimalCandidateSerializer(candidate).data,
                "total_score": float(candidate.total_score or 0.0),
            }
            for index, candidate in enumerate(league_candidates)
        ]

        snapshot = LeaderboardSnapshot.objects.create(
            data=leaderboard_data,
            published_by=staff,
        )

        logger.info(
            f"Leaderboard published by staff {staff.pk}. Snapshot ID: {snapshot.pk}"
        )
    except Staff.DoesNotExist:
        logger.error(f"Staff with id {staff_id} does not exist.")
    except Exception as e:
        logger.error(f"Failed to generate leaderboard snapshot: {e}")


@shared_task(name="generate_scores_snapshot_task")
def generate_scores_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the scores snapshot.
    """
    from .models import Candidate, CandidateScoreSnapshot, Staff, User
    from .serializers import MinimalCandidateSerializer

    try:
        if staff_id:
            staff = Staff.objects.get(pk=staff_id)
        else:
            # If no staff_id is provided, use the first superadmin
            superadmin_user = User.objects.filter(is_superuser=True).first()
            if not superadmin_user:
                logger.error("No superadmin user found to publish the scores snapshot.")
                return
            staff = superadmin_user.staff_profile
        candidates = Candidate.objects.with_scores().filter(is_active=True)

        scores_data = []
        for candidate in candidates:
            scores_data.append(
                {
                    "candidate": MinimalCandidateSerializer(candidate).data,
                    "total_score": float(candidate.total_score or 0.0),
                    "average_score": float(candidate.average_score or 0.0),
                    "exams_taken": candidate.exams_taken or 0,
                }
            )

        snapshot = CandidateScoreSnapshot.objects.create(
            data=scores_data,
            published_by=staff,
            published_at=timezone.now(),
        )

        logger.info(f"Scores published by staff {staff.pk}. Snapshot ID: {snapshot.pk}")
    except Staff.DoesNotExist:
        logger.error(f"Staff with id {staff_id} does not exist.")
    except Exception as e:
        logger.error(f"Failed to generate scores snapshot: {e}")


def _validate_file_size(value, max_size_mb, field_name):
    """Helper method to validate file size"""
    if value and value.size > max_size_mb * 1024 * 1024:
        raise ValueError(f"{field_name} must be less than {max_size_mb}MB.")


def _validate_image_file(value, field_name):
    """Helper method to validate image files"""
    if not value:
        return

    try:
        # Use PIL to verify it's a real image
        img = Image.open(value)
        img.verify()
        # Reset file pointer after verification
        value.seek(0)
    except Exception:
        raise ValueError(f"Invalid {field_name} image file.")


def _validate_file_type(value, allowed_types, field_name):
    """Helper method to validate file type using python-magic"""
    if not value:
        return

    try:
        # Get actual file type using magic
        file_type = magic.from_buffer(value.read(1024), mime=True)
        value.seek(0)  # Reset file pointer

        if file_type not in allowed_types:
            allowed_str = ", ".join(allowed_types)
            raise ValueError(f"{field_name} must be one of: {allowed_str}")
    except (OSError, magic.MagicException):
        # Fallback to content_type if magic fails
        if hasattr(value, "content_type") and value.content_type not in allowed_types:
            allowed_str = ", ".join(allowed_types)
            raise ValueError(f"{field_name} must be one of: {allowed_str}")


@shared_task(name="validate_user_verification_files_task")
def validate_user_verification_files_task(user_verification_id):
    """
    Celery task to validate user verification files.
    """
    from .models import UserVerification

    try:
        verification = UserVerification.objects.get(pk=user_verification_id)

        # Validate profile photo
        if verification.profile_photo:
            _validate_file_size(verification.profile_photo, 2, "Profile photo")
            allowed_types = ["image/jpg", "image/jpeg", "image/png"]
            _validate_file_type(
                verification.profile_photo, allowed_types, "Profile photo"
            )
            _validate_image_file(verification.profile_photo, "profile photo")

        # Validate ID card
        if verification.id_card:
            _validate_file_size(verification.id_card, 2, "ID card")
            allowed_types = ["image/jpg", "image/jpeg", "image/png", "application/pdf"]
            _validate_file_type(verification.id_card, allowed_types, "ID card")
            if (
                verification.id_card.file.content_type
                and verification.id_card.file.content_type.startswith("image/")
            ):
                _validate_image_file(verification.id_card, "ID card")

        # Validate verification document
        if verification.verification_document:
            _validate_file_size(
                verification.verification_document, 2, "Verification document"
            )
            allowed_types = ["image/jpg", "image/jpeg", "image/png", "application/pdf"]
            _validate_file_type(
                verification.verification_document,
                allowed_types,
                "Verification document",
            )
            if (
                verification.verification_document.file.content_type
                and verification.verification_document.file.content_type.startswith(
                    "image/"
                )
            ):
                _validate_image_file(
                    verification.verification_document, "verification document"
                )

        # If all validations pass
        verification.is_pending = True
        verification.save()
        logger.info(
            f"Successfully validated files for UserVerification {user_verification_id}"
        )

    except UserVerification.DoesNotExist:
        logger.error(f"UserVerification with id {user_verification_id} does not exist.")
    except ValueError as e:
        # Handle validation errors
        verification.is_rejected = True
        verification.is_pending = False
        verification.save()
        send_mail_task.delay(
            subject="User Verification Rejected",
            message=f"Your account verification has been rejected due to the following error: {e}. Please upload valid documents.",
            recipient_list=[verification.user.email],
        )
        logger.error(
            f"File validation failed for UserVerification {user_verification_id}: {e}"
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during file validation for UserVerification {user_verification_id}: {e}"
        )


# def user_profile_cache_task(user_id):
#     """Celery task to cache user's profile data."""
#     from .models import User, Candidate, Staff
#     from .serializers import MinimalCandidateSerializer, MinimalStaffSerializer


#     pass


@shared_task(name="update_staff_dashboard_cache_task")
def update_staff_dashboard_cache_task(staff_id=None):
    """
    Celery task to update the staff dashboard cache.
    If a staff_id is provided, it updates the cache for that specific staff member.
    Otherwise, it updates the cache for all staff members.
    """
    from .models import Staff
    from .utils.dashboard_utils import get_staff_dashboard_data

    try:
        if staff_id:
            staff_members = Staff.objects.filter(pk=staff_id)
            if not staff_members.exists():
                logger.error(f"Staff with id {staff_id} does not exist.")
        else:
            staff_members = Staff.objects.all()

        for staff in staff_members:
            staff_identifier = staff.user_id
            dashboard_data = get_staff_dashboard_data(staff)
            cache.set(
                f"staff_dashboard_data_{staff_identifier}", dashboard_data, timeout=3600
            )  # Cache for 1 hour
            logger.info(f"Successfully updated cache for staff {staff_identifier}")

    except Exception as e:
        logger.error(
            f"Failed to update staff dashboard cache for staff {staff_id}: {e}"
        )


@shared_task(name="update_candidate_dashboard_cache_task")
def update_candidate_dashboard_cache_task(candidate_id):
    """
    Celery task to update the candidate dashboard cache.
    """
    from .models import Candidate
    from .utils.dashboard_utils import get_candidate_dashboard_data

    try:
        candidate = Candidate.objects.get(pk=candidate_id)
        dashboard_data = get_candidate_dashboard_data(candidate)
        cache.set(
            f"candidate_dashboard_{candidate_id}", dashboard_data, timeout=3600
        )  # Cache for 1 hour
        logger.info(f"Successfully updated cache for candidate {candidate_id}")
    except Candidate.DoesNotExist:
        logger.error(f"Candidate with id {candidate_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Failed to update candidate dashboard cache for candidate {candidate_id}: {e}"
        )


@shared_task(name="update_candidate_ranking_cache_task")
def update_candidate_ranking_cache_task():
    """
    Celery task to update the candidate ranking cache for all league candidates.
    """
    from .models import Candidate
    from django.db.models import Sum, Q, F, Window
    from django.db.models.functions import Rank
    from vmlc.models import CandidateScoreSnapshot

    try:
        league_candidates = Candidate.objects.filter(role=Candidate.Roles.LEAGUE)
        latest_snapshot = (
            CandidateScoreSnapshot.objects.filter(published_at__isnull=False)
            .order_by("-published_at")
            .first()
        )

        if latest_snapshot:
            ranked_candidates = league_candidates.annotate(
                total_score=Sum(
                    "scores__score",
                    filter=Q(scores__date_recorded__lte=latest_snapshot.published_at),
                    default=0.0,
                ),
                rank=Window(
                    expression=Rank(),
                    order_by=F("total_score").desc(nulls_last=True),
                ),
            )

            for candidate in ranked_candidates:
                cache.set(
                    f"candidate_rank_{candidate.pk}", candidate.rank, timeout=3600
                )  # Cache for 1 hour

            logger.info("Successfully updated candidate ranking cache.")
    except Exception as e:
        logger.error(f"Failed to update candidate ranking cache: {e}")
