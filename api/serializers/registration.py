from django.contrib.auth import password_validation
from django.db import transaction

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    Candidate,
    Staff,
    User,
)


class BaseRegistrationSerializer(serializers.ModelSerializer):
    """
    Abstract base serializer for user registration.
    Handles common user creation and password validation logic.
    """

    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
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

    def create_user(self, validated_data):
        """
        Creates a user using the custom user manager.
        The manager expects email and password, and will automatically
        set the username from the email.
        """
        # The custom user manager's create_user expects email and password,
        # with other user fields passed as extra_fields.
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone=validated_data.get("phone", ""),
        )

    def create(self, validated_data):
        """
        Handles the creation of a User and its associated profile
        (Candidate or Staff).
        """
        password = validated_data.pop("password")
        validated_data.pop("password2")
        
        user_fields = {
            field: validated_data.pop(field)
            for field in ["email", "first_name", "last_name", "phone"]
        }

        with transaction.atomic():
            user = self.create_user({**user_fields, "password": password})
            profile = self.Meta.model.objects.create(user=user, **validated_data)
            return profile


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates.
    """

    class Meta:
        model = Candidate
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "school",
        )


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff (creates User and Staff).
    """

    class Meta:
        model = Staff
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "occupation",
        )