"""
Authentication-related API views for login, logout, and registration.
"""

import logging

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView

# from channels.db import database_sync_to_async
# from adrf.views import APIView as AdrfAPIView

from ..models import User
from ..permissions import HasXAPIKey
from ..serializers import (
    PasswordChangeOTPConfirmSerializer,
    PasswordChangeSerializer,
    RequestPasswordChangeSerializer,
    ResendEmailOTPSerializer,
    MinimalCandidateSerializer,
    MinimalStaffSerializer,
    VerifyEmailOTPSerializer,
)
from ..tasks import send_mail_task
from ..utils.exceptions import (
    InvalidTokenError,
    NotFound,
    ValidationError,
)

logger = logging.getLogger(__name__)


class VerifyEmailOTPView(APIView):
    """
    Handles OTP verification for user registration.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _verify_email(self, data):
        serializer = VerifyEmailOTPSerializer(data=data)
        if serializer.is_valid():
            try:
                user = serializer.save()

                send_mail_task.delay(
                    subject="Email Verified Successfully",
                    message="Your email has been successfully verified.",
                    recipient_list=[user.email],
                )
                logger.info(f"Email verified successfully for user {user.id}")
                return Response(
                    {"message": "Email verified successfully."},
                    status=status.HTTP_200_OK,
                )
            except User.DoesNotExist:
                raise NotFound("User not found.")
            except Exception as e:
                logger.error(f"Error during email verification: {str(e)}")
                return Response(
                    {"error": "Verification failed. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.warning(f"Email verification failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        return self._verify_email(request.data)


class ResendEmailOTPView(APIView):
    """
    Resend OTP to user's email with rate limiting.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _resend_email_otp(self, data):
        serializer = ResendEmailOTPSerializer(data=data)

        if serializer.is_valid():
            try:
                user = serializer.save()

                # Mask email for response
                email = user.email
                email_parts = email.split("@")
                masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"
                logger.info(f"Resending OTP to user {user.id}")
                return Response(
                    {
                        "message": "OTP has been resent to your email address",
                        "email": masked_email,
                        "expires_in_minutes": 10,
                    },
                    status=status.HTTP_200_OK,
                )

            except serializers.ValidationError as e:
                # Rate limiting error from utils
                raise ValidationError(
                    str(e), status_code=status.HTTP_429_TOO_MANY_REQUESTS
                )
            except Exception as e:
                logger.error(f"Unexpected error in resend OTP: {str(e)}")
                return Response(
                    {"error": "Failed to resend OTP. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        return self._resend_email_otp(request.data)


class RequestPasswordChangeView(APIView):
    """
    Request OTP for password change.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _request_password_change(self, data):
        """
        Send OTP to user's email for password change verification.

        Expected payload:
        {
            "email": "user@example.com"
        }
        """
        serializer = RequestPasswordChangeSerializer(data=data)

        if serializer.is_valid():
            try:
                user = serializer.save()

                # Mask email for response
                email = user.email
                email_parts = email.split("@")
                masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"

                return Response(
                    {
                        "message": "Password change verification code sent to your email",
                        "email": masked_email,
                        "expires_in_minutes": 10,
                    },
                    status=status.HTTP_200_OK,
                )

            except serializers.ValidationError as e:
                # Rate limiting error
                raise ValidationError(
                    str(e), status_code=status.HTTP_429_TOO_MANY_REQUESTS
                )
            except Exception as e:
                logger.error(f"Error requesting password change OTP: {str(e)}")
                return Response(
                    {
                        "error": "Failed to send verification code. Please try again later."
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        return self._request_password_change(request.data)


class PasswordChangeOTPConfirmView(APIView):
    """
    Confirm password change request with OTP.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _confirm_password_change_otp(self, data):
        """
        Change user password after OTP verification.

        Expected payload:
        {
            "email": "user@example.com",
            "otp": "123456"
        }
        """
        serializer = PasswordChangeOTPConfirmSerializer(data=data)

        if serializer.is_valid():
            return Response(
                {
                    "message": "OTP verified. User confirmed for password change. Proceed to change password.",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        return self._confirm_password_change_otp(request.data)


class PasswordChangeView(APIView):
    """
    Change user password with OTP verification.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _change_password(self, data):
        """
        Change password after OTP verification.

        Expected payload:
        {
            "email": "user@example.com",
            "otp": "123456",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        """
        serializer = PasswordChangeSerializer(data=data)

        if serializer.is_valid():
            try:
                user = serializer.save()
                from ..tasks import send_mail_task

                # Send notification email about password change
                send_mail_task.delay(
                    subject="Your Password Has Been Changed",
                    message="This is to inform you that your password has been successfully changed.",
                    recipient_list=[user.email],
                )
                logger.info(f"Password changed successfully for user {user.id}")
                return Response(
                    {
                        "message": "Password changed successfully. Please log in with your new password."
                    },
                    status=status.HTTP_200_OK,
                )

            except Exception as e:
                logger.error(f"Error changing password: {str(e)}")
                return Response(
                    {"error": "Failed to change password. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        return self._change_password(request.data)


class ResendPasswordChangeOTPView(APIView):
    """
    Resend OTP for password change with rate limiting.
    """

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _resend_password_change_otp(self, data):
        """
        Resend password change OTP.

        Expected payload:
        {
            "email": "user@example.com"
        }
        """
        try:
            email = data.get("email")

            if not email:
                raise ValidationError("Email is required")

            # Basic email format validation
            if "@" not in email:
                raise ValidationError("Please provide a valid email address")

            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Security: Return generic message
                logger.warning(
                    f"Password change OTP resend attempted for non-existent email: {email[:3]}***"
                )
                return Response(
                    {
                        "message": "If this email is registered, a verification code has been sent"
                    },
                    status=status.HTTP_200_OK,
                )
            from ..utils.auth import resend_otp_to_email

            resend_otp_to_email(user)
            logger.info(f"Password change OTP resent to user {user.id}")
            # Mask email for response
            email_parts = email.split("@")
            masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"

            return Response(
                {
                    "message": "Password change verification code has been resent",
                    "email": masked_email,
                    "expires_in_minutes": 10,
                },
                status=status.HTTP_200_OK,
            )

        except serializers.ValidationError as e:
            # Rate limiting error
            raise ValidationError(str(e), status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        except Exception as e:
            logger.error(f"Unexpected error in resend password change OTP: {str(e)}")
            return Response(
                {
                    "error": "Failed to resend verification code. Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        return self._resend_password_change_otp(request.data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token response to include user details.
    """

    def validate(self, attrs):
        # The default result (access/refresh tokens)
        data = super().validate(attrs)

        # Add profile information (candidate or staff)
        profile_data = None
        if hasattr(self.user, "candidate_profile"):
            profile_data = MinimalCandidateSerializer(self.user.candidate_profile).data
        elif hasattr(self.user, "staff_profile"):
            profile_data = MinimalStaffSerializer(self.user.staff_profile).data

        if profile_data:
            data["profile"] = profile_data

        return data


class LoginView(TokenObtainPairView):
    """
    Custom login view to handle user authentication and token generation.
    Uses the custom serializer to include user data in the response.
    """

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [HasXAPIKey]
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

    permission_classes = [HasXAPIKey]

    # @database_sync_to_async
    def _logout(self, refresh_token):
        """
        Expects a 'refresh' token in the request body.
        Extracts user info from the refresh token for logging.
        """
        if not refresh_token:
            raise ValidationError("Refresh token is required")

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
            raise InvalidTokenError("Invalid or expired refresh token")
        except Exception as e:
            logger.error("Logout failed with an unexpected error: %s", str(e))
            return Response(
                {"error": "Logout failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        return self._logout(request.get("refresh_token"))
