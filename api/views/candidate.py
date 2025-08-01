"""
API views specific to candidates.
"""

import logging

from django.db.models import Prefetch
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

from ..models import Candidate, CandidateScore, Staff
from ..permissions import HasStaffRole, IsCandidate
from ..serializers import (
    CandidateDetailSerializer,
    CandidateListSerializer,
    CandidateRoleSerializer,
)

from ..utils.query_filters import filter_candidates

logger = logging.getLogger(__name__)


class CandidateMeView(RetrieveAPIView):
    """
    Retrieve the authenticated candidate's own profile.
    """

    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = CandidateDetailSerializer
    queryset = Candidate.objects.with_complete_data()

    def get_object(self):
        """
        Return the candidate profile for the currently authenticated user.
        """
        # The IsCandidate permission already ensures the profile exists.
        return self.queryset.get(user=self.request.user)


class CandidateListView(ListAPIView):
    """
    List all candidates.

    Accessible by staff users with roles: moderator, admin, or owner.
    Supports pagination and query param filtering.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.OWNER),
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
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = CandidateDetailSerializer
    queryset = Candidate.objects.all()
    lookup_url_kwarg = "candidate_id"

    def get_queryset(self):
        """
        Returns a queryset with prefetch optimization for candidate scores,
        including related exams and submitters.
        """
        return Candidate.objects.with_scores().prefetch_related(
            Prefetch(
                "scores",
                queryset=CandidateScore.objects.select_related("exam", "submitted_by"),
            )
        )

    def perform_update(self, serializer) -> None:
        """
        Save updates to candidate and log the action.
        """
        logger.info(
            f"Updating candidate {serializer.instance.pk}",
            extra={"user": self.request.user.id},
        )
        serializer.save(updated_by=self.request.user.staff_profile)

    def perform_destroy(self, instance) -> None:
        """
        Soft-delete staff by setting `is_active` to False.
        """
        logger.info(
            f"Soft-deleting candidate {instance.pk}",
            extra={"user": self.request.user.id},
        )

        instance.is_active = False  # Make the instance inactive
        instance.save()


class AssignCandidateRoleView(UpdateAPIView):
    """
    Assign a new role to a candidate.

    Only staff with 'owner' or 'admin' roles are permitted.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = CandidateRoleSerializer
    queryset = Candidate.objects.all()
    lookup_url_kwarg = "candidate_id"
    http_method_names = ["put", "patch"]

    def perform_update(self, serializer):
        super().perform_update(serializer)
        logger.info("Assigned role '%s' to candidate %s by user %s.", serializer.instance.role, serializer.instance.pk, self.request.user.id)
