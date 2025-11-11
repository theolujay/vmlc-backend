from rest_framework import serializers

from .models import (
    Broadcast,
    BroadcastLog,
    Notification,
)
from vmlc.serializers.staff import MinimalStaffSerializer


class BroadcastListSerializer(serializers.ModelSerializer):
    """Serializer for listing broadcasts made"""

    created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "subject",
            "message",
            "created_by",
            "created_at",
            "mediums",
            "target_roles",
        ]


class BroadcastLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BroadcastLog
        fields = ["id", "medium", "target_role", "status", "message", "attempted_at"]


class BroadcastDetailSerializer(serializers.ModelSerializer):
    created_by = MinimalStaffSerializer(read_only=True)
    logs = BroadcastLogSerializer(many=True, read_only=True)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "subject",
            "message",
            "created_by",
            "created_at",
            "mediums",
            "target_roles",
            "status",
            "last_attempt",
            "logs",
        ]
        read_only_fields = ["id", "created_at", "status", "last_attempt", "logs"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "subject",
            "message",
            "read",
            "created_at",
        )
