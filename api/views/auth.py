"""
Authentication-related API views for login, logout, and registration.
"""
import logging

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from rest_framework import status, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_api_key.permissions import HasAPIKey

from ..utils.auth import resend_otp_to_email
from ..serializers import (
    UserSerializer,
    RequestPasswordChangeSerializer,
    PasswordChangeSerializer,
    VerifyEmailOTPSerializer,
    ResendEmailOTPSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class VerifyEmailOTPView(APIView):
    """
    Handles OTP verification for user registration.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response(
                    {'message': 'Email verified successfully.'}, 
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                logger.error(f"Error during email verification: {str(e)}")
                return Response(
                    {"error": "Verification failed. Please try again."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        logger.warning(f"Email verification failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendEmailOTPView(APIView):
    """
    Resend OTP to user's email with rate limiting.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendEmailOTPSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Mask email for response
                email = user.email
                email_parts = email.split('@')
                masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"
                
                return Response(
                    {
                        "message": "OTP has been resent to your email address",
                        "email": masked_email,
                        "expires_in_minutes": 10
                    },
                    status=status.HTTP_200_OK
                )
                
            except serializers.ValidationError as e:
                # Rate limiting error from utils
                return Response(
                    {"error": str(e)}, 
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            except Exception as e:
                logger.error(f"Unexpected error in resend OTP: {str(e)}")
                return Response(
                    {"error": "Failed to resend OTP. Please try again later."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            

class RequestPasswordChangeView(APIView):
    """
    Request OTP for password change.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Send OTP to user's email for password change verification.
        
        Expected payload:
        {
            "email": "user@example.com"
        }
        """
        serializer = RequestPasswordChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Mask email for response
                email = user.email
                email_parts = email.split('@')
                masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"
                
                return Response(
                    {
                        "message": "Password change verification code sent to your email",
                        "email": masked_email,
                        "expires_in_minutes": 10
                    },
                    status=status.HTTP_200_OK
                )
                
            except serializers.ValidationError as e:
                # Rate limiting error
                return Response(
                    {"error": str(e)}, 
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            except Exception as e:
                logger.error(f"Error requesting password change OTP: {str(e)}")
                return Response(
                    {"error": "Failed to send verification code. Please try again later."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordChangeView(APIView):
    """
    Change user password with OTP verification.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Change password after OTP verification.
        
        Expected payload:
        {
            "email": "user@example.com",
            "otp_code": "123456",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        """
        serializer = PasswordChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                logger.info(f"Password changed successfully for user {user.id}")
                return Response(
                    {
                        "message": "Password changed successfully. Please log in with your new password."
                    },
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                logger.error(f"Error changing password: {str(e)}")
                return Response(
                    {"error": "Failed to change password. Please try again."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendPasswordChangeOTPView(APIView):
    """
    Resend OTP for password change with rate limiting.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Resend password change OTP.
        
        Expected payload:
        {
            "email": "user@example.com"
        }
        """
        try:
            email = request.data.get('email')
            
            if not email:
                return Response(
                    {"error": "Email is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Basic email format validation
            if '@' not in email:
                return Response(
                    {"error": "Please provide a valid email address"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Security: Return generic message
                logger.warning(f"Password change OTP resend attempted for non-existent email: {email[:3]}***")
                return Response(
                    {"message": "If this email is registered, a verification code has been sent"}, 
                    status=status.HTTP_200_OK
                )
            
            # Send OTP
            from ..utils.auth import send_password_change_otp
            send_password_change_otp(user)
            
            # Mask email for response
            email_parts = email.split('@')
            masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"
            
            return Response(
                {
                    "message": "Password change verification code has been resent",
                    "email": masked_email,
                    "expires_in_minutes": 10
                },
                status=status.HTTP_200_OK
            )
            
        except serializers.ValidationError as e:
            # Rate limiting error
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except Exception as e:
            logger.error(f"Unexpected error in resend password change OTP: {str(e)}")
            return Response(
                {"error": "Failed to resend verification code. Please try again later."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token response to include user details.
    """
    def validate(self, attrs):
        # The default result (access/refres tokens)
        data = super().validate(attrs)
        
        # Add user information to the response
        user_serializer = UserSerializer(self.user)
        data["user"] = user_serializer.data
        
        return data
    
class LoginView(TokenObtainPairView):
    """
    Custom login view to handle user authentication and token generation.
    Uses the custom serializer to include user data in the response.
    """
    
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [HasAPIKey]
    throttle_scope = "login"
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        email = request.data.get("email", "N/A")
        if response.status_code == status.HTTP_200_OK:
            logger.info("User with email '%s' logged in successfully.", email)
        else:
            logger.warning("Failed login attempt for email: %s", email)
        return response
    
class LogoutView(APIView):
    """
    Handles user logout by blacklisting the provided refresh token.
    Uses AllowAny permission to handle expired access tokens.
    """
    
    permission_classes = [AllowAny]
    def post(self, request):
        """
        Expects a 'refresh' token in the request body.
        Extracts user info from the refresh token for logging.
        """
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            token = RefreshToken(refresh_token)
            user_id = token.payload.get("user_id")
            token.blacklist()
            
            if user_id:
                logger.info("User %s logged out successfully.", user_id)
            else:
                logger.info("User logged out successfully (no user_id in token")
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except TokenError as e:
            logger.warning("Logout failed with invalid refresh token: %s", str(e))
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error("Logout failed with an unexpected error: %s", str(e))
            return Response(
                {"error": "Logout failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )