from rest_framework import serializers

from identity.models import Staff
from identity.serializers.user import UserSerializer, MinimalUserSerializer


class MinimalStaffSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = ["user", "occupation", "role"]


class StaffListSerializer(serializers.ModelSerializer):
    user = MinimalUserSerializer(read_only=True)
    status = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "user",
            "role",
            "status",
            "occupation",
            "profile_type",
        ]

    def get_status(self, obj: Staff):
        return obj.status

    def get_profile_type(self, obj):
        return "staff"


class StaffDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    verification_document = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = [
            "user",
            "profile_type",
            "occupation",
            "role",
            "is_active",
            "status",
            "verification_document",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "user"]

    def get_face_id(self, obj: Staff):
        if obj.face_id and hasattr(obj.face_id, "url"):
            return obj.face_id.url
        return None

    def get_verification_document(self, obj: Staff):
        if obj.verification_document and hasattr(obj.verification_document, "url"):
            return obj.verification_document.url
        return None

    def get_id_card(self, obj: Staff):
        if obj.id_card and hasattr(obj.id_card, "url"):
            return obj.id_card.url
        return None

    def get_profile_type(self, obj: Staff):
        return "staff"

    def get_status(self, obj: Staff):
        return obj.status
