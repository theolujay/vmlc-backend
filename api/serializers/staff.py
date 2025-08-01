
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
        fields = (
            "user",
            "role",
            # "profile_photo",
            "occupation",
            # "is_verified",
            # "date_created"
        )


class StaffDetailSerializer(serializers.ModelSerializer):
    """
    Detailed staff serializer.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = (
            "user",
            "phone",
            "occupation",
            "profile_photo",
            "role",
            "is_verified",
            "is_active",
            "date_created",
            "date_updated",
        )
        read_only_fields = ("date_created", "date_updated", "user")

