from rest_framework import serializers

from identity.serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    MinimalUserSerializer,
)

from identity.models import User


class UserProfileDetailSerializer(serializers.Serializer):
    def to_representation(self, instance):
        from identity.models import Candidate, Staff

        if isinstance(instance, Candidate):
            return CandidateDetailSerializer(instance).data
        if isinstance(instance, Staff):
            return StaffDetailSerializer(instance).data

        if hasattr(instance, "candidate_profile"):
            return CandidateDetailSerializer(instance.candidate_profile).data
        if hasattr(instance, "staff_profile"):
            return StaffDetailSerializer(instance.staff_profile).data

        return {}


class UserProfileListSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    occupation = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    school_type = serializers.SerializerMethodField()
    current_class = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "user",
            "profile_type",
            "role",
            "status",
            "occupation",
            "school_name",
            "school_type",
            "current_class",
        ]

    def get_user(self, obj):
        from identity.models import PreRegUser

        if isinstance(obj, User):
            return MinimalUserSerializer(obj).data

        if isinstance(obj, PreRegUser):
            names = obj.full_name.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""

            return {
                "id": obj.id,
                "email": obj.email,
                "is_email_verified": False,
                "first_name": first_name,
                "last_name": last_name,
                "phone": obj.phone,
                "state": "",
                "date_joined": obj.created_at,
            }

        return None

    def get_profile_type(self, obj):
        from identity.models import PreRegUser

        if isinstance(obj, User):
            if hasattr(obj, "staff_profile"):
                return "staff"
            if hasattr(obj, "candidate_profile"):
                return "candidate"

        if isinstance(obj, PreRegUser):
            if obj.interest_type == "volunteer":
                return "pre_reg_staff"
            return "pre_reg_candidate"

        return None

    def get_role(self, obj):
        from identity.models import PreRegUser

        if isinstance(obj, User):
            if hasattr(obj, "staff_profile"):
                return obj.staff_profile.role
            if hasattr(obj, "candidate_profile"):
                return obj.candidate_profile.role

        if isinstance(obj, PreRegUser):
            return obj.interest_type

        return None

    def get_status(self, obj):
        from identity.models import PreRegUser

        if isinstance(obj, User):
            if hasattr(obj, "staff_profile") and obj.staff_profile:
                return obj.staff_profile.status
            if hasattr(obj, "candidate_profile") and obj.candidate_profile:
                return obj.candidate_profile.status
            return "inactive"

        if isinstance(obj, PreRegUser):
            return "pre_registered"

        return "inactive"

    def get_occupation(self, obj):
        if isinstance(obj, User) and hasattr(obj, "staff_profile"):
            return obj.staff_profile.occupation
        return None

    def get_school_name(self, obj):
        if isinstance(obj, User) and hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.school_name
        return None

    def get_school_type(self, obj):
        if isinstance(obj, User) and hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.school_type
        return None

    def get_current_class(self, obj):
        if isinstance(obj, User) and hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.current_class
        return None
