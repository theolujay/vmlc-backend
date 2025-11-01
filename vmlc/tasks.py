import logging
from datetime import timedelta

from django.db.models import F, Avg, ExpressionWrapper, DateTimeField
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import OperationalError
from django.utils import timezone
from celery import shared_task
from PIL import Image
import magic

from vmlc.models import Exam

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="send_mail_task", max_retries=3, default_retry_delay=60, queue="comms")
def send_mail_task(self, subject, message, recipient_list, html_message=None):
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
            html_message=html_message,
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
    queue="comms"
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
        candidate_score.score_submitted_by = "Auto Score"
        candidate_score.recorded_at = timezone.now()
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

@shared_task(name="update_exam_statuses_task")
def update_exam_statuses_task():
    """This task is deprecated since Exam.status is now a property."""
    logger.info("update_exam_statuses_task is deprecated and does nothing.")
    return "Task is deprecated."

@shared_task(name="generate_leaderboard_snapshot_task")
def generate_leaderboard_snapshot_task(staff_id=None):
    """
    Celery task to generate and publish the leaderboard snapshot.
    
    This task creates a comprehensive leaderboard structure that organizes
    exams by their stage (screening/league) and level (1, 2, 3, etc.).
    
    The resulting data structure looks like:
    {
        "screening_1": {...},
        "screening_2": {...},
        "league_1": {...},
        "league_2": {...},
        ...
    }
    
    Each key is a combination of stage and level, making it easy to fetch
    specific leaderboards from the frontend.
    """
    from .models import Exam, CandidateScore, LeaderboardSnapshot, Staff
    from .serializers import CandidateLeaderboardPerfSerializer
    
    now = timezone.now()
    
    # Find all concluded exams
    # We annotate each exam with its conclusion_time to filter efficiently
    exams = Exam.objects.annotate(
        conclusion_time=ExpressionWrapper(
            F('scheduled_date') + F('open_duration_hours') * timedelta(hours=1),
            output_field=DateTimeField()
        )
    ).filter(
        is_active=True,
        conclusion_time__lte=now  # Only concluded exams
    ).annotate(
        average_score=Avg("scores__score")
    ).order_by('stage', 'level')  # Order by stage, then level for consistent processing
    
    if not exams.exists():
        logger.info(
            f"Leaderboard snapshot triggered by {staff_id} ignored - No concluded exams yet"
        )
        return

    # Get the staff member who triggered this
    staff = Staff.objects.get(pk=staff_id) if staff_id else None
    
    # Dictionary to hold all leaderboards
    # Key format: "screening_1", "league_2", etc.
    all_leaderboards = {}
    
    for exam in exams:
        # Create a unique key for this exam: stage_level (e.g., "screening_1", "league_2")
        leaderboard_key = f"{exam.stage}_{exam.level}"
        
        # Get all scores for this exam, ordered by score (highest first)
        scores = (
            CandidateScore.objects
            .filter(exam=exam)
            .select_related('candidate__user')
            .prefetch_related('answers__question')
            .order_by("-score")
        )
        
        # Build the leaderboard for this specific exam
        leaderboard_entries = []
        
        for index, score in enumerate(scores):
            # Get candidate data
            candidate_data = CandidateLeaderboardPerfSerializer(score.candidate).data
            
            # Get all answers for this candidate's exam submission
            answers = score.answers.all()
            
            # Build submission details (all questions and selected answers)
            submission_list = []
            for answer in answers:
                submission_list.append({
                    "question_id": answer.question.id,
                    "question_text": answer.question.text,
                    "option_a": answer.question.option_a,
                    "option_b": answer.question.option_b,
                    "option_c": answer.question.option_c,
                    "option_d": answer.question.option_d,
                    "correct_answer": answer.question.correct_answer,
                    "selected_option": answer.selected_option,
                    "is_correct": answer.selected_option == answer.question.correct_answer,
                    "answered_at": answer.answered_at.isoformat(),
                })
            
            candidate_data["submissions"] = submission_list
            
            # Add this candidate to the leaderboard
            leaderboard_entries.append({
                "rank": index + 1,
                "candidate": candidate_data,
                "score": float(score.score),
                "percentage": round((float(score.score) / exam.questions.count() * 100), 2) if exam.questions.count() > 0 else 0
            })
        
        # Store this exam's complete leaderboard data
        all_leaderboards[leaderboard_key] = {
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_description": exam.description,
            "stage": exam.stage,
            "level": exam.level,
            "stage_display": leaderboard_key,  # e.g., "league_2"
            "scheduled_date": exam.scheduled_date.isoformat(),
            "concluded_at": exam.concluded_at.isoformat() if exam.concluded_at else None,
            "status": exam.status,
            "total_questions": exam.questions.count(),
            "average_score": float(exam.average_score) if exam.average_score else 0.0,
            "total_candidates": len(leaderboard_entries),
            "entries": leaderboard_entries
        }

    # Create the snapshot with all leaderboards
    snapshot = LeaderboardSnapshot.objects.create(
        data=all_leaderboards,
        published_by=staff,
        is_published=True,
    )

    logger.info(
        f"Leaderboard snapshot created by staff {staff.pk if staff else 'system'}. "
        f"Snapshot ID: {snapshot.pk}. "
        f"Leaderboards generated: {', '.join(all_leaderboards.keys())}"
    )
        
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
        candidates = Candidate.objects.with_scores().filter(user__is_active=True)

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

        # Validate face ID
        if verification.face_id:
            _validate_file_size(verification.face_id, 2, "face ID")
            allowed_types = ["image/jpg", "image/jpeg", "image/png"]
            _validate_file_type(
                verification.face_id, allowed_types, "face ID"
            )
            _validate_image_file(verification.face_id, "face ID")

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
                    filter=Q(scores__recorded_at__lte=latest_snapshot.published_at),
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


