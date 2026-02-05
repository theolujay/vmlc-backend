"""
Authentication-related API views for login, logout, and registration.
"""

from asyncio import sleep
import logging

from django.utils.decorators import method_decorator
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db import transaction

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from identity.models import User
from identity.permissions import HasXAPIKey
from ..serializers import (
    PasswordChangeOTPConfirmSerializer,
    PasswordChangeSerializer,
    RequestPasswordChangeSerializer,
    SendEmailOTPSerializer,
    VerifyEmailOTPSerializer,
)
from ..tasks import send_mail_task
from ..utils.email import create_email_html
from ..utils.exceptions import (
    InvalidTokenError,
    NotFound,
    ServerError,
    ValidationError,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_400,
    error_response_401,
    error_response_404,
    login_request_body,
    login_response_schema,
    logout_request_body,
    password_change_otp_confirm_request_body,
    password_change_request_body,
    request_password_change_request_body,
    resend_email_otp_request_body,
    resend_password_change_otp_request_body,
    verify_email_otp_request_body,
    token_refresh_response_schema,
    token_refresh_request_body,
)

logger = logging.getLogger(__name__)


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Refresh Access Token",
        operation_description="Takes a refresh token and returns an access token.",
        request_body=token_refresh_request_body,
        responses={
            200: token_refresh_response_schema,
            400: error_response_400,
            401: error_response_401,
        },
        tags=["Authentication"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class RefreshTokenView(TokenRefreshView):
    permission_classes = [HasXAPIKey]


class VerifyEmailOTPView(APIView):
    """
    Handles OTP verification for user registration.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Verify Email with OTP",
        operation_description="Verifies a user's email address using an OTP.",
        request_body=verify_email_otp_request_body,
        responses={
            200: openapi.Response("Email verified successfully."),
            400: error_response_400,
            404: error_response_404,
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._verify_email(request.data)

    def _verify_email(self, data):
        from vmlc.tasks import send_welcome_mail_task

        serializer = VerifyEmailOTPSerializer(data=data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                transaction.on_commit(
                    lambda: cache.delete(f"account_management_{user.id}")
                )
                subject = "Email Verified Successfully"
                message = "Your email has been successfully verified."
                html_message = create_email_html(subject=subject, message=message)
                send_mail_task.delay(
                    subject=subject,
                    message=message,
                    recipient_list=[user.email],
                    html_message=html_message,
                )
                if hasattr(user, "staff_profile") and user.last_login is None:
                    sleep(60)  # Ensure email is sent after transaction commit
                    send_welcome_mail_task.delay(
                        user_id=user.pk, generated_password=None
                    )
                logger.info(f"Email verified successfully for user {user.id}")
                return Response(
                    {"message": "Email verified successfully."},
                    status=status.HTTP_200_OK,
                )
            except User.DoesNotExist:
                raise NotFound("User not found.")
            except RuntimeError as e:
                logger.error(f"Error during email verification: {str(e)}")
                raise ServerError("Verification failed. Please try again.")

        logger.warning(f"Email verification failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendEmailOTPView(APIView):
    """
    Resend OTP to user's email with rate limiting.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Sends/resends Email OTP",
        operation_description="Sends/resends an OTP to a user's email address for verification.",
        request_body=resend_email_otp_request_body,
        responses={
            200: openapi.Response("OTP has been sent to your email address"),
            400: error_response_400,
            429: openapi.Response("Rate limit exceeded"),
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._resend_email_otp(request.data)

    def _resend_email_otp(self, data):
        serializer = SendEmailOTPSerializer(data=data)

        if serializer.is_valid():
            try:
                user = serializer.save()

                # Mask email for response
                email = user.email
                email_parts = email.split("@")
                masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}"
                logger.info(f"Sending OTP to user {user.id}")
                return Response(
                    {
                        "message": "OTP has been sent to your email address",
                        "email": masked_email,
                        "expires_in_minutes": 10,
                    },
                    status=status.HTTP_200_OK,
                )

            except serializers.ValidationError as e:
                # Rate limiting error from utils
                exc = ValidationError(str(e))
                exc.status_code = status.HTTP_429_TOO_MANY_REQUESTS
                raise exc
            except RuntimeError as e:
                logger.error(f"Unexpected error in send OTP: {str(e)}")
                raise ServerError("Failed to send OTP. Please try again later.")

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestPasswordChangeView(APIView):
    """
    Request OTP for password change.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Request Password Change",
        operation_description="Requests a password change and sends an OTP to the user's email.",
        request_body=request_password_change_request_body,
        responses={
            200: openapi.Response(
                "Password change verification code sent to your email"
            ),
            400: error_response_400,
            429: openapi.Response("Rate limit exceeded"),
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._request_password_change(request.data)

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
                exc = ValidationError(str(e))
                exc.status_code = status.HTTP_429_TOO_MANY_REQUESTS
                raise exc
            except RuntimeError as e:
                logger.error(f"Error requesting password change OTP: {str(e)}")
                raise ServerError(
                    "Failed to send verification code. Please try again later."
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordChangeOTPConfirmView(APIView):
    """
    Confirm password change request with OTP.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Confirm Password Change with OTP",
        operation_description="Confirms a password change request using an OTP.",
        request_body=password_change_otp_confirm_request_body,
        responses={
            200: openapi.Response(
                "OTP verified. User confirmed for password change. Proceed to change password."
            ),
            400: error_response_400,
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._confirm_password_change_otp(request.data)

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


class PasswordChangeView(APIView):
    """
    Change user password with OTP verification.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Change Password",
        operation_description="Changes a user's password after OTP verification.",
        request_body=password_change_request_body,
        responses={
            200: openapi.Response(
                "Password changed successfully. Please log in with your new password."
            ),
            400: error_response_400,
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._change_password(request.data)

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
                subject = "Your Password Has Been Changed"
                message = "This is to inform you that your password has been successfully changed."
                html_message = create_email_html(subject=subject, message=message)
                send_mail_task.delay(
                    subject=subject,
                    message=message,
                    recipient_list=[user.email],
                    html_message=html_message,
                )
                logger.info(f"Password changed successfully for user {user.id}")
                return Response(
                    {
                        "message": "Password changed successfully. Please log in with your new password."
                    },
                    status=status.HTTP_200_OK,
                )

            except RuntimeError as e:
                logger.error(f"Error changing password: {str(e)}")
                raise ServerError("Failed to change password. Please try again.")

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendPasswordChangeOTPView(APIView):
    """
    Resend OTP for password change with rate limiting.
    """

    permission_classes = [HasXAPIKey]

    @swagger_auto_schema(
        operation_summary="Resend Password Change OTP",
        operation_description="Resends a password change OTP to the user's email.",
        request_body=resend_password_change_otp_request_body,
        responses={
            200: openapi.Response("Password change verification code has been resent"),
            400: error_response_400,
            429: openapi.Response("Rate limit exceeded"),
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._resend_password_change_otp(request.data)

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
            from .. import utils

            utils.auth.resend_otp_to_email(user)
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
            exc = ValidationError(str(e))
            exc.status_code = status.HTTP_429_TOO_MANY_REQUESTS
            raise exc
        except RuntimeError as e:
            logger.error(f"Unexpected error in resend password change OTP: {str(e)}")
            raise ServerError(
                "Failed to resend verification code. Please try again later."
            )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customizes the JWT token response to include user details.
    """

    default_error_messages = {"no_active_account": "Invalid email or password"}

    def validate(self, attrs):
        # The default result (access/refresh tokens)
        data = super().validate(attrs)

        user_logged_in.send(
            sender=self.user.__class__, request=self.context["request"], user=self.user
        )

        # Add profile information (candidate or staff)
        from .user.management import ProfileManager

        profile_data = ProfileManager.serialize_profile(self.user)

        if profile_data:
            profile_data["is_setup_complete"] = self.user.is_setup_complete
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

    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description="Authenticates a user and returns access and refresh tokens.",
        request_body=login_request_body,
        responses={
            200: login_response_schema,
            400: error_response_400,
            401: error_response_401,
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
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

    @swagger_auto_schema(
        operation_summary="User Logout",
        operation_description="Blacklists a refresh token to log a user out.",
        request_body=logout_request_body,
        responses={
            204: openapi.Response("Successfully logged out."),
            400: error_response_400,
        },
        tags=["Authentication"],
        manual_parameters=[api_key],
    )
    def post(self, request):
        return self._logout(request.data.get("refresh"))

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
        except RuntimeError as e:
            logger.error("Logout failed with an unexpected error: %s", str(e))
            raise ServerError("Logout failed")
