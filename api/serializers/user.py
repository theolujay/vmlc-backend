

import logging
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    User,
    UserVerification,
)


User = get_user_model()
logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for the Django User model.
    """
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    def validate_phone(self, value):
        import re
        if not re.match(r"^(\+234[789][01]\d{8}|0[789][01]\d{8})$", value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        return value

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")

class MinimalUserSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing user info.
    """
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone")

class UserVerificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserVerification
        fields = [
            "user",
            "is_pending",
            "is_verified", 
            "profile_photo",
            "id_card",
            "verification_document",
            "date_created",
            "date_updated",
        ]
        read_only_fields = ["user", "is_pending", "is_verified", "date_created", "date_updated"]

    def validate(self, data):
        """
        Custom validation to ensure at least one verification file is provided
        """
        profile_photo = data.get('profile_photo')
        id_card = data.get('id_card') 
        verification_document = data.get('verification_document')
        
        # For new submissions, require at least profile_photo and id_card
        if not self.instance:  # Creating new verification
            if not profile_photo:
                raise serializers.ValidationError({
                    'profile_photo': 'Profile photo is required for verification.'
                })
            if not id_card:
                raise serializers.ValidationError({
                    'id_card': 'ID card is required for verification.'
                })
        
        return data

    def validate_profile_photo(self, value):
        """Additional serializer-level validation for profile photo"""
        if value:
            # Check if it's actually an image by trying to get dimensions
            try:
                # This will raise an exception if it's not a valid image
                value.image.verify()
            except Exception:
                raise serializers.ValidationError("Invalid image file.")
        return value
