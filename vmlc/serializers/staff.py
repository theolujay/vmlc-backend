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
        fields = ["user"]


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
