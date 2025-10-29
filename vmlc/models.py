
"""
This module defines the database models for the VMLC backend application.
"""

import os
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Avg, Count, F, Max, Min, Q, Sum, Window
from django.db.models.functions import Rank
from django.utils import timezone

from .storage_backends import PrivateMediaStorage, PublicMediaStorage


class FeatureFlag(models.Model):
    """Feature flag model."""

    key = models.CharField(max_length=50, unique=True)
    value = models.BooleanField(default=True)

    @classmethod
    def get_bool(cls, key, default=True):
        """Get the boolean value of a feature flag."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    def __str__(self):
        """Return a string representation of the feature flag."""
        return f"{self.key}: {'Enabled' if self.value else 'Disabled'}"


class CustomUserManager(BaseUserManager):
    """Custom user manager for the User model."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)

        if "username" not in extra_fields:
            extra_fields["username"] = email
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model."""

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False)
    phone_regex = RegexValidator(
        regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
        message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Nigerian phone number for SMS notifications and contact",
    )
    username = models.CharField(max_length=255, unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()


def validate_id_card_file(value):
    """Validate that the uploaded file is an image or PDF"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported file extension. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 2 * 1024 * 1024:
        raise ValidationError("File size cannot exceed 2MB.")


def validate_face_id(
    value,
):  # TODO: swap and reconfigure for `avatar` and `face_id`
    """Validate face ID file"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported image format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Image size cannot exceed 5MB.")


def validate_document_file(value):
    """Validate verification document file"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported document format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 2 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 2MB.")


class UserVerification(models.Model):
    """Model for user verification data."""

    user = models.OneToOneField(
        "User", on_delete=models.CASCADE, related_name="verification"
    )
    is_pending = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    face_id = models.ImageField(
        upload_to="face_ids/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
        validators=[validate_face_id],
    )
    id_card = models.FileField(
        upload_to="id_cards/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
        validators=[validate_id_card_file],
    )
    verification_document = models.FileField(
        upload_to="verification_docs/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
        validators=[validate_document_file],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Return a string representation of the user verification."""
        return f"Verification for {self.user.get_full_name()}"

    # Helper methods to get secure URLs
    def get_face_id_url(self):
        """Returns public URL for face ID (no expiration)"""
        if self.face_id:
            return self.face_id.url
        return None

    def get_secure_id_card_url(self):
        """Returns a signed URL for ID card that expires in 1 hour"""
        if self.id_card:
            return self.id_card.url  # Automatically signed by PrivateMediaStorage
        return None

    def get_secure_verification_doc_url(self):
        """Returns a signed URL for verification document that expires in 1 hour"""
        if self.verification_document:
            return (
                self.verification_document.url
            )  # Automatically signed by PrivateMediaStorage
        return None

    class Meta:
        """Meta options for the UserVerification model."""

        verbose_name = "User Verification"


class EmailOTP(models.Model):  # pylint: disable=too-few-public-methods
    """One-time password for email verification"""

    user = models.ForeignKey("User", on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        """Check if the OTP has expired"""
        return timezone.now() > self.expires_at

    def __str__(self):
        """Return a string representation of the OTP."""
        return f"OTP for {self.user.email}"


class Staff(models.Model):  # pylint: disable=too-many-lines
    """
    Administrative user with a specific role for managing candidates, exams, and scores.
    """

    class Roles(models.TextChoices):
        """Roles for staff members."""

        SUPERADMIN = "superadmin", "Superadmin"
        MANAGER = "manager", "Manager"
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        SPONSOR = "sponsor", "Sponsor"
        VOLUNTEER = "volunteer", "Volunteer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verification_override = None

    user = models.OneToOneField(
        User, primary_key=True, on_delete=models.CASCADE, related_name="staff_profile"
    )
    occupation = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="invited_staff"
    )
    updated_at = models.DateTimeField(auto_now=True)
    role = models.CharField(
        max_length=20, choices=Roles.choices, default=Roles.VOLUNTEER, db_index=True
    )

    @property
    def is_active(self):
        """Reference the user's is_active status"""
        return self.user.is_active

    @property
    def face_id(self):
        """Get face ID from UserVerification with error handling"""
        try:
            return self.user.verification.face_id
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def id_card(self):
        """Get ID card from UserVerification with error handling"""
        try:
            return self.user.verification.id_card
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def verification_document(self):
        """
        Get verification document from UserVerification with error handling
        """
        try:
            return self.user.verification.verification_document
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def is_verified(self):
        """Check if user has verification and is verified"""
        if self._verification_override is not None:
            return self._verification_override
        return hasattr(self.user, "verification") and self.user.verification.is_verified

    def set_verification_override(self, value):
        """Manually override verification status"""
        self._verification_override = value

    def clear_verification_override(self):
        """Remove override, return to normal verification checking"""
        self._verification_override = None

    def __str__(self):
        """Return a string representation of the staff member."""
        return f"{self.user.get_full_name()} ({self.role})"


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
        Staff,
        blank=True,
        null=True,
        related_name="questions_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        Staff,
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
            'id', 'title', 'description', 'stage', 'scheduled_date'
        )
        
        return {
            "count": self.exams.count(),
            "list": list(exams)
        }

    def __str__(self):
        """Return a string representation of the question."""
        return f"Q{self.id}: {self.text[:50]}..."


