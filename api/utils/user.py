"""
User-related utility functions.
"""

from rest_framework import serializers


def validate_role_for_serializer(value: str, model_class) -> None:
    """
    Validator for a role field on a serializer.
    Raises serializers.ValidationError if the role is not a valid choice.
    """
    valid_roles = [role[0] for role in model_class.Roles.choices]
    if value not in valid_roles:
        raise serializers.ValidationError(
            f"'{value}' is not a valid role. "
            f"Valid choices are: {', '.join(valid_roles)}."
        )
