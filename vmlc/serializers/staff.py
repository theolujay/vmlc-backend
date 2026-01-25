from rest_framework import serializers

from ..models import (
    Staff,
)

from .user import UserSerializer, MinimalUserSerializer


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

    user = MinimalUserSerializer(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "user",
            "role",
            "status",
            "occupation",
            "is_user_verified",
        ]

    def get_status(self, obj: Staff):
        return obj.status


class StaffDetailSerializer(serializers.ModelSerializer):
    """
    Detailed staff serializer.
    """

    user = UserSerializer(read_only=True)
    # face_id = serializers.SerializerMethodField()
    # id_card = serializers.SerializerMethodField()
    verification_document = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "user",
            "profile_type",
            "occupation",
            "role",
            "is_active",
            "status",
            "verification_document",
            "created_at",
            "updated_at",
            # "id_card",
            # "face_id",
            # "is_user_verified",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]

    def get_face_id(self, obj: Staff):
        """
        Safely returns the face ID URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded a face ID.
        """
        if obj.face_id and hasattr(obj.face_id, "url"):
            return obj.face_id.url
        return None

    def get_verification_document(self, obj: Staff):
        """
        Safely returns the verification document URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded a verification document.
        """
        if obj.verification_document and hasattr(obj.verification_document, "url"):
            return obj.verification_document.url
        return None

    def get_id_card(self, obj: Staff):
        """
        Safely returns the ID card URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded an ID card.
        """
        if obj.id_card and hasattr(obj.id_card, "url"):
            return obj.id_card.url
        return None

    def get_profile_type(self, obj: Staff):
        return "staff"

    def get_status(self, obj: Staff):
        return obj.status
