import uuid
import logging

from django.utils import timezone
from django.db import transaction
from celery import shared_task

from competition.services.ranking import (
    RankingSnapshotGenerator,
    RankingSnapshotGenerationError,
)
from competition.services.leaderboard import LeaderboardService
from competition.models import RankingSnapshot, RankingSnapshotEntry
from vmlc.v2.utils import invalidate_candidate_cache, invalidate_score_boards

logger = logging.getLogger(__name__)


@shared_task(name="invalidate_published_ranking_cache_task")
def invalidate_published_ranking_cache_task(ranking_snapshot_id):
    """
    Task to invalidate caches for candidates when a ranking snapshot is published.
    """
    try:
        ranking = RankingSnapshot.objects.get(id=ranking_snapshot_id)
        # Invalidate global scoreboards (league leaderboard, etc.)
        invalidate_score_boards(exam_id=ranking.exam_id)
        # Invalidate all candidate dashboards for candidates in this snapshot
        candidate_ids = RankingSnapshotEntry.objects.filter(
            ranking_snapshot_id=ranking_snapshot_id
        ).values_list("candidate_id", flat=True)

        for candidate_id in candidate_ids:
            invalidate_candidate_cache(candidate_id)

        logger.info(
            f"Cache invalidated for {len(candidate_ids)} candidates after publishing RankingSnapshot {ranking_snapshot_id}"
        )

    except RankingSnapshot.DoesNotExist:
        logger.error(
            f"RankingSnapshot {ranking_snapshot_id} not found during cache invalidation."
        )
    except Exception as exc:
        logger.error(
            f"Error invalidating published ranking cache: {exc}", exc_info=True
        )


@shared_task(name="generate_ranking_task")
def generate_ranking_task(stage_exam_id, actor_id=None, ranking_policy="standard"):
    """
    Celery task to generate (and optionally publish) ranking snapshot for a stage exam.
    """
    logger.info(f"Starting ranking snapshot generation for StageExam {stage_exam_id}")
    try:
        generator = RankingSnapshotGenerator(stage_exam_id=stage_exam_id)

        # Convert string actor_id back to UUID if passed as string (Celery serialization)
        if actor_id and isinstance(actor_id, str):
            actor_id = uuid.UUID(actor_id)

        generator.generate_and_save_ranking(
            actor_id=actor_id, ranking_policy=ranking_policy
        )

        logger.info(f"Ranking snapshot for StageExam {stage_exam_id} generated.")

    except RankingSnapshotGenerationError as e:
        logger.error(
            f"Ranking snapshot generation error for StageExam {stage_exam_id}: {e}"
        )
    except Exception as exc:
        logger.error(
            f"Unexpected error generating ranking snapshot for StageExam {stage_exam_id}: {exc}",
            exc_info=True,
        )
        raise


@shared_task(name="update_leaderboard_task")
def update_leaderboard_task(competition_id, as_of_round):
    """
    Celery task to update the aggregate league leaderboard.
    """
    logger.info(
        f"Updating league leaderboard for competition {competition_id} as of round {as_of_round}"
    )
    try:
        LeaderboardService.update_league_leaderboard(
            competition_id=competition_id, as_of_round=as_of_round
        )
        logger.info(f"League leaderboard updated successfully for round {as_of_round}.")
    except Exception as exc:
        logger.error(f"Error updating league leaderboard: {exc}", exc_info=True)
        raise
