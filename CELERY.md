## `vmlc/tasks.py`

```python
import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(name="invalidate_exam_related_caches_task")
def invalidate_exam_related_caches_task(exam_id):
    """
    Invalidates caches related to a specific exam, including candidate dashboards.
    """
    from competition.models import Enrollment
    from core.utils.cache import (
        CacheKeys,
        invalidate_exam_cache,
        invalidate_score_boards,
        invalidate_staff_dashboard,
    )
    from vmlc.models import Exam

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

    from core.utils.events import log_event

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
    from datetime import timedelta

    from django.utils import timezone

    from core.utils.events import log_event
    from vmlc.models import Exam

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
    newly_scheduled_exams = Exam.objects.select_related(
        "competition_slot__competition_stage"
    ).filter(is_active=True, scheduled_date__gt=now, updated_at__gt=last_run)
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
    from competition.models import Stage
    from vmlc.models import Exam
    from vmlc.services.exam_access import ExamAccessService

    stage = exam_stage

    logger.info(f"Generating and sending passcodes for exam {exam_id}")
    ExamAccessService.generate_passcodes(exam_id)

    if stage is None:
        try:
            exam = Exam.objects.select_related(
                "competition_slot__competition_stage"
            ).get(pk=exam_id)
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

    from django.utils import timezone

    from core.utils.cache import invalidate_candidate_cache
    from vmlc.models import ExamAccess

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
```

---

## `vmlc/models.py`

