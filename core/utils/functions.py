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
)
from vmlc.models import (
    LeaderboardSnapshot,
    Exam,
    CandidateExamResult,
    CandidateAnswer,
    CandidateExamResultSnapshot,
    ExamAccess,
)
from vmlc.serializers import MinimalCandidateSerializer
from vmlc.utils.dashboard import (
    get_staff_dashboard_data,
)

logger = logging.getLogger(__name__)

def compute_candidate_result(candidate_result_id):
    """
    Calculate and save the auto-score for a candidate's exam submission.
    """

    try:
        candidate_exam_result = CandidateExamResult.objects.get(pk=candidate_result_id)
        _compute_and_save_candidate_exam_result(candidate_exam_result)
        logger.info(
            f"Successfully computed result for CandidateExamResult {candidate_result_id}"
        )
    except CandidateExamResult.DoesNotExist:
        logger.error(
            f"CandidateExamResult with id {candidate_result_id} does not exist."
        )
    except Exception as e:
        logger.error(
            f"Failed to compute result for CandidateExamResult {candidate_result_id}: {e}"
        )


def compute_exam_results(exam_id):
    """
    Ensures CandidateExamResult records exist for all submitted ExamAccess records
    for a specific exam, and then calculates and saves their auto-scores.
    """
    try:
        exam = Exam.objects.get(pk=exam_id)

        # Find all submitted exam accesses for this exam
        submitted_accesses = ExamAccess.objects.filter(
            exam=exam, status=ExamAccess.Status.SUBMITTED
        ).select_related("candidate")

        created_count = 0
        scored_count = 0

        for access in submitted_accesses:
            # Get or create CandidateExamResult for each submitted access
            candidate_exam_result = CandidateExamResult.objects.filter(
                candidate=access.candidate, exam=exam
            ).first()

            if candidate_exam_result is None:
                candidate_exam_result = CandidateExamResult.objects.create(
                    candidate=access.candidate, exam=exam
                )
                created_count += 1

            # Now compute and save the score for this result
            _compute_and_save_candidate_exam_result(candidate_exam_result)
            scored_count += 1

        logger.info(
            f"Exam {exam_id}: Created {created_count} new CandidateExamResult records, "
            f"scored {scored_count} total submissions."
        )
        return scored_count
    except Exam.DoesNotExist:
        logger.error(f"Exam with id {exam_id} does not exist.")
        return 0
    except Exception as e:
        logger.error(
            f"Failed to score submissions for exam {exam_id}: {e}", exc_info=True
        )
        raise


def _compute_and_save_candidate_exam_result(candidate_exam_result):
    """Internal helper to compute and save result for a single CandidateExamResult."""
    submitted_answers = CandidateAnswer.objects.filter(
        candidate_exam_result=candidate_exam_result, question__is_archived=False
    ).select_related("question")

    total_questions = candidate_exam_result.exam.questions.filter(
        is_archived=False
    ).count()

    if not total_questions:
        logger.warning(
            f"Exam {candidate_exam_result.exam.id} has no active questions. Scoring 0."
        )
        candidate_exam_result.score = 0
    else:
        answer_count = submitted_answers.count()
        if answer_count == 0:
            logger.warning(
                f"No answers found for CandidateExamResult {candidate_exam_result.id} (Candidate: {candidate_exam_result.candidate.pk})"
            )

        correct_count = 0
        for answer in submitted_answers:
            selected = (answer.selected_option or "").strip().upper()
            correct = (answer.question.correct_answer or "").strip().upper()
            if selected == correct:
                correct_count += 1

        score = (correct_count / total_questions) * 100
        candidate_exam_result.score = round(score, 2)

        logger.debug(
            f"Scored CandidateExamResult {candidate_exam_result.id}: "
            f"{correct_count}/{total_questions} correct. Score: {candidate_exam_result.score}"
        )

    candidate_exam_result.auto_score = True
    candidate_exam_result.score_submitted_by = None
    candidate_exam_result.recorded_at = timezone.now()
    candidate_exam_result.save()

    from vmlc.v2.utils import invalidate_candidate_cache

    invalidate_candidate_cache(
        candidate_exam_result.candidate.pk, candidate_exam_result.candidate.user.id
    )


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
                logger.error(
                    "No superadmin user found to publish the results snapshot."
                )
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

        # Notify all active candidates
        from comms.services.notification import NotificationService
        from comms.models import Broadcast

        notification_service = NotificationService()
        subject = "Overall Results Published"
        message = (
            "The overall results snapshot has been published. "
            "Please check your dashboard to see your updated standing and performance across all exams."
        )
        active_candidates = Candidate.objects.filter(
            user__is_active=True
        ).select_related("user")
        for candidate in active_candidates:
            notification_service.notify_user(
                user=candidate.user,
                subject=subject,
                message=message,
                mediums=[Broadcast.Medium.PLATFORM, Broadcast.Medium.EMAIL],
                notification_type="success",
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
