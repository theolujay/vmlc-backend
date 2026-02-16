import logging
from typing import Optional
from competition.models import Competition, Enrollment, Stage
from identity.models import Candidate
from vmlc.models import Exam

logger = logging.getLogger(__name__)


class EligibilityService:
    """
    Centralized service for determining candidate eligibility for competition resources.
    """

    @staticmethod
    def can_take_exam(candidate: Candidate, exam: Exam) -> bool:
        """
        Determines if a candidate is eligible to take a specific exam based on
        competition rules and their current progress.
        """
        if not candidate.user.is_active:
            logger.warning(f"Candidate {candidate.pk} is inactive.")
            return False

        # If exam is not active, nobody can take it
        if not exam.is_active:
            return False

        # Check if the exam is currently open (time-wise)
        if not exam.is_currently_open:
            # TODO: examine if this is initially returned due to race condition,
            # as exam.is_currently_open is computed at runtime (as a property) and
            # probably makes it required for a user to refresh their dashboard
            # to check the expected state (exam.is_currently_open=True).
            # But what handles this state change, check_exam_status_transitions_task in vmlc/v2/tasks.py?
            return False

        # Check competition context
        slot = getattr(exam, "competition_slot", None)
        if not slot:
            # If not enrolled in a competition, we allow it if it's active and open.
            # TODO: look the issue where candidates may not be enrollment of a competition
            return True

        # Get active enrollment for THIS exam's competition
        exam_competition = slot.competition_stage.competition
        enrollment = (
            Enrollment.objects.filter(
                candidate=candidate,
                competition=exam_competition,
                status=Enrollment.Status.ACTIVE,
            )
            .select_related("current_stage")
            .first()
        )

        # Determine the candidate's effective stage for this check
        candidate_current_stage = enrollment.current_stage if enrollment else None

        if not candidate_current_stage:
            # Fallback for unenrolled candidates:
            # If the exam belongs to the active competition and matches the candidate's role,
            # we treat them as being in that stage for eligibility purposes.
            active_comp = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()
            if active_comp and slot.competition_stage.competition == active_comp:
                if candidate.role == slot.competition_stage.type:
                    candidate_current_stage = slot.competition_stage

        if not candidate_current_stage:
            logger.info(
                f"Candidate {candidate.pk} has no active competition enrollment or valid role fallback."
            )
            return False

        # Check if candidate's current stage matches the exam's stage
        if candidate_current_stage != slot.competition_stage:
            logger.info(
                f"Candidate {candidate.pk} stage mismatch. "
                f"Candidate stage: {candidate_current_stage.type}, "
                f"Exam stage: {slot.competition_stage.type}"
            )
            return False

        # Ensure they have an IN_PROGRESS EnrollmentStageProgress for this stage
        from competition.models import EnrollmentStageProgress

        if enrollment:
            has_progress = EnrollmentStageProgress.objects.filter(
                enrollment=enrollment,
                stage=slot.competition_stage,
                status=EnrollmentStageProgress.Status.IN_PROGRESS,
            ).exists()
            if not has_progress:
                logger.info(
                    f"Candidate {candidate.pk} has no IN_PROGRESS progress for stage {slot.competition_stage.type}"
                )
                return False

        # Check if they have already submitted this exam
        from vmlc.models import ExamAccess

        if ExamAccess.objects.filter(
            candidate=candidate, exam=exam, status=ExamAccess.Status.SUBMITTED
        ).exists():
            logger.info(f"Candidate {candidate.pk} already submitted exam {exam.pk}.")
            return False

        return True

    @staticmethod
    def can_view_leaderboard(candidate: Candidate, stage_type: str) -> bool:
        """
        Determines if a candidate can view the leaderboard for a specific stage.
        Usually, candidates can only view the leaderboard for their current or past stages.
        """

        enrollment = (
            Enrollment.objects.filter(
                candidate=candidate,
                competition__status=Competition.Status.ACTIVE,
                status=Enrollment.Status.ACTIVE,
            )
            .select_related("competition", "current_stage")
            .first()
        )
        # Determine effective stage type
        candidate_stage_type = (
            enrollment.current_stage.type
            if (enrollment and enrollment.current_stage)
            else candidate.role
        )

        stage_order = {
            Stage.Type.SCREENING: 1,
            Stage.Type.LEAGUE: 2,
            Stage.Type.FINAL: 3,
        }

        candidate_stage_level = stage_order.get(candidate_stage_type, 0)
        requested_stage_level = stage_order.get(stage_type, 99)

        # If no enrollment, only allow viewing if an active competition exists
        if not enrollment:
            if not Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).exists():
                return False

        return candidate_stage_level >= requested_stage_level
