from rest_framework import serializers
from django.db.models import Count, Q

from vmlc.serializers.staff import MinimalStaffSerializer

from .models import (
    PublicSupportRequest,
    SupportTicket,
    TicketMessage,
    MessageRead,
    Broadcast,
    BroadcastLog,
    Notification,
)

class PublicSupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicSupportRequest
        fields = [
            "id",
            "name",
            "email",
            "subject",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ============================================================
# Ticket Messages
# ============================================================
class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source="sender.get_full_name",
        read_only=True
    )
    sender_type = serializers.CharField(read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "sender_type",
            "message_type",
            "text",
            "attachment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "sender_type",
        ]


class SupportTicketListSerializer(serializers.ModelSerializer):
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "status",
            "priority",
            "last_message_at",
            "unread_count",
            "created_at",
        ]

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        # Count messages that do not have a read record for this user
        return obj.messages.exclude(
            reads__user=request.user
        ).count()


# ============================================================
# Support Ticket (Detail)
# ============================================================
class SupportTicketDetailSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "status",
            "priority",
            "subject",
            "description",
            "assigned_to",
            "last_message_at",
            "messages",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "last_message_at",
            "created_at",
        ]

class BroadcastCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broadcast
        fields = [
            "subject",
            "message",
            "target_roles",
            "scheduled_at",
            "created_by",
        ]


class BroadcastListSerializer(serializers.ModelSerializer):
    created_by = MinimalStaffSerializer(read_only=True)
    class Meta:
        model = Broadcast
        fields = [
            "id",
            "subject",
            "message",
            "status",
            "created_by",
            "created_at",
            "mediums",
            "target_roles",
            "sent_at",
        ]


class BroadcastDetailSerializer(serializers.ModelSerializer):
    created_by = MinimalStaffSerializer(read_only=True)
    logs = serializers.SerializerMethodField()

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "subject",
            "message",
            "target_roles",
            "mediums",
            "created_by",
            "status",
            "created_at",
            "scheduled_at",
            "sent_at",
            "last_attempt",
            "logs",
        ]
        read_only_fields = ["id", "created_at", "status", "sent_at", "logs"]

    def get_logs(self, obj):
        return BroadcastLogSerializer(
            obj.logs.all(),
            many=True
        ).data


class BroadcastLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BroadcastLog
        fields = [
            "id",
            "medium",
            "target_role",
            "role_type",
            "status",
            "message",
            "attempted_at",
        ]


# ============================================================
# Notifications
# ============================================================

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "message",
            "link",
            "metadata",
            "is_read",
            "created_at",
            "expires_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]
