import logging
from collections import OrderedDict

from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.settings import api_settings


from vmlc.models import Candidate, LeaderboardSnapshot
from vmlc.permissions import (
    AuthenticatedUser,
    IsVerifiedModeratorOrCandidate,
    VerifiedAdminPermissions,
)
from vmlc.serializers.leaderboard import (
    PublishLeaderboardSerializer,
)
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_401,
    error_response_403,
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
        from vmlc.utils.helpers import invalidate_all_candidate_records
        from vmlc.tasks import (
            generate_scores_snapshot_task,
            generate_leaderboard_snapshot_task,
        )

        logger.info(
            f"PublishLeaderboardView: request from user {request.user.id} (staff_id: {staff_id})"
        )

        # Invalidate leaderboard cache before triggering regeneration
        cache.delete_pattern("leaderboard_*")
        logger.info("Leaderboard cache invalidated.")

        invalidate_all_candidate_records()
        generate_scores_snapshot_task.delay(staff_id)
        generate_leaderboard_snapshot_task.delay(staff_id)

        logger.info(f"Leaderboard generation triggered by staff {staff_id}")

        return Response(
            {
                "message": "Leaderboard generation has been started and will be available shortly."
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LeaderboardViewMixin:
    """Shared functionality for leaderboard views."""

    def _get_latest_leaderboard_snapshot(self):
        """Helper to fetch the latest published leaderboard snapshot."""
        return (
            LeaderboardSnapshot.objects.filter(is_published=True)
            .order_by("-created_at")
            .first()
        )


class LoadLeaderboardView(APIView, LeaderboardViewMixin):
    """
    Returns published leaderboard snapshots.
    Filters leaderboards based on the user's role.
    """

    permission_classes = AuthenticatedUser + [IsVerifiedModeratorOrCandidate]
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    @swagger_auto_schema(
        operation_summary="Get Published Leaderboards",
        operation_description=(
            "Returns published leaderboard snapshots, filtered by user role. "
            "Provide 'stage' and 'level' query parameters to view a specific leaderboard. "
            "Without them, it returns a summary of all accessible leaderboards."
        ),
        manual_parameters=[
            openapi.Parameter(
                "stage",
                openapi.IN_QUERY,
                description="The stage of the exam (e.g., 'screening', 'league')",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "level",
                openapi.IN_QUERY,
                description="The level of the exam.",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            api_key,
            bearer_auth,
        ],
        responses={
            200: openapi.Response(
                description="Successfully retrieved leaderboard data. The response structure varies based on query parameters."
            ),
            401: error_response_401,
            403: error_response_403,
            404: openapi.Response(description="No published leaderboard found."),
        },
        tags=["Leaderboard"],
    )
    def get(self, request: Request):
        logger.info(f"LoadLeaderboardView: request from user {request.user.id}")
        user = request.user

        latest_snapshot = self._get_latest_leaderboard_snapshot()
        if latest_snapshot is None:
            return Response(
                {"detail": "No published leaderboard found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_role_key = self._get_user_role_key(user)
        requested_stage = request.query_params.get("stage")
        requested_level = request.query_params.get("level")
        page = request.query_params.get(self.pagination_class.page_query_param, 1)

        cache_key = f"leaderboard_view_{latest_snapshot.id}_{user_role_key}_{requested_stage or 'all'}_{requested_level or 'all'}_{page}"
        cached_data = self._get_cached_leaderboard_response(cache_key)
        if cached_data:
            return Response(cached_data)

        all_leaderboards = latest_snapshot.data

        if (
            hasattr(user, "candidate_profile")
            and not user.candidate_profile.is_user_verified
        ):
            return Response(
                {"detail": "Candidate must be verified to view the leaderboard."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if requested_stage and requested_level:
            response_data = self._handle_specific_leaderboard_request(
                user,
                all_leaderboards,
                requested_stage,
                requested_level,
                self.pagination_class(),
                request,
            )
        else:
            response_data = self._handle_overall_leaderboard_request(
                user, all_leaderboards, latest_snapshot
            )

        cache.set(cache_key, response_data, timeout=21600)  # cache for 6 hours
        return Response(response_data)

    def _get_cached_leaderboard_response(self, cache_key):
        """Helper to check and return cached leaderboard data."""
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached leaderboard data for key: {cache_key}")
        return cached_data

    def _get_user_role_key(self, user):
        """Helper to generate a cache key based on user role."""
        if hasattr(user, "candidate_profile"):
            return f"candidate_{user.candidate_profile.role}_{user.candidate_profile.is_user_verified}"
        return "staff"

    def _handle_specific_leaderboard_request(
        self,
        user,
        all_leaderboards,
        requested_stage,
        requested_level,
        paginator,
        request,
    ):
        """Helper to handle requests for a specific stage and level leaderboard."""
        leaderboard_key = f"{requested_stage}_{requested_level}"

        if leaderboard_key not in all_leaderboards:
            return Response(
                {
                    "detail": f"No leaderboard found for {requested_stage} level {requested_level}"
                },
                status=status.HTTP_200_OK,
            )

        leaderboard_data = all_leaderboards[leaderboard_key]

        if hasattr(user, "candidate_profile"):
            candidate = user.candidate_profile
            if (
                candidate.role == Candidate.Roles.SCREENING
                and requested_stage != "screening"
            ):
                return Response(
                    {"detail": "You can only view screening leaderboards."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        entries = leaderboard_data.get("entries", [])
        for entry in entries:
            entry["candidate"].pop("submissions", None)
        top_three = entries[:3] if len(entries) >= 3 else entries
        remaining = entries[3:] if len(entries) > 3 else []

        exam_details = {
            "id": leaderboard_data.get("exam_id"),
            "title": leaderboard_data.get("exam_title"),
            "stage": leaderboard_data.get("stage"),
            "level": leaderboard_data.get("level"),
            "scheduled_date": leaderboard_data.get("scheduled_date"),
            "concluded_at": leaderboard_data.get("concluded_at"),
            "total_questions": leaderboard_data.get("total_questions"),
            "total_candidates": leaderboard_data.get("total_candidates"),
            "average_score": leaderboard_data.get("average_score"),
        }

        paginated_remaining = paginator.paginate_queryset(remaining, request, view=self)

        pagination_data = paginator.get_paginated_response_data(paginated_remaining)

        return OrderedDict(
            [
                ("exam_details", exam_details),
                ("top_three", top_three),
                ("remaining_candidates", pagination_data["results"]),
                ("pagination", pagination_data["pagination"]),
            ]
        )

    def _handle_overall_leaderboard_request(
        self, user, all_leaderboards, latest_snapshot
    ):
        """Helper to handle requests for the overall leaderboard summary."""
        accessible_leaderboards = {}

        if hasattr(user, "candidate_profile"):
            candidate = user.candidate_profile
            if candidate.role == Candidate.Roles.SCREENING:
                accessible_leaderboards = {
                    key: value
                    for key, value in all_leaderboards.items()
                    if key.startswith("screening_")
                }
            else:
                accessible_leaderboards = all_leaderboards
        elif hasattr(user, "staff_profile"):
            accessible_leaderboards = all_leaderboards

        def sort_key_func(key):
            try:
                stage, level_str = key.split("_", 1)
                level = int(level_str)
                # Prioritize 'league' (0) over 'screening' (1)
                stage_priority = 1 if stage == "screening" else 0
                # Sort by level in descending order
                return (stage_priority, -level)
            except (ValueError, IndexError):
                # Fallback for unexpected key formats
                return (2, key)

        leaderboards_summary = []
        for key in sorted(accessible_leaderboards.keys(), key=sort_key_func):
            lb = accessible_leaderboards[key]
            if isinstance(lb, dict):
                leaderboards_summary.append(
                    {
                        "stage": lb.get("stage"),
                        "level": lb.get("level"),
                        "stage_display": key,
                        "exam_title": lb.get("exam_title"),
                        "total_candidates": lb.get("total_candidates"),
                        "average_score": lb.get("average_score"),
                    }
                )

        return {
            "snapshot_id": latest_snapshot.id,
            "published_at": latest_snapshot.created_at.isoformat(),
            "available_leaderboards": leaderboards_summary,
        }


class LoadLeaderboardDetailView(APIView, LeaderboardViewMixin):
    """
    Returns detailed performance for a specific candidate in a specific exam.

    URL: leaderboard/<stage>/<level>/candidate/<candidate_id>/
    Example: leaderboard/league/2/candidate/123/
    """

    permission_classes = AuthenticatedUser + [IsVerifiedModeratorOrCandidate]

    @swagger_auto_schema(
        operation_summary="Get Candidate Leaderboard Details",
        operation_description="Returns detailed performance for a specific candidate in a specific exam leaderboard.",
        manual_parameters=[api_key, bearer_auth],
        responses={
            200: openapi.Response(
                description="Detailed performance data for the candidate."
            ),
            401: error_response_401,
            403: error_response_403,
            404: openapi.Response(
                description="Not Found. E.g., leaderboard or candidate not found."
            ),
        },
        tags=["Leaderboard"],
    )
    def get(self, request: Request, stage: str, level: int, candidate_id):
        user = request.user
        user_role_key = self._get_user_role_key(user)

        latest_snapshot = self._get_latest_leaderboard_snapshot()
        if not latest_snapshot:
            return Response(
                {"detail": "No published leaderboard found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cache_key = f"leaderboard_detail_{latest_snapshot.id}_{stage}_{level}_{candidate_id}_{user_role_key}"
        cached_data = self._get_cached_leaderboard_detail_response(cache_key)
        if cached_data:
            return Response(cached_data)

        candidate_entry, leaderboard = self._get_leaderboard_entry(
            latest_snapshot, stage, level, candidate_id
        )

        if not candidate_entry:
            return Response(
                {"detail": "Candidate not found in this leaderboard"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(request.user, "candidate_profile"):
            if request.user.candidate_profile.role == Candidate.Roles.SCREENING:
                if request.user.candidate_profile.id != candidate_id:
                    return Response(
                        {"detail": "You can only view your own performance."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        exam_details = {
            "id": leaderboard.get("exam_id"),
            "title": leaderboard.get("exam_title"),
            "stage": leaderboard.get("stage"),
            "level": leaderboard.get("level"),
            "scheduled_date": leaderboard.get("scheduled_date"),
            "concluded_at": leaderboard.get("concluded_at"),
            "total_questions": leaderboard.get("total_questions"),
            "total_candidates": leaderboard.get("total_candidates"),
            "average_score": leaderboard.get("average_score"),
        }

        response_data = {
            "exam_details": exam_details,
            "candidate_performance": candidate_entry,
        }
        cache.set(cache_key, response_data, timeout=21600)  # cache for 6 hours
        return Response(response_data)

    def _get_cached_leaderboard_detail_response(self, cache_key):
        """Helper to check and return cached leaderboard detail data."""
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached leaderboard detail for key: {cache_key}")
        return cached_data

    def _get_user_role_key(self, user):
        """Helper to generate a cache key based on user role."""
        if hasattr(user, "candidate_profile"):
            return f"candidate_{user.candidate_profile.role}"
        return "staff"

    def _get_leaderboard_entry(self, latest_snapshot, stage, level, candidate_id):
        """Helper to find the specific candidate's entry in the leaderboard."""
        leaderboard_key = f"{stage}_{level}"

        if leaderboard_key not in latest_snapshot.data:
            return None, None

        leaderboard = latest_snapshot.data[leaderboard_key]
        entries = leaderboard.get("entries", [])

        candidate_entry = next(
            (
                entry
                for entry in entries
                if entry["candidate"]["id"] == str(candidate_id)
            ),
            None,
        )
        return candidate_entry, leaderboard