class Exam(models.Model):
    """
    Represents a collection of questions scheduled at a specific date for a stage of competition.
    """

    class Stages(models.TextChoices):
        """Stages of an exam."""

        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"
        
    class Status(models.TextChoices):
        """Statuses for an exam."""

        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        ONGOING = "ongoing", "Ongoing"
        CONCLUDED = "concluded", "Concluded"
        CANCELLED = "cancelled", "Cancelled"

    stage = models.CharField(
        max_length=20, choices=Stages.choices, default=Stages.LEAGUE, db_index=True
    )
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    scheduled_date = models.DateTimeField(blank=True, null=True, db_index=True)
    open_duration_hours = models.PositiveIntegerField(default=12)
    countdown_minutes = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    questions = models.ManyToManyField(Question, blank=True, related_name="exams")
    created_by = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="exams_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        Staff,
        blank=True,
        null=True,
        related_name="exams_updated",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        """Return a string representation of the exam."""
        return f"{self.title} ({self.id})"

    @classmethod
    def active_exams(cls):
        """
        Returns only exams marked as active.
        """
        return cls.objects.filter(is_active=True)

    @property
    def is_currently_open(self):
        """
        Exam is open only if it's active, and either:
        - scheduled_date is None (always open)
        - or current time is within open window
        """
        if not self.is_active:
            return False
        if self.scheduled_date is None:
            return True
        if self.scheduled_date:
            now = timezone.now()
            end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
            return self.scheduled_date <= now <= end_time
        else:
            return False

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
        # Check cancellation first - it overrides everything except draft
        if not self.is_active:
            # Unless it's never been scheduled, it's cancelled
            if self.scheduled_date is None:
                return self.Status.DRAFT
            return self.Status.CANCELLED
        
        # If no scheduled date, it's still being drafted
        if self.scheduled_date is None:
            return self.Status.DRAFT
        
        # If no duration set, can't determine time-based status
        if self.open_duration_hours is None:
            return self.Status.DRAFT
        
        now = timezone.now()
        
        # Calculate the conclusion time
        conclusion_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
        
        # Check time-based statuses
        if now < self.scheduled_date:
            return self.Status.SCHEDULED
        elif now < conclusion_time:
            return self.Status.ONGOING
        else:
            return self.Status.CONCLUDED
            
    @property
    def concluded_at(self):
        now = timezone.now()
        end_time = self.scheduled_date + timedelta(hours=self.open_duration_hours)
        if self.scheduled_date and self.open_duration_hours and self.scheduled_date:
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
        return self.scores.aggregate(avg_score=Avg("score"))["avg_score"]


class CandidateManager(models.Manager):
    """
    Custom manager for the Candidate model.
    """

    def with_scores(self):
        """
        Annotate candidates with total, average, and count of exam scores,
        excluding scores from exams at the 'screening' stage.
        """
        return self.annotate(
            total_score=Sum(
                "scores__score", filter=Q(scores__exam__stage=Exam.Stages.LEAGUE)
            ),
            average_score=Avg(
                "scores__score", filter=Q(scores__exam__stage=Exam.Stages.LEAGUE)
            ),
            exams_taken=Count(
                "scores",
                filter=Q(scores__exam__stage=Exam.Stages.LEAGUE),
                distinct=True,
            ),
        )

    def with_complete_data(self):
        """
        Annotate candidates with scores and optimize related data fetching.
        """
        return (
            self.with_scores()
            .prefetch_related("scores__exam", "scores__score_submitted_by__user")
            .select_related("user")
        )

    def active(self):
        """
        Get only active candidates
        """
        return self.filter(user__is_active=True)

    def by_role(self, role):
        """
        Get active candidates by role
        """
        return self.filter(role=role, user__is_active=True)