@shared_task(name="revoke_staff_invite_task")
def revoke_staff_invite_task(user_id):
    """
    Celery task to revoke staff credentials if they haven't logged in within a week.
    """
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
        if user.last_login is None:
            user.is_active = False
            user.save()
            send_mail_task.delay(
                subject="Your account has been revoked",
                message=f"Your account has been revoked because you didn't log in within seven days of receiving your invite. "
                        f"Please contact {settings.SUPPORT_EMAIL} if you have any inquires.\n\n"
                        "Regards,\n\nManagement, Verboheit MLC",
                recipient_list=[user.email],
            )                
            logger.info(f"Revoked credentials for user {user.email} due to inactivity.")
        else:
            logger.info(f"User {user.email} has logged in. No action taken.")
    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} not found for invite revocation.")

@shared_task(bind=True, name="revoke_staff_registration_task", max_retries=20)
def revoke_staff_registration_task(self, user_id):
    """
    Delete staff registration if not email_verified
    """
    from datetime import timedelta
    from .models import User, EmailOTP
    
    try:
        user = User.objects.get(pk=user_id)

        if not hasattr(user, "staff_profile"):
            logger.info(f"User {user.id} is not a staff member. Skipping revocation.")
            return
            
        if user.is_email_verified:
            logger.info(f"User {user.id} has already verified their email. Skipping revocation.")
            return

        latest_otp = (
            EmailOTP.objects.filter(user=user).order_by("-created_at").first()
        )
        if not latest_otp:
            if self.request.retries >= 5:
                logger.warning(
                    f"No OTP found for user {user.id} after {self.request.retries} retries. "
                    "Deleting user as precaution."
                )
                user.delete()
                return
            
            logger.debug(
                f"No OTP found for user {user.id} (attempt {self.request.retries + 1}). Retrying..."
            )
            raise self.retry(countdown=60)

        time_since_last: timedelta = timezone.now() - latest_otp.created_at
        grace_period: timedelta = timedelta(minutes=5)
        
        if latest_otp.is_expired() and time_since_last >= grace_period:
            logger.debug(
                f"Registration grace period elapsed. Revoking user registration for {user.id}."
            )
        
            user.delete()
            logger.info(f"Revoked staff registration for user {user.email}")
        
        elif latest_otp.is_expired() and time_since_last < grace_period:
            logger.debug(f"OTP expired, but within grace period for user {user.id}. Retrying...")
            # Retry the task after the grace period has passed
            raise self.retry(countdown=(grace_period - time_since_last).total_seconds())
        
        else:
            logger.info(f"OTP for user {user.id} is still valid. No action taken.")

    except User.DoesNotExist:
        logger.warning(f"User with id {user_id} not found for registration revocation.")
        # Don't retry - user is gone
        return

    except OperationalError as e:
        # Database temporarily unavailable - retry makes sense
        logger.error(f"Database error during revocation for user {user_id}: {e}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        # Unexpected error - log and decide if we should retry
        logger.error(
            f"Unexpected error during revocation for user {user_id}: {e}",
            exc_info=True
        )
        
        if self.request.retries >= 3:
            logger.error(f"Max retries reached for user {user_id}. Giving up.")
            return
        
        raise self.retry(exc=e, countdown=60)