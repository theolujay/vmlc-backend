import logging

from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request

from ..utils import ToggleFeatureFlagView
from ..models import FeatureFlag, LeaderboardSnapshot
from ..permissions import (
    AuthenticatedUser,
    IsLeagueCandidateOrStaff,
    VerifiedAdminPermissions,
    VerifiedManagerPermissions,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    leaderboard_snapshot_response_schema,
    error_response_401,
    error_response_403,
    error_response_404,
)

logger = logging.getLogger(__name__)


class PublishLeaderboardView(APIView):
    """
    Refreshes and publishes the leaderboard snapshot. Admin/Superadmin only.
    """

    permission_classes = VerifiedAdminPermissions

    @swagger_auto_schema(
        operation_summary="Publish Leaderboard",
        operation_description="Refreshes and publishes the leaderboard snapshot.",
        responses={
            202: openapi.Response(
                "Leaderboard generation has been started and will be available shortly."
            ),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Leaderboard"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request: Request) -> Response:
        """
        Triggers an asynchronous task to generate and publish the leaderboard.
        """
        from ..tasks import generate_scores_snapshot_task, generate_leaderboard_snapshot_task

        staff_id = request.user.staff_profile.pk
        logger.info(
            f"PublishLeaderboardView: request from user {request.user.id} (staff_id: {staff_id})"
        )
        generate_scores_snapshot_task.delay(staff_id)
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

    permission_classes = AuthenticatedUser + [IsLeagueCandidateOrStaff]

    @swagger_auto_schema(
        operation_summary="Load Leaderboard",
        operation_description="Returns the most recently published leaderboard snapshot.",
        responses={
            200: leaderboard_snapshot_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Leaderboard"],
        manual_parameters=[api_key, bearer_auth],
    )
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

        leaderboard_visible = FeatureFlag.get_bool("leaderboard_visible", default=False)
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

    def _get_snapshot(self):
        return LeaderboardSnapshot.objects.order_by("-created_at").first()


@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Toggle Leaderboard Visibility",
        operation_description="Toggles the visibility of the leaderboard.",
        responses={
            200: openapi.Response("Feature flag toggled successfully."),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Leaderboard"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ToggleLeaderboardVisibilityView(ToggleFeatureFlagView):
    """
    Toggles the 'leaderboard_open' feature flag.
    Accessible only by staff with 'admin' or 'superadmin' roles.
    """

    permission_classes = VerifiedManagerPermissions
    feature_flag_key = "leaderboard_visible"
