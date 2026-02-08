from rest_framework import serializers
from vmlc.models import SupportInquiry, SupportMessage
from vmlc.utils.user import normalize_title


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "sender_profile",
            "text",
            "created_at",
            "is_read_by_staff",
            "is_read_by_user",
        ]
        read_only_fields = ["id", "created_at", "sender_profile"]


class SupportConversationSerializer(serializers.ModelSerializer):
    """Serializer for listing conversations with latest message preview"""

    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    user_name = serializers.CharField(source="full_name", read_only=True)

    class Meta:
        model = SupportInquiry
        fields = [
            "id",
            "user_name",
            "email",
            "support_type",
            "status",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return {
                "text": last_msg.text,
                "created_at": last_msg.created_at,
                "sender_profile": last_msg.sender_profile,
            }
        return {
            "text": obj.message,
            "created_at": obj.created_at,
            "sender_profile": "user",
        }

    def get_unread_count(self, obj):
        return obj.messages.filter(is_read_by_staff=False).count()


class SupportConversationDetailSerializer(SupportConversationSerializer):
    """Detailed serializer including full message history"""

    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta(SupportConversationSerializer.Meta):
        fields = SupportConversationSerializer.Meta.fields + [
            "messages",
            "phone",
            "organization",
        ]


class SupportInquirySerializer(serializers.ModelSerializer):
    """Basic serializer for creating inquiries (existing)"""

    class Meta:
        model = SupportInquiry
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "support_type",
            "message",
            "organization",
            "consent",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "consent": {"required": True},
        }

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("You must consent to be contacted.")
        return value

    def validate_full_name(self, value):
        """Normalize full name to title case."""
        return normalize_title(value)
