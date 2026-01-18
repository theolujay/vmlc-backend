import logging
from django.contrib.auth import password_validation
from django.db import transaction, IntegrityError, DatabaseError
from rest_framework.validators import UniqueValidator
from rest_framework import serializers

from vmlc.serializers.staff import MinimalStaffSerializer

# from vmlc.tasks import revoke_staff_registration_task
from ..models import (
    Candidate,
    Staff,
    User,
)


logger = logging.getLogger(__name__)


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
    generate_password = serializers.BooleanField(write_only=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial_data.get("generate_password"):
            self.fields["password"].required = False
            self.fields["password2"].required = False

    def validate_phone(self, value):
        """Validate phone number format."""
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value

    def validate(self, attrs):
        """Validate that passwords match"""
        if not self.initial_data.get("generate_password"):
            if attrs["password"] != attrs["password2"]:
                raise serializers.ValidationError(
                    {"password2": "Passwords do not match."}
                )
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
        user_data = {
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "phone": validated_data.pop("phone"),
        }
        password = validated_data.pop("password", None)
        validated_data.pop("password2", None)
        validated_data.pop("generate_password", None)

        try:
            with transaction.atomic():
                user = self.create_user(user_data, password)
                profile = self.Meta.model.objects.create(user=user, **validated_data)
                # if hasattr(user, "staff_profile"):
                #     revoke_staff_registration_task.apply_async(
                #         args=[user.id], countdown=60 * 15
                #     )
                return profile

        except IntegrityError:
            raise serializers.ValidationError(
                {"error": "A user with this information already exists."}
            )

        except DatabaseError as e:
            logger.error(f"Database error during registration: {str(e)}", exc_info=True)
            raise serializers.ValidationError(
                {
                    "error": "Registration temporarily unavailable. Please try again later."
                }
            )


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates.
    """

    school_name = serializers.CharField(max_length=150)

    class Meta:
        model = Candidate
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "school_name",
            "generate_password",
        ]


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff.
    """

    occupation = serializers.CharField(max_length=50, required=False)

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
            "generate_password",
        ]


class StaffInviteSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff.
    """

    created_by = MinimalStaffSerializer(read_only=True)
    occupation = serializers.CharField(max_length=50, required=False)
    role = serializers.ChoiceField(choices=Staff.Roles.choices, required=False)

    class Meta:
        model = Staff
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "role",
            "occupation",
            "created_by",
            "generate_password",
        ]

    def validate_role(self, value):
        """
        Validate the role assignment.

        - Ensures the role is a valid choice.
        - Prevents assigning 'superadmin'.
        - Prevents managers from assigning 'manager' roles.
        """
        valid_roles: list[str] = [
            role[0] for role in Staff.Roles.choices if role[0] != "superadmin"
        ]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"'{value}' is not a valid role. "
                f"Valid choices are: {', '.join(valid_roles)}."
            )

        if value == "superadmin":
            raise serializers.ValidationError(
                "The 'superadmin' role cannot be assigned via the API."
                f"Valid choices are: {', '.join(valid_roles)}."
            )

        user = self.context["request"].user

        if hasattr(user, "staff_profile") and user.staff_profile.role == "manager":
            if value == "manager":
                raise serializers.ValidationError(
                    "Managers cannot assign the 'manager' role."
                )

        return value


class CandidateInviteSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates.
    """

    created_by = MinimalStaffSerializer(read_only=True)
    school_name = serializers.CharField(max_length=100, required=False)
    role = serializers.ChoiceField(choices=Candidate.Roles.choices, required=False)

    class Meta:
        model = Candidate
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "password",
            "password2",
            "role",
            "school_name",
            "created_by",
            "generate_password",
        ]

    def validate_role(self, value):
        """
        Validate the role assignment.

        - Ensures the role is a valid choice.
        - Prevents assigning 'final' and 'winner' roles.
        """
        valid_roles: list[str] = [role[0] for role in Candidate.Roles.choices]

        if value not in valid_roles:
            raise serializers.ValidationError(
                f"'{value}' is not a valid role. "
                f"Valid choices are: {', '.join(valid_roles)}."
            )

        if value in ("final", "winner"):
            raise serializers.ValidationError(
                f"The '{value}' role cannot be assigned via the API."
                f"Valid choices are: {', '.join(valid_roles)}."
            )

        return value
