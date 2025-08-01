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
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create_user(self, user_data, password):
        """
        Creates a user using the custom user manager.
        The manager expects email and password, and will automatically
        set the username from the email.
        """
        # The custom user manager's create_user expects email and password,
        # with other user fields passed as extra_fields.
        return User.objects.create_user(
            email=user_data["email"],
            password=password,
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            phone=user_data.get("phone", ""),
        )

    def create(self, validated_data):
        """
        Handles the creation of a User and its associated profile
        (Candidate or Staff).
        """
        user_data = validated_data.pop("user")
        password = validated_data.pop("password")
        validated_data.pop("password2")

        with transaction.atomic():
            user = self.create_user(user_data, password)
            # self.Meta.model will be either Candidate or Staff
            profile = self.Meta.model.objects.create(user=user, **validated_data)
            return profile


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates (creates User and Candidate).
    """

    class Meta:
        model = Candidate
        fields = ("user", "password", "password2", "school", "profile_photo")


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff (creates User and Staff).
    """

    class Meta:
        model = Staff
        fields = (
            "user",
            "password",
            "password2",
            "occupation",
            "profile_photo",
        )
