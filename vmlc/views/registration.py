import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from ..permissions import HasXAPIKey
# from channels.db import database_sync_to_async

from ..models import FeatureFlag, Staff
from ..permissions import HasStaffRole
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


class ToggleFeatureFlagView(APIView):
    """
    A generic view to toggle a boolean feature flag.
    Subclasses must specify `feature_flag_key` and `permission_classes`.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.SUPERADMIN),
    ]
    feature_flag_key = None

    # @database_sync_to_async
    def _toggle_feature_flag(self, request, *args, **kwargs):
        logger.info(
            f"{self.__class__.__name__}: request from user {request.user.id} with data: {request.data}"
        )
        if not self.feature_flag_key:
            logger.error(f"{self.__class__.__name__} is missing a feature_flag_key.")
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
            "Feature flag '%s' toggled to %s by user %s.",
            self.feature_flag_key,
            obj.value,
            request.user.id,
        )

        FEATURE_FLAG_MESSAGES = {
            "candidate_registration_open": {
                True: "Candidate registration is now open.",
                False: "Candidate registration is now closed.",
            },
            "staff_registration_open": {
                True: "Staff registration is now open.",
                False: "Staff registration is now closed.",
            },
            "leaderboard_visible": {
                True: "Leaderboard is now visible.",
                False: "Leaderboard is now hidden.",
            },
        }

        message_config = FEATURE_FLAG_MESSAGES.get(self.feature_flag_key)
        if message_config:
            message = message_config[obj.value]
        else:
            feature_name = self.feature_flag_key.replace("_", " ").title()
            status_text = "enabled" if obj.value else "disabled"
            message = f"'{feature_name}' is now {status_text}."

        return Response(
            {"message": message},
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        return self._toggle_feature_flag(request, *args, **kwargs)


class ToggleCandidateRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'candidate_registration_open' feature flag."""

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    feature_flag_key = "candidate_registration_open"


class ToggleStaffRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'staff_registration_open' feature flag."""

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.SUPERADMIN),
    ]
    feature_flag_key = "staff_registration_open"
