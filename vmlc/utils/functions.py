import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import (
    F,
    Q,
    Avg,
    Sum,
    Window,
    ExpressionWrapper,
    DateTimeField,
    functions,
)
from django.utils import timezone
from PIL import Image
import magic
import mimetypes

from identity.models import (
    Candidate,
    Staff,
    User,
    UserVerification,
)
from vmlc.models import (
    LeaderboardSnapshot,
    Exam,
    CandidateExamResult,
    CandidateAnswer,
    CandidateExamResultSnapshot,
)
from vmlc.serializers import (
    CandidateLeaderboardPerfSerializer,
    MinimalCandidateSerializer,
)
from vmlc.utils.dashboard import (
    get_staff_dashboard_data,
    get_candidate_dashboard_data,
)

logger = logging.getLogger(__name__)


def generate_leaderboard_snapshot(staff_id=None):
    """
    Celery task to generate and publish the leaderboard snapshot.
    """

    now = timezone.now()
    concluded_exams = _get_concluded_exams(now)

    if not concluded_exams.exists():
        logger.info(
            f"Leaderboard snapshot triggered by {staff_id} ignored - No concluded exams yet"
        )
        return

    staff = Staff.objects.get(pk=staff_id) if staff_id else None
    all_leaderboards = {}

    for exam in concluded_exams:
        stage_display = f"{exam.stage_display}"
        leaderboard_entries = _build_leaderboard_entries(exam)
        all_leaderboards[stage_display] = _create_exam_leaderboard_data(
            exam, leaderboard_entries, stage_display
        )

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


def _get_concluded_exams(now):
    """Helper to get all concluded exams."""

    return (
        Exam.objects.annotate(
            conclusion_time=ExpressionWrapper(
                F("scheduled_date") + F("open_duration_hours") * timedelta(hours=1),
                output_field=DateTimeField(),
            )
        )
        .filter(is_active=True, conclusion_time__lte=now)
        .annotate(average_score=Avg("results__score"))
        .order_by("stage", "round")
    )


def _build_leaderboard_entries(exam):
    """Helper to build leaderboard entries for a given exam."""

    results = (
        CandidateExamResult.objects.filter(exam=exam)
        .select_related("candidate__user")
        .prefetch_related("answers__question")
        .order_by("-score")
    )

    leaderboard_entries = []
    for index, result in enumerate(results):
        candidate_data = CandidateLeaderboardPerfSerializer(result.candidate).data
        answers = result.answers.all()
        submission_list = []
        for answer in answers:
            submission_list.append(
                {
                    "question_id": answer.question.id,
                    "question_text": answer.question.text,
                    "option_a": answer.question.option_a,
                    "option_b": answer.question.option_b,
                    "option_c": answer.question.option_c,
                    "option_d": answer.question.option_d,
                    "correct_answer": answer.question.correct_answer,
                    "selected_option": answer.selected_option,
                    "is_correct": answer.selected_option
                    == answer.question.correct_answer,
                    # "answered_at": answer.answered_at.isoformat(),
                }
            )
        candidate_data["submissions"] = submission_list
        leaderboard_entries.append(
            {
                "rank": index + 1,
                "score": float(result.score),
                "percentage": (
                    round((float(result.score) / exam.questions.count() * 100), 2)
                    if exam.questions.count() > 0
                    else 0
                ),
                "participated_at": str(result.recorded_at),
                "candidate": candidate_data,
            }
        )
    return leaderboard_entries


def _create_exam_leaderboard_data(exam, leaderboard_entries, stage_display):
    """Helper to create the final data structure for an exam's leaderboard."""
    return {
        "exam_id": str(exam.id),
        "exam_title": exam.title,
        "exam_description": exam.description,
        "stage": exam.stage,
        "round": exam.round,
        "stage_display": stage_display,
        "scheduled_date": exam.scheduled_date.isoformat(),
        "concluded_at": exam.concluded_at.isoformat() if exam.concluded_at else None,
        "status": exam.status,
        "total_questions": exam.questions.count(),
        "average_score": float(exam.average_score) if exam.average_score else 0.0,
        "total_candidates": len(leaderboard_entries),
        "entries": leaderboard_entries,
    }


