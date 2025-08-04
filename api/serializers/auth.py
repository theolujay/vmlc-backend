
from datetime import timezone
import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.core.exceptions import ValidationError

from ..utils.auth import send_password_change_otp, verify_otp_for_password_change
from ..models import (
    EmailOTP,
    User,
)


User = get_user_model()
logger = logging.getLogger(__name__)

class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_otp(self, value):
        """Validate OTP format."""
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain only digits.')
        return value

    def validate(self, data):
        """Validate email and OTP combination."""
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or OTP.')

        # Check if email is already verified
        if user.is_email_verified:
            raise serializers.ValidationError('Email is already verified.')

        try:
            # Get the most recent valid OTP for this user
            otp_obj = EmailOTP.objects.filter(
                user=user, 
                otp=data['otp']
            ).order_by('-created_at').first()
            
            if not otp_obj:
                raise serializers.ValidationError('Invalid email or OTP.')
                
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError('Invalid email or OTP.')

        # Check if OTP is expired
        if otp_obj.is_expired():
            raise serializers.ValidationError('OTP has expired. Please request a new one.')

        # Store user and otp_obj for save method
        data['user'] = user
        data['otp_obj'] = otp_obj
        return data

    def save(self):
        """Mark email as verified and invalidate OTP."""
        user = self.validated_data['user']
        otp_obj = self.validated_data['otp_obj']
        
        # Mark email as verified
        user.is_email_verified = True
        user.save()
        
        # Invalidate the OTP (mark as expired instead of deleting for audit)
        otp_obj.expires_at = timezone.now()
        otp_obj.save()
        
        logger.info(f"Email verified successfully for user {user.id}")
        return user


class ResendEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate email and check if user exists."""
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No account found with this email address.")

        if user.is_email_verified:
            raise serializers.ValidationError("Email is already verified.")

        # Store user in context for later use
        self.context['user'] = user
        return value

    def save(self):
        """Resend OTP to user's email."""
        user = self.context['user']
        from ..utils.auth import resend_otp_to_email
        resend_otp_to_email(user)
        return user

class RequestPasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for requesting password change OTP.
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """
        Check if user exists with this email.
        """
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email address.")
        return value
    
    def save(self):
        """
        Send OTP for password change.
        """
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        send_password_change_otp(user)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing password with OTP verification.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate_email(self, value):
        """
        Check if user exists with this email.
        """
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email address.")
        return value
    
    def validate_otp_code(self, value):
        """
        Validate OTP format (6 digits).
        """
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value
    
    def validate_new_password(self, value):
        """
        Validate password strength using Django's validators.
        """
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def validate(self, data):
        """
        Validate that passwords match and OTP is correct.
        """
        # Check password confirmation
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        # Verify OTP
        user = User.objects.get(email=data['email'])
        if not verify_otp_for_password_change(user, data['otp_code']):
            raise serializers.ValidationError("Invalid or expired OTP code.")
        
        return data
    
    def save(self):
        """
        Change the user's password.
        """
        email = self.validated_data['email']
        new_password = self.validated_data['new_password']
        
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        
        logger.info(f"Password changed successfully for user {user.id}")
        return user