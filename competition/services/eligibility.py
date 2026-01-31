import logging
from typing import Optional
from competition.models import (
    Competition, 
    CandidateCompetition, 
    Stage
)
from identity.models import Candidate
from vmlc.models import Exam

logger = logging.getLogger(__name__)

class EligibilityService:
    """
    Centralized service for determining candidate eligibility for competition resources.
    """

    @staticmethod
    def get_active_participation(candidate: Candidate) -> Optional[CandidateCompetition]:
        """Helper to get candidate's active competition participation."""
        return CandidateCompetition.objects.filter(
            candidate=candidate,
            competition__status=Competition.Status.ACTIVE,
            status=CandidateCompetition.Status.ACTIVE
        ).select_related('competition', 'current_stage').first()

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
            return False

        # Check competition context
        slot = getattr(exam, 'competition_slot', None)
        if not slot:
            # If not part of a competition, we might fall back to old role-based logic 
            # or just allow it if it's a general exam.
            # For now, let's assume it's allowed if it's active and open.
            return True

        # Get active participation
        part = EligibilityService.get_active_participation(candidate)
        if not part:
            logger.info(f"Candidate {candidate.pk} has no active competition participation.")
            return False

        # Check if candidate's current stage matches the exam's stage
        if part.current_stage != slot.competition_stage:
            logger.info(
                f"Candidate {candidate.pk} stage mismatch. "
                f"Candidate stage: {part.current_stage.type if part.current_stage else 'None'}, "
                f"Exam stage: {slot.competition_stage.type}"
            )
            return False

        # Optional: check if they have already submitted this exam
        from vmlc.models import CandidateExamResult
        if CandidateExamResult.objects.filter(candidate=candidate, exam=exam).exists():
            logger.info(f"Candidate {candidate.pk} already took exam {exam.pk}.")
            return False

        return True

    @staticmethod
    def can_view_leaderboard(candidate: Candidate, stage_type: str) -> bool:
        """
        Determines if a candidate can view the leaderboard for a specific stage.
        Usually, candidates can only view the leaderboard for their current or past stages.
        """
        part = EligibilityService.get_active_participation(candidate)
        if not part:
            return False

        # If they are active and in the requested stage, allow.
        # If they've passed it, they should also see it.
        # For simplicity, if they are active in the competition, let them see it
        # as long as it's not a future stage they haven't reached?
        # Screening candidates shouldn't see League leaderboard if they haven't reached it.
        
        stage_order = {
            Stage.Type.SCREENING: 1,
            Stage.Type.LEAGUE: 2,
            Stage.Type.FINAL: 3,
        }
        
        candidate_stage_level = stage_order.get(part.current_stage.type, 0) if part.current_stage else 0
        requested_stage_level = stage_order.get(stage_type, 99)
        
        return candidate_stage_level >= requested_stage_level
