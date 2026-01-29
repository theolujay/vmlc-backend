import uuid
import logging

from django.utils import timezone
from celery import shared_task

from competition.services.standings import StandingsGenerator, StandingsGenerationError

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
            standings.is_published = True
            standings.published_at = timezone.now()
            standings.save(update_fields=["is_published", "published_at"])
            logger.info(f"Standings for StageExam {stage_exam_id} generated and published.")
        else:
            logger.info(f"Standings for StageExam {stage_exam_id} generated (unpublished).")
            
    except StandingsGenerationError as e:
        logger.error(f"Standings generation error for StageExam {stage_exam_id}: {e}")
        # We might not want to retry logic errors
    except Exception as exc:
        logger.error(f"Unexpected error generating standings for StageExam {stage_exam_id}: {exc}", exc_info=True)
        raise # Let Celery handle retry if configured or log failure
