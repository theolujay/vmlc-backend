from django.contrib.auth import password_validation
from django.db import transaction

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    Candidate,
    Staff,
    User,
    EmailOTP,
)
from .user import UserSerializer


class BaseRegistrationSerializer(serializers.ModelSerializer):
    """
    Abstract base serializer for user registration.
    Handles common user creation and password validation logic.
    """
    user = UserSerializer()
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[password_validation.validate_password],
        style={"input_type": "password"},
        help_text="Required. 8 characters minimum.",
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Confirm password",
    )

    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create_user(self, user_data, password):
        return User.objects.create_user(
            email=user_data["email"],
            password=password,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            phone=user_data["phone"],
        )

    def create(self, validated_data):
        """
        Handles the creation of a User and its associated profile.
        """
        password = validated_data.pop("password")
        validated_data.pop("password2")
        user_data = validated_data.pop("user")
        
        try:
            with transaction.atomic():
                user = self.create_user(user_data, password)
                profile = self.Meta.model.objects.create(user=user, **validated_data)
                return profile
        except Exception as e:
            raise serializers.ValidationError(f"Registration failed: {str(e)}")


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates.
    """
    class Meta:
        model = Candidate
        fields = (
            "user",
            "password", 
            "password2",
            "school",
        )


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff.
    """
    class Meta:
        model = Staff
        fields = (
            "user",
            "password",
            "password2", 
            "occupation",
        )
        

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email.')

        try:
            otp_obj = EmailOTP.objects.filter(user=user, otp=data['otp']).order_by('-created_at').first()
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError('Invalid OTP.')

        if otp_obj.is_expired():
            raise serializers.ValidationError('OTP expired.')

        data['user'] = user
        otp_obj.delete()  # One-time use
        return data

    def save(self):
        user = self.validated_data['user']
        user.is_email_verified = True
        user.save()
        

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user with this email.")

        if user.is_email_verified:
            raise serializers.ValidationError("Email is already verified.")

        self.context['user'] = user
        return value