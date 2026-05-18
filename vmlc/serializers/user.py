import logging

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from identity.models import User
from vmlc.utils.user import normalize_title

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

    def validate_first_name(self, value):
        """Normalize first name to title case."""
        return normalize_title(value)

    def validate_last_name(self, value):
        """Normalize last name to title case."""
        return normalize_title(value)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_email_verified",
            "is_active",
            "first_name",
            "last_name",
            "profile_picture",
            "phone",
            "state",
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
            "state",
            "date_joined",
        ]



