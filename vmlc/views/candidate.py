import logging

from django.core.cache import cache
from django.utils.decorators import method_decorator
from rest_framework.generics import (
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
    UpdateAPIView,
    RetrieveAPIView,
)
from rest_framework.response import Response
from rest_framework.settings import api_settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..models import Candidate
from ..permissions import (
    CandidatePermissions,
    VerifiedModeratorPermissions,
    VerifiedAdminPermissions,
)
from ..serializers import (
    CandidateDetailSerializer,
    CandidateListSerializer,
    CandidateRoleSerializer,
    MinimalCandidateSerializer,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    candidate_me_response_schema,
    candidate_list_response_schema,
    candidate_detail_response_schema,
    candidate_role_request_body,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.query_filters import filter_candidates
from ..utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get My Profile",
        operation_description="Retrieve the authenticated candidate's own profile.",
        responses={
            200: candidate_me_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class CandidateMeView(RetrieveAPIView):
    """
    Retrieve the authenticated candidate's own profile.
    """

    permission_classes = CandidatePermissions
    serializer_class = MinimalCandidateSerializer

    def get_object(self):
        """
        Returns a structured data payload for the authenticated candidate.
        """
        user_id = self.request.user.id
        cache_key = f"candidate_profile_{user_id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        data = Candidate.objects.get(user=self.request.user)
        cache.set(cache_key, data, 3600)  # Cache for 1 hour
        return data


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Candidates",
        operation_description="List all candidates. Required roles: moderator or higher",
        responses={
            200: candidate_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class CandidateListView(ListAPIView):
    """
    List all candidates.

    Accessible by staff users with roles: moderator, admin, manager, or superadmin.
    Supports pagination and query param filtering.
    """

    permission_classes = VerifiedModeratorPermissions
    serializer_class = CandidateListSerializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Returns a filtered queryset of candidates based on request query parameters.
        """
        logger.info(
            f"CandidateListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        # Eagerly fetch related user data to prevent N+1 queries by the serializer.
        queryset = Candidate.objects.select_related("user").order_by("-created_at")
        return filter_candidates(queryset, self.request.query_params)

@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Candidate Details",
        operation_description="Retrieve details for candidate with given 'id'.",
        responses={
            200: candidate_detail_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Update Candidate Details",
        operation_description="Update details for candidate with given 'id'.",
        request_body=CandidateDetailSerializer,
        responses={
            200: candidate_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        operation_summary="Delete Candidate",
        operation_description="Delete candidate with given 'id'.",
        responses={
            204: openapi.Response("Candidate deleted successfully."),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    )
)
class CandidateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific candidate profile.

    Only accessible to staff with 'owner' or 'admin' roles.
    """

    permission_classes = VerifiedAdminPermissions
    serializer_class = CandidateDetailSerializer
    lookup_url_kwarg = "candidate_id"
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        logger.info(
            f"CandidateDetailView: request from user {self.request.user.id} for candidate {self.kwargs.get(self.lookup_url_kwarg)}"
        )
        return (
            Candidate.objects.select_related("user")
            .prefetch_related("scores__exam", "scores__score_submitted_by__user")
            .all()
        )

    def retrieve(self, request, *args, **kwargs):
        candidate_id = self.kwargs.get(self.lookup_url_kwarg)
        cache_key = f"candidate_detail_{candidate_id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        cache.set(cache_key, data, 86400)  # Cache for 24 hours
        return Response(data)

    def perform_update(self, serializer):
        """
        Save updates to candidate and log the action.
        """
        logger.info(
            "Updating candidate %s by user %s with data: %s",
            serializer.instance.pk,
            self.request.user.id,
            serializer.validated_data,
        )
        serializer.save(updated_by=self.request.user.staff_profile)
        cache.delete(f"candidate_detail_{serializer.instance.pk}")
        cache.delete(f"candidate_profile_{serializer.instance.user.id}")
    def perform_destroy(self, instance):
        """
        Soft-delete candidate by setting `is_active` to False.
        """
        logger.info(
            "Soft-deleting candidate %s by user %s",
            instance.pk,
            self.request.user.id,
        )
        cache.delete(f"candidate_detail_{instance.pk}")
        cache.delete(f"candidate_profile_{instance.user.id}")
        instance.is_active = False
        instance.save()

@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        operation_summary="Assign Candidate Role",
        operation_description="Assign role to candidate with given 'id'.",
        request_body=candidate_role_request_body,
        responses={
            200: CandidateRoleSerializer,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Candidates"],
        manual_parameters=[api_key, bearer_auth],
    )
)
class AssignCandidateRoleView(UpdateAPIView):
    """
    Assign a new role to a candidate.

    Only staff with 'owner' or 'admin' roles are permitted.
    """

    permission_classes = VerifiedAdminPermissions
    serializer_class = CandidateRoleSerializer
    queryset = Candidate.objects.all()
    lookup_url_kwarg = "candidate_id"
    http_method_names = ["put"]

    def perform_update(self, serializer):
        """
        Update candidate role and log the action.
        """
        if not serializer.instance.is_user_verified:
            logger.warning(
                f"Attempted to assign role to unverified candidate {serializer.instance.pk} by user {self.request.user.id}"
            )
            raise ValidationError("Cannot assign role to unverified candidate.")

        old_role = serializer.instance.role
        super().perform_update(serializer)

        cache.delete(f"candidate_detail_{serializer.instance.pk}")
        cache.delete(f"candidate_profile_{serializer.instance.user.id}")
        cache.delete(f"account_management_{serializer.instance.user.id}")

        logger.info(
            "Changed candidate %s role from '%s' to '%s' by user %s",
            serializer.instance.pk,
            old_role,
            serializer.instance.role,
            self.request.user.id,
        )
