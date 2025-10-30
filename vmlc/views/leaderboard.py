import logging

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.settings import api_settings


from ..models import Candidate, LeaderboardSnapshot
from ..permissions import (
    CandidatePermissions,
    VerifiedAdminPermissions,
    VerifiedModeratorPermissions,
)
from ..serializers.leaderboard import (
    PublishLeaderboardSerializer,
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
    Refreshes and publishes the leaderboard snapshot for a specific exam.
    Admin role required.
    """

    permission_classes = VerifiedAdminPermissions

    @swagger_auto_schema(
        operation_summary="Publish Exam Leaderboard",
        operation_description="Refreshes and publishes the leaderboard snapshot for a given exam.",
        request_body=PublishLeaderboardSerializer,
        responses={
            202: openapi.Response(
                "Leaderboard generation has been started and will be available shortly."
            ),
            400: "Invalid request",
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Leaderboard"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request: Request) -> Response:
        """
        Triggers an asynchronous task to generate and publish the leaderboard for an exam.
        """
        staff_id = request.user.staff_profile.pk

        from ..tasks import (
            generate_scores_snapshot_task,
            generate_leaderboard_snapshot_task,
        )

        logger.info(
            f"PublishLeaderboardView: request from user {request.user.id} (staff_id: {staff_id})"
        )
        generate_scores_snapshot_task.delay(staff_id)
        generate_leaderboard_snapshot_task.delay(staff_id)

        logger.info(
            f"Leaderboard generation triggered by staff {staff_id}"
        )

        return Response(
            {
                "message": "Leaderboard generation has been started and will be available shortly."
            },
            status=status.HTTP_202_ACCEPTED,
        )
        
class LoadLeaderboardView(APIView):
    """
    Returns published leaderboard snapshots.
    Filters leaderboards based on the user's role.
    """

    permission_classes = VerifiedModeratorPermissions or CandidatePermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    @swagger_auto_schema(
        operation_summary="Load Leaderboard(s)",
        operation_description="Returns published leaderboard snapshots, filtered by user role.",
        manual_parameters=[
            openapi.Parameter(
                "exam_id",
                openapi.IN_QUERY,
                description="ID of the exam to retrieve the leaderboard for",
                type=openapi.TYPE_INTEGER,
            )
        ],
        responses={
            200: leaderboard_snapshot_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Leaderboard"],
    )
    def get(self, request: Request):
        logger.info(f"LoadLeaderboardView: request from user {request.user.id}")
        user = request.user

        # Base queryset for published leaderboards
        snapshots = LeaderboardSnapshot.objects.filter(is_published=True)
        latest_snapshot = snapshots.order_by("-created_at").first()
        
        if latest_snapshot is None:
            return Response(
                {"detail": "No published leaderboard found."},
                status=status.HTTP_404_NOT_FOUND
            )

        raw_data = latest_snapshot.data
        
        # Handle both dict and potential old list format from snapshot
        if isinstance(raw_data, list):
            screening_lbs = [lb for lb in raw_data if lb.get("stage") == "screening"]
            league_lbs = [lb for lb in raw_data if lb.get("stage") == "league"]
        else:
            screening_lbs = raw_data.get("screening_leaderboard", [])
            league_lbs = raw_data.get("league_leaderboard", [])

        leaderboard_details = {
            "screening_total": len(screening_lbs),
            "league_total": len(league_lbs),
        }

        # Filter based on user role
        leaderboards_to_show = []
        if hasattr(user, "candidate_profile"):
            if not user.candidate_profile.is_verified:
                return Response(
                    {"detail": "Candidate must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if user.candidate_profile.role == Candidate.Roles.SCREENING:
                leaderboards_to_show = screening_lbs
            else: # LEAGUE and other roles
                leaderboards_to_show = screening_lbs + league_lbs
        
        elif hasattr(user, "staff_profile"):
            leaderboards_to_show = screening_lbs + league_lbs
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(leaderboards_to_show, request, view=self)

        if page is not None:
            response = paginator.get_paginated_response(page)
            response.data["leaderboard_details"] = leaderboard_details
            response.data["list"] = response.data.pop("results")
            if "count" in response.data:
                del response.data["count"]
            return response

        # If pagination not applied
        return Response(
            {
                "leaderboard_details": leaderboard_details,
                "list": leaderboards_to_show
            }
        )