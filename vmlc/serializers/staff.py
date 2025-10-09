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

    class Meta:
        model = Staff
        fields = [
            "user",
            "occupation",
            "profile_photo",
            "role",
            "is_active",
            "is_verified",
            "id_card",
            "verification_document",
            "date_created",
            "date_updated",
        ]
        read_only_fields = ["date_created", "date_updated", "user"]
        
    def get_profile_photo(self, obj: Staff):
        """
        Safely returns the profile photo URL if it exists, otherwise returns None.
        This prevents errors when a staff member hasn't uploaded a profile photo.
        """
        if obj.profile_photo and hasattr(obj.profile_photo, 'url'):
            return obj.profile_photo.url
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