def compute_candidate_result(candidate_result_id):
    """
    Calculate and save the auto-score for a candidate's exam submission.
    """

    try:
        candidate_exam_result = CandidateExamResult.objects.get(pk=candidate_result_id)
        _compute_and_save_result(candidate_exam_result)
        logger.info(
            f"Successfully computed result for CandidateExamResult {candidate_result_id}"
        )
    except CandidateExamResult.DoesNotExist:
        logger.error(f"CandidateExamResult with id {candidate_result_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Failed to compute result for CandidateExamResult {candidate_result_id}: {e}"
        )


def score_exam_submissions(exam_id):
    """
    Calculate and save auto-scores for all submissions of a specific exam.
    """
    try:
        exam = Exam.objects.get(pk=exam_id)
        results = CandidateExamResult.objects.filter(exam=exam)
        
        count = 0
        for result in results:
            _compute_and_save_result(result)
            count += 1
            
        logger.info(f"Successfully computed results for {count} submissions of exam {exam_id}")
        return count
    except Exam.DoesNotExist:
        logger.error(f"Exam with id {exam_id} does not exist.")
        return 0
    except Exception as e:
        logger.error(f"Failed to score submissions for exam {exam_id}: {e}")
        raise


def _compute_and_save_result(candidate_exam_result):
    """Internal helper to compute and save result for a single CandidateExamResult."""
    submitted_answers = CandidateAnswer.objects.filter(
        candidate_exam_result=candidate_exam_result
    ).select_related("question")

    total_questions = candidate_exam_result.exam.questions.filter(
        is_archived=False
    ).count()
    
    if not total_questions:
        candidate_exam_result.score = 0
    else:
        correct_count = sum(
            1
            for answer in submitted_answers
            if answer.selected_option == answer.question.correct_answer
        )
        score = (correct_count / total_questions) * 100
        candidate_exam_result.score = round(score, 2)

    candidate_exam_result.auto_score = True
    candidate_exam_result.score_submitted_by = None
    candidate_exam_result.recorded_at = timezone.now()
    candidate_exam_result.save()
    cache.delete(f"candidate_dashboard_{candidate_exam_result.candidate.pk}")



def generate_results_snapshot(staff_id=None):
    """
    Generate and publish the results snapshot.
    """

    try:
        if staff_id:
            staff = Staff.objects.get(pk=staff_id)
        else:
            # If no staff_id is provided, use the first superadmin
            superadmin_user = User.objects.filter(is_superuser=True).first()
            if not superadmin_user:
                logger.error("No superadmin user found to publish the results snapshot.")
                return
            staff = superadmin_user.staff_profile
        candidates = Candidate.objects.with_results().filter(user__is_active=True)

        results_data = []
        for candidate in candidates:
            results_data.append(
                {
                    "candidate": MinimalCandidateSerializer(candidate).data,
                    "total_score": float(candidate.total_score or 0.0),
                    "average_score": float(candidate.average_score or 0.0),
                    "exams_taken": candidate.exams_taken or 0,
                }
            )

        snapshot = CandidateExamResultSnapshot.objects.create(
            data=results_data,
            published_by=staff,
            published_at=timezone.now(),
        )

        logger.info(f"Scores published by staff {staff.pk}. Snapshot ID: {snapshot.pk}")
    except Staff.DoesNotExist:
        logger.error(f"Staff with id {staff_id} does not exist.")
    except Exception as e:
        logger.error(f"Failed to generate results snapshot: {e}")


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

    file_type = None
    try:
        # Get actual file type using magic
        file_type = magic.from_buffer(value.read(1024), mime=True)
        value.seek(0)  # Reset file pointer
    except (OSError, magic.MagicException):
        # Fallback to guessing from filename if magic fails
        logger.warning(
            f"Magic could not determine file type for {field_name}. Guessing from filename."
        )
        if hasattr(value, "name"):
            file_type, _ = mimetypes.guess_type(value.name)

    # Final fallback for in-memory files without a name
    if not file_type and hasattr(value, "content_type"):
        file_type = value.content_type

    if file_type not in allowed_types:
        allowed_str = ", ".join(allowed_types)
        raise ValueError(f"{field_name} must be one of: {allowed_str}")


