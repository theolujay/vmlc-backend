from rest_framework import serializers
from django.db.models import Count, Q

from vmlc.serializers.staff import MinimalStaffSerializer

from .models import (
    PublicSupportRequest,
    SupportChatThread,
    ThreadMessage,
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
            "full_name",
            "email",
            "organization",
            "phone",
            "type",
            "message",
            "consent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ============================================================
# Thread Messages
# ============================================================
class ThreadMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source="sender.get_full_name",
        read_only=True
    )
    sender_type = serializers.CharField(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = ThreadMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "sender_type",
            "message_type",
            "text",
            "attachment",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "sender_type",
        ]

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.reads.filter(user=request.user).exists()


class SupportChatThreadListSerializer(serializers.ModelSerializer):
    unread_count = serializers.SerializerMethodField()
    user_email = serializers.CharField(source="user.email", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.user.get_full_name", read_only=True)
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = SupportChatThread
        fields = [
            "id",
            "user_email",
            "assigned_to_name",
            "status",
            "priority",
            "message",
            "last_message_at",
            "unread_count",
            "last_message_preview",
            "created_at",
        ]

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.exclude(reads__user=request.user).count()

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return last_msg.text[:100] + ("..." if len(last_msg.text) > 100 else "")
        return obj.message[:100] + ("..." if len(obj.message) > 100 else "")


# ============================================================
# Support Thread (Detail)
# ============================================================
class SupportChatThreadDetailSerializer(serializers.ModelSerializer):
    messages = ThreadMessageSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = SupportChatThread
        fields = [
            "id",
            "user_name",
            "user_email",
            "assigned_to",
            "status",
            "priority",
            "message",
            "last_message_at",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_message_at",
            "created_at",
            "updated_at",
        ]


class BroadcastLogSerializer(serializers.ModelSerializer):
    duration = serializers.ReadOnlyField()

    class Meta:
        model = BroadcastLog
        fields = [
            "id",
            "medium",
            "target_role",
            "role_type",
            "status",
            "recipient_count",
            "message",
            "sent_at",
            "attempted_at",
            "duration",
        ]


class BroadcastListSerializer(serializers.ModelSerializer):
    created_by = MinimalStaffSerializer(read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)
    is_sent = serializers.BooleanField(read_only=True)

    class Meta:
        model = Broadcast
        fields = [
            "id",
            "subject",
            "status",
            "created_by",
            "created_at",
            "mediums",
            "target_roles",
            "sent_at",
            "scheduled_at",
            "is_scheduled",
            "is_sent",
            "retry_count",
        ]


class BroadcastDetailSerializer(serializers.ModelSerializer):
    created_by = MinimalStaffSerializer(read_only=True)
    logs = BroadcastLogSerializer(many=True, read_only=True)
    duration = serializers.ReadOnlyField()

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
            "total_recipients",
            "scheduled_at",
            "last_attempt",
            "sent_at",
            "retry_count",
            "task_id",
            "duration",
            "logs",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_recipients",
            "last_attempt",
            "sent_at",
            "retry_count",
            "task_id",
            "duration",
            "logs",
            "created_at",
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
            "subject",
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