class Candidate(models.Model):
    """
    Represents a student or participant in the exam system.
    Linked to a User, assigned a role, and tracks their profile and score history.
    """

    class Roles(models.TextChoices):
        """
        Roles for a candidate."""

        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"
        FINAL = "final", "Final"
        WINNER = "winner", "Winner"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._verification_override = None

    user = models.OneToOneField(
        User,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    school = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    role = models.CharField(
        max_length=15, choices=Roles.choices, default=Roles.SCREENING, db_index=True
    )

    objects = CandidateManager()  # type: ignore

    @property
    def is_active(self):
        """Reference the user's is_active status"""
        return self.user.is_active

    @property
    def face_id(self):
        """Get face ID from UserVerification with error handling"""
        try:
            return self.user.verification.face_id
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def id_card(self):
        """
        Get ID card from UserVerification with error handling
        """
        try:
            return self.user.verification.id_card
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def verification_document(self):
        """
        Get verification document from UserVerification with error handling
        """
        try:
            return self.user.verification.verification_document
        except (
            AttributeError,
            UserVerification.DoesNotExist,
        ):
            return None

    @property
    def is_verified(self):
        """Check if user has verification and is verified"""
        if self._verification_override is not None:
            return self._verification_override
        return hasattr(self.user, "verification") and self.user.verification.is_verified

    def set_verification_override(self, value):
        """Manually override verification status"""
        self._verification_override = value

    def clear_verification_override(self):
        """Remove override, return to normal verification checking"""
        self._verification_override = None

    @property
    def score_data(self):
        """
        Returns score summary (total and average) if annotated via `with_scores()`.
        """
        if hasattr(self, "total_score"):
            return {
                "total_score": float(self.total_score or 0),
                "average_score": float(self.average_score or 0),
            }
        return None

    @property
    def is_winner(self):
        """
        Returns True if candidate has 'winner' role.
        """
        return self.role == self.Roles.WINNER

    def __str__(self):
        """Return a string representation of the candidate."""
        return f"{self.user.get_full_name()} - {self.school}"

    @classmethod
    def active_candidates(cls):
        """
        Returns all currently active candidates.
        """
        return cls.objects.filter(user__is_active=True)

    @classmethod
    def candidates_by_role(cls, role):
        """
        Returns active candidates filtered by role.
        """
        return cls.objects.filter(role=role, user__is_active=True)

    def get_latest_score(self):
        """
        Returns the most recent score submitted for this candidate.
        """
        return self.scores.latest("recorded_at")

    def get_records(self):
        """
        Returns a dictionary of a candidate's performance stats, scores, and available exams.
        """
        latest_snapshot = (
            CandidateScoreSnapshot.objects.filter(published_at__isnull=False)
            .order_by("-published_at")
            .first()
        )

        scores_qs = self.scores.all()
        if latest_snapshot:
            scores_qs = scores_qs.filter(recorded_at__lte=latest_snapshot.published_at)

        score_stats = scores_qs.aggregate(
            total_exams_taken=Count("id"),
            average_score=Avg("score"),
            highest_score=Max("score"),
            lowest_score=Min("score"),
            total_score=Sum("score"),
        )

        recent_scores_list = list(
            scores_qs.order_by("-recorded_at")
            .select_related("exam")
            .values("score", "exam__title", "recorded_at")[:1]
        )

        latest_score_data = None
        if recent_scores_list:
            latest_score_data = {
                "score": float(recent_scores_list[0]["score"]),
                "exam_title": recent_scores_list[0]["exam__title"],
                "date": recent_scores_list[0]["recorded_at"],
            }

        # available_exams
        available_exams_list = []
        if self.is_verified:
            all_relevant_exams = (
                Exam.objects.filter(stage=self.role, is_active=True)
                .annotate(question_count=Count("questions"))
                .order_by("scheduled_date")[:5]
            )

            for exam in all_relevant_exams:
                if exam.is_currently_open:
                    available_exams_list.append(
                        {
                            "id": exam.id,
                            "title": exam.title,
                            "description": exam.description,
                            "open_duration_hours": exam.open_duration_hours,
                            "scheduled_date": exam.scheduled_date,
                            "countdown_minutes": exam.countdown_minutes,
                            "question_count": exam.question_count,
                            "stage": exam.stage,
                        }
                    )

        # leaderboard ranking
        candidate_rank = None
        total_league_candidates = 0
        if self.role == self.Roles.LEAGUE and latest_snapshot:
            league_candidates_qs = Candidate.candidates_by_role(
                self.Roles.LEAGUE
            ).annotate(
                total_score=Sum(
                    "scores__score",
                    filter=Q(scores__recorded_at__lte=latest_snapshot.published_at),
                    default=0.0,
                )
            )

            ranked_candidates_qs = league_candidates_qs.annotate(
                rank=Window(
                    expression=Rank(),
                    order_by=F("total_score").desc(nulls_last=True),
                )
            )

            ranked_candidate = ranked_candidates_qs.filter(pk=self.pk).first()
            if ranked_candidate:
                candidate_rank = ranked_candidate.rank

            total_league_candidates = league_candidates_qs.count()

        # Use prefetched scores for the `exams` list
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "scores" in self._prefetched_objects_cache
        ):
            scores = self._prefetched_objects_cache["scores"]
        else:
            scores = self.scores.select_related(
                "exam", "score_submitted_by__user"
            ).prefetch_related(
                "answers__question"
            ).all()
    
        exams_taken_list = []
        for score in scores:
            answers = score.answers.all()
            
            submission_list = []
            for answer in answers:
                submission_list.append({
                    "question_id": answer.question.id,
                    "question_text": answer.question.text,
                    "option_a": answer.question.option_a,
                    "option_b": answer.question.option_b,
                    "option_c": answer.question.option_c,
                    "option_d": answer.question.option_d,
                    "selected_option": answer.selected_option,
                    "answered_at": answer.answered_at.isoformat(),
                })
                
            exams_taken_list.append({
                "exam_id": score.exam.id,
                "exam_title": score.exam.title,
                "exam_stage": score.exam.stage,
                "scheduled_date": score.exam.scheduled_date,
                "score": float(score.score),
                "recorded_at": score.recorded_at.isoformat(),
                "score_submitted_by": (
                    score.score_submitted_by.user.get_full_name()
                    if score.score_submitted_by and score.score_submitted_by.user
                    else None
                ),
                "auto_score": score.auto_score,
                "submission": submission_list,
            })

        records = {
            "performance": {
                "stats": {
                    "total_score": float(score_stats["total_score"] or 0),
                    "average_score": round(
                        float(score_stats["average_score"] or 0), 2
                    ),
                    "leaderboard_ranking": (
                        {
                            "current_rank": candidate_rank,
                            "total_candidates": total_league_candidates,
                        }
                        if self.role == self.Roles.LEAGUE
                        else None
                    ),
                    "latest_score": latest_score_data,
                    "highest_score": float(score_stats["highest_score"] or 0),
                    "total_exams_taken": score_stats["total_exams_taken"],
                    "lowest_score": float(score_stats["lowest_score"] or 0),
                    "highest_obtainable_score": 100.0,
                },
                "exams_taken": exams_taken_list,
            },
            "available_exams": available_exams_list,
        }

        return records

    class Meta:
        """Meta options for the Candidate model."""

        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["school"]),
        ]


