"""
This module defines the database models for the VMLC backend application.
"""

import uuid
import logging
from datetime import timedelta

from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone

from competition.models import Stage
from identity.validators import validate_image
from core.storage_backends import PrivateMediaStorage, PublicMediaStorage

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
            from comms.tasks import notify_staff_about_exam_event_task
            from django.db import transaction

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


class LeaderboardSnapshot(models.Model):  # pylint: disable=too-few-public-methods
    """Model for a snapshot of the leaderboard."""

    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    published_by = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaderboard_snapshots",
    )

    class Meta:
        """Meta options for the LeaderboardSnapshot model."""

        ordering = ["-created_at"]


class CandidateExamResultSnapshot(
    models.Model
):  # pylint: disable=too-few-public-methods
    """Model for a snapshot of a candidate's result."""

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    data = models.JSONField()

    published_by = models.ForeignKey(
        "identity.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_exam_result_snapshots",
    )

    class Meta:
        """Meta options for the CandidateExamResultSnapshot model."""

        ordering = ["-created_at"]


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
