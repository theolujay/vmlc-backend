import logging
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..tasks import send_mail_task
from ..models import (
    User,
    UserVerification,
)


User = get_user_model()
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
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")


class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing user info.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone")


class UserVerificationStatusSerializer(serializers.ModelSerializer):
    """
    Secure serializer for user verification status.
    Only exposes the status and which documents have been uploaded.
    """

    documents_uploaded = serializers.SerializerMethodField()

    class Meta:
        model = UserVerification
        fields = (
            "is_pending",
            "is_verified",
            "is_rejected",
            "date_created",
            "date_updated",
            "documents_uploaded",
        )

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
        fields = (
            "profile_photo",
            "id_card",
            "verification_document",
        )

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