class CandidateScore(models.Model):
    """
    A score representing a candidate's performance in an exam.

    Links to candidate, exam, and submitting staff member.
    """

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="scores"
    )
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="scores")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    recorded_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    score_submitted_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True
    )
    auto_score = models.BooleanField(default=False, db_index=True)

    class Meta:
        """Meta options for the CandidateScore model."""

        unique_together = ("candidate", "exam")
        ordering = ["-recorded_at"]


class CandidateAnswer(models.Model):
    """Model for a candidate's answer to a question."""

    candidate_score = models.ForeignKey(
        CandidateScore,
        related_name="answers",
        on_delete=models.PROTECT
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT
    )
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
                fields=["candidate_score", "question"],
                name="unique_answer_per_candidate_score",
            )
        ]

    def __str__(self):
        if self.candidate_score and self.question:
            username = self.candidate_score.candidate.user.username
            return f"Answer by {username} for Q{self.question.id}"
        elif self.candidate_score:
            return f"Answer by {self.candidate_score.candidate.user.username} (deleted question)"
        elif self.question:
            return f"Answer for Q{self.question.id} (deleted score)"
        return f"Orphaned Answer #{self.id}"

class LeaderboardSnapshot(models.Model):  # pylint: disable=too-few-public-methods
    """Model for a snapshot of the leaderboard."""

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name="leaderboard_snapshots"
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    published_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaderboard_snapshots",
    )

    class Meta:
        """Meta options for the LeaderboardSnapshot model."""

        ordering = ["-created_at"]
        unique_together = ("exam", "created_at")


class CandidateScoreSnapshot(models.Model):  # pylint: disable=too-few-public-methods
    """Model for a snapshot of a candidate's score."""

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    data = models.JSONField()

    published_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_score_snapshots",
    )

    class Meta:
        """Meta options for the CandidateScoreSnapshot model."""

        ordering = ["-created_at"]
