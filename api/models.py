"""
Core database models for candidate assessments and staff administration.

Includes models for:
- CustomUser with email as unique identifier
- Candidate and their role-based progression
- Staff and administrative roles
- Exams and questions
- Candidate scores with submission metadata
"""

from datetime import timedelta
from typing import Optional
import uuid

from django.db import models
from django.db.models import Sum, Avg, Count
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)

        if "username" not in extra_fields:
            extra_fields["username"] = email

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    email = models.EmailField(unique=True)
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


class CandidateManager(models.Manager):
    """
    Custom manager for the Candidate model.

    Provides annotation methods for scores and prefetch optimization.
    """

    def with_scores(self):
        """
        Annotate candidates with total, average, and count of exam scores.
        """
        return self.annotate(
            total_score=Sum("scores__score"),
            average_score=Avg("scores__score"),
            exams_taken=Count("scores", distinct=True),
        )

    def with_complete_data(self):
        """
        Annotate candidates with scores and optimize related data fetching.
        """
        return (
            self.with_scores()
            .prefetch_related("scores__exam", "scores__submitted_by__user")
            .select_related("user")
        )


class Candidate(models.Model):
    """
    Represents a student or participant in the exam system.
    Linked to a User, assigned a role, and tracks their profile and score history.
    """

    class Roles(models.TextChoices):
        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"
        FINAL = "final", "Final"
        WINNER = "winner", "Winner"

    user = models.OneToOneField(
        User,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    school = models.CharField(max_length=150)
    profile_photo = models.ImageField(
        upload_to="candidate_profile_photos/",
        default="candidate_profile_photos/default.png",
        null=True,
        blank=True,
    )
    id_card = models.ImageField(upload_to="candidate_id_cards/", blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    role = models.CharField(
        max_length=15, choices=Roles.choices, default=Roles.SCREENING, db_index=True
    )

    objects = CandidateManager()
    total_score: Optional[float]
    average_score: Optional[float]
    exams_taken: Optional[int]

    class Meta:
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["school"]),
        ]

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
        return f"{self.user.get_full_name()} - {self.school}"

    @classmethod
    def active_candidates(cls):
        """
        Returns all currently active candidates.
        """
        return cls.objects.filter(is_active=True)

    @classmethod
    def candidates_by_role(cls, role):
        """
        Returns active candidates filtered by role.
        """
        return cls.objects.filter(role=role, is_active=True)

    def get_latest_score(self):
        """
        Returns the most recent score submitted for this candidate.
        """
        return self.scores.latest("date_recorded")

    def get_score_dict(self):
        """
        Returns a dictionary of total, average, and per-exam scores for this candidate.
        Uses annotated and prefetched data if available to avoid extra queries.
        """
        # Use annotated values if they exist
        total_score = getattr(self, "total_score", None)
        average_score = getattr(self, "average_score", None)

        # Use prefetched scores if they exist, otherwise query
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "scores" in self._prefetched_objects_cache
        ):
            scores = self._prefetched_objects_cache["scores"]
        else:
            scores = self.scores.select_related("exam", "submitted_by__user").all()

        # If total/average scores were not annotated, calculate them from the scores list
        if total_score is None and scores:
            total_score = sum(s.score for s in scores if s.score is not None)
        if average_score is None and scores:
            average_score = total_score / len(scores) if scores else 0

        return {
            "total_score": float(total_score) if total_score is not None else 0.0,
            "average_score": float(average_score) if average_score is not None else 0.0,
            "scores": [
                {
                    "exam_id": s.exam.id,
                    "exam_title": s.exam.title,
                    "score": float(s.score),
                    "date_recorded": s.date_recorded.isoformat(),
                    "submitted_by": (
                        s.submitted_by.user.get_full_name()
                        if s.submitted_by and s.submitted_by.user
                        else None
                    ),
                    "auto_score": s.auto_score,
                }
                for s in scores
            ],
        }


