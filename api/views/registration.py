"""
API views for user registration and managing registration status.
"""

import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey  # type: ignore

from ..models import FeatureFlag, Staff
from ..permissions import HasStaffRole
from ..serializers import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
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
            {"message": "Registration successful"},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class CandidateRegistrationView(BaseRegistrationView):
    """Register a new candidate"""

    serializer_class = CandidateRegistrationSerializer
    feature_flag_key = "candidate_registration_open"


class StaffRegistrationView(BaseRegistrationView):
    """Register a new staff member"""

    serializer_class = StaffRegistrationSerializer
    feature_flag_key = "staff_registration_open"


class ToggleFeatureFlagView(APIView):
    """
    A generic view to toggle a boolean feature flag.
    Subclasses must specify `feature_flag_key` and `permission_classes`.
    """

    permission_classes = [IsAuthenticated]  # Base permission
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
        return Response(
            {"message": f"'{self.feature_flag_key}' is now {'open' if obj.value else 'closed'}."},
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