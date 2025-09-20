import logging

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from ..utils import ToggleFeatureFlagView
from ..models import FeatureFlag
from ..permissions import HasXAPIKey, VerifiedManagerPermissions
from ..serializers import (
    CandidateRegistrationSerializer,
    StaffRegistrationSerializer,
)
from ..utils.exceptions import PermissionDenied


logger = logging.getLogger(__name__)


class BaseRegistrationView(CreateAPIView):
    """Base registration view with common logic"""

    permission_classes = [HasXAPIKey]
    feature_flag_key = None  # Subclasses must define this

    def create(self, request, *args, **kwargs):
        logger.info(f"{self.__class__.__name__}: request data: {request.data}")
        if request.user.is_authenticated:
            logger.warning(
                f"Authenticated user {request.user.id} attempted to register a new account."
            )
            raise PermissionDenied(
                "Already authenticated. Please log out to register a new account."
            )

        # Use the specific feature flag key for the registration type
        if self.feature_flag_key and not FeatureFlag.get_bool(
            self.feature_flag_key, default=False
        ):
            logger.warning(
                f"Registration attempt for {self.feature_flag_key} which is currently closed."
            )
            raise PermissionDenied(
                f"{self.feature_flag_key.replace('_', ' ').title()} is currently closed."
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        logger.info(
            f"Successfully registered new user with email: {serializer.data.get('email')}"
        )
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
    """
    Register a new staff member
    """

    serializer_class = StaffRegistrationSerializer
    feature_flag_key = "staff_registration"


class ToggleCandidateRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'candidate_registration_open' feature flag."""

    permission_classes = VerifiedManagerPermissions
    feature_flag_key = "candidate_registration_open"


class ToggleStaffRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'staff_registration_open' feature flag."""

    permission_classes = VerifiedManagerPermissions
    feature_flag_key = "staff_registration_open"
