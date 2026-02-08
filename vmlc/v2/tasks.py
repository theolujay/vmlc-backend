import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(name="invalidate_exam_related_caches_task")
def invalidate_exam_related_caches_task(exam_id):
    """
    Invalidates caches related to a specific exam, including candidate dashboards.
    """
    from vmlc.models import Exam
    from competition.models import Enrollment
    from vmlc.v2.utils import CacheKeys, invalidate_staff_dashboard

    try:
        exam = Exam.objects.select_related(
            "competition_slot__competition_stage__competition"
        ).get(pk=exam_id)
    except Exam.DoesNotExist:
        logger.warning(f"Exam {exam_id} not found for cache invalidation.")
        return

    cache.delete(CacheKeys.EXAM_DETAIL.format(exam_id=exam.id))
    cache.delete(CacheKeys.EXAM_QUESTIONS.format(exam_id=exam.id))
    cache.delete(CacheKeys.EXAM_RESULTS.format(exam_id=exam.id))

    # Invalidate Candidate Dashboards for everyone in this competition
    if exam.competition_slot and exam.competition_slot.competition_stage:
        competition = exam.competition_slot.competition_stage.competition

        candidates = Enrollment.objects.filter(competition=competition).values_list(
            "candidate_id", "candidate__user_id"
        )

        all_keys = []
        for candidate_id, user_id in candidates:
            all_keys.extend(CacheKeys.get_candidate_keys(candidate_id, user_id))

        # Delete in chunks to be safe with when competition is large
        CHUNK_SIZE = 500
        for i in range(0, len(all_keys), CHUNK_SIZE):
            cache.delete_many(all_keys[i : i + CHUNK_SIZE])

        logger.info(
            f"Invalidated caches for {len(candidates)} candidates for exam {exam_id}"
        )

    # Also invalidate staff dashboard
    invalidate_staff_dashboard()

    from vmlc.utils.events import log_event

    log_event(
        event_name="CACHE_INVALIDATION_EXAM",
        metadata={
            "exam_id": str(exam_id),
            "affected_candidates_count": (
                len(candidates) if "candidates" in locals() else 0
            ),
            "reason": "Exam update or status change",
        },
    )


@shared_task(name="check_exam_status_transitions_task")
def check_exam_status_transitions_task():
    """
    Periodic task to check for exams that have transitioned status due to time.
    Invalidates caches if a transition is detected.
    """
    from vmlc.models import Exam
    from django.utils import timezone
    from datetime import timedelta
    from vmlc.utils.events import log_event

    now = timezone.now()
    # We look for exams that have scheduled_date or conclusion_time
    # within the last few minutes (to catch transitions)
    # or just check all active exams if the number is small.

    # For simplicity and correctness, we can look for exams that are
    # either about to start or just ended.
    # But a better way is to track the last run time.

    last_run = cache.get("last_exam_status_check_time")
    if not last_run:
        last_run = now - timedelta(minutes=5)

    if isinstance(last_run, str):
        from dateutil import parser

        last_run = parser.isoparse(last_run)

    # Exams that transitioned from SCHEDULED to ONGOING
    starting_exams = Exam.objects.filter(
        scheduled_date__gt=last_run, scheduled_date__lte=now, is_active=True
    )

    # Exams that transitioned from ONGOING to CONCLUDED
    # Conclusion time is scheduled_date + open_duration_hours
    # This is harder to query directly in DB without F expressions and timedelta,
    # but we can do it.

    # Or just fetch all exams that are recently concluded
    # (where scheduled_date + open_duration_hours is between last_run and now)

    # Let's just invalidate for any exam that is "Active" and has a
    # scheduled_date in a relevant range.

    transitioned_exams = list(starting_exams)

    # For concluding exams:
    # scheduled_date = now - open_duration_hours
    # We can iterate over potentially ongoing/scheduled exams and check.

    active_exams = Exam.objects.filter(is_active=True).exclude(scheduled_date=None)
    for exam in active_exams:
        if exam.scheduled_date and exam.open_duration_hours:
            conclusion_time = exam.scheduled_date + timedelta(
                hours=exam.open_duration_hours
            )
            if last_run < exam.scheduled_date <= now:
                # Started
                transitioned_exams.append(exam)
            elif last_run < conclusion_time <= now:
                # Concluded
                transitioned_exams.append(exam)

    unique_exam_ids = {str(e.id) for e in transitioned_exams}
    for exam_id in unique_exam_ids:
        invalidate_exam_related_caches_task.delay(exam_id)
        logger.info(f"Triggered invalidation for transitioned exam {exam_id}")

    if unique_exam_ids:
        log_event(
            event_name="EXAM_STATUS_TRANSITION_DETECTED",
            metadata={
                "transitioned_exam_ids": list(unique_exam_ids),
                "timestamp": now.isoformat(),
            },
        )

    cache.set("last_exam_status_check_time", now, timeout=86400)