```python
"""
This module defines the database models for the VMLC backend application.
"""

import logging
import uuid
from datetime import timedelta

from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone

from competition.models import Stage
from core.storage_backends import PrivateMediaStorage, PublicMediaStorage
from identity.validators import validate_image

logger = logging.getLogger(__name__)

phone_regex = RegexValidator(
    regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
    message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
)

phone_field = models.CharField(
    validators=[phone_regex],
    max_length=17,
    help_text="Nigerian phone number",
)


class FeatureFlag(models.Model):
    """Feature flag model."""

    key = models.CharField(max_length=50, unique=True)
    value = models.BooleanField(default=True)
    auto_off_date = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_bool(cls, key, default=False):
        """Get the boolean value of a feature flag."""
        cache_key = f"feature_flag_{key}"
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        try:
            value = cls.objects.get(key=key).value
            cache.set(cache_key, value, 86400)  # Cache for 24 hours
            return value
        except cls.DoesNotExist:
            return default

    def save(self, *args, **kwargs):
        """Invalidate the cache when a feature flag is saved."""
        cache.delete(f"feature_flag_{self.key}")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Invalidate the cache when a feature flag is deleted."""
        cache.delete(f"feature_flag_{self.key}")
        super().delete(*args, **kwargs)

    def __str__(self):
        """Return a string representation of the feature flag."""
        return f"{self.key}: {'Enabled' if self.value else 'Disabled'}"


class Question(models.Model):
    """
    A question belonging to one or more exams. Includes text, difficulty, and staff author.
    """

    class Options(models.TextChoices):
        """Options for a question."""

        A = "A", "Option A"
        B = "B", "Option B"
        C = "C", "Option C"
        D = "D", "Option D"

    class Difficulty(models.TextChoices):
        """Difficulty levels for a question."""

        EASY = "easy", "Easy"
        MODERATE = "moderate", "Moderate"
        HARD = "hard", "Hard"

    text = models.TextField()
    image = models.ImageField(
        upload_to="question_images/",
        blank=True,
        null=True,
        storage=PublicMediaStorage(),
        validators=[validate_image],
    )
    option_a = models.TextField(blank=True)
    option_b = models.TextField(blank=True)
    option_c = models.TextField(blank=True)
    option_d = models.TextField(blank=True)
    correct_answer = models.CharField(max_length=1, choices=Options.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="questions_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="questions_updated",
        on_delete=models.SET_NULL,
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MODERATE,
    )
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    def archive(self):
        """Archive the question instead of deleting it."""
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save()

    def __str__(self):
        """Return a string representation of the question."""
        return f"Q{self.id}: {self.text[:50]}..."


class Exam(models.Model):
    """
    Defines the content and delivery configuration for an assessment.

    This model serves as the 'Blueprint' for an exam. It is linked to a
    specific Competition Stage via a 'competition_slot', which
    dictates where and when this exam occurs within the tournament logic.
    """

    def __str__(self):
        return self.get_title()

    class ExamDeliveryMode(models.TextChoices):
        VIRTUAL = "virtual", "Virtual"
        IN_PERSON = "in_person", "In-Person (CBT Venue)"

    class Status(models.TextChoices):
        """Statuses for an exam."""

        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        ONGOING = "ongoing", "Ongoing"
        CONCLUDED = "concluded", "Concluded"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    description = models.TextField(blank=True, null=True)
    questions = models.ManyToManyField(Question, blank=True, related_name="exams")
    delivery_mode = models.CharField(
        max_length=20,
        choices=ExamDeliveryMode.choices,
        default=ExamDeliveryMode.VIRTUAL,
        db_index=True,
    )
    scheduled_date = models.DateTimeField(blank=True, null=True, db_index=True)
    open_duration_hours = models.PositiveIntegerField(null=True, blank=True)
    countdown_minutes = models.PositiveIntegerField(null=True, blank=True)
    competition_slot = models.OneToOneField(
        "competition.StageExam",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="exam",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="exams_created",
        on_delete=models.SET_NULL,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="exams_updated",
        on_delete=models.SET_NULL,
    )
    _status_override = models.CharField(
        max_length=20,
        choices=Status.choices,
        null=True,
        blank=True,
        help_text="For testing only: temporarily override the computed status.",
    )

    def retract(self):
        """
        Retracts a scheduled exam back to draft status.
        Only allowed if the status is SCHEDULED.
        """
        if self.status != self.Status.SCHEDULED:
            return False, f"Cannot retract an exam that is {self.status}."

        self.scheduled_date = None
        self.countdown_minutes = None
        self.open_duration_hours = None
        self.is_active = True
        self.save()

        if self.competition_slot:
            self.competition_slot.is_active = False
            self.competition_slot.save(update_fields=["is_active"])

        return True, "Exam retracted successfully."

    @property
    def title(self):
        """Inferred title from StageExam context"""
        return self.get_title()

    @property
    def stage(self):
        """Inferred stage type from StageExam context"""
        return (
            self.competition_slot.competition_stage.type
            if self.competition_slot
            else None
        )

    @property
    def stage_id(self):
        """Inferred stage ID from StageExam context"""
        return (
            self.competition_slot.competition_stage.id
            if self.competition_slot
            else None
        )

    @property
    def round(self):
        """Inferred round from StageExam context"""
        return self.competition_slot.round if self.competition_slot else None

    @property
    def stage_display(self):
        """Inferred stage display label from StageExam context"""
        return (
            self.competition_slot.competition_stage.get_type_display()
            if self.competition_slot
            else None
        )

    @property
    def is_currently_open(self):
        """
        Determines if the exam is currently open for submissions.

        An exam is considered open if it is marked as active, has a scheduled
        start date, and the current time is within the allowed window
        (from `scheduled_date` to `scheduled_date` + `open_duration_hours`).

        Returns:
            bool: True if the exam is currently open, False otherwise.
        """
        if not self.is_active or not self.scheduled_date:
            return False

        now = timezone.now()

        if not self.scheduled_date:
            return False

        end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
        return self.scheduled_date <= now <= end_time

    @property
    def status(self):
        """
        Returns the current status of the exam.
        If _status_override is set, it will return that value.

        Status flow:
        - DRAFT: No scheduled date set
        - CANCELLED: Exam was deactivated (is_active=False)
        - SCHEDULED: Has a future scheduled date
        - ONGOING: Currently open for taking
        - CONCLUDED: Past the end time
        """
        if self._status_override:
            return self._status_override

        if self.scheduled_date is None or self.open_duration_hours is None:
            return self.Status.DRAFT

        if not self.is_active:
            return self.Status.CANCELLED

        now = timezone.now()

        if self.scheduled_date is None or self.open_duration_hours is None:
            return self.Status.DRAFT

        conclusion_time = self.scheduled_date + timedelta(
            hours=self.open_duration_hours
        )

        if now < self.scheduled_date:
            return self.Status.SCHEDULED
        if now < conclusion_time:
            return self.Status.ONGOING

        return self.Status.CONCLUDED

    @property
    def concluded_at(self):
        if self.scheduled_date is not None and self.open_duration_hours is not None:
            now = timezone.now()

            if not self.scheduled_date:
                return None

            end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
            if end_time < now:
                return end_time
        return None

    @classmethod
    def active_exams(cls):
        """
        Returns only exams marked as active.
        """
        return cls.objects.filter(is_active=True)

    def get_title(self):
        if not self.competition_slot:
            return f"Exam {str(self.id)[:8]}"

        slot = self.competition_slot
        stage = slot.competition_stage
        stage_type = stage.type
        stage_label = stage.get_type_display()

        if stage_type == "screening" and slot.round is None:
            exam_index = (
                Exam.objects.filter(
                    competition_slot__competition_stage__type=Stage.Type.SCREENING,
                    competition_slot__round__isnull=True,
                    created_at__lt=self.created_at,
                ).count()
                + 1
            )

            stage_part = (
                f"Screening Test {exam_index}" if exam_index > 1 else "Screening Test"
            )
        elif stage_type == "league" and slot.round is not None:
            stage_part = f"League Round {slot.round}"
        elif stage_type == "final" and slot.round is None:
            stage_part = "Final Exam"
        else:
            stage_part = stage_label

        return stage_part

    def get_question_count(self):
        """
        Returns the number of questions in the exam.
        """
        return self.questions.filter(is_archived=False).count()

    def get_average_score(self):
        """
        Calculates the average score for all submissions tied to this exam.
        """
        return self.results.aggregate(avg_score=Avg("score"))["avg_score"]

    def save(self, *args, **kwargs):
        """
        Overridden save to synchronize StageExam visibility and notify on status changes.
        """
        if self.stage == "final":
            self.delivery_mode = self.ExamDeliveryMode.IN_PERSON

        # Ensure scheduled_date is a datetime object
        if isinstance(self.scheduled_date, str):
            from django.utils.dateparse import parse_datetime

            self.scheduled_date = parse_datetime(self.scheduled_date)
        # Fetch the old status if the object already exists
        old_status = None
        if self.pk:
            try:
                old_exam = Exam.objects.get(pk=self.pk)
                old_status = old_exam.status
            except Exam.DoesNotExist:
                pass  # Object is new, no old status

        super().save(*args, **kwargs)

        new_status = self.status

        # If status changed and it's now CANCELLED, trigger notification
        if old_status != new_status and new_status == self.Status.CANCELLED:
            from django.db import transaction

            from comms.tasks import notify_staff_about_exam_event_task

            transaction.on_commit(
                lambda: notify_staff_about_exam_event_task.delay(
                    str(self.id), "cancelled"
                )
            )
            logger.info(f"Triggered 'cancelled' notification for exam {self.id}")

        if self.competition_slot:
            # StageExam should be active ONLY IF the exam is scheduled AND is_active is True
            should_be_active = self.scheduled_date is not None and self.is_active

            if self.competition_slot.is_active != should_be_active:
                from django.db import transaction

                def update_slot():
                    self.competition_slot.is_active = should_be_active
                    self.competition_slot.save(update_fields=["is_active"])

                transaction.on_commit(update_slot)


class CandidateExamResult(models.Model):
    """
    A result representing a candidate's performance in an exam.

    Links to candidate, exam, and submitting staff member.
    """

    candidate = models.ForeignKey(
        "identity.Candidate", on_delete=models.CASCADE, related_name="results"
    )
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="results")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    recorded_at = models.DateTimeField(
        default=timezone.now
    )  # TODO: consider making this field nullable so `generate_ranking_and_update_leaderboard_task` updates it
    updated_at = models.DateTimeField(auto_now=True)
    is_auto_submit = models.BooleanField(default=False)
    score_submitted_by = models.ForeignKey(
        "identity.Staff", on_delete=models.SET_NULL, null=True, blank=True
    )
    auto_score = models.BooleanField(default=False, db_index=True)

    class Meta:
        """Meta options for the CandidateExamResult model."""

        unique_together = ("candidate", "exam")
        ordering = ["-recorded_at"]


class CandidateAnswer(models.Model):
    """Model for a candidate's answer to a question."""

    candidate_exam_result = models.ForeignKey(
        CandidateExamResult,
        null=True,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    selected_option = models.CharField(
        max_length=1,
        choices=Question.Options.choices,
        blank=True,
        null=True,
    )
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for the CandidateAnswer model."""

        constraints = [
            models.UniqueConstraint(
                fields=["candidate_exam_result", "question"],
                name="unique_answer_per_candidate_exam_result",
            )
        ]

    def __str__(self):
        if self.candidate_exam_result and self.question:
            username = self.candidate_exam_result.candidate.user.username
            return f"Answer by {username} for Q{self.question.id}"
        if self.candidate_exam_result:
            return f"Answer by {self.candidate_exam_result.candidate.user.username} (deleted question)"
        if self.question:
            return f"Answer for Q{self.question.id} (deleted result)"
        return f"Orphaned Answer #{self.id}"


class Event(models.Model):
    """
    Model for recording key events for analytics and dashboards.
    Append-only log of events.
    """

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    event_name = models.CharField(max_length=255, db_index=True)
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        help_text="User who triggered the event, if applicable.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        """Meta options for the Event model."""

        ordering = ["-timestamp"]
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def __str__(self):
        """Return a string representation of the event."""
        return f"{self.event_name} at {self.timestamp}"


class ExamAccess(models.Model):
    """
    Represents a per-candidate execution contract for an exam on a facilitator.

    Created when an exam is provisioned to an external system (e.g. Esturdi).
    Stores access URLs, passcodes, and execution state.
    """

    class Facilitator(models.TextChoices):
        VMLC = "vmlc", "VMLC"
        ESTURDI = "esturdi", "Esturdi"

    class Status(models.TextChoices):
        PENDING = (
            "pending",
            "Pending",
        )  # provisioned but not opened... this is for Esturdi
        ISSUED = "issued", "Issued"  # URL generated... also for Esturdi

        STARTED = (
            "started",
            "Started",
        )  # mostly for VMLC, as I'm unsure when Esturdi will provide this in its case
        SUBMITTED = "submitted", "Submitted"  # also mostly for VMLC...

        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    exam = models.ForeignKey(
        "vmlc.Exam",
        on_delete=models.CASCADE,
        related_name="access_records",
    )
    candidate = models.ForeignKey(
        "identity.Candidate",
        on_delete=models.CASCADE,
        related_name="exam_accesses",
    )

    facilitator_system = models.CharField(
        max_length=20, choices=Facilitator.choices, default=Facilitator.VMLC
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    facilitator_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw request/response metadata exchanged with facilitator.",
    )

    face_capture = models.ImageField(
        upload_to="exam_face_captures/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
    )

    proctoring_status = models.CharField(
        max_length=20,
        choices=[
            ("clear", "Clear"),
            ("suspicious", "Suspicious"),
            ("flagged", "Flagged"),
        ],
        null=True,
        blank=True,
        db_index=True,
    )
    is_manually_reviewed = models.BooleanField(
        default=False,
        help_text="Whether an admin has manually confirmed or cleared this attempt.",
    )

    is_unlocked = models.BooleanField(
        default=False,
        help_text="Whether this session has been unlocked via QR code (for final exams).",
    )
    unlocked_by = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unlocked_exams",
        help_text="The admin who scanned the QR code to unlock this session.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "candidate"], name="unique_exam_access_per_candidate"
            ),
        ]
        indexes = [
            models.Index(fields=["exam", "status"]),
            models.Index(fields=["candidate", "status"]),
        ]


class ExamAccessPasscode(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"

        USED = "used", "Used"

        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    exam_access = models.OneToOneField(
        "ExamAccess",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="exam_access",
    )

    access_url = models.URLField(
        null=True,
        blank=True,
        help_text="Candidate-specific exam URL on the facilitator.",
    )

    passcode = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Opaque passcode or token embedded in the URL.",
    )

    is_passcode_sent = models.BooleanField(
        default=False,
        help_text="Whether the passcode email has been sent to the candidate.",
    )

    expiry_date = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ISSUED,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def regenerate_passcode(self, *args):
        pass


class CacheManagement(models.Model):
    """

    Proxy model for cache management in the admin panel.

    """

    class Meta:
        managed = False

        verbose_name = "Cache Management"

        verbose_name_plural = "Cache Management"


class ExamHeartbeat(models.Model):
    """
    Stores periodic proctoring telemetry (heartbeats) for an exam attempt.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_access = models.ForeignKey(
        "vmlc.ExamAccess",
        on_delete=models.CASCADE,
        related_name="heartbeats",
    )
    sequence_number = models.PositiveIntegerField(
        help_text="Sequential index of the heartbeat to detect gaps."
    )
    client_uuid = models.UUIDField(
        unique=True,
        help_text="Idempotency key generated by the client.",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    period_start = models.DateTimeField(help_text="Start of the telemetry interval.")
    period_end = models.DateTimeField(help_text="End of the telemetry interval.")
    summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Aggregated counts of violation types.",
    )
    face_capture = models.ImageField(
        upload_to="exam_heartbeats/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
    )
    suspicion_score = models.FloatField(
        default=0.0,
        help_text="Computed score for this specific heartbeat (0.0 - 1.0).",
    )
    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Client environment metadata (OS, Browser, etc.).",
    )

    class Meta:
        ordering = ["sequence_number"]
        indexes = [
            models.Index(fields=["exam_access", "sequence_number"]),
        ]

    def __str__(self):
        return f"Heartbeat {self.sequence_number} for {self.exam_access_id}"


class ViolationEvent(models.Model):
    """
    Stores high-fidelity individual violation events captured within a heartbeat.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    heartbeat = models.ForeignKey(
        ExamHeartbeat,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(help_text="Precise time the event occurred.")
    is_critical = models.BooleanField(
        default=False,
        help_text="Whether this event should trigger immediate attention.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contextual info (question_id, duration, etc.).",
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.event_type} at {self.timestamp}"
```