class Staff(models.Model):
    """
    Administrative user with a specific role for managing candidates, exams, and scores.
    """

    class Roles(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        SPONSOR = "sponsor", "Sponsor"
        VOLUNTEER = "volunteer", "Volunteer"

    user = models.OneToOneField(
        User, primary_key=True, on_delete=models.CASCADE, related_name="staff_profile"
    )
    occupation = models.CharField(max_length=50, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    profile_photo = models.ImageField(
        upload_to="staff_profile_photos/",
        default="staff_profile_photos/default.png",
        blank=True,
        null=True,
    )
    id_card = models.ImageField(upload_to="staff_id_cards/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=Roles.choices, default=Roles.VOLUNTEER, db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"


class Question(models.Model):
    """
    A question belonging to one or more exams. Includes text, difficulty, and staff author.
    """

    class Options(models.TextChoices):
        A = "A", "Option A"
        B = "B", "Option B"
        C = "C", "Option C"
        D = "D", "Option D"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    text = models.TextField()
    option_a = models.CharField(max_length=255, blank=True)
    option_b = models.CharField(max_length=255, blank=True)
    option_c = models.CharField(max_length=255, blank=True)
    option_d = models.CharField(max_length=255, blank=True)
    correct_answer = models.CharField(max_length=1, choices=Options.choices)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "Staff",
        blank=True,
        null=True,
        related_name="questions_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        "Staff",
        blank=True,
        null=True,
        related_name="questions_updated",
        on_delete=models.SET_NULL,
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"Q{self.id}: {self.text[:50]}..."


class Exam(models.Model):
    """
    Represents a collection of questions scheduled at a specific date for a stage of competition.
    """

    class Stages(models.TextChoices):
        SCREENING = "screening", "Screening"
        LEAGUE = "league", "League"

    stage = models.CharField(
        max_length=20, choices=Stages.choices, default=Stages.LEAGUE, db_index=True
    )
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False, db_index=True)
    exam_date = models.DateTimeField(blank=True, null=True, db_index=True)
    open_duration_hours = models.PositiveIntegerField(default=12)
    countdown_minutes = models.PositiveIntegerField(default=60)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    questions = models.ManyToManyField("Question", blank=True)
    created_by = models.ForeignKey(
        "Staff",
        blank=True,
        null=True,
        related_name="exams_created",
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        "Staff",
        blank=True,
        null=True,
        related_name="exams_updated",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
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
        - exam_date is None (always open)
        - or current time is within open window
        """
        if not self.is_active:
            return False
        if self.exam_date is None:
            return True
        now = timezone.now()
        end_time = self.exam_date + timedelta(hours=self.open_duration_hours)
        return self.exam_date <= now <= end_time

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


class CandidateScore(models.Model):
    """
    A score representing a candidate's performance in an exam.

    Links to candidate, exam, and submitting staff member.
    """

    candidate = models.ForeignKey(
        "Candidate", on_delete=models.CASCADE, related_name="scores"
    )
    exam = models.ForeignKey("Exam", on_delete=models.PROTECT, related_name="scores")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    date_recorded = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    submitted_by = models.ForeignKey(
        "Staff", on_delete=models.SET_NULL, null=True, blank=True
    )
    auto_score = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ("candidate", "exam")
        ordering = ["-date_recorded"]

    def calculate_and_save_auto_score(self, submitted_answers):
        """
        Scores an exam based on a list of submitted answers, updates the
        instance, and saves it.

        Args:
            submitted_answers (list[CandidateAnswer]): A list of unsaved
                CandidateAnswer objects. This avoids a race condition by not
                re-querying the database within the transaction.
        """
        total_questions = self.exam.questions.count()
        if not total_questions:
            self.score = 0
        else:
            correct_count = sum(
                1
                for answer in submitted_answers
                if answer.selected_option == answer.question.correct_answer
            )
            score = (correct_count / total_questions) * 100
            self.score = round(score, 2)

        self.auto_score = True
        self.date_recorded = timezone.now()
        self.save()


class CandidateAnswer(models.Model):
    candidate_score = models.ForeignKey(
        "CandidateScore", related_name="answers", on_delete=models.CASCADE
    )
    question = models.ForeignKey("Question", on_delete=models.CASCADE)
    selected_option = models.CharField(
        max_length=1,
        choices=Question.Options.choices,
        blank=True,
        null=True,
    )
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_score", "question"],
                name="unique_answer_per_candidate_score",
            )
        ]

    def __str__(self):
        return f"Answer by {self.candidate_score.candidate.user.username} for Q{self.question.id}"


class LeaderboardSnapshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    published_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaderboard_snapshots",
    )

    class Meta:
        ordering = ["-created_at"]

class CandidateScoreSnapshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()

    published_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_score_snapshots",
    )

class FeatureFlag(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.BooleanField(default=True)

    @classmethod
    def get_bool(cls, key, default=True):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    def __str__(self):
        return f"{self.key}: {'Enabled' if self.value else 'Disabled'}"
