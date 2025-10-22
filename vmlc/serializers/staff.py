from rest_framework import serializers

from ..models import (
    Staff,
)

from .user import UserSerializer
from .registration import BaseRegistrationSerializer

class MinimalStaffSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing staff info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = ["user", "occupation", "role"]


class StaffListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing staff info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = [
            "user",
            "role",
            "occupation",
        ]


class StaffDetailSerializer(serializers.ModelSerializer):
    """
    Detailed staff serializer.
    """

    user = UserSerializer(read_only=True)
    face_id = serializers.SerializerMethodField()
    id_card = serializers.SerializerMethodField()
    verification_document = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "user",
            "occupation",
            "face_id",
            "role",
            "is_active",
            "is_verified",
            "id_card",
            "verification_document",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]
        
    def get_face_id(self, obj: Staff):
        """
        Safely returns the face ID URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded a face ID.
        """
        if obj.face_id and hasattr(obj.face_id, 'url'):
            return obj.face_id.url
        return None
    def get_verification_document(self, obj: Staff):
        """
        Safely returns the verification document URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded a verification document.
        """
        if obj.verification_document and hasattr(obj.verification_document, 'url'):
            return obj.verification_document.url
        return None
    def get_id_card(self, obj: Staff):
        """
        Safely returns the ID card URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded an ID card.
        """
        if obj.id_card and hasattr(obj.id_card, 'url'):
            return obj.id_card.url
        return None
    
class StaffInviteSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff.
    """
    created_by = MinimalStaffSerializer(read_only=True)
    occupation = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=Staff.Roles.choices)

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
        ]
        
    def validate_role(self, value):
        """
        Validate the role assignment.

        - Ensures the role is a valid choice.
        - Prevents assigning 'superadmin'.
        - Prevents managers from assigning 'manager' roles.
        """
        valid_roles: list[str] = [role[0] for role in Staff.Roles.choices if role[0] != "superadmin"]
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
