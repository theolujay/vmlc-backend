"""
API views specific to candidates.
"""

import logging

from rest_framework.generics import (
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
    UpdateAPIView,
)
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.exceptions import ValidationError

from ..models import Candidate, Staff
from ..permissions import HasStaffRole, IsCandidate, IsVerifiedStaff
from ..serializers import (
    CandidateDetailSerializer,
    CandidateListSerializer,
    CandidateRoleSerializer,
)
from ..utils.dashboard_utils import get_candidate_dashboard_data
from ..utils.query_filters import filter_candidates

logger = logging.getLogger(__name__)

# class CandidateMeView(RetrieveAPIView):
#     """
#     Retrieve the authenticated candidate's own profile.
#     """
#     permission_classes = [IsAuthenticated, IsCandidate]
#     serializer_class = CandidateDetailSerializer

#     def get(self, request, *args, **kwargs):
#         """
#         Returns a structured data payload for the authenticated candidate.
#         """
#         # The IsCandidate permission already ensures the profile exists.
#         data = get_candidate_dashboard_data(request.user.candidate_profile)
#         return Response(data)


class CandidateListView(ListAPIView):
    """
    List all candidates.

    Accessible by staff users with roles: moderator, admin, or superadmin.
    Supports pagination and query param filtering.
    """
    permission_classes = [
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
        # Eagerly fetch related user data to prevent N+1 queries by the serializer.
        queryset = Candidate.objects.select_related("user").order_by("-date_created")
        return filter_candidates(queryset, self.request.query_params)


class CandidateDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific candidate profile.

    Only accessible to staff with 'owner' or 'admin' roles.
    """
    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = CandidateDetailSerializer
    lookup_url_kwarg = "candidate_id"

    def get_queryset(self):
        # The dashboard utility function handles all necessary queries.
        return Candidate.objects.select_related("user").all()

    def retrieve(self, request, *args, **kwargs):
        """
        Custom retrieve method to return structured candidate data.
        """
        candidate = self.get_object()
        data = get_candidate_dashboard_data(candidate)
        return Response(data, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        """
        Save updates to candidate and log the action.
        """
        logger.info(
            "Updating candidate %s by user %s",
            serializer.instance.pk,
            self.request.user.id,
            extra={"user_id": self.request.user.id, "candidate_id": serializer.instance.pk}
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
            extra={"user_id": self.request.user.id, "candidate_id": instance.pk}
        )
        instance.is_active = False
        instance.save()


class AssignCandidateRoleView(UpdateAPIView):
    """
    Assign a new role to a candidate.

    Only staff with 'owner' or 'admin' roles are permitted.
    """
    permission_classes = [
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
            raise ValidationError("Cannot assign role to unverified candidate.")

        old_role = serializer.instance.role
        super().perform_update(serializer)

        logger.info(
            "Changed candidate %s role from '%s' to '%s' by user %s",
            serializer.instance.pk,
            old_role,
            serializer.instance.role,
            self.request.user.id,
            extra={
                "user_id": self.request.user.id,
                "candidate_id": serializer.instance.pk,
                "old_role": old_role,
                "new_role": serializer.instance.role
            }
        )