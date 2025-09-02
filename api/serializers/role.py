from rest_framework import serializers


from ..models import Candidate, Staff
from ..utils.user import validate_role_for_serializer


class CandidateRoleSerializer(serializers.ModelSerializer):
    """Serializer for updating a Candidate's role."""

    class Meta:
        model = Candidate
        fields = ["role"]

    def validate_role(self, value):
        validate_role_for_serializer(value, Candidate)
        return value


class StaffRoleSerializer(serializers.ModelSerializer):
    """Serializer for updating a Staff member's role."""

    class Meta:
        model: Staff = Staff
        fields = ["role"]

    def validate_role(self, value):
        validate_role_for_serializer(value, Staff)
        return value