---

## `comms/tasks.py`

```python
import logging
import uuid
from typing import Dict, List

from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import DatabaseError

from comms.services.kudi_sms import KudiSmsService
from comms.services.notification import NotificationService
from comms.services.slack import SlackService
from core.utils.exceptions import ServerError
from identity.models import User

logger = logging.getLogger(__name__)

notification_service = NotificationService()
kudi_sms_service = KudiSmsService()
slack_service = SlackService()


@shared_task(name="deliver_notifications_task", queue="comms")
def deliver_notifications_task(notification_ids: List[int]):
    """
    Background task to deliver notifications via WebSocket (real-time) and Email (if requested).
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from comms.models import Notification
    from comms.services.email import create_email_html

    notifications = Notification.objects.filter(id__in=notification_ids).select_related(
        "recipient"
    )
    channel_layer = get_channel_layer()

    for n in notifications:
        # 1. Real-time WebSocket push
        if channel_layer:
            group_name = f"user__{n.recipient_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "notification_activity",
                    "message": {
                        "id": n.id,
                        "subject": n.subject,
                        "message": n.message,
                        "type": n.type,
                        "is_read": n.is_read,
                        "metadata": n.metadata,
                        "expires_at": (
                            n.expires_at.isoformat() if n.expires_at else None
                        ),
                        "created_at": n.created_at.isoformat(),
                    },
                },
            )

        # 2. Email delivery if flagged in metadata
        if n.metadata.get("send_email"):
            image_path = n.metadata.get("image_path")
            html_message = n.metadata.get("html_message") or create_email_html(
                n.subject,
                n.message,
                image_cid="email_image" if image_path else None,
            )
            send_mail_task.delay(
                subject=n.subject,
                message=n.message,
                recipient_list=[n.recipient.email],
                html_message=html_message,
                image_path=image_path,
            )

    return {
        "notification_ids": notification_ids,
        "count": len(notifications),
        "status": "completed",
    }


@shared_task(
    bind=True,
    name="send_broadcast_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_broadcast_task(self, broadcast_id):
    """
    Send a broadcast to multiple recipients across different mediums.
    """
    try:
        result = notification_service.send_broadcast(broadcast_id)
        return result
    except (DatabaseError, ServerError) as e:
        logger.warning(
            "Retryable error for broadcast %s (attempt %s/%s): %s",
            broadcast_id,
            self.request.retries + 1,
            self.max_retries,
            str(e),
        )
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.exception(
            "Fatal error during broadcast %s: %s",
            broadcast_id,
            str(e),
        )
        raise


@shared_task(name="notify_prereg_users_via_whatsapp_task")
def notify_prereg_users_via_whatsapp_task():
    """
    Notify PreRegUser entities via WhatsApp if registration is open.
    """
    import re

    from django.conf import settings

    from identity.models import PreRegUser
    from vmlc.models import FeatureFlag

    if not FeatureFlag.get_bool("candidate_registration"):
        logger.info("Candidate registration is closed. Skipping WhatsApp notification.")
        return

    candidates = PreRegUser.objects.filter(
        interest_type=PreRegUser.InterestType.CANDIDATE
    )

    if not candidates.exists():
        logger.info("No pre-registered candidates found.")
        return

    phones = []
    for candidate in candidates:
        if not candidate.phone:
            continue

        phone = candidate.phone.strip()
        if re.match(r"^(\+234[789][01]\d{8})$", phone):
            phones.append(phone)
        elif re.match(r"^(0[789][01]\d{8})$", phone):
            phones.append("+234" + phone[1:])

    if not phones:
        logger.info("No valid phone numbers found for pre-registered candidates.")
        return

    phones = list(set(phones))

    registration_url = f"{settings.LANDING_BASE_URL}/register"
    message = (
        f"Hi! Registration for the Verboheit Mathematics League Competition is now open. "
        f"You previously expressed interest. Please complete your registration here: {registration_url}"
    )

    result = notification_service.send_bulk_phone_msg(
        body=message, recipients=phones, medium="whatsapp"
    )

    logger.info(
        f"Pre-reg WhatsApp notification task completed. "
        f"Success: {result.get('success_count', 0)}, Failed: {result.get('failure_count', 0)}"
    )


@shared_task(
    bind=True,
    name="notify_user_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def notify_user_task(
    self,
    user_id: int | str,
    subject: str,
    message: str,
    mediums: List[str] | None = None,
    notification_type: str = "info",
    metadata: Dict | None = None,
    expires_at: str | None = None,
):
    """
    Sends a notification to a single user.
    """
    from django.utils.dateparse import parse_datetime

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for notification task.")
        return

    # Parse expires_at if it's a string (ISO format expected)
    parsed_expires_at = None
    if expires_at:
        parsed_expires_at = parse_datetime(expires_at)

    results = notification_service.notify_user(
        user=user,
        subject=subject,
        message=message,
        mediums=mediums,
        notification_type=notification_type,
        metadata=metadata,
        expires_at=parsed_expires_at,
    )

    # Only retry if email was explicitly requested but failed to queue
    if mediums and "email" in [m.lower() for m in mediums]:
        if not results.get("email"):
            raise self.retry(exc="Email medium failed", countdown=60)


@shared_task(name="notify_candidates_about_exam_task")
def notify_candidates_about_exam_task(exam_id, event_type):
    """
    Unified task to notify candidates about exam events (scheduled or started).
    """
    from vmlc.models import Exam

    try:
        exam = Exam.objects.select_related("competition_slot__competition_stage").get(
            id=exam_id
        )
        notification_service.notify_candidates_about_exam(
            exam=exam, event_type=event_type
        )
    except Exam.DoesNotExist:
        logger.error(f"Exam {exam_id} not found for notification task.")


@shared_task(
    bind=True,
    name="send_bulk_sms_task",
    max_retries=12,
    default_retry_delay=3600,  # 1 hour
    queue="comms",
)
def send_bulk_sms_task(
    self,
    body: str,
    recipients: List[str],
    broadcast_log_id: int = None,
    broadcast_id: int = None,
):
    """
    Sends bulk SMS and retries if the balance is insufficient.
    Updates the BroadcastLog status if broadcast_log_id is provided.
    """
    from comms.models import BroadcastLog

    log = None
    if broadcast_log_id:
        try:
            log = BroadcastLog.objects.get(id=broadcast_log_id)
        except BroadcastLog.DoesNotExist:
            logger.error(f"BroadcastLog with id {broadcast_log_id} not found.")
            return

    try:
        estimated_cost = kudi_sms_service.estimate_cost(body, len(recipients))
        balance_resp = kudi_sms_service.get_balance()
        current_balance = kudi_sms_service.parse_balance(
            balance_resp.get("balance", "0")
        )

        logger.info(
            "Kudi SMS Task: Cost ~%s N, Balance: %s N",
            estimated_cost,
            current_balance,
        )

        if current_balance < estimated_cost:
            logger.warning(
                "Insufficient Kudi balance for bulk SMS (log: %s). Retrying in 1 hour.",
                broadcast_log_id,
            )
            if self.request.retries == 0:
                slack_service.send_low_kudi_balance_alert(
                    current_balance, estimated_cost, len(recipients)
                )
            raise self.retry(countdown=3600)

        kudi_recipients = ",".join([r.lstrip("+") for r in recipients])
        response = kudi_sms_service.send_bulk_sms(
            message=body, recipients=kudi_recipients
        )

        is_success = response.get("status") == "success" or response.get("error") == 0

        if is_success:
            logger.info(
                "Bulk SMS via Kudi sent successfully for log %s.", broadcast_log_id
            )
            if log:
                from django.db.models import F
                from django.utils import timezone

                log.status = BroadcastLog.MediumStatus.SENT
                log.sent_at = timezone.now()
                log.recipient_count = len(recipients)
                log.message = f"Successfully sent to {len(recipients)} recipients."
                log.save(
                    update_fields=["status", "sent_at", "recipient_count", "message"]
                )

                # Update broadcast stats and potentially final status
                broadcast = log.broadcast
                broadcast.total_recipients = F("total_recipients") + len(recipients)
                broadcast.save(update_fields=["total_recipients"])
                broadcast.refresh_from_db()

                # Check if this was the last pending medium/role
                if not broadcast.logs.filter(
                    status=BroadcastLog.MediumStatus.PENDING
                ).exists():
                    from comms.services.notification import NotificationService

                    ns = NotificationService()
                    total = broadcast.logs.count()
                    success = broadcast.logs.filter(
                        status=BroadcastLog.MediumStatus.SENT
                    ).count()
                    broadcast.status = ns._resolve_broadcast_status(total, success)
                    if broadcast.status == broadcast.Status.SENT:
                        broadcast.sent_at = timezone.now()
                    broadcast.save(update_fields=["status", "sent_at"])

                    # Invalidate cache
                    from django.core.cache import cache

                    from core.utils.cache import CacheKeys

                    cache.delete(
                        CacheKeys.BROADCAST_DETAIL.format(broadcast_id=broadcast.pk)
                    )
                    cache.delete(CacheKeys.BROADCAST_SUMMARY)
                    logger.info(
                        f"Invalidated broadcast cache for broadcast {broadcast.pk} from task."
                    )

            return {
                "status": "SUCCESS",
                "count": len(recipients),
                "broadcast_id": broadcast_id,
            }
        else:
            message = response.get("message", "Unknown error from Kudi")
            logger.error(
                "Bulk SMS via Kudi failed for log %s: %s. Retrying in 5 mins.",
                broadcast_log_id,
                message,
            )
            if log:
                log.message = f"Kudi API Error: {message}. Retrying..."
                log.save(update_fields=["message"])
            raise self.retry(countdown=300)

    except Retry as e:
        raise e
    except Exception as e:
        logger.exception(
            "Unexpected error in send_bulk_sms_task for log %s.", broadcast_log_id
        )
        if log:
            log.status = BroadcastLog.MediumStatus.FAILED
            log.message = f"Fatal Error: {str(e)}"
            log.save(update_fields=["status", "message"])
        raise


@shared_task(
    bind=True,
    name="send_mail_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_mail_task(
    self, subject, message, recipient_list, html_message=None, image_path=None
):
    """
    Celery task to send an email asynchronously.
    Supports inline image attachment via image_path.
    """
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )

        if image_path:
            import mimetypes

            content_type, _ = mimetypes.guess_type(image_path)
            if content_type is None:
                content_type = "application/octet-stream"
            with open(image_path, "rb") as f:
                email.attach(
                    "image",
                    f.read(),
                    content_type,
                    headers={"Content-ID": "<email_image>"},
                )

        if html_message:
            email.attach_alternative(html_message, "text/html")

        email.send(fail_silently=False)
        logger.info(f"Successfully sent email to {recipient_list}")
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, name="send_system_email_task", max_retries=20)
def send_system_email_task(
    self,
    obj_id=None,
    generated_password=None,
    is_pre_reg=False,
    is_full_reg=False,
    is_public_support=False,
    is_support_notification=False,
):
    """
    Send system emails for user registration and support inquiries.
    """
    from comms.models import PublicSupportRequest
    from comms.services.email import (
        build_pre_registration_email,
        build_registration_welcome_email,
        build_support_confirmation_email,
        build_support_notification_email,
        send_system_email,
    )
    from identity.models import PreRegUser, User

    if not obj_id:
        logger.error("No object ID provided for email task")
        return

    try:
        # Determine object type and build email content
        if is_pre_reg:
            user = PreRegUser.objects.get(pk=obj_id)
            subject, message = build_pre_registration_email(user=user)
            recipient_email = user.email
            email_type = "pre-registration"

        elif is_full_reg:
            user = User.objects.get(pk=obj_id)
            subject, message = build_registration_welcome_email(
                user=user, generated_password=generated_password
            )
            recipient_email = user.email
            email_type = "full registration"

        elif is_public_support:
            inquiry = PublicSupportRequest.objects.get(pk=obj_id)
            subject, message = build_support_confirmation_email(inquiry=inquiry)
            recipient_email = inquiry.email
            email_type = "support inquiry"

        elif is_support_notification:
            inquiry = PublicSupportRequest.objects.get(pk=obj_id)
            subject, message = build_support_notification_email(inquiry=inquiry)
            recipient_email = settings.SUPPORT_EMAIL
            email_type = "support notification"

        else:
            logger.error(f"No valid email type specified for object ID {obj_id}")
            return

    except (
        User.DoesNotExist,
        PreRegUser.DoesNotExist,
        PublicSupportRequest.DoesNotExist,
    ) as e:
        logger.error(f"Object not found for email task: {e}")
        return

    # Send email with retry logic
    try:
        send_system_email(subject, message, recipient_email)
        logger.info(
            f"{email_type.capitalize()} email sent successfully to {recipient_email}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send {email_type} email to {recipient_email} "
            f"(attempt {self.request.retries + 1}/{self.max_retries}): {e}"
        )

        if self.request.retries >= self.max_retries - 1:
            logger.error(
                f"Max retries reached for {email_type} email to {recipient_email}. "
                f"Object ID: {obj_id}"
            )


@shared_task(name="auto_close_in_progress_threads_task", queue="comms")
def auto_close_in_progress_threads_task():
    """
    Periodic task to close helpdesk threads that have been IN_PROGRESS for at least 10 minutes
    where the last message was NOT from the candidate.
    """
    from django.db.models import OuterRef, Subquery
    from django.utils import timezone

    from comms.models import HelpdeskThread, ThreadMessage

    ten_minutes_ago = timezone.now() - timezone.timedelta(minutes=10)
    # Subquery to get the sender_type of the latest message for each thread
    latest_message_sender_type = Subquery(
        ThreadMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at")
        .values("sender_type")[:1]
    )
    # Find threads that are IN_PROGRESS, last message was > 10 mins ago,
    # and last message sender was NOT CANDIDATE.
    threads_to_close = (
        HelpdeskThread.objects.annotate(latest_sender_type=latest_message_sender_type)
        .filter(
            status=HelpdeskThread.Status.IN_PROGRESS,
            last_message_at__lte=ten_minutes_ago,
        )
        .exclude(latest_sender_type=ThreadMessage.SenderType.CANDIDATE)
    )

    count = threads_to_close.count()
    if count > 0:
        # We need to update them. update() doesn't work directly on annotated querysets in some Django versions
        # or might be tricky. Let's get IDs and update.
        thread_ids = list(threads_to_close.values_list("id", flat=True))
        HelpdeskThread.objects.filter(id__in=thread_ids).update(
            status=HelpdeskThread.Status.CLOSED, snoozed_until=None
        )

        logger.info(f"Auto-closed {count} IN_PROGRESS helpdesk threads.")

        # Invalidate stats cache
        from django.core.cache import cache

        from core.utils.cache import CacheKeys

        cache.delete(CacheKeys.STATS_HELPDESK)
        try:
            cache.incr(CacheKeys.HELPDESK_THREADS_VERSION_STAFF)
        except ValueError:
            cache.set(CacheKeys.HELPDESK_THREADS_VERSION_STAFF, 1, timeout=86400)

        # Trigger WebSocket update for staff dashboard
        broadcast_staff_helpdesk_update_task.delay()

    return count


@shared_task(name="cleanup_snoozed_helpdesk_threads_task", queue="comms")
def cleanup_snoozed_helpdesk_threads_task():
    """
    Periodic task to revert SNOOZED helpdesk threads to CLOSED if snoozed_until is in the past.
    """
    from django.utils import timezone

    from comms.models import HelpdeskThread

    now = timezone.now()
    expired_snoozed_threads = HelpdeskThread.objects.filter(
        status=HelpdeskThread.Status.SNOOZED, snoozed_until__lte=now
    )

    count = expired_snoozed_threads.update(
        status=HelpdeskThread.Status.OPEN, snoozed_until=None
    )

    if count > 0:
        logger.info(f"Reverted {count} SNOOZED helpdesk threads to CLOSED.")
        # Invalidate stats cache
        from django.core.cache import cache

        from core.utils.cache import CacheKeys

        cache.delete(CacheKeys.STATS_HELPDESK)
        try:
            cache.incr(CacheKeys.HELPDESK_THREADS_VERSION_STAFF)
        except ValueError:
            cache.set(CacheKeys.HELPDESK_THREADS_VERSION_STAFF, 1, timeout=86400)

        # Trigger WebSocket update for staff dashboard
        broadcast_staff_helpdesk_update_task.delay()

    return count


@shared_task(name="broadcast_staff_helpdesk_update_task", queue="comms")
def broadcast_staff_helpdesk_update_task():
    """
    Broadcasts the latest helpdesk stats and potentially thread updates
    to the staff helpdesk dashboard group.
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from django.core.cache import cache

    from competition.utils.stats import get_helpdesk_stats_cached
    from core.utils.cache import CacheKeys

    # Invalidate stats cache to get fresh data
    cache.delete(CacheKeys.STATS_HELPDESK)
    stats = get_helpdesk_stats_cached()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "staff_helpdesk_dashboard",
        {
            "type": "helpdesk.update",
            "data": {
                "stats": stats,
                # We can also signal the client to refresh its thread list
                "refresh_threads": True,
            },
        },
    )


@shared_task(bind=True, name="send_welcome_mail_task", max_retries=20)
def send_welcome_mail_task(
    self, user_id=None, generated_password=None, is_pre_reg=False
):
    """Send welcome email to newly registered user."""
    from celery.exceptions import Retry

    from comms.services.email import send_welcome_email
    from identity.models import PreRegUser, User

    try:
        if is_pre_reg:
            user = PreRegUser.objects.get(pk=user_id)
        else:
            user = User.objects.get(pk=user_id)
    except (PreRegUser.DoesNotExist, User.DoesNotExist):
        logger.error(f"User with id {user_id} does not exist.")
        return

    try:
        send_welcome_email(user, generated_password)
        logger.info(f"Welcome email sent to {user.email}")
    except Retry:
        raise
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")
        if self.request.retries >= 3:
            logger.error(f"Max retries reached for user {user_id}. Giving up.")
            return

        raise self.retry(exc=e, countdown=60)


@shared_task(
    bind=True,
    name="send_otp_on_registration_task",
    max_retries=3,
    default_retry_delay=60,
    queue="comms",
)
def send_otp_on_registration_task(self, user_id):
    """
    Celery task to send OTP to user on registration.
    """
    from celery.exceptions import Retry

    from core.utils.auth import send_otp_to_email
    from identity.models import User

    try:
        user = User.objects.get(pk=user_id)
        send_otp_to_email(user)
        logger.info(f"Successfully sent OTP to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
    except Retry:
        raise
    except Exception as exc:
        logger.error(f"Failed to send OTP to user with id {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="helpdesk_escalation_task", queue="comms")
def helpdesk_escalation_task(message_id):
    """
    Check if a support message from a candidate has been replied to within 2 minutes.
    If not, escalate to admins and managers.
    """
    from django.utils import timezone

    from comms.models import ThreadMessage
    from vmlc.models import Exam, ExamAccess

    try:
        message = ThreadMessage.objects.select_related("thread__candidate").get(
            id=message_id
        )
        thread = message.thread
        candidate = thread.candidate

        # Get the absolute latest message in this thread
        latest_message = thread.messages.order_by("-created_at").first()
        exam_title = None
        # Only proceed if the latest message is still from a candidate
        if (
            latest_message
            and latest_message.sender_type == ThreadMessage.SenderType.CANDIDATE
        ):
            exam_id = message.metadata.get("exam_id") if message.metadata else None
            is_ongoing_exam = False

            if exam_id:
                try:
                    # Check for an active ExamAccess record for this candidate and exam
                    exam_access = ExamAccess.objects.get(
                        candidate=candidate,
                        exam_id=exam_id,
                        status=ExamAccess.Status.STARTED,
                        deadline__gt=timezone.now(),
                    )
                    # Additionally, check if the parent Exam itself is considered 'ONGOING'
                    # The Exam.status property handles scheduled_date and open_duration_hours logic
                    exam = exam_access.exam
                    exam_title = exam.get_title()
                    if exam.status == Exam.Status.ONGOING:
                        is_ongoing_exam = True
                        logger.info(
                            f"Exam {exam_id} is ongoing for candidate {candidate.user.email}."
                        )
                    else:
                        logger.info(
                            f"Exam {exam_id} is NOT ongoing for candidate {candidate.user.email} (status: {exam.status})."
                        )

                except ExamAccess.DoesNotExist:
                    logger.info(
                        f"No active ExamAccess found for candidate {candidate.user.email} for exam {exam_id}."
                    )
                except Exam.DoesNotExist:
                    logger.warning(
                        f"Exam {exam_id} referenced in metadata not found for candidate {candidate.user.email}."
                    )
                except Exception as e:
                    logger.exception(
                        f"Error checking ongoing exam status for candidate {candidate.user.email}, exam {exam_id}: {e}"
                    )

            if not exam_id or not is_ongoing_exam:
                logger.info(
                    f"Skipping helpdesk escalation for thread {thread.id}. No exam_id in metadata or exam not ongoing."
                )
                return

            # If we reach here, it means the candidate is in an ongoing exam and
            # the latest message is still from them. Proceed with escalation.
            logger.info(
                f"Escalating helpdesk thread {thread.id} - candidate in ongoing exam, no staff reply after 2 minutes."
            )
            slack_service.send_support_escalation_alert(thread, latest_message)

            subject = f"URGENT: Helpdesk Escalation - {thread.candidate.user.get_full_name()} - {exam_title}"
            body = (
                f"Helpdesk thread for {thread.candidate.user.get_full_name()} ({thread.candidate.user.email}) "
                f"has a new message during an ongoing exam and has been waiting for a reply for over 2 minutes.\n\n"
                f"Exam ID: {exam_id}\n\n"
                f"Latest Message: \n\n{latest_message.text}\n\n"
                f"Please review and respond immediately."
            )

            from comms.models import Broadcast

            broadcast = Broadcast.objects.create(
                subject=subject,
                message=body,
                mediums=[Broadcast.Medium.EMAIL],
                target_roles={"staff": ["moderator", "admin"]},
            )

            notification_service.send_broadcast(broadcast_id=broadcast.id)

    except ThreadMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found for escalation task.")
    except Exception as e:
        logger.exception(f"Error in helpdesk_escalation_task: {e}")


@shared_task(name="notify_staff_about_exam_event_task", queue="comms")
def notify_staff_about_exam_event_task(exam_id: uuid.UUID, event_type: str):
    """
    Notify staff members about exam status changes.
    """
    from comms.services.email import create_email_html
    from identity.models import Staff
    from vmlc.models import Exam

    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        logger.error(f"Exam {exam_id} not found for staff notification task.")
        return

    if event_type not in ["ongoing", "concluded", "cancelled"]:
        logger.warning(
            f"Invalid event_type '{event_type}' for exam {exam_id} staff notification."
        )
        return

    # Notify via Slack
    slack_service.send_exam_status_notification(exam, event_type)

    # Notify via Email
    staff_to_notify = Staff.objects.filter(
        role__in=[Staff.Roles.ADMIN, Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN],
        user__is_active=True,
    ).select_related("user")

    if not staff_to_notify.exists():
        logger.info(
            f"No staff found to notify for exam {exam_id} event '{event_type}'."
        )
        return

    app_environment = settings.APP_ENVIRONMENT
    subject = f"{app_environment.title() if app_environment != 'production' else ''} Exam Update: {exam.get_title()} is now {event_type.capitalize()}"
    message = (
        f"This is an automated notification to inform you that the exam "
        f"'{exam.get_title()}' has been marked as '{event_type.capitalize()}' "
        f"in {app_environment}."
    )

    for staff in staff_to_notify:
        notification_service.notify_user(
            user=staff.user,
            subject=subject,
            message=message,
            mediums=["email"],
            notification_type="alert",
            metadata={
                "html_message": create_email_html(
                    subject=subject,
                    message=message,
                )
            },
        )

    logger.info(
        f"Sent '{event_type}' notifications for exam {exam_id} to {staff_to_notify.count()} staff."
    )
```

