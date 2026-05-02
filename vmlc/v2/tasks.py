import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


def do_nothing():  # this is called to alllow celery registered tasks that are somehow not found in other apps
    pass


@shared_task(name="invalidate_exam_related_caches_task")
def invalidate_exam_related_caches_task(exam_id):
    """
    Invalidates caches related to a specific exam, including candidate dashboards.
    """
    from vmlc.models import Exam
    from competition.models import Enrollment
    from vmlc.v2.utils import (
        CacheKeys,
        invalidate_staff_dashboard,
        invalidate_exam_cache,
        invalidate_score_boards,
    )

    try:
        exam = Exam.objects.select_related(
            "competition_slot__competition_stage__competition"
        ).get(pk=exam_id)
    except Exam.DoesNotExist:
        logger.warning(f"Exam {exam_id} not found for cache invalidation.")
        return

    invalidate_exam_cache(str(exam.id))
    invalidate_score_boards(exam_id=str(exam.id))

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

    # Passcode Generation: Identify exams that became SCHEDULED since the last run
    # (Exam status is SCHEDULED if scheduled_date is in the future)
    newly_scheduled_exams = Exam.objects.select_related("competition_slot__competition_stage").filter(
        is_active=True, scheduled_date__gt=now, updated_at__gt=last_run
    )
    for exam in newly_scheduled_exams:
        generate_and_send_exam_passcodes_task.delay(str(exam.id), exam.stage)
        logger.info(
            f"Triggered passcode task for newly scheduled/updated exam {exam.id}"
        )

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
            start_time = exam.scheduled_date

            reminder_time = start_time - timedelta(hours=1)
            if last_run < reminder_time <= now:
                # 1 hour reminder
                from comms.tasks import notify_candidates_about_exam_task

                notify_candidates_about_exam_task.delay(str(exam.id), "reminder")
                logger.info(f"Triggered 1-hour reminder for exam {exam.id}")

            if last_run < start_time <= now:
                # Started
                transitioned_exams.append(exam)
                # Notify candidates that the exam has started
                from comms.tasks import (
                    notify_candidates_about_exam_task,
                    notify_staff_about_exam_event_task,
                )

                notify_candidates_about_exam_task.delay(str(exam.id), "started")
                notify_staff_about_exam_event_task.delay(str(exam.id), "ongoing")
                logger.info(f"Triggered start time notification for exam {exam.id}")

            elif last_run < conclusion_time <= now:
                # Concluded
                transitioned_exams.append(exam)
                from comms.tasks import notify_staff_about_exam_event_task

                notify_staff_about_exam_event_task.delay(str(exam.id), "concluded")
                logger.info(f"Triggered conclusion notification for exam {exam.id}")

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


@shared_task(name="generate_and_send_exam_passcodes_task")
def generate_and_send_exam_passcodes_task(exam_id, exam_stage=None):
    """
    Task to generate passcodes and send them via email to eligible candidates.
    """
    from vmlc.models import Exam
    from competition.models import Stage
    from vmlc.services.exam_access import ExamAccessService

    stage = exam_stage

    logger.info(f"Generating and sending passcodes for exam {exam_id}")
    ExamAccessService.generate_passcodes(exam_id)

    if stage is None:
        try:
            exam = Exam.objects.select_related("competition_slot__competition_stage").get(pk=exam_id)
            stage = exam.stage
        except Exam.DoesNotExist:
            logger.warning(f"Exam {exam_id} not found for passcode task.")
            return

    # Only send passcodes for Screening and Final exams
    if stage not in [Stage.Type.SCREENING, Stage.Type.FINAL]:
        logger.info(f"Skipping passcode generation for exam {exam_id} (Stage: {stage})")
        return

    ExamAccessService.send_passcode_emails(exam_id)


@shared_task(name="mark_exam_access_as_expired_task")
def mark_exam_access_as_expired_task(access_id):
    """
    Marks an ExamAccess as EXPIRED if it's still in STARTED status after its deadline.
    Includes a 5-minute grace period consistent with SubmitAnswersV2View.
    """
    from vmlc.models import ExamAccess
    from vmlc.v2.utils import invalidate_candidate_cache
    from django.utils import timezone
    from datetime import timedelta

    try:
        access = ExamAccess.objects.select_related("candidate").get(pk=access_id)
    except ExamAccess.DoesNotExist:
        logger.warning(f"ExamAccess {access_id} not found for expiration task.")
        return

    # Check if still STARTED and deadline has passed
    if access.status == ExamAccess.Status.STARTED:
        if timezone.now() >= access.deadline:
            access.status = ExamAccess.Status.EXPIRED
            access.save(update_fields=["status"])

            # Invalidate cache so candidate sees the expired status
            invalidate_candidate_cache(access.candidate_id, access.candidate.user_id)

            logger.info(
                f"ExamAccess {access_id} marked as EXPIRED for candidate {access.candidate_id}"
            )
        else:
            # If we're called before the grace period (unlikely given ETA),
            # we could reschedule, but for now just log it.
            logger.info(
                f"ExamAccess {access_id} is still within grace period. No action taken."
            )


@shared_task(name="process_heartbeat_events_task")
def process_heartbeat_events_task(heartbeat_id, events_data):
    """
    Background task to process violation events and update the suspicion score
    for a given heartbeat.
    """
    from vmlc.services.proctoring import ProctoringService

    logger.info(f"Processing events for heartbeat {heartbeat_id}")
    ProctoringService.process_events_and_score(heartbeat_id, events_data)
