"""
API views for user registration and managing registration status.
"""

import logging

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from rest_framework import status, serializers
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from api.utils.registration import resend_otp_to_email  # type: ignore

from ..models import FeatureFlag, Staff, User
from ..permissions import HasStaffRole
from ..serializers import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
    VerifyOTPSerializer,
    ResendOTPSerializer,
)


logger = logging.getLogger(__name__)


class BaseRegistrationView(CreateAPIView):
    """Base registration view with common logic"""

    permission_classes = [HasAPIKey]
    feature_flag_key = None  # Subclasses must define this

    def create(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return Response(
                {"error": "Already authenticated. Please log out to register a new account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use the specific feature flag key for the registration type
        if self.feature_flag_key and not FeatureFlag.get_bool(
            self.feature_flag_key, default=False
        ):
            return Response(
                {"detail": f"{self.feature_flag_key.replace('_', ' ').title()} is currently closed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"message": "Registration successful."},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class CandidateRegistrationView(BaseRegistrationView):
    """Register a new candidate"""

    serializer_class = CandidateRegistrationSerializer
    feature_flag_key = "candidate_registration"


class StaffRegistrationView(BaseRegistrationView):
    """Register a new staff member"""

    serializer_class = StaffRegistrationSerializer
    feature_flag_key = "staff_registration"


class ToggleFeatureFlagView(APIView):
    """
    A generic view to toggle a boolean feature flag.
    Subclasses must specify `feature_flag_key` and `permission_classes`.
    """

    permission_classes = [IsAuthenticated, HasStaffRole(Staff.Roles.OWNER)]
    feature_flag_key = None

    def post(self, request, *args, **kwargs):
        if not self.feature_flag_key:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} is missing a feature_flag_key."
            )

        visible_flag = request.data.get("open", False)
        obj, created = FeatureFlag.objects.get_or_create(
            key=self.feature_flag_key, defaults={"value": visible_flag}
        )

        if not created:
            obj.value = visible_flag
            obj.save()

        logger.info(
            "Feature flag '%s' toggled to %s by user %s.", self.feature_flag_key, obj.value, request.user.id
        )

        FEATURE_FLAG_MESSAGES = {
            "candidate_registration_open": {
                True: "Candidate registration is now open.",
                False: "Candidate registration is now closed."
            },
            "staff_registration_open": {
                True: "Candidate registration is now open.",
                True: "Candidate registration is now enabled.", 
                False: "Candidate mode is now closed."
            },
            "leaderboard_visible": {
                True: "Leaderboard is now visible.", 
                False: "Leaderboard is now hidden."
            },
        }

        message_config = FEATURE_FLAG_MESSAGES.get(self.feature_flag_key)
        if message_config:
            message = message_config[obj.value]
        else:
            feature_name = self.feature_flag_key.replace('_', ' ').title()
            status_text = 'enabled' if obj.value else 'disabled'
            message = f"'{feature_name}' is now {status_text}."

        return Response(
            {"message": message},
            status=status.HTTP_200_OK,
        )

class ToggleCandidateRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'candidate_registration_open' feature flag."""

    permission_classes = [IsAuthenticated, HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER)]
    feature_flag_key = "candidate_registration_open"


class ToggleStaffRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'staff_registration_open' feature flag."""

    permission_classes = [IsAuthenticated, HasStaffRole(Staff.Roles.OWNER)]
    feature_flag_key = "staff_registration_open"


class VerifyOTPView(APIView):
    """
    Handles OTP verification for user registration.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info("Email verification successful for user %s", serializer.validated_data['user'].id)
            return Response(
                {'message': 'Email verified successfully.'}, 
                status=status.HTTP_200_OK
            )
        
        logger.warning(f"Email verification failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    """
    Resend OTP to user's email with rate limiting.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            email = request.data.get('email')
            if not email:
                return Response(
                    {"error": "Email is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            if '@' not in email:
                return Response(
                    {"error": "Please provide a valid email address"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = get_object_or_404(User, email=email)
            
            # Resend OTP
            resend_otp_to_email(user)
            
            # Mask email for response
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
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except User.DoesNotExist:
            # Return generic message (don't reveal if email exists)
            logger.warning(f"OTP resend attempted for non-existent email: {email[:3]}***")
            return Response(
                {"message": "If this email is registered, an OTP has been sent"}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Unexpected error in resend OTP for {email[:3]}***: {str(e)}")
            return Response(
                {"error": "Failed to resend OTP. Please try again later."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )