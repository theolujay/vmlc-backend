"""
This module defines the identity models for the VMLC backend application.
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

# TODO: move to core/utils/storage
from vmlc.storage_backends import PrivateMediaStorage, PublicMediaStorage

phone_regex = RegexValidator(
    regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
    message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
)

phone_field = models.CharField(
    validators=[phone_regex],
    max_length=17,
    help_text="Nigerian phone number",
)

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

def validate_verification_document(value):
    """Validate verification document"""
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported document format. Allowed: {", ".join(valid_extensions)}'
        )

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 5MB.")


def validate_profile_picture(value):
    """Validate profile picture file"""
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

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("File size cannot exceed 5MB.")


def validate_face_id(value):
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

    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 5MB.")


class User(AbstractUser):
    """Custom user model."""

    id = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False)
    phone = phone_field
    state = models.CharField(max_length=50, blank=True)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
        storage=PublicMediaStorage(),
        validators=[validate_profile_picture],
    )
    username = models.CharField(max_length=255, unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    @property
    def is_setup_complete(self):
        """
        Check if the user has completed their profile setup.
        Returns True if all required fields from RegistrationV2 are present.
        """
        # Base user fields
        if not all([self.first_name, self.last_name, self.phone, self.state]):
            return False

        # Candidate specific fields
        if hasattr(self, "candidate_profile"):
            cp = self.candidate_profile
            return all([cp.school_name, cp.school_type, cp.current_class])

        # Staff specific fields
        if hasattr(self, "staff_profile"):
            sp = self.staff_profile
            return bool(sp.occupation)

        return False

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()


class UserVerification(models.Model):
    """Model for user verification data."""

    user = models.OneToOneField(
        "User", on_delete=models.CASCADE, related_name="verification"
    )
    is_pending = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
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
    verification_document_type = models.CharField(max_length=50, blank=True, null=True)
    action_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="verified_users",
    )
    rejection_reason = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate that only one status flag is True."""
        true_count = sum(
            [int(self.is_pending), int(self.is_approved), int(self.is_rejected)]
        )

        if true_count > 1:
            raise ValidationError(
                "Only one of is_pending, is_approved, or is_rejected can be True"
            )

    def save(self, *args, **kwargs):
        """Call clean before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def status(self):
        """Get current verification status as a string."""
        if self.is_approved:
            return "approved"
        elif self.is_rejected:
            return "rejected"
        elif self.is_pending:
            return "pending"
        return "not_started"

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


class PreRegUser(models.Model):
    """Model for pre-registration data."""

    class InterestType(models.TextChoices):
        """Interest types for pre-registration."""

        CANDIDATE = "candidate", "Candidate"
        VOLUNTEER = "volunteer", "Volunteer"

    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = phone_field
    interest_type = models.CharField(
        max_length=20,
        choices=InterestType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return a string representation of the pre-registration."""
        return f"{self.full_name} ({self.interest_type})"


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
    Administrative user with a specific role for managing candidates, exams, and results.
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
        "User", primary_key=True, on_delete=models.CASCADE, related_name="staff_profile"
    )
    occupation = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="invited_staffs",
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
    def is_user_verified(self):
        """
        Check if user has verification and is verified.
        DEPRECATED: Currently suppressed to always return True.
        """
        return True

    @property
    def status(self):
        """Get the user status"""
        if not self.user.is_active:
            return "deactivated"

        seven_days_ago = timezone.now() - timedelta(days=7)
        if self.user.last_login and self.user.last_login >= seven_days_ago:
            return "active"

        return "inactive"

    def set_verification_override(self, value):
        """Manually override verification status"""
        self._verification_override = value

    def clear_verification_override(self):
        """Remove override, return to normal verification checking"""
        self._verification_override = None

    def __str__(self):
        """Return a string representation of the staff member."""
        return f"{self.user.get_full_name()} ({self.role})"


