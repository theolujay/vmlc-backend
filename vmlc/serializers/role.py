from rest_framework import serializers

from ..models import Candidate, Staff


class CandidateRoleSerializer(serializers.ModelSerializer):
    """Serializer for updating a Candidate's role."""

    class Meta:
        model = Candidate
        fields = ["role"]

    def validate_role(self, value):
        """
        Validate the role assignment.

        - Ensures the role is a valid choice.
        """
        valid_roles: list[str] = [role[0] for role in Candidate.Roles.choices]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"'{value}' is not a valid role. "
                f"Valid choices are: {', '.join(valid_roles)}."
            )
        return value


class StaffRoleSerializer(serializers.ModelSerializer):
    """Serializer for updating a Staff member's role."""

    class Meta:
        model = Staff
        fields = ["role"]

    def validate_role(self, value):
        """
        Validate the role assignment.

        - Ensures the role is a valid choice.
        - Prevents assigning 'superadmin'.
        - Prevents managers from assigning 'manager' roles.
        """
        valid_roles: list[str] = [role[0] for role in Staff.Roles.choices]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"'{value}' is not a valid role. "
                f"Valid choices are: {', '.join(valid_roles)}."
            )

        if value == "superadmin":
            raise serializers.ValidationError(
                "The 'superadmin' role cannot be assigned via the API."
            )

        user = self.context["request"].user

        if hasattr(user, "staff_profile") and user.staff_profile.role == "manager":
            if value == "manager":
                raise serializers.ValidationError(
                    "Managers cannot assign the 'manager' role."
                )

        return value
