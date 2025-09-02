import logging
from typing import Any, Dict

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import UserVerification, User
from ..tasks import send_mail_task

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for the Django User model.
    """

    email: serializers.EmailField = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    def validate_phone(self, value: Any) -> str:
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value

    class Meta:
        model: User = User
        fields: tuple[str, ...] = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        )
        read_only_fields: tuple[str, ...] = ("id", "date_joined")


class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing user info.
    """

    class Meta:
        model: User = User
        fields: tuple[str, ...] = ("email", "first_name", "last_name", "phone")


class UserVerificationStatusSerializer(serializers.ModelSerializer):
    """
    Secure serializer for user verification status.
    Only exposes the status and which documents have been uploaded.
    """

    documents_uploaded: serializers.SerializerMethodField = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model: UserVerification = UserVerification
        fields: tuple[str, ...] = (
            "is_pending",
            "is_verified",
            "is_rejected",
            "date_created",
            "date_updated",
            "documents_uploaded",
        )

    def get_documents_uploaded(self, obj: UserVerification) -> Dict[str, bool]:
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
        model: UserVerification = UserVerification
        fields: tuple[str, ...] = (
            "profile_photo",
            "id_card",
            "verification_document",
        )


class UserVerificationActionSerializer(serializers.ModelSerializer):
    """Serializer for verifying a user."""

    class Meta:
        model: UserVerification = UserVerification
        fields: list[str] = ["is_verified", "is_rejected"]

    def update(
        self, instance: UserVerification, validated_data: Dict[str, Any]
    ) -> UserVerification:
        """Handle verification status updates."""
        is_verified: bool = validated_data.get("is_verified")
        is_rejected: bool = validated_data.get("is_rejected")

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
