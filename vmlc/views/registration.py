import logging

from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
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
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    candidate_registration_request_body,
    staff_registration_request_body,
    error_response_400,
    error_response_403,
    error_response_401,
)
from ..utils.exceptions import PermissionDenied
from ..utils.helpers import sanitize_data


logger = logging.getLogger(__name__)


class BaseRegistrationView(CreateAPIView):
    """Base registration view with common logic"""

    permission_classes = [HasXAPIKey]
    feature_flag_key = None  # Subclasses must define this

    def create(self, request, *args, **kwargs):
        safe_data = sanitize_data(request.data)
        logger.info(
            f"{self.__class__.__name__}: Registration attempt with data: {safe_data}"
        )
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


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Register Candidate",
        operation_description="Register a new candidate.",
        request_body=candidate_registration_request_body,
        responses={
            201: openapi.Response("Registration successful."),
            400: error_response_400,
            403: error_response_403,
        },
        tags=["Registration"],
        manual_parameters=[api_key],
    ),
)
class CandidateRegistrationView(BaseRegistrationView):
    """Register a new candidate"""

    serializer_class = CandidateRegistrationSerializer
    feature_flag_key = "candidate_registration"


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Register Staff",
        operation_description="Register a new staff member.",
        request_body=staff_registration_request_body,
        responses={
            201: openapi.Response("Registration successful."),
            400: error_response_400,
            403: error_response_403,
        },
        tags=["Registration"],
        manual_parameters=[api_key],
    ),
)
class StaffRegistrationView(BaseRegistrationView):
    """
    Register a new staff member
    """

    serializer_class = StaffRegistrationSerializer
    feature_flag_key = "staff_registration"


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Toggle Candidate Registration",
        operation_description="Toggle candidate registration.",
        responses={
            200: openapi.Response("Feature flag toggled successfully."),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Registration"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ToggleCandidateRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'candidate_registration_open' feature flag."""

    swagger_schema = None
    permission_classes = VerifiedManagerPermissions
    feature_flag_key = "candidate_registration_open"


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Toggle Staff Registration",
        operation_description="Toggle staff registration.",
        responses={
            200: openapi.Response("Feature flag toggled successfully."),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Registration"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ToggleStaffRegistrationView(ToggleFeatureFlagView):
    """Toggles the 'staff_registration_open' feature flag."""

    swagger_schema = None
    permission_classes = VerifiedManagerPermissions
    feature_flag_key = "staff_registration_open"
