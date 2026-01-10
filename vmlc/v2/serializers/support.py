from rest_framework import serializers
from vmlc.models import SupportInquiry

class SupportInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportInquiry
        fields = [
            "full_name",
            "email",
            "phone",
            "support_type",
            "message",
            "organization",
            "consent",
        ]
        extra_kwargs = {
            "consent": {"required": True},
        }

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("You must consent to be contacted.")
        return value
