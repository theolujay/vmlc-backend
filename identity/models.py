"""
This module defines the identity models for the VMLC backend application.
"""

import os
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.apps import apps
from django.db import models
from django.db.models import Avg, Count, F, Max, Min, Q, Sum, Window
from django.db.models.functions import Rank
from django.utils import timezone

# TODO: move to core/utils/storage
from vmlc.storage_backends import PrivateMediaStorage, PublicMediaStorage
from identity.validators import (
    validate_profile_picture,
    validate_face_id,
    validate_id_card_file,
    validate_document_file,
)


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
                "results__score",
                filter=Q(
                    results__exam__competition_contexts__competition_stage__type="league"
                ),
            ),
            average_score=Avg(
                "results__score",
                filter=Q(
                    results__exam__competition_contexts__competition_stage__type="league"
                ),
            ),
            exams_taken=Count(
                "results",
                filter=Q(
                    results__exam__competition_contexts__competition_stage__type="league"
                ),
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

    class Meta:
        """Meta options for the Candidate model."""

        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["school_name"]),
        ]