from rest_framework import serializers

from vmlc.serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    MinimalUserSerializer,
)

from vmlc.models import User, Staff, Candidate

class UserProfileDetailSerializer(serializers.Serializer):
    """
    Generic user profile serializer that dynamically delegates to the
    appropriate detailed serializer based on the user's profile type.
    """

    def to_representation(self, instance):
        """
        Dynamically serialize the instance based on whether it's a Candidate or Staff.
        """
        if hasattr(instance, "candidate_profile"):
            return CandidateDetailSerializer(instance.candidate_profile).data
        if hasattr(instance, "staff_profile"):
            return StaffDetailSerializer(instance.staff_profile).data

        return super().to_representation(instance)

class UserProfileListSerializer(serializers.Serializer):
    """
    Serializer for listing users with their profile type (Staff or Candidate).
    Combines fields from both StaffListSerializer and CandidateListSerializer.
    """
    
    user = MinimalUserSerializer(source='*')
    profile_type = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    occupation = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()
    is_user_verified = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "user",
            "profile_type",
            "role",
            "status",
            "occupation",
            "school",
            "is_user_verified",
        ]

    def get_profile_type(self, obj: User):
        if hasattr(obj, 'staff_profile'):
            return 'staff'
        if hasattr(obj, 'candidate_profile'):
            return 'candidate'
        return None

    def get_role(self, obj: User):
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.role
        if hasattr(obj, 'candidate_profile'):
            return obj.candidate_profile.role
        return None

    def get_status(self, obj: User):
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.get_status
        if hasattr(obj, 'candidate_profile'):
            return obj.candidate_profile.get_status
        return 'inactive'

    def get_occupation(self, obj: User):
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.occupation
        return None

    def get_school(self, obj: User):
        if hasattr(obj, 'candidate_profile'):
            return obj.candidate_profile.school
        return None

    def get_is_user_verified(self, obj: User):
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.is_user_verified
        if hasattr(obj, 'candidate_profile'):
            return obj.candidate_profile.is_user_verified
        if hasattr(obj, "verification"):
             return obj.verification.is_approved
        return False