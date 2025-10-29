import logging

from django.db.models import Count, Q
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.settings import api_settings

from vmlc.serializers.exam import ExamListSerializer

from ..models import Candidate, Exam, LeaderboardSnapshot
from ..permissions import (
    CandidatePermissions,
    VerifiedAdminPermissions,
    VerifiedModeratorPermissions,
)
from ..serializers.leaderboard import (
    PublishLeaderboardSerializer,
    LeaderboardSnapshotListSerializer,
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
        serializer = PublishLeaderboardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        exam_id = serializer.validated_data["exam_id"]
        staff_id = request.user.staff_profile.pk

        from ..tasks import (
            generate_scores_snapshot_task,
            generate_leaderboard_snapshot_task,
        )

        logger.info(
            f"PublishLeaderboardView: request from user {request.user.id} (staff_id: {staff_id}) for exam {exam_id}"
        )
        generate_scores_snapshot_task.delay(staff_id)
        generate_leaderboard_snapshot_task.delay(exam_id, staff_id)

        logger.info(
            f"Leaderboard generation for exam {exam_id} triggered by staff {staff_id}"
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
        snapshots = LeaderboardSnapshot.objects.filter(is_published=True).select_related(
            "exam"
        )

        # Filter based on candidate role
        if hasattr(user, "candidate_profile"):
            if not user.candidate_profile.is_verified:
                return Response(
                    {"detail": "Candidate must be verified to view the leaderboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if user.candidate_profile.role == Candidate.Roles.SCREENING:
                snapshots = snapshots.filter(exam__stage=Candidate.Roles.SCREENING)
            elif user.candidate_profile.role == Candidate.Roles.LEAGUE:
                snapshots = snapshots.filter(
                    Q(exam__stage=Candidate.Roles.SCREENING)
                    | Q(exam__stage=Candidate.Roles.LEAGUE)
                )

        exam_id = request.query_params.get("exam_id")
        
        # If specific exam_id is requested - return leaderboard ENTRIES
        if exam_id:
            try:
                exam = Exam.objects.get(pk=exam_id)
            except Exam.DoesNotExist:
                return Response(
                    {"detail": "Exam not found. Leaderboard unavailable."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            try:
                snapshot = snapshots.get(exam_id=exam_id)
            except LeaderboardSnapshot.DoesNotExist:
                return Response(
                    {"detail": "Leaderboard snapshot not found for this exam."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Extract leaderboard entries - already serialized
            leaderboard_data = snapshot.data
            
            exam_details = ExamListSerializer(exam).data
            
            # Paginate the leaderboard entries
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(leaderboard_data, request, view=self)

            if page is not None:
                # Data is already serialized, just return it
                response = paginator.get_paginated_response(page)
                response.data["exam_details"] = exam_details
                response.data["list"] = response.data.pop("results")
                if "count" in response.data:
                    del response.data["count"]
                return response

            # If pagination not applied (shouldn't happen)
            return Response({"exam_details": exam_details, "list": leaderboard_data})
        
        # If no exam_id - return list of SNAPSHOTS (metadata only)
        else:
            snapshot_list = snapshots.order_by("-created_at")
            
            # Aggregate exam statistics
            exam_details = Exam.objects.aggregate(
                total_exams=Count("id"),
                screening_exams=Count("id", filter=Q(stage=Exam.Stages.SCREENING)),
                league_exams=Count("id", filter=Q(stage=Exam.Stages.LEAGUE)),
            )
            
            # Paginate the queryset of snapshots
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(snapshot_list, request, view=self)

            if page is not None:
                # Serialize the snapshot objects (not their data)
                serializer = LeaderboardSnapshotListSerializer(page, many=True)
                response = paginator.get_paginated_response(serializer.data)
                response.data["exam_details"] = exam_details
                response.data["list"] = response.data.pop("results")
                if "count" in response.data:
                    del response.data["count"]
                return response

            # If pagination not applied
            serializer = LeaderboardSnapshotListSerializer(snapshot_list, many=True)
            return Response({"exam_details": exam_details, "list": serializer.data})