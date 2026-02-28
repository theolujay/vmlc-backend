from rest_framework import serializers

from identity.models import User
from vmlc.serializers.staff import MinimalStaffSerializer

from .models import (
    PublicSupportRequest,
    HelpdeskThread,
    ThreadMessage,
    Broadcast,
    BroadcastLog,
    Notification,
)


class UUIDPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        return str(value)


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

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "You must consent to us contacting you about this inquiry."
            )
        return value


# ============================================================
# Thread Messages
# ============================================================
class ThreadMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = ThreadMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "sender_type",
            "text",
            "metadata",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "sender",
            "sender_type",
            "created_at",
        ]

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.reads.filter(user=request.user).exists()


class HelpdeskThreadListSerializer(serializers.ModelSerializer):
    unread_by_staff_count = serializers.SerializerMethodField()
    candidate_email = serializers.CharField(
        source="candidate.user.email", read_only=True
    )
    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    assigned_staff_name = serializers.CharField(
        source="assigned_staff.user.get_full_name", read_only=True
    )
    candidate_last_msg_preview = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    last_message_sender_type = serializers.SerializerMethodField()
    is_unattended = serializers.SerializerMethodField()

    class Meta:
        model = HelpdeskThread
        fields = [
            "id",
            "candidate_email",
            "candidate_name",
            "assigned_staff",
            "assigned_staff_name",
            "status",
            "priority",
            "last_message_at",
            "unread_by_staff_count",
            "candidate_last_msg_preview",
            "is_online",
            "last_message_sender_type",
            "is_unattended",
            "created_at",
        ]

    def get_unread_by_staff_count(self, obj):
        return (
            obj.messages.filter(sender_type=ThreadMessage.SenderType.CANDIDATE)
            .exclude(reads__user__staff_profile__isnull=False)
            .count()
        )

    def get_candidate_last_msg_preview(self, obj):
        candidate_last_msg = (
            obj.messages.filter(sender_type="candidate").order_by("-created_at").first()
        )
        if candidate_last_msg:
            return candidate_last_msg.text[:100] + (
                "..." if len(candidate_last_msg.text) > 100 else ""
            )
        return ""

    def get_is_online(self, obj):
        from django.core.cache import cache

        return cache.get(f"user_online_{obj.candidate.user_id}") is not None

    def get_last_message_sender_type(self, obj):
        # Prefer using annotated value if available for performance in list views
        if hasattr(obj, "last_msg_sender_type"):
            return obj.last_msg_sender_type
        
        last_msg = obj.messages.order_by("-created_at").first()
        return last_msg.sender_type if last_msg else None

    def get_is_unattended(self, obj):
        sender_type = self.get_last_message_sender_type(obj)
        return sender_type == ThreadMessage.SenderType.CANDIDATE


# ============================================================
# Helpdesk Thread (Detail)
# ============================================================
class HelpdeskThreadDetailSerializer(serializers.ModelSerializer):
    messages = ThreadMessageSerializer(many=True, read_only=True)
    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_email = serializers.CharField(
        source="candidate.user.email", read_only=True
    )
    candidate_phone = serializers.CharField(
        source="candidate.user.phone", read_only=True
    )
    assigned_staff_name = serializers.CharField(
        source="assigned_staff.user.get_full_name", read_only=True
    )
    participating_staff_names = serializers.SerializerMethodField()
    last_message_sender_type = serializers.SerializerMethodField()

    class Meta:
        model = HelpdeskThread
        fields = [
            "id",
            "candidate_name",
            "candidate_email",
            "candidate_phone",
            "assigned_staff",
            "assigned_staff_name",
            "participating_staff_names",
            "status",
            "priority",
            "last_message_at",
            "last_message_sender_type",
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

    def get_candidate_phone(self, obj):
        from comms.utils import _normalize_phone

        return _normalize_phone(self.candidate_phone)

    def get_participating_staff_names(self, obj):
        # Retrieve unique staff members who have sent messages in this thread
        staff_users = User.objects.filter(
            sent_helpdesk_messages__thread=obj,
            sent_helpdesk_messages__sender_type=ThreadMessage.SenderType.STAFF,
        ).distinct()
        return [user.get_full_name() for user in staff_users]


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
            "sms_message",
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

    def validate_target_roles(self, value):
        from identity.models import Staff, Candidate

        if not isinstance(value, dict):
            raise serializers.ValidationError("target_roles must be a dictionary.")

        valid_keys = {"staff", "candidate"}
        invalid_keys = set(value.keys()) - valid_keys
        if invalid_keys:
            raise serializers.ValidationError(
                f"Invalid keys in target_roles: {invalid_keys}"
            )

        if "staff" in value:
            valid_staff_roles = {choice[0] for choice in Staff.Roles.choices}
            invalid = set(value["staff"]) - valid_staff_roles
            if invalid:
                raise serializers.ValidationError(f"Invalid staff roles: {invalid}")

        if "candidate" in value:
            valid_candidate_roles = {choice[0] for choice in Candidate.Roles.choices}
            invalid = set(value["candidate"]) - valid_candidate_roles
            if invalid:
                raise serializers.ValidationError(f"Invalid candidate roles: {invalid}")

        return value


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


class WebSocketThreadMessageSerializer(serializers.ModelSerializer):
    sender = UUIDPrimaryKeyRelatedField(queryset=User.objects.all())
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)

    class Meta:
        model = ThreadMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "sender_type",
            "text",
            "metadata",
            "created_at",
        ]
