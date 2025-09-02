from django.contrib.auth import password_validation
from django.db import transaction

from rest_framework import serializers


from ..models import (
    Candidate,
    Staff,
    User,
)
from .user import UserSerializer


class BaseRegistrationSerializer(serializers.ModelSerializer):
    """
    Abstract base serializer for user registration.
    Handles common user creation and password validation logic.
    """

    user = UserSerializer()
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[password_validation.validate_password],
        style={"input_type": "password"},
        help_text="Required. 8 characters minimum.",
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Confirm password",
    )

    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create_user(self, user_data, password):
        return User.objects.create_user(
            email=user_data["email"],
            password=password,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            phone=user_data["phone"],
        )

    def create(self, validated_data):
        """
        Handles the creation of a User and its associated profile.
        """
        password = validated_data.pop("password")
        validated_data.pop("password2")
        user_data = validated_data.pop("user")

        try:
            with transaction.atomic():
                user = self.create_user(user_data, password)
                profile = self.Meta.model.objects.create(
                    user=user, **validated_data
                )
                return profile
        except Exception as e:
            raise serializers.ValidationError(f"Registration failed: {str(e)}")


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates.
    """

    class Meta:
        model = Candidate
        fields = [
            "user",
            "password",
            "password2",
            "school",
        ]


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff.
    """

    class Meta:
        model = Staff
        fields = [
            "user",
            "password",
            "password2",
            "occupation",
        ]
