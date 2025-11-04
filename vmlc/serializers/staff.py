from rest_framework import serializers

from ..models import (
    Staff,
)

from .user import UserSerializer


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
            "is_user_verified",
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
