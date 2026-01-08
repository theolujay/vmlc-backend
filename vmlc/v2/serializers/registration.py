from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from ...models import (
    PreRegUser,
    User,
    Candidate,
    Staff,
    validate_id_card_file,
    validate_document_file,
)
from ...utils.auth import generate_password

class RegistrationV2Serializer(serializers.Serializer):
    """
    Unified serializer for v2 registration (Candidate and Volunteer).
    """

    user_type = serializers.ChoiceField(choices=["candidate", "volunteer"])
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=17)

    # File upload fields
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
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value

    def validate(self, data):
        user_type = data.get("user_type")
        document_type = data.get("document_type")

        # Validate consent
        if data.get("consent", "").lower() != "true":
            raise serializers.ValidationError(
                {"consent": _("You must accept the consent.")}
            )

        # Validate conditional fields
        if user_type == "candidate":
            required_fields = ["school_name", "school_type", "current_class"]
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(
                        {field: _("This field is required for candidates.")}
                    )

            valid_doc_types = ["NIN", "school result"]
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

        # Validate file content based on intended target (id_card vs verification_document)
        document = data.get("document")
        if document:
            try:
                if self._is_id_card(user_type, document_type):
                    validate_id_card_file(document)
                else:
                    validate_document_file(document)
            except serializers.ValidationError as e:
                # Re-raise as field error
                raise serializers.ValidationError({"document": e.detail})

        return data

    def _is_id_card(self, user_type, document_type):
        """Helper to determine if document maps to id_card"""
        if user_type == "volunteer":
            return True
        if user_type == "candidate" and document_type == "NIN":
            return True
        return False

    @transaction.atomic
    def create(self, validated_data):

        import os
        import uuid
        from django.core.files.storage import default_storage
        from vmlc.tasks import upload_user_document_task

        user_type = validated_data.get("user_type")
        email = validated_data.get("email")
        document = validated_data.get("document")
        document_type = validated_data.get("document_type")
        # Create User
        password = generate_password()
        user = User.objects.create_user(
            email=email,
            password=password,
            username=email,  # Using email as username per convention
            first_name=validated_data.get("first_name"),
            last_name=validated_data.get("last_name"),
            phone=validated_data.get("phone_number"),
            state=validated_data.get("state"),
            is_active=True,
            is_email_verified=False,
            # We don't set verification_document here yet to keep response fast
            verification_document_type=document_type,
        )
        # Handle file asynchronously
        if document:
            # Save to a temporary location in the local filesystem
            temp_dir = os.path.join(settings.BASE_DIR, "media", "temp_uploads")
            os.makedirs(temp_dir, exist_ok=True)
            # Use a unique filename to avoid collisions
            ext = os.path.splitext(document.name)[1]
            temp_filename = f"{uuid.uuid4()}{ext}"
            temp_file_path = os.path.join(temp_dir, temp_filename)

            with open(temp_file_path, "wb+") as destination:
                for chunk in document.chunks():
                    destination.write(chunk)
            # Trigger asynchronous upload
            transaction.on_commit(
                lambda: upload_user_document_task.delay(user.pk, temp_file_path)
            )
        # Create Profile (Candidate or Staff/Volunteer)
        if user_type == "candidate":
            profile = Candidate.objects.create(
                user=user,
                school=validated_data.get("school_name"),
                school_type=validated_data.get("school_type"),
                current_class=validated_data.get("current_class"),
                role=Candidate.Roles.SCREENING,
            )
        else:  # volunteer
            profile = Staff.objects.create(
                user=user,
                occupation=validated_data.get("occupation"),
                role=Staff.Roles.VOLUNTEER,
            )
        # Return the profile instance and generated password for the view to handle tasks
        # Attaching password to instance so view can access it
        profile._generated_password = password
        return profile

class PreRegUserSerializer(serializers.Serializer):

    full_name = serializers.CharField(max_length=50)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=17)
    interest_type = serializers.ChoiceField(choices=["candidate", "volunteer"])

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        if PreRegUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("This email has already been pre-registered.")
            )
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format."""
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value
    
    def create(self, validated_data):

        full_name = validated_data.get("full_name")
        email = validated_data.get("email")
        phone_number = validated_data.get("phone_number")
        interest_type = validated_data.get("interest_type")

        interested_user = PreRegUser.objects.create(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            interest_type=interest_type
        )
        return interested_user