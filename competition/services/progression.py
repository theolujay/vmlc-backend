import logging
from django.db import transaction
from django.utils import timezone
from competition.models import (
    Competition,
    Stage,
    CandidateCompetition,
    CandidateStageProgress,
    Standings,
)
from competition.services.leaderboard import LeaderboardService

logger = logging.getLogger(__name__)

class ProgressionError(Exception):
    pass

class ProgressionService:
    """
    Service to handle candidate promotion between competition stages.
    """

    @staticmethod
    @transaction.atomic
    def promote_candidates(from_stage_type, to_stage_type, cutoff_rank=None, competition_id=None):
        """
        Promotes the top N candidates from one stage to the next.
        """
        if competition_id:
            competition = Competition.objects.get(id=competition_id)
        else:
            competition = Competition.objects.filter(status=Competition.Status.ACTIVE).first()

        if not competition:
            raise ProgressionError("No active competition found.")

        # Identify the 'to' stage object
        to_stage = Stage.objects.filter(competition=competition, type=to_stage_type).first()
        if not to_stage:
            raise ProgressionError(f"Target stage '{to_stage_type}' not found for this competition.")

        # If cutoff_rank not provided, try to get it from stage config
        if cutoff_rank is None:
            cutoff_rank = to_stage.config.get("promotion_cutoff")
            if cutoff_rank is None:
                raise ProgressionError(f"No cutoff_rank provided and 'promotion_cutoff' not found in {to_stage_type} config.")

        # Identify candidate IDs to promote
        candidate_ids_to_promote = []
        candidate_ids_to_eliminate = []
        
        if from_stage_type == Stage.Type.SCREENING:
            standings = Standings.objects.filter(
                competition=competition, 
                stage=Stage.Type.SCREENING, 
                is_published=True
            ).order_by('-published_at').first()
            
            if not standings:
                raise ProgressionError("No published Screening standings found.")
            
            candidate_ids_to_promote = list(standings.entries.filter(
                rank__lte=cutoff_rank
            ).values_list('candidate_id', flat=True))

            candidate_ids_to_eliminate = list(standings.entries.filter(
                rank__gt=cutoff_rank
            )).values_list('candidate_id', flat=True)

        elif from_stage_type == Stage.Type.LEAGUE:
            leaderboard = LeaderboardService.get_latest_league_leaderboard(competition)
            if not leaderboard:
                raise ProgressionError("No League leaderboard found.")
            
            # Use the entries from the leaderboard
            candidate_ids_to_promote = [
                entry.candidate_id for entry in leaderboard.entries.filter(overall_rank__lte=cutoff_rank)
            ]
            candidate_ids_to_eliminate = [
                entry.candidate_id for entry in leaderboard.entries.filter(overall_rank__gt=cutoff_rank)
            ]
        
        else:
            raise ProgressionError(f"Promotion from stage '{from_stage_type}' is not supported.")

        if not candidate_ids_to_promote:
            return 0

        now = timezone.now()
        
        # 1. Update CandidateCompetition
        CandidateCompetition.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_promote,
            status=CandidateCompetition.Status.ACTIVE
        ).update(current_stage=to_stage, last_active_at=now)

        CandidateCompetition.objects.filter(
            competition=competition,
            candidate_id__in=candidate_ids_to_eliminate,
            status=CandidateCompetition.Status.ELIMINATED
        ).update(current_stage=to_stage, last_active_at=now)

        # 2. Update Old StageProgress
        from_stage = Stage.objects.filter(competition=competition, type=from_stage_type).first()
        if from_stage:
            CandidateStageProgress.objects.filter(
                candidate_competition__competition=competition,
                candidate_competition__candidate_id__in=(candidate_ids_to_promote + candidate_ids_to_eliminate),
                stage=from_stage
            ).update(status=CandidateStageProgress.Status.COMPLETED, completed_at=now)

        # 3. Create/Update New StageProgress
        participations = CandidateCompetition.objects.filter(
            competition=competition, 
            candidate_id__in=candidate_ids_to_promote
        )
        
        for part in participations:
             CandidateStageProgress.objects.update_or_create(
                 candidate_competition=part,
                 stage=to_stage,
                 defaults={
                     'status': CandidateStageProgress.Status.IN_PROGRESS,
                     'started_at': now
                 }
             )

        logger.info(f"Successfully promoted {len(candidate_ids_to_promote)} candidates from {from_stage_type} to {to_stage_type}.")
        return len(candidate_ids_to_promote)
