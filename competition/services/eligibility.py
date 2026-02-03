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
            # If not part of a competition, we allow it if it's active and open.
            # TODO: look the issue where candidates may not be part of a competition
            return True

        # Get active participation
        part = EligibilityService.get_active_participation(candidate)
        
        # Determine the candidate's effective stage for this check
        candidate_current_stage = part.current_stage if part else None
        
        if not candidate_current_stage:
            # Fallback for unenrolled candidates:
            # If the exam belongs to the active competition and matches the candidate's role,
            # we treat them as being in that stage for eligibility purposes.
            active_comp = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if active_comp and slot.competition_stage.competition == active_comp:
                if candidate.role == slot.competition_stage.type:
                    candidate_current_stage = slot.competition_stage

        if not candidate_current_stage:
            logger.info(f"Candidate {candidate.pk} has no active competition participation or valid role fallback.")
            return False

        # Check if candidate's current stage matches the exam's stage
        if candidate_current_stage != slot.competition_stage:
            logger.info(
                f"Candidate {candidate.pk} stage mismatch. "
                f"Candidate stage: {candidate_current_stage.type}, "
                f"Exam stage: {slot.competition_stage.type}"
            )
            return False

        # Check if they have already submitted this exam
        from vmlc.models import ExamAccess
        if ExamAccess.objects.filter(
            candidate=candidate, 
            exam=exam, 
            status=ExamAccess.Status.SUBMITTED
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
        part = EligibilityService.get_active_participation(candidate)
        
        # Determine effective stage type
        candidate_stage_type = part.current_stage.type if (part and part.current_stage) else candidate.role
        
        stage_order = {
            Stage.Type.SCREENING: 1,
            Stage.Type.LEAGUE: 2,
            Stage.Type.FINAL: 3,
        }
        
        candidate_stage_level = stage_order.get(candidate_stage_type, 0)
        requested_stage_level = stage_order.get(stage_type, 99)
        
        # If no participation, only allow viewing if an active competition exists
        if not part:
            if not Competition.objects.filter(status=Competition.Status.ACTIVE).exists():
                return False
        
        return candidate_stage_level >= requested_stage_level
