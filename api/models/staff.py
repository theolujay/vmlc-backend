from django.core.files.base import File
from django.db import models

from .user import User, UserVerification


class Staff(models.Model):
    """
    Administrative user with a specific role for managing candidates, exams, and scores.
    """

    class Roles(models.TextChoices):
        SUPERADMIN = "superadmin", "Superadmin"
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
    role = models.CharField(
        max_length=20, choices=Roles.choices, default=Roles.VOLUNTEER, db_index=True
    )

    @property
    def is_active(self):
        """Reference the user's is_active status"""
        return self.user.is_active

    @property
    def profile_photo(self):
        """Get profile photo from UserVerification with error handling"""
        try:
            return self.user.verification.profile_photo
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def id_card(self):
        """Get ID card from UserVerification with error handling"""
        try:
            return self.user.verification.id_card
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def utility_bill(self):
        """Get utility bill from UserVerification with error handling"""
        try:
            return self.user.verification.verification_document
        except (AttributeError, UserVerification.DoesNotExist):
            return None

    @property
    def is_verified(self):
        """Check if user has verification and is verified"""
        return hasattr(self.user, "verification") and self.user.verification.is_verified

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"
