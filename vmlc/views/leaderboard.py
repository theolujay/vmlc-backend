import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
# from channels.db import database_sync_to_async

from ..utils import ToggleFeatureFlagView
from ..models import FeatureFlag, LeaderboardSnapshot
from ..permissions import (
    HasMinimumStaffRole,
    IsLeagueCandidateOrStaff,
    IsVerifiedStaff,
    HasXAPIKey,
)

logger = logging.getLogger(__name__)


class PublishLeaderboardView(APIView):
    """
    Refreshes and publishes the leaderboard snapshot. Admin/Superadmin only.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasMinimumStaffRole("admin"),
    ]

    def post(self, request: Request) -> Response:
        """
        Triggers an asynchronous task to generate and publish the leaderboard.
        """
        from ..tasks import generate_leaderboard_snapshot_task

        staff_id = request.user.staff_profile.pk
        logger.info(
            f"PublishLeaderboardView: request from user {request.user.id} (staff_id: {staff_id})"
        )
        generate_leaderboard_snapshot_task.delay(staff_id)

        logger.info(f"Leaderboard generation triggered by staff {staff_id}")

        return Response(
            {
                "message": "Leaderboard generation has been started and will be available shortly."
            },
            status=status.HTTP_202_ACCEPTED,
        )



class LoadLeaderboardView(APIView):
    """
    Returns the most recently published leaderboard snapshot.
    """

    permission_classes = [HasXAPIKey, IsAuthenticated, IsLeagueCandidateOrStaff]

    # @database_sync_to_async
    def _get_snapshot(self):
        return LeaderboardSnapshot.objects.order_by("-created_at").first()

    def get(self, request):
        logger.info(f"LoadLeaderboardView: request from user {request.user.id}")
        if hasattr(request.user, "candidate_profile"):
            if not request.user.candidate_profile.is_verified:
                logger.warning(
                    f"Unverified candidate {request.user.id} attempted to view the leaderboard."
                )
                return Response(
                    {"detail": "Candidate must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif hasattr(request.user, "staff_profile"):
            if not request.user.staff_profile.is_verified:
                logger.warning(
                    f"Unverified staff {request.user.id} attempted to view the leaderboard."
                )
                return Response(
                    {"detail": "Staff must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # leaderboard_visible = await database_sync_to_async(FeatureFlag.get_bool)(
        #     "leaderboard_visible", default=False
        # )
        leaderboard_visible = FeatureFlag.get_bool(
            "leaderboard_visible", default=False
        )
        logger.info(f"Leaderboard visibility is set to {leaderboard_visible}")
        if not leaderboard_visible:
            logger.warning(
                f"User {request.user.id} attempted to view the leaderboard while it is not visible."
            )
            return Response(
                {"detail": "The leaderboard is currently not available."},
                status=status.HTTP_403_FORBIDDEN,
            )

        snapshot = self._get_snapshot()

        if not snapshot:
            logger.warning("Leaderboard requested but not yet published.")
            return Response(
                {"detail": "The leaderboard has not been published yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info(f"Leaderboard loaded successfully for user {request.user.id}")
        return Response(snapshot.data)


class ToggleLeaderboardVisibilityView(ToggleFeatureFlagView):
    """
    Toggles the 'leaderboard_open' feature flag.
    Accessible only by staff with 'admin' or 'superadmin' roles.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasMinimumStaffRole("admin"),
    ]
    feature_flag_key = "leaderboard_visible"