def validate_user_verification_files(user_verification_id):
    """
    Celery task to validate user verification files.
    """
    from vmlc.tasks import send_mail_task

    try:
        verification = UserVerification.objects.get(pk=user_verification_id)

        # Validate face ID
        if verification.face_id:
            _validate_file_size(verification.face_id, 2, "face ID")
            allowed_types = ["image/jpg", "image/jpeg", "image/png"]
            _validate_file_type(verification.face_id, allowed_types, "face ID")
            _validate_image_file(verification.face_id, "face ID")

        # Validate ID card
        if verification.id_card:
            _validate_file_size(verification.id_card, 2, "ID card")
            allowed_types = ["image/jpg", "image/jpeg", "image/png", "application/pdf"]
            _validate_file_type(verification.id_card, allowed_types, "ID card")

            content_type, _ = mimetypes.guess_type(verification.id_card.name)
            if content_type and content_type.startswith("image/"):
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
            content_type, _ = mimetypes.guess_type(
                verification.verification_document.name
            )
            if content_type and content_type.startswith("image/"):
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


def update_staff_dashboard_cache(staff_id=None):
    """
    Celery task to update the staff dashboard cache.
    If a staff_id is provided, it updates the cache for that specific staff member.
    Otherwise, it updates the cache for all staff members.
    """

    try:
        if staff_id:
            staff_members = Staff.objects.filter(pk=staff_id)
            if not staff_members.exists():
                logger.error(f"Staff with id {staff_id} does not exist.")
        else:
            staff_members = Staff.objects.all()

        for staff in staff_members:
            dashboard_data = get_staff_dashboard_data(staff)
            cache.set(
                f"staff_dashboard_data_{staff.user_id}", dashboard_data, timeout=3600
            )  # Cache for 1 hour
            logger.info(f"Successfully updated cache for staff {staff.user_id}")

    except Exception as e:
        logger.error(
            f"Failed to update staff dashboard cache for staff {staff_id}: {e}"
        )


def update_candidate_dashboard_cache(candidate_id=None):
    """
    Celery task to update the candidate dashboard cache.
    """

    try:
        if candidate_id:
            candidates = Candidate.objects.filter(pk=candidate_id)
            if not candidates.exists():
                logger.error(f"Candidate with id {candidate_id} does not exist.")
        else:
            candidates = Candidate.objects.all()
        for candidate in candidates:
            dashboard_data = get_candidate_dashboard_data(candidate)
            cache.set(
                f"candidate_dashboard_{candidate.user_id}", dashboard_data, timeout=3600
            )  # Cache for 1 hour
            logger.info(f"Successfully updated cache for candidate {candidate.user_id}")
    except Exception as e:
        logger.error(
            f"Failed to update candidate dashboard cache for candidate {candidate_id}: {e}"
        )


def update_candidate_ranking_cache():
    """
    Celery task to update the candidate ranking cache for all league candidates.
    """

    try:
        league_candidates = Candidate.objects.filter(role=Candidate.Roles.LEAGUE)
        latest_snapshot = (
            CandidateExamResultSnapshot.objects.filter(published_at__isnull=False)
            .order_by("-published_at")
            .first()
        )

        if latest_snapshot:
            ranked_candidates = league_candidates.annotate(
                total_score=Sum(
                    "results__score",
                    filter=Q(results__recorded_at__lte=latest_snapshot.published_at),
                    default=0.0,
                ),
                rank=Window(
                    expression=functions.Rank(),
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
