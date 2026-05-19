import os
import uuid
import logging
from django.conf import settings
from django.db import transaction, IntegrityError, DatabaseError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from identity.models import (
    PreRegUser,
    User,
    UserVerification,
    Candidate,
    Staff,
    validate_document_file,
    validate_face_id,
)
from core.utils.auth import generate_password
from identity.utils.user import normalize_title
from identity.serializers.staff import MinimalStaffSerializer

logger = logging.getLogger(__name__)


class RegistrationV2Serializer(serializers.Serializer):
    """
    Unified serializer for v2 registration (Candidate and Volunteer).
    """

    user_type = serializers.ChoiceField(choices=["candidate", "volunteer"])
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=17)

    # File upload fields
    face_capture = serializers.FileField(required=False)
    document = serializers.FileField()
    document_type = serializers.CharField(max_length=50)
    consent = serializers.CharField()  # "true" or "false" string from form-data

    # Candidate specific
    school_name = serializers.CharField(max_length=150, required=False)
    school_type = serializers.ChoiceField(
        choices=[("public", "Public"), ("private", "Private")], required=False
    )
    current_class = serializers.ChoiceField(
        choices=[("SS1", "SS1"), ("SS2", "SS2"), ("SS3", "SS3")], required=False
    )

    # Volunteer specific
    occupation = serializers.CharField(max_length=50, required=False)

    # Shared
    state = serializers.CharField(max_length=50)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        return value

    def validate_phone(self, value):
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value

    def validate_first_name(self, value):
        return normalize_title(value)

    def validate_last_name(self, value):
        return normalize_title(value)

    def validate_school_name(self, value):
        return normalize_title(value)

    def validate_occupation(self, value):
        return normalize_title(value)

    def validate(self, data):
        user_type = data.get("user_type")
        document_type = data.get("document_type")

        if data.get("consent", "").lower() != "true":
            raise serializers.ValidationError(
                {"consent": _("You must accept the consent.")}
            )

        if user_type == "candidate":
            required_fields = ["school_name", "school_type", "current_class"]
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(
                        {field: _("This field is required for candidates.")}
                    )

            valid_doc_types = ["school ID card", "report card", "NIN"]
            if document_type not in valid_doc_types:
                raise serializers.ValidationError(
                    {
                        "document_type": f"Invalid document type for candidate. Allowed: {', '.join(valid_doc_types)}"
                    }
                )

        elif user_type == "volunteer":
            if not data.get("occupation"):
                raise serializers.ValidationError(
                    {"occupation": _("This field is required for volunteers.")}
                )

            valid_doc_types = ["NIN", "passport", "drivers license"]
            if document_type not in valid_doc_types:
                raise serializers.ValidationError(
                    {
                        "document_type": f"Invalid document type for volunteer. Allowed: {', '.join(valid_doc_types)}"
                    }
                )

        document = data.get("document")
        if document:
            try:
                validate_document_file(document)
            except (serializers.ValidationError, DjangoValidationError) as e:
                detail = (
                    e.messages if isinstance(e, DjangoValidationError) else e.detail
                )
                raise serializers.ValidationError({"document": detail})

        face_capture = data.get("face_capture")
        if face_capture:
            try:
                validate_face_id(face_capture)
            except (serializers.ValidationError, DjangoValidationError) as e:
                detail = (
                    e.messages if isinstance(e, DjangoValidationError) else e.detail
                )
                raise serializers.ValidationError({"face_capture": detail})

        return data

    @transaction.atomic
    def create(self, validated_data):
        from identity.tasks import upload_user_documents_task

        user_type = validated_data.get("user_type")
        email = validated_data.get("email")
        document = validated_data.get("document")
        document_type = validated_data.get("document_type")
        face_capture = validated_data.get("face_capture")

        password = generate_password()
        user = User.objects.create_user(
            email=email,
            password=password,
            username=email,
            first_name=validated_data.get("first_name"),
            last_name=validated_data.get("last_name"),
            phone=validated_data.get("phone"),
            state=validated_data.get("state"),
            is_active=True,
            is_email_verified=False,
        )

        UserVerification.objects.create(
            user=user,
            verification_document_type=document_type,
        )

        if user_type == "candidate":
            profile = Candidate.objects.create(
                user=user,
                school_name=validated_data.get("school_name"),
                school_type=validated_data.get("school_type"),
                current_class=validated_data.get("current_class"),
                role=Candidate.Roles.SCREENING,
            )
            from competition.models import (
                Competition,
                Enrollment,
                EnrollmentStageProgress,
            )

            active_comp = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()
            if active_comp:
                first_stage = active_comp.stages.order_by("order").first()
                if first_stage:
                    enrollment = Enrollment.objects.create(
                        candidate=profile,
                        competition=active_comp,
                        current_stage=first_stage,
                        status=Enrollment.Status.PENDING,
                    )
                    EnrollmentStageProgress.objects.create(
                        enrollment=enrollment,
                        stage=first_stage,
                        status=EnrollmentStageProgress.Status.IN_PROGRESS,
                    )
        else:
            profile = Staff.objects.create(
                user=user,
                occupation=validated_data.get("occupation"),
                role=Staff.Roles.VOLUNTEER,
            )
        profile._generated_password = password

        temp_dir = os.path.join(settings.BASE_DIR, "media", "temp_uploads")
        os.makedirs(temp_dir, exist_ok=True)

        file_mappings = []

        if document:
            doc_ext = os.path.splitext(document.name)[1]
            doc_temp_name = f"{uuid.uuid4()}_verification_document{doc_ext}"
            doc_temp_path = os.path.join(temp_dir, doc_temp_name)

            with open(doc_temp_path, "wb") as dest:
                for chunk in document.chunks():
                    dest.write(chunk)

            file_mappings.append(
                {
                    "temp_path": doc_temp_path,
                    "field_name": "verification_document",
                    "original_name": document.name,
                }
            )

        if face_capture:
            face_ext = os.path.splitext(face_capture.name)[1]
            face_temp_name = f"{uuid.uuid4()}_face_id{face_ext}"
            face_temp_path = os.path.join(temp_dir, face_temp_name)

            with open(face_temp_path, "wb") as dest:
                for chunk in face_capture.chunks():
                    dest.write(chunk)

            file_mappings.append(
                {
                    "temp_path": face_temp_path,
                    "field_name": "face_id",
                    "original_name": face_capture.name,
                }
            )

        def schedule_upload():
            upload_user_documents_task.delay(user.pk, file_mappings)

        transaction.on_commit(schedule_upload)
        return profile


class PreRegUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreRegUser
        fields = ["full_name", "email", "phone", "interest_type", "created_at"]
        read_only_fields = ["created_at"]

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        if PreRegUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("This email has already been pre-registered.")
            )
        return value

    def validate_phone(self, value):
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value

    def validate_full_name(self, value):
        return normalize_title(value)


class BaseRegistrationSerializer(serializers.ModelSerializer):
    """Abstract base serializer for staff invite user creation."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    phone = serializers.CharField(max_length=17)
    state = serializers.CharField(max_length=50, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
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
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value

    def validate_first_name(self, value):
        return normalize_title(value)

    def validate_last_name(self, value):
        return normalize_title(value)

    def validate(self, attrs):
        if not self.initial_data.get("generate_password"):
            if attrs["password"] != attrs["password2"]:
                raise serializers.ValidationError(
                    {"password2": "Passwords do not match."}
                )
        return attrs

    def create_user(self, user_data, password):
        return User.objects.create_user(
            email=user_data["email"],
            password=password,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            phone=user_data["phone"],
            state=user_data.get("state", ""),
        )

    def create(self, validated_data):
        user_data = {
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "phone": validated_data.pop("phone"),
            "state": validated_data.pop("state", ""),
        }
        password = validated_data.pop("password", None)
        validated_data.pop("password2", None)
        validated_data.pop("generate_password", None)

        try:
            with transaction.atomic():
                user = self.create_user(user_data, password)
                profile = self.Meta.model.objects.create(user=user, **validated_data)
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


class StaffInviteSerializer(BaseRegistrationSerializer):
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
            "state",
            "password",
            "password2",
            "role",
            "occupation",
            "created_by",
            "generate_password",
        ]

    def validate_role(self, value):
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
