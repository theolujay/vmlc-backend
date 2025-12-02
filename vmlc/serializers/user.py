import logging

from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

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
            "is_email_verified",
            "first_name",
            "last_name",
            "profile_picture",
            "phone",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "is_email_verified"]

    def get_profile_picture(self, obj: User):
        """
        Safely returns the profile picture URL if it exists, otherwise returns None.
        This prevents errors when a user hasn't uploaded a profile picture yet.
        """
        if obj.profile_picture and hasattr(obj.profile_picture, "url"):
            return obj.profile_picture.url
        return None


class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing user info.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_email_verified",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        ]


class UserVerificationListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing user verification requests.
    """

    user_id = serializers.CharField(source="user.id", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    has_face_id = serializers.SerializerMethodField()
    has_id_card = serializers.SerializerMethodField()
    has_verification_document = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = UserVerification
        fields = [
            "user_id",
            "full_name",
            "email",
            "status",
            "has_face_id",
            "has_id_card",
            "has_verification_document",
            "created_at",
        ]

    def get_status(self, obj):
        return obj.status

    def get_has_face_id(self, obj):
        return bool(obj.face_id)

    def get_has_id_card(self, obj):
        return bool(obj.id_card)

    def get_has_verification_document(self, obj):
        return bool(obj.verification_document)


class UserVerificationStatusSerializer(serializers.ModelSerializer):
    """
    Secure serializer for user verification status.
    Only exposes the status and which documents have been uploaded.
    """

    documents_uploaded = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = UserVerification
        fields = [
            "status",
            "created_at",
            "updated_at",
            "documents_uploaded",
        ]

    def get_documents_uploaded(self, obj):
        return {
            "face_id": bool(obj.face_id),
            "id_card": bool(obj.id_card),
            "verification_document": bool(obj.verification_document),
        }

    def get_status(self, obj):
        return obj.status


class UserVerificationUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading verification documents.
    Validation is handled asynchronously by a Celery task.
    """

    class Meta:
        model = UserVerification
        fields = [
            "face_id",
            "id_card",
            "verification_document",
        ]


class UserVerificationActionSerializer(serializers.ModelSerializer):
    """Serializer for verifying a user."""

    rejection_reason = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )

    class Meta:
        model = UserVerification
        fields = ["is_approved", "is_rejected", "rejection_reason"]

    def validate(self, data):
        """
        Validate the verification action data.
        - `rejection_reason` is only allowed when `is_rejected` is true.
        - Either `is_approved` or `is_rejected` must be provided.
        """
        is_approved = data.get("is_approved", False)
        is_rejected = data.get("is_rejected", False)
        rejection_reason = data.get("rejection_reason")

        if rejection_reason and not is_rejected:
            raise serializers.ValidationError(
                {"rejection_reason": "A rejection reason can only be provided when rejecting an application."}
            )
        
        if is_rejected and not rejection_reason:
            raise serializers.ValidationError(
                {"rejection_reason": "A rejection reason is required when rejecting an application."}
            )

        if not is_approved and not is_rejected:
            raise serializers.ValidationError(
                "Either 'is_approved' or 'is_rejected' must be true."
            )
            
        if is_approved and is_rejected:
            raise serializers.ValidationError(
                "A verification can either be approved or rejected, not both."
            )

        return data

    def update(self, instance, validated_data):
        """
        Handle verification status updates.
        - If approved, clear any previous rejection reason.
        - If rejected, save the rejection reason.
        """
        is_approved = validated_data.get("is_approved", False)
        is_rejected = validated_data.get("is_rejected", False)
        rejection_reason = validated_data.get("rejection_reason")

        if is_approved:
            instance.is_approved = True
            instance.is_rejected = False
            instance.is_pending = False
            instance.rejection_reason = ""
        elif is_rejected:
            instance.is_approved = False
            instance.is_rejected = True
            instance.is_pending = False
            instance.rejection_reason = rejection_reason

        instance.save()
        return instance
