import logging
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

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
