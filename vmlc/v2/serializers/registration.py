import os
import uuid
from django.conf import settings
from django.db import transaction
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
from vmlc.models import (
    SupportInquiry,
)
from vmlc.utils.auth import generate_password
from vmlc.utils.user import normalize_title
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
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        return value

    def validate_phone(self, value):
        """Validate phone number format."""
        import re

        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value

    def validate_first_name(self, value):
        """Normalize first name to title case."""
        return normalize_title(value)

    def validate_last_name(self, value):
        """Normalize last name to title case."""
        return normalize_title(value)
    
    def validate_school_name(self, value):
        """Normalize school name to title case."""
        return normalize_title(value)
    
    def validate_occupation(self, value):
        """Normalize occupation to title case"""
        return normalize_title(value)

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

        # Validate file content based on intended target (id_card vs verification_document)
        document = data.get("document")
        if document:
            try:
                # if self._is_id_card(user_type, document_type):
                #     validate_id_card_file(document)
                # else:
                validate_document_file(document)
            except (serializers.ValidationError, DjangoValidationError) as e:
                # Re-raise as field error
                detail = e.messages if isinstance(e, DjangoValidationError) else e.detail
                raise serializers.ValidationError({"document": detail})

        # Validate face capture
        face_capture = data.get("face_capture")
        if face_capture:
            try:
                validate_face_id(face_capture)
            except (serializers.ValidationError, DjangoValidationError) as e:
                detail = e.messages if isinstance(e, DjangoValidationError) else e.detail
                raise serializers.ValidationError({"face_capture": detail})

        return data

    # def _is_id_card(self, user_type, document_type):
    #     """Helper to determine if document maps to id_card"""
    #     if user_type == "volunteer":
    #         return True
    #     if user_type == "candidate" and document_type == "NIN":
    #         return True
    #     return False
    @transaction.atomic
    def create(self, validated_data):
        """
        Create user and related objects with async file upload.
        """
        from vmlc.tasks import upload_user_documents_task
        
        user_type = validated_data.get("user_type")
        email = validated_data.get("email")
        document = validated_data.get("document")
        document_type = validated_data.get("document_type")
        face_capture = validated_data.get("face_capture")

        # Create User
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

        # Create UserVerification
        verification = UserVerification.objects.create(
            user=user,
            verification_document_type=document_type,
        )

        # Create Profile (Candidate or Staff/Volunteer)
        if user_type == "candidate":
            profile = Candidate.objects.create(
                user=user,
                school_name=validated_data.get("school_name"),
                school_type=validated_data.get("school_type"),
                current_class=validated_data.get("current_class"),
                role=Candidate.Roles.SCREENING,
            )
            # Auto-enroll in active competition if one exists
            from competition.models import Competition, CandidateCompetition, Stage, CandidateStageProgress
            active_comp = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if active_comp:
                first_stage = active_comp.stages.order_by('order').first()
                if first_stage:
                    participation = CandidateCompetition.objects.create(
                        candidate=profile,
                        competition=active_comp,
                        current_stage=first_stage,
                        status=CandidateCompetition.Status.ACTIVE
                    )
                    CandidateStageProgress.objects.create(
                        candidate_competition=participation,
                        stage=first_stage,
                        status=CandidateStageProgress.Status.IN_PROGRESS
                    )
        else:
            profile = Staff.objects.create(
                user=user,
                occupation=validated_data.get("occupation"),
                role=Staff.Roles.VOLUNTEER,
            )
        profile._generated_password = password

        # Prepare files for async upload - save to temp location
        temp_dir = os.path.join(settings.BASE_DIR, "media", "temp_uploads")
        os.makedirs(temp_dir, exist_ok=True)
        
        file_mappings = []
        
        # Process document file
        if document:
            doc_ext = os.path.splitext(document.name)[1]
            doc_temp_name = f"{uuid.uuid4()}_verification_document{doc_ext}"
            doc_temp_path = os.path.join(temp_dir, doc_temp_name)
            
            with open(doc_temp_path, "wb") as dest:
                for chunk in document.chunks():
                    dest.write(chunk)
            
            file_mappings.append({
                "temp_path": doc_temp_path,
                "field_name": "verification_document",
                "original_name": document.name
            })
        
        # Process face capture file
        if face_capture:
            face_ext = os.path.splitext(face_capture.name)[1]
            face_temp_name = f"{uuid.uuid4()}_face_id{face_ext}"
            face_temp_path = os.path.join(temp_dir, face_temp_name)
            
            with open(face_temp_path, "wb") as dest:
                for chunk in face_capture.chunks():
                    dest.write(chunk)
            
            file_mappings.append({
                "temp_path": face_temp_path,
                "field_name": "face_id",
                "original_name": face_capture.name
            })
        
        # Schedule async upload after transaction commits
        # Use a proper closure to avoid variable capture issues
        def schedule_upload():
            upload_user_documents_task.delay(user.pk, file_mappings)
        
        transaction.on_commit(schedule_upload)
        return profile

class PreRegUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreRegUser
        fields = ['full_name', 'email', 'phone', 'interest_type', 'created_at']
        read_only_fields = ['created_at']
    
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
    
    def validate_phone(self, value):
        """Validate phone number format."""
        import re
        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError(_("Enter a valid Nigerian phone number."))
        return value

    def validate_full_name(self, value):
        """Normalize full name to title case."""
        return normalize_title(value)

class SupportInquirySerializer(serializers.ModelSerializer):

    # full_name = serializers.CharField(max_length=50)
    # email = serializers.EmailField()
    # phone = serializers.CharField(max_length=17)
    # support_type = serializers.ChoiceField(
    #     choices=[
    #         "sponsorship", "partnership", "media_support", "other"
    #     ]
    # )
    # message = serializers.CharField(required=True)

    class Meta:
        model = SupportInquiry
        fields = [
            "full_name",
            "email",
            "phone",
            "support_type",
            "message",
            "organization",
        ]

    def validate_full_name(self, value):
        """Normalize full name to title case."""
        return normalize_title(value)