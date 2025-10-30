import logging
import uuid
from collections import OrderedDict

from django.core.paginator import Paginator
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

    def get(self, request: Request):
        logger.info(f"LoadLeaderboardView: request from user {request.user.id}")
        user = request.user

        # Get the most recent published snapshot
        latest_snapshot = LeaderboardSnapshot.objects.filter(
            is_published=True
        ).order_by("-created_at").first()
        
        if latest_snapshot is None:
            return Response(
                {"detail": "No published leaderboard found."},
                status=status.HTTP_404_NOT_FOUND
            )

        all_leaderboards = latest_snapshot.data
        
        # Check if user has permission to view leaderboards
        if hasattr(user, "candidate_profile"):
            if not user.candidate_profile.is_user_verified:
                return Response(
                    {"detail": "Candidate must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Filter based on query parameters
        requested_stage = request.query_params.get('stage')
        requested_level = request.query_params.get('level')
        
        # If specific stage and level requested, return that leaderboard
        if requested_stage and requested_level:
            leaderboard_key = f"{requested_stage}_{requested_level}"
            
            if leaderboard_key not in all_leaderboards:
                return Response(
                    {"detail": f"No leaderboard found for {requested_stage} level {requested_level}"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            leaderboard_data = all_leaderboards[leaderboard_key]
            
            # Apply role-based access control
            if hasattr(user, "candidate_profile"):
                candidate = user.candidate_profile
                
                if candidate.role == Candidate.Roles.SCREENING and requested_stage != "screening":
                    return Response(
                        {"detail": "You can only view screening leaderboards."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            
            # Split entries into top 3 and remaining
            entries = leaderboard_data.get("entries", [])
            top_three = entries[:3] if len(entries) >= 3 else entries
            remaining = entries[3:] if len(entries) > 3 else []
            
            # Use the global pagination class to paginate remaining candidates
            paginator = self.pagination_class()
            paginated_remaining = paginator.paginate_queryset(remaining, request, view=self)
            
            # Get pagination data (without Response wrapper)
            pagination_data = paginator.get_paginated_response_data(paginated_remaining)
            
            # Build custom response with exam info + top_three + paginated remaining
            return Response(OrderedDict([
                ("exam_id", leaderboard_data.get("exam_id")),
                ("exam_title", leaderboard_data.get("exam_title")),
                ("stage", leaderboard_data.get("stage")),
                ("level", leaderboard_data.get("level")),
                ("stage_display", leaderboard_data.get("stage_display")),
                ("total_candidates", leaderboard_data.get("total_candidates")),
                ("average_score", leaderboard_data.get("average_score")),
                ("top_three", top_three),
                ("remaining_candidates", pagination_data["results"]),
                ("pagination", pagination_data["pagination"]),
            ]))
        
        # No specific leaderboard requested - return summary
        accessible_leaderboards = {}
        
        if hasattr(user, "candidate_profile"):
            candidate = user.candidate_profile
            
            if candidate.role == Candidate.Roles.SCREENING:
                accessible_leaderboards = {
                    key: value for key, value in all_leaderboards.items() 
                    if key.startswith("screening_")
                }
            else:
                accessible_leaderboards = all_leaderboards
        elif hasattr(user, "staff_profile"):
            accessible_leaderboards = all_leaderboards
        
        # Build summary
        leaderboards_summary = []
        for key in sorted(accessible_leaderboards.keys()):
            lb = accessible_leaderboards[key]
            if isinstance(lb, dict):
                leaderboards_summary.append({
                    "stage": lb.get("stage"),
                    "level": lb.get("level"),
                    "stage_display": key,
                    "exam_title": lb.get("exam_title"),
                    "total_candidates": lb.get("total_candidates"),
                    "average_score": lb.get("average_score"),
                })
        
        return Response({
            "snapshot_id": latest_snapshot.id,
            "published_at": latest_snapshot.created_at.isoformat(),
            "available_leaderboards": leaderboards_summary
        })
    
class LoadLeaderboardDetailView(APIView):
    """
    Returns detailed performance for a specific candidate in a specific exam.
    
    URL: leaderboard/<stage>/<level>/candidate/<candidate_id>/
    Example: leaderboard/league/2/candidate/123/
    """
    
    permission_classes = VerifiedModeratorPermissions or CandidatePermissions
    
    def get(self, request: Request, stage: str, level: int, candidate_id: uuid):
        # Get latest snapshot
        latest_snapshot = LeaderboardSnapshot.objects.filter(
            is_published=True
        ).order_by("-created_at").first()
        
        if not latest_snapshot:
            return Response(
                {"detail": "No published leaderboard found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build the leaderboard key
        leaderboard_key = f"{stage}_{level}"
        
        if leaderboard_key not in latest_snapshot.data:
            return Response(
                {"detail": f"No leaderboard found for {stage} level {level}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        leaderboard = latest_snapshot.data[leaderboard_key]
        entries = leaderboard.get("entries", [])
        
        # Find the candidate in the entries
        candidate_entry = next(
            (entry for entry in entries 
             if entry["candidate"]["id"] == candidate_id),
            None
        )
        
        if not candidate_entry:
            return Response(
                {"detail": "Candidate not found in this leaderboard"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Apply permission check
        if hasattr(request.user, "candidate_profile"):
            # Candidates can only view their own details or if they're in league stage
            if request.user.candidate_profile.role == Candidate.Roles.SCREENING:
                if request.user.candidate_profile.id != candidate_id:
                    return Response(
                        {"detail": "You can only view your own performance."},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        # Return full candidate details including submissions
        return Response({
            "exam_info": {
                "exam_id": leaderboard.get("exam_id"),
                "exam_title": leaderboard.get("exam_title"),
                "stage": leaderboard.get("stage"),
                "level": leaderboard.get("level"),
                "total_questions": leaderboard.get("total_questions"),
            },
            "candidate_performance": candidate_entry
        })