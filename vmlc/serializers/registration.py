from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework.validators import UniqueValidator
from rest_framework import serializers

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
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    phone = serializers.CharField(max_length=17)
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
    def validate_phone(self, value):
        """Validate phone number format."""
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create_user(self, user_data, password):
        """Helper to create a user instance."""
        return User.objects.create_user(
            email=user_data["email"],
            password=password,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            phone=user_data["phone"],
        )

    def create(self, validated_data):
        """
        Handles the creation of a User and its associated profile (from a flat structure).
        """
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        phone = validated_data.pop("phone")
        password = validated_data.pop("password")
        validated_data.pop("password2")
        user_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
        }

        try:
            with transaction.atomic():
                user = self.create_user(user_data, password)
                profile = self.Meta.model.objects.create(user=user, **validated_data)
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
            "email",
            "first_name",
            "last_name",
            "phone",
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
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "occupation",
        ]
