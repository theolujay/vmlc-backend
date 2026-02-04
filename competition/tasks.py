import uuid
import logging

from django.utils import timezone
from django.db import transaction
from celery import shared_task

from competition.services.standings import StandingsGenerator, StandingsGenerationError
from competition.services.leaderboard import LeaderboardService
from competition.models import Standings, Stage

logger = logging.getLogger(__name__)

@shared_task(name="generate_standings_task")
def generate_standings_task(stage_exam_id, publish_now=False, staff_id=None):
    """
    Celery task to generate (and optionally publish) standings for a stage exam.
    """
    logger.info(f"Starting standings generation for StageExam {stage_exam_id} (publish_now={publish_now})")
    try:
        generator = StandingsGenerator(stage_exam_id=stage_exam_id)
        
        # Convert string staff_id back to UUID if passed as string (Celery serialization)
        if staff_id and isinstance(staff_id, str):
            staff_id = uuid.UUID(staff_id)
            
        standings = generator.generate_and_save_standings(
            published_by_staff_id=staff_id
        )
        
        if publish_now:
            # Enforce the 'one_published_standings_per_stage_round' constraint by
            # unpublishing any other standings for the same stage/round.
            with transaction.atomic():
                Standings.objects.filter(
                    competition=standings.competition,
                    stage=standings.stage,
                    round=standings.round,
                    is_published=True
                ).exclude(id=standings.id).update(is_published=False, published_at=None)

                standings.is_published = True
                standings.published_at = timezone.now()
                standings.save(update_fields=["is_published", "published_at"])
                
            logger.info(f"Standings for StageExam {stage_exam_id} generated and published.")
            
            # Trigger leaderboard update if it's a league exam
            if standings.stage == Stage.Type.LEAGUE:
                update_leaderboard_task.delay(
                    competition_id=str(standings.competition_id),
                    as_of_round=standings.round
                )
        else:
            logger.info(f"Standings for StageExam {stage_exam_id} generated (unpublished).")
            
    except StandingsGenerationError as e:
        logger.error(f"Standings generation error for StageExam {stage_exam_id}: {e}")
    except Exception as exc:
        logger.error(f"Unexpected error generating standings for StageExam {stage_exam_id}: {exc}", exc_info=True)
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
