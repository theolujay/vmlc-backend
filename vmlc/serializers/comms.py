from rest_framework import serializers


class BulkNotificationSerializer(serializers.Serializer):
    """
    Serializer for validating bulk notification requests.
    Subject is required for email, optional for SMS.
    """
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        help_text="List of user IDs to send notification to"
    )
    message = serializers.CharField(
        required=True,
        help_text="Message content (max 160 chars for SMS)"
    )
    medium = serializers.ChoiceField(
        choices=["email", "sms", "both"],
        required=False,
        default="email",
        help_text="Delivery channel: email, sms, or both"
    )
    subject = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Subject (required for email, optional for SMS)"
    )

    def validate_user_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one user ID is required.")
        return value

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value

    def validate(self, data):
        medium = data.get("medium", "email")
        subject = data.get("subject", "")

        # Subject is required for email
        if medium in ["email", "both"] and not subject.strip():
            raise serializers.ValidationError({
                "subject": "Subject is required for email notifications."
            })

        # SMS message length validation
        if medium in ["sms", "both"] and len(data["message"]) > 160:
            raise serializers.ValidationError({
                "message": "SMS message cannot exceed 160 characters."
            })

        return data
