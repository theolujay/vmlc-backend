"""
This module defines the database models for the VMLC backend application.
"""

import uuid
from datetime import timedelta

from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone

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

class SupportInquiry(models.Model):
    """Model for support inquiries and conversations"""

    class SupportType(models.TextChoices):
        """Type of support inquires"""

        SPONSORSHIP = "sponsorship", "Sponsorship"
        PARTNERSHIP = "partnership", "Partnership"
        MEDIA_SUPPORT = "media_publiciy", "Media/Publicity"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        """Status of the inquiry"""

        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    user = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_inquiries",
        help_text="Authenticated user who submitted the inquiry, if applicable.",
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Nigerian phone number",
        blank=True,
    )
    support_type = models.CharField(
        max_length=20,
        choices=SupportType.choices,
    )
    message = models.TextField(help_text="Initial message from the user.")
    organization = models.CharField(
        max_length=255,
        blank=True,
    )
    consent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Return a string representation of the support inquiry"""

        return f"{self.full_name} ({self.support_type}) - {self.status}"

    class Meta:
        verbose_name = "Support Inquiry"
        verbose_name_plural = "Support Inquiries"
        ordering = ["-created_at"]


class SupportMessage(models.Model):
    """Immutable message within a support conversation"""

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    inquiry = models.ForeignKey(
        SupportInquiry,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_support_messages",
    )
    sender_profile = models.CharField(
        max_length=50,
        help_text="The role of the sender at the time the message was sent.",
    )
    text = models.TextField()
    is_read_by_staff = models.BooleanField(default=False, db_index=True)
    is_read_by_user = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        """Meta options for the SupportMessage model."""

        ordering = ["created_at"]
        verbose_name = "Support Message"
        verbose_name_plural = "Support Messages"

    def __str__(self):
        return f"Message from {self.sender_profile} on {self.created_at}"

    def save(self, *args, **kwargs):
        if self.pk:
            # Enforce immutability for existing messages
            return
        super().save(*args, **kwargs)

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
    option_a = models.CharField(max_length=255, blank=True)
    option_b = models.CharField(max_length=255, blank=True)
    option_c = models.CharField(max_length=255, blank=True)
    option_d = models.CharField(max_length=255, blank=True)
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

    def get_related_exams(self):
        """Get a list of exams a question has been added to."""
        exams = self.exams.values(
            "id", "title", "description", "stage", "scheduled_date"
        )

        return {"count": self.exams.count(), "list": list(exams)}

    def __str__(self):
        """Return a string representation of the question."""
        return f"Q{self.id}: {self.text[:50]}..."


class Exam(models.Model):
    """
    Represents a collection of questions scheduled at a specific date for a stage of competition.
    """

    # class Stages(models.TextChoices):
    #     """Stages of an exam."""

    #     SCREENING = "screening", "Screening"
    #     LEAGUE = "league", "League"

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
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="exams_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        "identity.Staff",
        blank=True,
        null=True,
        related_name="exams_updated",
        on_delete=models.SET_NULL,
    )
    open_duration_hours = models.PositiveIntegerField(default=12)
    countdown_minutes = models.PositiveIntegerField(default=60)
    scheduled_date = models.DateTimeField(blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    questions = models.ManyToManyField(Question, blank=True, related_name="exams")
    updated_at = models.DateTimeField(auto_now=True)

    # def __str__(self):
    #     """Return a string representation of the exam."""
    #     if self.stage == self.Stages.SCREENING:
    #         return f"Screening {self.round}: {self.title} ({self.id})"
    #     return f"League {self.round}: {self.title} ({self.id})"

    # @property
    # def stage_display(self):
    #     """Returns a formatted stage display like 'screening_1' or 'league_2'"""
    #     return f"{self.stage}_{self.round}"

    @classmethod
    def active_exams(cls):
        """
        Returns only exams marked as active.
        """
        return cls.objects.filter(is_active=True)

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
        end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
        return self.scheduled_date <= now <= end_time

    @property
    def status(self):
        """
        Returns the current status of the exam.

        Status flow:
        - DRAFT: No scheduled date set
        - CANCELLED: Exam was deactivated (is_active=False)
        - SCHEDULED: Has a future scheduled date
        - ONGOING: Currently open for taking
        - CONCLUDED: Past the end time
        """
        if self.scheduled_date is None or self.open_duration_hours is None:
            return self.Status.DRAFT

        if not self.is_active:
            return self.Status.CANCELLED

        now = timezone.now()
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
            end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
            if end_time < now:
                return end_time
        return None

    def get_question_count(self):
        """
        Returns the number of questions in the exam.
        """
        return self.questions.count()

    def get_average_score(self):
        """
        Calculates the average score for all submissions tied to this exam.
        """
        return self.results.aggregate(avg_score=Avg("score"))["avg_score"]

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
    recorded_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
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
        CandidateExamResult, related_name="answers", on_delete=models.PROTECT
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


class CandidateExamResultSnapshot(models.Model):  # pylint: disable=too-few-public-methods
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
        PENDING = "pending", "Pending"          # provisioned but not opened
        ISSUED = "issued", "Issued"              # URL generated
        STARTED = "started", "Started"
        SUBMITTED = "submitted", "Submitted"
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
        max_length=20,
        choices=Facilitator.choices,
    )

    access_url = models.URLField(
        null=True,
        blank=True,
        help_text="Candidate-specific exam URL on the facilitator."
    )
    passcode = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Opaque passcode or token embedded in the URL."
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    facilitator_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw request/response metadata exchanged with facilitator."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "candidate"],
                name="unique_exam_access_per_candidate"
            ),
        ]
        indexes = [
            models.Index(fields=["exam", "status"]),
            models.Index(fields=["candidate", "status"]),
        ]
