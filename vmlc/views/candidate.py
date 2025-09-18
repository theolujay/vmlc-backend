import logging

from rest_framework.generics import (
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
    UpdateAPIView,
    RetrieveAPIView,
)
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.settings import api_settings

from ..models import Candidate, Staff
from ..permissions import (
    HasStaffRole,
    IsVerifiedStaff,
    IsCandidate,
    HasXAPIKey,
)
from ..serializers import (
    CandidateDetailSerializer,
    CandidateListSerializer,
    CandidateRoleSerializer,
    MinimalCandidateSerializer,
)
from ..utils.dashboard_utils import get_candidate_dashboard_data
from ..utils.query_filters import filter_candidates
from ..utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CandidateMeView(RetrieveAPIView):
    """
    Retrieve the authenticated candidate's own profile.
    """

    permission_classes = [HasXAPIKey, IsAuthenticated, IsCandidate]
    serializer_class = MinimalCandidateSerializer

    def get(self, request, *args, **kwargs):
        """
        Returns a structured data payload for the authenticated candidate.
        """
        data = Candidate.objects.get(request.user)
        return Response(data)


class CandidateListView(ListAPIView):
    """
    List all candidates.

    Accessible by staff users with roles: moderator, admin, or superadmin.
    Supports pagination and query param filtering.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
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
        queryset = Candidate.objects.select_related("user").order_by("-date_created")
        return filter_candidates(queryset, self.request.query_params)


class CandidateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific candidate profile.

    Only accessible to staff with 'owner' or 'admin' roles.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = CandidateDetailSerializer
    lookup_url_kwarg = "candidate_id"

    def get_queryset(self):
        logger.info(
            f"CandidateDetailView: request from user {self.request.user.id} for candidate {self.kwargs.get(self.lookup_url_kwarg)}"
        )
        return (
            Candidate.objects.select_related("user")
            .prefetch_related("scores__exam", "scores__submitted_by__user")
            .all()
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Custom retrieve method to return structured candidate data.
        """
        candidate = self.get_object()
        logger.info(
            f"Retrieving dashboard data for candidate {candidate.pk} by user {request.user.id}"
        )
        data = get_candidate_dashboard_data(candidate)
        return Response(data, status=status.HTTP_200_OK)

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

    def perform_destroy(self, instance):
        """
        Soft-delete candidate by setting `is_active` to False.
        """
        logger.info(
            "Soft-deleting candidate %s by user %s",
            instance.pk,
            self.request.user.id,
        )
        instance.is_active = False
        instance.save()


class AssignCandidateRoleView(UpdateAPIView):
    """
    Assign a new role to a candidate.

    Only staff with 'owner' or 'admin' roles are permitted.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = CandidateRoleSerializer
    queryset = Candidate.objects.all()
    lookup_url_kwarg = "candidate_id"
    http_method_names = ["put", "patch"]

    def perform_update(self, serializer):
        """
        Update candidate role and log the action.
        """
        if not serializer.instance.is_verified:
            logger.warning(
                f"Attempted to assign role to unverified candidate {serializer.instance.pk} by user {self.request.user.id}"
            )
            raise ValidationError("Cannot assign role to unverified candidate.")

        old_role = serializer.instance.role
        super().perform_update(serializer)

        logger.info(
            "Changed candidate %s role from '%s' to '%s' by user %s",
            serializer.instance.pk,
            old_role,
            serializer.instance.role,
            self.request.user.id,
        )
