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
from competition.models import RankingSnapshot, RankingSnapshotEntry, Stage
from vmlc.utils.cache import invalidate_candidate_cache, invalidate_score_boards

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


@shared_task(name="generate_ranking_and_update_leaderboard_task")
def generate_ranking_and_update_leaderboard_task(stage_exam_id, actor_id=None, ranking_policy="standard"):
    """
    Celery task to generate (and optionally publish) ranking snapshot for a stage exam.
    """
    logger.info(f"Starting ranking snapshot generation for StageExam {stage_exam_id}")
    try:
        generator = RankingSnapshotGenerator(stage_exam_id=stage_exam_id)

        # Convert string actor_id back to UUID if passed as string (Celery serialization)
        if actor_id and isinstance(actor_id, str):
            actor_id = uuid.UUID(actor_id)

        ranking = generator.generate_and_save_ranking(
            actor_id=actor_id, ranking_policy=ranking_policy
        )
        if ranking.stage == Stage.Type.LEAGUE:
            update_leaderboard_task.delay(
                competition_id=ranking.competition.id,
                as_of_round=ranking.round,
            )
            invalidate_score_boards(exam_id=ranking.exam_id)

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

@shared_task(name="publish_league_leaderboard_update_task")
def publish_league_leaderboard_update_task(competition_id, as_of_round):
    logger.info(
        "Publishing league leaderboard update"
    )
    try:
        LeaderboardService.publish_league_leaderboard_update(competition_id, as_of_round)
        invalidate_score_boards()
        logger.info("League leaderboard update published")
    except Exception as exc:
        logger.error(f"Error publishing league leaderboard update: {exc}", exc_info=True)
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


@shared_task(name="publish_ranking_task")
def publish_ranking_task(ranking_snapshot_id, actor_id=None):
    """
    Task to mark a ranking snapshot as published and trigger related updates.
    """
    logger.info(f"Publishing RankingSnapshot {ranking_snapshot_id}")
    try:
        with transaction.atomic():
            ranking = RankingSnapshot.objects.select_for_update().get(
                id=ranking_snapshot_id
            )

            if not ranking:
                logger.warning(f"RankingSnapshot {ranking_snapshot_id} not found.")
                return

            if not ranking.is_active:
                logger.warning(
                    f"RankingSnapshot {ranking_snapshot_id} marked as inactive. Will not publish."
                )
                return

            if ranking.is_published:
                logger.warning(
                    f"RankingSnapshot {ranking_snapshot_id} is already published."
                )
                return

            # Enforce the 'one_published_ranking_per_stage_round' constraint by
            # unpublishing any other ranking snapshot for the same stage/round.
            RankingSnapshot.objects.filter(
                competition=ranking.competition_id,
                stage=ranking.stage,
                round=ranking.round,
            ).exclude(id=ranking.id).update(
                is_published=False, published_at=None, is_active=False
            )

            ranking.is_active = True
            ranking.is_published = True
            ranking.published_at = timezone.now()
            if actor_id:
                ranking.meta["published_by"] = str(actor_id)

            # Remove scheduled info if it exists
            ranking.meta.pop("scheduled_publish_at", None)

            ranking.save(
                update_fields=[
                    "is_active",
                    "is_published",
                    "published_at",
                    "meta",
                ]
            )

            # Trigger cache invalidation for all candidates in this snapshot
            transaction.on_commit(
                lambda: invalidate_published_ranking_cache_task.delay(
                    ranking_snapshot_id=ranking.id
                )
            )

            # Trigger notifications
            from comms.services.notification import NotificationService

            ns = NotificationService()
            transaction.on_commit(lambda: ns.notify_ranking_published(ranking))

            from competition.models import Stage

            # Trigger leaderboard update if it's a league exam
            if ranking.stage == Stage.Type.LEAGUE:
                transaction.on_commit(
                    lambda: update_leaderboard_task.delay(
                        competition_id=ranking.competition_id,
                        as_of_round=ranking.round,
                    )
                )

        logger.info(f"RankingSnapshot {ranking_snapshot_id} published successfully.")

    except RankingSnapshot.DoesNotExist:
        logger.error(f"RankingSnapshot {ranking_snapshot_id} not found.")
    except Exception as exc:
        logger.error(
            f"Error publishing ranking snapshot {ranking_snapshot_id}: {exc}",
            exc_info=True,
        )
        raise


@shared_task(name="generate_stats_overview_task")
def generate_stats_overview_task():
    """
    Asynchronously generates and caches each part of the statistics overview individually.
    """
    from competition.utils.stats import (
        get_candidate_stats_cached,
        get_staff_stats_cached,
        get_exam_stats_cached,
        get_competition_stats_cached,
        get_helpdesk_stats_cached,
        get_funnel_metrics_cached,
        get_geographic_stats_cached,
    )

    get_candidate_stats_cached()
    get_staff_stats_cached()
    get_exam_stats_cached()
    get_competition_stats_cached()
    get_helpdesk_stats_cached()
    get_funnel_metrics_cached()
    get_geographic_stats_cached()

    logger.info("Successfully regenerated decentralized stats overview caches.")