---

## `comms/models.py`

```python
import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from identity.models import Candidate, Staff

# TODO: move to [core] app
phone_regex = RegexValidator(
    regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
    message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
)


# ---------------------------------------------------------------------------
# Public / Unauthenticated
# ---------------------------------------------------------------------------
class PublicSupportRequest(models.Model):
    """
    Captures support inquiries submitted by unauthenticated (public) users,
    from the Verboheit landing page (https://verboheit.org/support-us).

    Intended for sponsorship, partnership, media, and general enquiries where
    the submitter does not have a platform account.
    """

    class Type(models.TextChoices):
        SPONSORSHIP = "sponsorship", "Sponsorship"
        PARTNERSHIP = "partnership", "Partnership"
        MEDIA_SUPPORT = "media_publiciy", "Media/Publicity"
        OTHER = "other", "Other"

    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255, blank=True)
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Nigerian phone number.",
        blank=True,
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    message = models.TextField(help_text="Message from the user.")
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Public Support Request"
        verbose_name_plural = "Public Support Requests"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.type}) - {self.organization}"


# ---------------------------------------------------------------------------
# Helpdesk Threading
# ---------------------------------------------------------------------------
class HelpdeskThread(models.Model):
    """
    Represents an authenticated helpdesk conversation between a candidate and staff.

    Threads are persistent and unique per candidate (1:1).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        CLOSED = "closed", "Closed"
        SNOOZED = "snoozed", "Snoozed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    candidate = models.OneToOneField(
        "identity.Candidate",
        on_delete=models.CASCADE,
        related_name="helpdesk_thread",
        help_text="Candidate who owns this helpdesk thread.",
    )
    assigned_staff = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_helpdesk_threads",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    snoozed_until = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Helpdesk Thread"
        verbose_name_plural = "Helpdesk Threads"
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["last_message_at"]),
            models.Index(fields=["assigned_staff"]),
        ]

    def __str__(self) -> str:
        return f"Helpdesk Thread: {self.candidate.user.email} ({self.status})"

    def refresh_status(self) -> None:
        """
        Reverts status to CLOSED if SNOOZED and snoozed_until is in the past.
        """
        if (
            self.status == self.Status.SNOOZED
            and self.snoozed_until
            and self.snoozed_until < timezone.now()
        ):
            self.status = self.Status.CLOSED
            self.snoozed_until = None
            self.save(update_fields=["status", "snoozed_until"])


class ThreadMessage(models.Model):
    """
    An individual message within a HelpdeskThread.
    """

    class SenderType(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    thread = models.ForeignKey(
        HelpdeskThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_helpdesk_messages",
    )
    sender_type = models.CharField(
        max_length=20,
        choices=SenderType.choices,
        default=SenderType.SYSTEM,
    )
    text = models.TextField()
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def __str__(self) -> str:
        actor = self.sender.email if self.sender else "System"
        return f"{actor} ({self.sender_type}) - {self.created_at}"

    def save(self, *args, **kwargs) -> None:
        """
        Updates the parent thread's last_message_at field.
        """
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            HelpdeskThread.objects.filter(pk=self.thread_id).update(
                last_message_at=self.created_at
            )


class MessageRead(models.Model):
    """
    Tracks message read status per user.
    """

    message = models.ForeignKey(
        "ThreadMessage",
        on_delete=models.CASCADE,
        related_name="reads",
    )
    user = models.ForeignKey("identity.User", on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")
        indexes = [
            models.Index(fields=["user"]),
        ]


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------
class Broadcast(models.Model):
    """
    Represents a mass message dispatched to one or more target role groups
    across one or more delivery mediums (Email, SMS, Platform, WhatsApp).

    The target_roles JSON field specifies which staff or candidate roles
    should receive the message. Validation is enforced via clean().

    Broadcasts are executed asynchronously via Celery; task_id stores the
    Celery task identifier for monitoring. BroadcastLog records are created
    per medium-role combination to track individual delivery outcomes.
    """

    class Medium(models.TextChoices):
        PLATFORM = "platform", "Platform"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        FAILED_TO_QUEUE = "failed_to_queue", "Failed to Queue"
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partial Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.AutoField(primary_key=True)
    created_by = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="broadcasts",
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    sms_message = models.TextField(
        blank=True,
        null=True,
        help_text="Optional shorter message for SMS/WhatsApp. If blank, the main message is condensed automatically.",
    )
    mediums = ArrayField(
        models.CharField(max_length=20, choices=Medium.choices),
        default=list,
        help_text="Ordered list of delivery mediums (Email, SMS, Platform, WhatsApp).",
    )
    target_roles = models.JSONField(
        default=dict,
        help_text=(
            "Dictionary of role groups to target. "
            "Valid structure: "
            '{"staff": ["volunteer", "moderator", ...], "candidate": ["screening", "league", ...]}'
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Overall broadcast delivery status.",
    )
    total_recipients = models.IntegerField(
        default=0,
        help_text="Total number of unique users targeted by this broadcast.",
    )
    scheduled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Future date/time when this broadcast should be dispatched. If null, sent immediately.",
    )
    last_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp of the most recent delivery attempt.",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp when the broadcast successfully completed all delivery paths.",
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this broadcast has been retried after partial or total failure.",
    )
    task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Celery task ID for async tracking and potential cancellation.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Broadcast"
        verbose_name_plural = "Broadcasts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        mediums = ", ".join(self.mediums)
        target_parts = []
        if self.target_roles.get("staff"):
            target_parts.append(f"Staff: {', '.join(self.target_roles['staff'])}")
        if self.target_roles.get("candidate"):
            target_parts.append(
                f"Candidate: {', '.join(self.target_roles['candidate'])}"
            )
        target_roles = " | ".join(target_parts) if target_parts else "No targets"
        return f"{self.subject} [{mediums}] -> [{target_roles}] ({self.status})"

    @property
    def is_scheduled(self) -> bool:
        """Checks if the broadcast is scheduled for the future."""
        return self.scheduled_at is not None and self.scheduled_at > timezone.now()

    @property
    def is_sent(self) -> bool:
        """Checks if the broadcast has completed sending."""
        return self.status in [self.Status.SENT, self.Status.PARTIAL]

    @property
    def duration(self):
        """Calculates the time taken from the first attempt to completion."""
        if self.last_attempt and self.sent_at:
            return self.sent_at - self.last_attempt
        return None

    def cancel(self) -> bool:
        """
        Attempts to cancel a pending or scheduled broadcast.
        Returns True if cancelled, False if already in progress or sent.
        """
        if self.status in [self.Status.PENDING, self.Status.FAILED_TO_QUEUE]:
            self.status = self.Status.CANCELLED
            self.save(update_fields=["status"])
            return True
        return False

    def clean(self) -> None:
        """
        Validates the structure and contents of target_roles.

        Raises ValidationError if:
        - target_roles is not a dict.
        - Any keys other than 'staff' or 'candidate' are present.
        - Any role values are not valid choices for their respective model.
        """
        from django.core.exceptions import ValidationError

        if not isinstance(self.target_roles, dict):
            raise ValidationError("target_roles must be a dictionary.")

        valid_keys = {"staff", "candidate"}
        invalid_keys = set(self.target_roles.keys()) - valid_keys
        if invalid_keys:
            raise ValidationError(f"Invalid keys in target_roles: {invalid_keys}")

        if "staff" in self.target_roles:
            valid_staff_roles = {choice[0] for choice in Staff.Roles.choices}
            invalid = set(self.target_roles["staff"]) - valid_staff_roles
            if invalid:
                raise ValidationError(f"Invalid staff roles: {invalid}")

        if "candidate" in self.target_roles:
            valid_candidate_roles = {choice[0] for choice in Candidate.Roles.choices}
            invalid = set(self.target_roles["candidate"]) - valid_candidate_roles
            if invalid:
                raise ValidationError(f"Invalid candidate roles: {invalid}")


class BroadcastLog(models.Model):
    """
    Records the delivery outcome for a single medium-role combination within
    a Broadcast.

    For example, a broadcast targeting staff:volunteer via both Email and
    SMS will produce two BroadcastLog entries. This granularity allows
    partial retries and precise failure attribution.
    """

    class MediumStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    COMBINED_ROLE_CHOICES = list(Candidate.Roles.choices) + list(Staff.Roles.choices)

    id = models.AutoField(primary_key=True)
    broadcast = models.ForeignKey(
        Broadcast,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    medium = models.CharField(max_length=20, choices=Broadcast.Medium.choices)
    target_role = models.CharField(max_length=20, choices=COMBINED_ROLE_CHOICES)
    role_type = models.CharField(
        max_length=10,
        default="candidate",
        choices=[("staff", "Staff"), ("candidate", "Candidate")],
        help_text="Whether this log entry targets a staff or candidate role.",
    )
    status = models.CharField(
        max_length=20,
        choices=MediumStatus.choices,
        default=MediumStatus.PENDING,
    )
    recipient_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of recipients within this specific medium-role slice.",
    )
    message = models.TextField(blank=True, help_text="Error or status message.")
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp when this specific delivery path finished.",
    )
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Broadcast Log"
        verbose_name_plural = "Broadcast Logs"
        ordering = ["-attempted_at"]

    def __str__(self) -> str:
        return (
            f"{self.broadcast.subject} "
            f"[{self.medium} -> {self.role_type}:{self.target_role}] "
            f"{self.status} ({self.recipient_count} sent)"
        )

    @property
    def duration(self):
        """Time taken for this specific log entry to complete."""
        if self.attempted_at and self.sent_at:
            return self.sent_at - self.attempted_at
        return None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class Notification(models.Model):
    """
    A real-time, in-platform notification delivered to a specific user.

    Notifications are created by the notification service and pushed
    immediately to the recipient's WebSocket group (user__<id>) via
    Django Channels. They persist in the database to populate notification
    history on the dashboard.

    expires_at can be set to automatically suppress stale notifications
    in the UI. is_archived provides soft-removal without data loss.
    """

    class Type(models.TextChoices):
        ALERT = "alert", "Alert"
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    recipient = models.ForeignKey(
        "identity.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    subject = models.CharField(max_length=100)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.ALERT,
        db_index=True,
    )
    link = models.URLField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Notification for {self.recipient.email}: {self.subject}"


# ---------------------------------------------------------------------------
# System / Infrastructure
# ---------------------------------------------------------------------------
class BackupLog(models.Model):
    """
    Records the outcome of a scheduled database backup operation.

    Populated by the backup pipeline and surfaced to engineers via Slack
    alerts on failure. SUCCESS_AFTER_RETRY distinguishes recoveries from
    clean first-attempt successes for monitoring purposes.
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FIRST_FAILURE = "first_failure", "First Failure"
        FINAL_FAILURE = "final_failure", "Final Failure"
        SUCCESS_AFTER_RETRY = "success_after_retry", "Success After Retry"

    class Environment(models.TextChoices):
        PRODUCTION = "prod", "Production"
        STAGING = "staging", "Staging"

    status = models.CharField(max_length=30, choices=Status.choices)
    environment = models.CharField(max_length=10, choices=Environment.choices)
    timestamp = models.DateTimeField()
    backup_filename = models.CharField(max_length=255)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Backup Log"
        verbose_name_plural = "Backup Logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"BackupLog [{self.environment}] {self.timestamp}: {self.status}"
```

---

## `config/celery.py`

```python
import os
import warnings

from celery import Celery
from celery.schedules import crontab
from django.apps import apps

warnings.filterwarnings("ignore", category=UserWarning, module="pycparser")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker_dev")

app = Celery("vmlc-backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])

app.conf.beat_schedule = {
    "notify-prereg-users-every-4-days": {
        "task": "notify_prereg_users_via_whatsapp_task",
        "schedule": crontab(minute=0, hour=10, day_of_month="*/4"),
    },
    "generate-stats-overview-every-5-minutes": {
        "task": "generate_stats_overview_task",
        "schedule": crontab(minute="*/5"),
    },
    "check-exam-status-transitions-every-minute": {
        "task": "check_exam_status_transitions_task",
        "schedule": crontab(minute="*"),
    },
    "cleanup-snoozed-helpdesk-threads-every-5-minutes": {
        "task": "cleanup_snoozed_helpdesk_threads_task",
        "schedule": crontab(minute="*/5"),
    },
    "auto-close-in-progress-threads-every-10-minutes": {
        "task": "auto_close_in_progress_threads_task",
        "schedule": crontab(minute="*/10"),
    },
}
```
