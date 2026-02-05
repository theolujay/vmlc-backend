import uuid
import logging

from django.utils import timezone
from django.db import transaction
from celery import shared_task

from competition.services.ranking_snapshot import RankingSnapshotGenerator, RankingSnapshotGenerationError
from competition.services.leaderboard import LeaderboardService
from competition.models import RankingSnapshot, Stage

logger = logging.getLogger(__name__)

@shared_task(name="generate_ranking_snapshot_task")
def generate_ranking_snapshot_task(stage_exam_id, publish_now=False, staff_id=None):
    """
    Celery task to generate (and optionally publish) ranking snapshot for a stage exam.
    """
    logger.info(f"Starting ranking snapshot generation for StageExam {stage_exam_id} (publish_now={publish_now})")
    try:
        generator = RankingSnapshotGenerator(stage_exam_id=stage_exam_id)
        
        # Convert string staff_id back to UUID if passed as string (Celery serialization)
        if staff_id and isinstance(staff_id, str):
            staff_id = uuid.UUID(staff_id)
            
        ranking_snapshot = generator.generate_and_save_ranking_snapshot(
            published_by_staff_id=staff_id
        )
        
        if publish_now:
            # Enforce the 'one_published_ranking_snapshot_per_stage_round' constraint by
            # unpublishing any other ranking snapshot for the same stage/round.
            with transaction.atomic():
                RankingSnapshot.objects.filter(
                    competition=ranking_snapshot.competition,
                    stage=ranking_snapshot.stage,
                    round=ranking_snapshot.round,
                    is_published=True
                ).exclude(id=ranking_snapshot.id).update(is_published=False, published_at=None)

                ranking_snapshot.is_published = True
                ranking_snapshot.published_at = timezone.now()
                ranking_snapshot.save(update_fields=["is_published", "published_at"])
                
            logger.info(f"Ranking snapshot for StageExam {stage_exam_id} generated and published.")
            
            # Trigger leaderboard update if it's a league exam
            if ranking_snapshot.stage == Stage.Type.LEAGUE:
                update_leaderboard_task.delay(
                    competition_id=str(ranking_snapshot.competition_id),
                    as_of_round=ranking_snapshot.round
                )
        else:
            logger.info(f"Ranking snapshot for StageExam {stage_exam_id} generated (unpublished).")
            
    except RankingSnapshotGenerationError as e:
        logger.error(f"Ranking snapshot generation error for StageExam {stage_exam_id}: {e}")
    except Exception as exc:
        logger.error(f"Unexpected error generating ranking snapshot for StageExam {stage_exam_id}: {exc}", exc_info=True)
        raise


@shared_task(name="update_leaderboard_task")
def update_leaderboard_task(competition_id, as_of_round):
    """
    Celery task to update the aggregate league leaderboard.
    """
    logger.info(f"Updating league leaderboard for competition {competition_id} as of round {as_of_round}")
    try:
        LeaderboardService.update_league_leaderboard(
            competition_id=uuid.UUID(competition_id) if isinstance(competition_id, str) else competition_id,
            as_of_round=as_of_round
        )
        logger.info(f"League leaderboard updated successfully for round {as_of_round}.")
    except Exception as exc:
        logger.error(f"Error updating league leaderboard: {exc}", exc_info=True)
        raise
