from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from identity.permissions import (
    ActiveAdminPermissions, 
    HasXAPIKey, 
    IsLeagueParticipantOrStaff
)
from rest_framework.permissions import IsAuthenticated
from vmlc.models import Exam
from vmlc.utils.swagger_schemas import api_key, bearer_auth, error_response_401, error_response_403
from competition.models import Standings
from competition.serializers import (
    PublishStandingsSerializer, 
    StandingsSerializer, 
    AggregateLeaderboardSerializer,
    AggregateLeaderboardEntrySerializer
)
from competition.tasks import generate_standings_task
from competition.services.leaderboard import LeaderboardService

class PublishStandingsView(APIView):
    """
    View to trigger the generation and optional publishing of standings.
    """
    permission_classes = ActiveAdminPermissions

    @swagger_auto_schema(
        operation_summary="Generate/Publish Standings",
        operation_description="Triggers async generation of standings for a specific Exam.",
        request_body=PublishStandingsSerializer,
        responses={
            202: "Standings generation started.",
            400: "Invalid request",
            401: error_response_401,
            403: error_response_403
        },
        manual_parameters=[api_key, bearer_auth],
        tags=["Competition Leaderboard"]
    )
    def post(self, request):
        serializer = PublishStandingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        exam_id = data['exam_id']
        publish_now = data['publish_now']

        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
             return Response({"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND)

        if not exam.competition_slot:
            return Response(
                {"detail": "This exam is not linked to any competition stage round."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not exam.status == Exam.Status.CONCLUDED:
            return Response(
                {
                    "detail": "This exam isn't yet concluded"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        stage_exam_id = exam.competition_slot.id
        
        # Pass user ID if available
        staff_id = None
        if hasattr(request.user, 'staff_profile'):
             staff_id = str(request.user.staff_profile.id)

        generate_standings_task.delay(
            stage_exam_id=str(stage_exam_id),
            publish_now=publish_now,
            staff_id=staff_id
        )
        
        return Response(
            {
                "message": "Standings generation has been started."
            },
            status=status.HTTP_202_ACCEPTED
        )


class RetrieveStandingsView(RetrieveAPIView):
    """
    View to retrieve a specific standing.
    """
    queryset = Standings.objects.prefetch_related(
        'entries',
        'entries__candidate__user'
    ).all()
    serializer_class = StandingsSerializer
    permission_classes = [ActiveAdminPermissions]
    lookup_field = 'exam_id'

    @swagger_auto_schema(
        operation_summary="Get Specific Standing",
        operation_description="Retrieves the details and entries of a specific standing using Exam ID.",
        responses={
            200: StandingsSerializer,
            401: error_response_401,
            403: error_response_403,
            404: "Not Found"
        },
        manual_parameters=[api_key, bearer_auth],
        tags=["Competition Leaderboard"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class LeagueLeaderboardView(APIView):
    """
    View to retrieve the cumulative league leaderboard.
    """
    permission_classes = [HasXAPIKey, IsAuthenticated, IsLeagueParticipantOrStaff]

    @swagger_auto_schema(
        operation_summary="Get League Leaderboard",
        operation_description="Retrieves the latest cumulative leaderboard for the active competition's league stage.",
        responses={
            200: AggregateLeaderboardSerializer,
            401: error_response_401,
            403: error_response_403,
            404: "No active league leaderboard found."
        },
        manual_parameters=[api_key, bearer_auth],
        tags=["Competition Leaderboard"]
    )
    def get(self, request):
        # TODO: Implement stricter access control.
        # Only candidates in the 'league' stage (or staff) should view this.
        
        leaderboard = LeaderboardService.get_latest_league_leaderboard()
        
        if not leaderboard:
            return Response(
                {"detail": "No active league leaderboard found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AggregateLeaderboardSerializer(leaderboard)
        data = serializer.data
        
        # Replace entries with the processed list from the service
        # (which includes rank_change annotations)
        data['entries'] = AggregateLeaderboardEntrySerializer(
            leaderboard.processed_entries, 
            many=True
        ).data
        
        return Response(data)