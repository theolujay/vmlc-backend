from rest_framework import serializers
from typing import List

from ..models import (
    Staff,
)

from .user import UserSerializer


class MinimalStaffSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing staff info.
    """

    user: UserSerializer = UserSerializer(read_only=True)

    class Meta:
        model: Staff = Staff
        fields: List[str] = ["user"]


class StaffListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing staff info.
    """

    user: UserSerializer = UserSerializer(read_only=True)

    class Meta:
        model: Staff = Staff
        fields: List[str] = (
            "user",
            "role",
            "occupation",
        )


class StaffDetailSerializer(serializers.ModelSerializer):
    """
    Detailed staff serializer.
    """

    user: UserSerializer = UserSerializer(read_only=True)

    class Meta:
        model: Staff = Staff
        fields: List[str] = (
            "user",
            "occupation",
            "profile_photo",
            "role",
            "is_active",
            "is_verified",
            "id_card",
            "utility_bill",
            "date_created",
            "date_updated",
        )
        read_only_fields: List[str] = ("date_created", "date_updated", "user")
