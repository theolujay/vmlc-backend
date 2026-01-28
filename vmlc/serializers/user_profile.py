from rest_framework import serializers

from vmlc.serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    MinimalUserSerializer,
)

from identity.models import User


class UserProfileDetailSerializer(serializers.Serializer):
    """
    Generic user profile serializer that dynamically delegates to the
    appropriate detailed serializer based on the user's profile type.
    """

    def to_representation(self, instance):
        """
        Dynamically serialize the instance based on whether it's a Candidate or Staff.
        """
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
    """
    Serializer for listing users with their profile type (Staff or Candidate).
    Combines fields from both StaffListSerializer and CandidateListSerializer.
    """

    user = MinimalUserSerializer(source="*")
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

    def get_profile_type(self, obj: User):
        if hasattr(obj, "staff_profile"):
            return "staff"
        if hasattr(obj, "candidate_profile"):
            return "candidate"
        return None

    def get_role(self, obj: User):
        if hasattr(obj, "staff_profile"):
            return obj.staff_profile.role
        if hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.role
        return None

    def get_status(self, obj: User):
        if hasattr(obj, "staff_profile"):
            return obj.staff_profile.status
        if hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.status
        return "inactive"

    def get_occupation(self, obj: User):
        if hasattr(obj, "staff_profile"):
            return obj.staff_profile.occupation
        return None

    def get_school_name(self, obj: User):
        if hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.school_name
        return None

    def get_school_type(self, obj: User):
        if hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.school_type
        return None

    def get_current_class(self, obj: User):
        if hasattr(obj, "candidate_profile"):
            return obj.candidate_profile.current_class
        return None