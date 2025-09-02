import os
import uuid
from typing import Any, Optional

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from ..storage_backends import PrivateMediaStorage, PublicMediaStorage


class CustomUserManager(BaseUserManager):
    def create_user(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)

        if "username" not in extra_fields:
            extra_fields["username"] = email

        user: "User" = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    id: models.UUIDField = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    email: models.EmailField = models.EmailField(unique=True)
    is_email_verified: models.BooleanField = models.BooleanField(default=False)
    first_name: models.CharField = models.CharField(max_length=30, blank=False)
    last_name: models.CharField = models.CharField(max_length=30, blank=False)
    phone_regex: RegexValidator = RegexValidator(
        regex=r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$",
        message="Phone number must be in format: '+234XXXXXXXXXX' or '0XXXXXXXXXX'",
    )
    phone: models.CharField = models.CharField(
        validators=[phone_regex],
        max_length=17,
        help_text="Nigerian phone number for SMS notifications and contact",
    )
    username: models.CharField = models.CharField(max_length=255, unique=True)
    USERNAME_FIELD: str = "email"
    REQUIRED_FIELDS: list[str] = []

    objects: CustomUserManager = CustomUserManager()

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def validate_id_card_file(value: File) -> None:
    """Validate that the uploaded file is an image or PDF"""
    if not value:
        return

    ext: str = os.path.splitext(value.name)[1].lower()
    valid_extensions: list[str] = [".jpg", ".jpeg", ".png", ".pdf"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported file extension. Allowed: {", ".join(valid_extensions)}'
        )

    # Check file size (max 10MB)
    if value.size > 10 * 1024 * 1024:
        raise ValidationError("File size cannot exceed 10MB.")


def validate_profile_photo(value: File) -> None:
    """Validate profile photo file"""
    if not value:
        return

    ext: str = os.path.splitext(value.name)[1].lower()
    valid_extensions: list[str] = [".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported image format. Allowed: {", ".join(valid_extensions)}'
        )

    # Check file size (max 5MB for images)
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Image size cannot exceed 5MB.")


def validate_document_file(value: File) -> None:
    """Validate verification document file"""
    if not value:
        return

    ext: str = os.path.splitext(value.name)[1].lower()
    valid_extensions: list[str] = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(
            f'Unsupported document format. Allowed: {", ".join(valid_extensions)}'
        )

    # Check file size (max 15MB for documents)
    if value.size > 15 * 1024 * 1024:
        raise ValidationError("Document size cannot exceed 15MB.")


class UserVerification(models.Model):
    user: models.OneToOneField = models.OneToOneField(
        "User", on_delete=models.CASCADE, related_name="verification"
    )
    is_pending: models.BooleanField = models.BooleanField(default=False)
    is_verified: models.BooleanField = models.BooleanField(default=False)
    is_rejected: models.BooleanField = models.BooleanField(default=False)
    profile_photo: models.ImageField = models.ImageField(
        upload_to="profile_photos/",
        blank=True,
        null=True,
        storage=PublicMediaStorage(),
        validators=[validate_profile_photo],
    )
    id_card: models.FileField = models.FileField(
        upload_to="id_cards/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
        validators=[validate_id_card_file],
    )
    verification_document: models.FileField = models.FileField(
        upload_to="verification_docs/",
        blank=True,
        null=True,
        storage=PrivateMediaStorage(),
        validators=[validate_document_file],
    )
    date_created: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    date_updated: models.DateTimeField = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Verification for {self.user.get_full_name()}"

    # Helper methods to get secure URLs
    def get_profile_photo_url(self) -> Optional[str]:
        """Returns public URL for profile photo (no expiration)"""
        if self.profile_photo:
            return self.profile_photo.url
        return None

    def get_secure_id_card_url(self) -> Optional[str]:
        """Returns a signed URL for ID card that expires in 1 hour"""
        if self.id_card:
            return self.id_card.url  # Automatically signed by PrivateMediaStorage
        return None

    def get_secure_verification_doc_url(self) -> Optional[str]:
        """Returns a signed URL for verification document that expires in 1 hour"""
        if self.verification_document:
            return (
                self.verification_document.url
            )  # Automatically signed by PrivateMediaStorage
        return None

    class Meta:
        verbose_name = "User Verification"


class EmailOTP(models.Model):
    """One-time password for email verification"""

    user: models.ForeignKey = models.ForeignKey("User", on_delete=models.CASCADE)
    otp: models.CharField = models.CharField(max_length=6)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    expires_at: models.DateTimeField = models.DateTimeField()

    def is_expired(self) -> bool:
        """Check if the OTP has expired"""
        return timezone.now() > self.expires_at

    def __str__(self) -> str:
        return f"OTP for {self.user.email}"
