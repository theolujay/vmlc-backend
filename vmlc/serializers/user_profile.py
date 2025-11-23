"""
This module provides a generic user profile serializer.
"""
from rest_framework import serializers

from ..models import Candidate, Staff
from .candidate import CandidateDetailSerializer
from .staff import StaffDetailSerializer


class UserProfileDetailSerializer(serializers.Serializer):
    """
    Generic user profile serializer that dynamically delegates to the
    appropriate detailed serializer based on the user's profile type.
    """

    def to_representation(self, instance):
        """
        Dynamically serialize the instance based on whether it's a Candidate or Staff.
        """
        if isinstance(instance, Candidate):
            return CandidateDetailSerializer(instance).data
        if isinstance(instance, Staff):
            return StaffDetailSerializer(instance).data

        # Optionally, handle cases where the instance is not a recognized profile
        return super().to_representation(instance)

