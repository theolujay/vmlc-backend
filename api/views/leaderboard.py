"""
API views for retrieving and managing the leaderboard.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Candidate, FeatureFlag, LeaderboardSnapshot, Staff
from ..permissions import HasStaffRole, IsLeagueCandidateOrStaff, IsVerifiedStaff
from ..serializers import MinimalCandidateSerializer
from .registration import ToggleFeatureFlagView

logger = logging.getLogger(__name__)


class PublishLeaderboardView(APIView):
    """
    Refreshes and publishes the leaderboard snapshot. Admin/Owner only.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]

    def post(self, request):
        """
        Generates a new leaderboard from current candidate scores and saves it.
        """
        staff = request.user.staff_profile

        # Use the optimized manager method to get candidates with scores
        league_candidates = (
            Candidate.objects.with_scores()
            .filter(role=Candidate.Roles.LEAGUE, is_active=True)
            .order_by("-total_score")
        )

        leaderboard_data = [
            {
                "rank": index + 1,
                "candidate": MinimalCandidateSerializer(candidate).data,
                "total_score": float(candidate.total_score or 0.0),
            }
            for index, candidate in enumerate(league_candidates)
        ]

        snapshot = LeaderboardSnapshot.objects.create(
            data=leaderboard_data,
            published_by=staff,
        )

        logger.info(
            "Leaderboard published by staff %s. Snapshot ID: %s",
            staff.pk,
            snapshot.pk,
        )

        return Response(
            {
                "message": "Leaderboard published successfully!",
                "published_at": snapshot.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class LoadLeaderboardView(APIView):
    """
    Returns the most recently published leaderboard snapshot.
    """

    permission_classes = [IsAuthenticated, IsLeagueCandidateOrStaff]

    def get(self, request):
        if hasattr(request.user, "candidate_profile"):
            if not request.user.candidate_profile.is_verified:
                return Response(
                    {"detail": "Candidate must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif hasattr(request.user, "staff_profile"):
            if not request.user.staff_profile.is_verified:
                return Response(
                    {"detail": "Staff must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if not FeatureFlag.get_bool("leaderboard_visible", default=False):
            return Response(
                {"detail": "The leaderboard is currently not available."},
                status=status.HTTP_403_FORBIDDEN,
            )

        snapshot = LeaderboardSnapshot.objects.order_by("-created_at").first()

        if not snapshot:
            return Response(
                {"detail": "The leaderboard has not been published yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(snapshot.data)


class ToggleLeaderboardVisibilityView(ToggleFeatureFlagView):
    """
    Toggles the 'leaderboard_open' feature flag.
    Accessible only by staff with 'admin' or 'owner' roles.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    feature_flag_key = "leaderboard_visible"