class CandidateManager(models.Manager):
    """
    Custom manager for the Candidate model.
    """

    def with_results(self):
        """
        Annotate candidates with total, average, and count of exam results,
        excluding results from exams at the 'screening' stage.
        """

        return self.annotate(
            total_score=Sum(
                "results__score", filter=Q(results__exam__stage="league")
            ),
            average_score=Avg(
                "results__score", filter=Q(results__exam__stage="league")
            ),
            exams_taken=Count(
                "results",
                filter=Q(results__exam__stage="league"),
                distinct=True,
            ),
        )

    def with_complete_data(self):
        """
        Annotate candidates with results and optimize related data fetching.
        """
        return (
            self.with_results()
            .prefetch_related("results__exam", "results__score_submitted_by__user")
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
    Linked to a User, assigned a role, and tracks their profile and result history.
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
        "User",
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    school_name = models.CharField(max_length=150)
    school_type = models.CharField(
        max_length=20,
        choices=[("public", "Public"), ("private", "Private")],
        blank=True,
    )
    current_class = models.CharField(
        max_length=10,
        choices=[("SS1", "SS1"), ("SS2", "SS2"), ("SS3", "SS3")],
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="invited_candidates",
    )
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
    def is_user_verified(self):
        """
        Check if user has verification and is verified.
        DEPRECATED: Currently suppressed to always return True.
        """
        return True

    def set_verification_override(self, value):
        """Manually override verification status"""
        self._verification_override = value

    def clear_verification_override(self):
        """Remove override, return to normal verification checking"""
        self._verification_override = None

    @property
    def result_data(self):
        """
        Returns result summary (total and average scores) if annotated via `with_results()`.
        """
        if hasattr(self, "total_score"):
            return {
                "total_score": float(self.total_score or 0),
                "average_score": float(self.average_score or 0),
            }
        return None

    @property
    def status(self):
        """Get the user status"""
        from vmlc.utils.user import get_last_concluded_exam

        if not self.user.is_active:
            return "deactivated"

        seven_days_ago = timezone.now() - timedelta(days=7)

        last_concluded_exam = get_last_concluded_exam()
        if last_concluded_exam:
            is_active_based_on_exam = (
                self.__class__.objects.filter(
                    pk=self.pk,
                    user__is_active=True,
                    user__last_login__gte=seven_days_ago,
                    results__exam=last_concluded_exam,
                )
                .distinct()
                .exists()
            )

            if is_active_based_on_exam:
                return "active"

        return "inactive"

    @property
    def is_winner(self):
        """
        Returns True if candidate has 'winner' role.
        """
        return self.role == self.Roles.WINNER

    def __str__(self):
        """Return a string representation of the candidate."""
        return f"{self.user.get_full_name()} - {self.school_name}"

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
        return self.results.latest("recorded_at")

    def get_records(self):
        """
        Returns a dictionary of a candidate's performance stats, results, and available exams.
        """
        return {
            "performance": self._get_performance_stats(),
            "available_exams": self._get_available_exams(),
        }

    def _get_performance_stats(self):
        """Helper to compute performance statistics for the candidate."""

        latest_snapshot = (
            models.get_model("vmlc", "CandidateExamResultSnapshot").objects.filter(published_at__isnull=False)
            .order_by("-published_at")
            .first()
        )

        results_qs = self.results.all()
        if latest_snapshot:
            results_qs = results_qs.filter(recorded_at__lte=latest_snapshot.published_at)

        result_stats = results_qs.aggregate(
            total_exams_taken=Count("id"),
            average_score=Avg("score"),
            highest_score=Max("score"),
            lowest_score=Min("score"),
            total_score=Sum("score"),
        )

        recent_results_list = list(
            results_qs.order_by("-recorded_at")
            .select_related("exam")
            .values("score", "exam__title", "recorded_at")[:1]
        )

        latest_score_data = None
        if recent_results_list:
            latest_score_data = {
                "score": float(recent_results_list[0]["score"]),
                "exam_title": recent_results_list[0]["exam__title"],
                "date": recent_results_list[0]["recorded_at"],
            }

        candidate_rank, total_league_candidates = self._get_leaderboard_ranking(
            latest_snapshot
        )

        return {
            "stats": {
                "total_score": float(result_stats["total_score"] or 0),
                "average_score": round(float(result_stats["average_score"] or 0), 2),
                "leaderboard_ranking": (
                    {
                        "current_rank": candidate_rank,
                        "total_candidates": total_league_candidates,
                    }
                    if self.role == self.Roles.LEAGUE
                    else None
                ),
                "latest_score": latest_score_data,
                "highest_score": float(result_stats["highest_score"] or 0),
                "total_exams_taken": result_stats["total_exams_taken"],
                "lowest_result": float(result_stats["lowest_score"] or 0),
                "highest_obtainable_score": 100.0,
            },
            "exams_taken": self._get_exams_taken(),
        }

    def _get_leaderboard_ranking(self, latest_snapshot):
        """Helper to get the candidate's leaderboard ranking."""
        if self.role == self.Roles.LEAGUE and latest_snapshot:
            league_candidates_qs = self.__class__.candidates_by_role(
                self.Roles.LEAGUE
            ).annotate(
                total_score=Sum(
                    "results__score",
                    filter=Q(results__recorded_at__lte=latest_snapshot.published_at),
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
                return ranked_candidate.rank, league_candidates_qs.count()

        return None, 0

    def _get_available_exams(self):
        """Helper to get a list of available exams for the candidate."""

        all_relevant_exams = (
            models.get_model("vmlc", "Exam").objects.filter(stage=self.role, is_active=True)
            .annotate(question_count=Count("questions"))
            .order_by("scheduled_date")[:5]
        )

        available_exams_list = []
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
        return available_exams_list

    def _get_exams_taken(self):
        """Helper to get a list of exams taken by the candidate."""
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "results" in self._prefetched_objects_cache
        ):
            results = self._prefetched_objects_cache["results"]
        else:
            results = (
                self.results.select_related("exam", "score_submitted_by__user")
                .prefetch_related("answers__question")
                .all()
            )

        exams_taken_list = []
        for result in results:
            answers = result.answers.all()
            submission_list = []
            for answer in answers:
                submission_list.append(
                    {
                        "question_id": answer.question.id,
                        "question_text": answer.question.text,
                        "option_a": answer.question.option_a,
                        "option_b": answer.question.option_b,
                        "option_c": answer.question.option_c,
                        "option_d": answer.question.option_d,
                        "selected_option": answer.selected_option,
                        "answered_at": answer.answered_at.isoformat(),
                    }
                )

            exams_taken_list.append(
                {
                    "exam_id": result.exam.id,
                    "exam_title": result.exam.title,
                    "exam_stage": result.exam.stage,
                    "scheduled_date": result.exam.scheduled_date,
                    "score": float(result.score),
                    "recorded_at": result.recorded_at.isoformat(),
                    "score_submitted_by": (
                        result.score_submitted_by.user.get_full_name()
                        if result.score_submitted_by and result.score_submitted_by.user
                        else None
                    ),
                    "auto_score": result.auto_score,
                    "submission": submission_list,
                }
            )
        return exams_taken_list

    class Meta:
        """Meta options for the Candidate model."""

        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["school_name"]),
        ]