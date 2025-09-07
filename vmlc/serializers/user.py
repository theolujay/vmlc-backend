import logging

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from PIL import Image
import magic

from ..models import User, UserVerification
from ..tasks import send_mail_task

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for the Django User model.
    """

    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    def validate_phone(self, value):
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing user info.
    """

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone"]


class UserVerificationStatusSerializer(serializers.ModelSerializer):
    """
    Secure serializer for user verification status.
    Only exposes the status and which documents have been uploaded.
    """

    documents_uploaded = serializers.SerializerMethodField()

    class Meta:
        model = UserVerification
        fields = [
            "is_pending",
            "is_verified",
            "is_rejected",
            "date_created",
            "date_updated",
            "documents_uploaded",
        ]

    def get_documents_uploaded(self, obj):
        return {
            "profile_photo": bool(obj.profile_photo),
            "id_card": bool(obj.id_card),
            "verification_document": bool(obj.verification_document),
        }


class UserVerificationUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading verification documents.
    """

    class Meta:
        model = UserVerification
        fields = [
            "profile_photo",
            "id_card",
            "verification_document",
        ]

    def _validate_file_size(self, value, max_size_mb, field_name):
        """Helper method to validate file size"""
        if value and value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"{field_name} must be less than {max_size_mb}MB."
            )

    def _validate_image_file(self, value, field_name):
        """Helper method to validate image files"""
        if not value:
            return

        try:
            # Use PIL to verify it's a real image
            img = Image.open(value)
            img.verify()
            # Reset file pointer after verification
            value.seek(0)
        except Exception:
            raise serializers.ValidationError(f"Invalid {field_name} image file.")

    def _validate_file_type(self, value, allowed_types, field_name):
        """Helper method to validate file type using python-magic"""
        if not value:
            return

        try:
            # Get actual file type using magic
            file_type = magic.from_buffer(value.read(1024), mime=True)
            value.seek(0)  # Reset file pointer

            if file_type not in allowed_types:
                allowed_str = ", ".join(allowed_types)
                raise serializers.ValidationError(
                    f"{field_name} must be one of: {allowed_str}"
                )
        except (OSError, magic.MagicException):
            # Fallback to content_type if magic fails
            if (
                hasattr(value, "content_type")
                and value.content_type not in allowed_types
            ):
                allowed_str = ", ".join(allowed_types)
                raise serializers.ValidationError(
                    f"{field_name} must be one of: {allowed_str}"
                )

    def validate_profile_photo(self, value):
        """Validation for profile photo"""
        if value:
            self._validate_file_size(value, 2, "Profile photo")
            allowed_types = ["image/jpg", "image/jpeg", "image/png"]
            self._validate_file_type(value, allowed_types, "Profile photo")
            self._validate_image_file(value, "profile photo")
        return value

    def validate_id_card(self, value):
        """Validation for ID card uploads"""
        if value:
            self._validate_file_size(value, 2, "ID card")
            allowed_types = ["image/jpg", "image/jpeg", "image/png", "application/pdf"]
            self._validate_file_type(value, allowed_types, "ID card")

            # If it's an image, validate it properly
            if value.content_type and value.content_type.startswith("image/"):
                self._validate_image_file(value, "ID card")
        return value

    def validate_verification_document(self, value):
        """Validation for verification document uploads"""
        if value:
            self._validate_file_size(value, 2, "Verification document")
            allowed_types = ["image/jpg", "image/jpeg", "image/png", "application/pdf"]
            self._validate_file_type(value, allowed_types, "Verification document")

            # If it's an image, validate it properly
            if value.content_type and value.content_type.startswith("image/"):
                self._validate_image_file(value, "verification document")
        return value


class UserVerificationActionSerializer(serializers.ModelSerializer):
    """Serializer for verifying a user."""

    class Meta:
        model = UserVerification
        fields = ["is_verified", "is_rejected"]

    def update(self, instance, validated_data):
        """Handle verification status updates."""
        is_verified = validated_data.get("is_verified")
        is_rejected = validated_data.get("is_rejected")

        if is_verified is True:
            # Approve
            instance.is_verified = True
            instance.is_pending = False
            instance.is_rejected = False
            send_mail_task.delay(
                subject="User Verification Successful",
                message="Your account is now verified.",
                recipient_list=[instance.user.email],
            )

        elif is_rejected is True:
            # Reject
            instance.is_verified = False
            instance.is_pending = False
            instance.is_rejected = True
            send_mail_task.delay(
                subject="User Verification Rejected",
                message="Your account verification has been rejected. Please contact a staf member for enquires.",
                recipient_list=[instance.user.email],
            )

        instance.save()
        return instance
