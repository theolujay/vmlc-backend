from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from identity.permissions import (
    ActiveManagerPermissions,
    ActiveAdminPermissions,
    ActiveVolunteerPermissions,
    CandidatePermissions,
    IsLeagueParticipantOrStaff
)
from vmlc.models import Exam
from competition.models import Standings, StandingsEntry
from competition.serializers import (
    PublishStandingsSerializer, 
    StandingsSerializer, 
    CandidateResultDetailSerializer,
    AggregateLeaderboardSerializer,
    AggregateLeaderboardEntrySerializer,
    CompetitionDashboardSerializer,
    PromoteCandidatesSerializer
)
from competition.tasks import generate_standings_task
from competition.services.leaderboard import LeaderboardService
from competition.services.staff_dashboard import StaffCompetitionDashboardService
from competition.services.candidate_dashboard import CandidateDashboardService
from competition.services.progression import ProgressionService, ProgressionError

from vmlc.models import Exam, CandidateExamResult
from vmlc.v2.utils import get_or_set_cache



class CandidateDashboardView(APIView):
    """
    Retrieve comprehensive dashboard data for the currently authenticated candidate.
    """
    permission_classes = CandidatePermissions

    def get(self, request):
        candidate = request.user.candidate_profile
        participation = getattr(request, 'participation', None)
        cache_key = f"candidate_dashboard_v2_{candidate.pk}"
        
        data = get_or_set_cache(
            cache_key,
            lambda: CandidateDashboardService.get_dashboard_data(candidate, participation),
            ttl=3600
        )
        return Response(data)


class StaffCompetitionDashboardView(APIView):
    """
    Provides an aggregated view of competition statistics and progress.
    """
    permission_classes = ActiveVolunteerPermissions

    def get(self, request):
        data = StaffCompetitionDashboardService.get_dashboard_data()
        if not data:
            return Response(
                {"detail": "No active competition found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CompetitionDashboardSerializer(data)
        return Response(serializer.data)


class PublishStandingsView(APIView):
    """
    View to trigger the generation and optional publishing of standings.
    """
    permission_classes = ActiveAdminPermissions

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
    View to retrieve a specific standing using Exam ID.
    """
    queryset = Standings.objects.prefetch_related(
        'entries',
        'entries__candidate__user'
    ).all()
    serializer_class = StandingsSerializer
    permission_classes = ActiveAdminPermissions
    lookup_field = 'exam_id'

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class LeagueLeaderboardView(APIView):
    """
    View to retrieve the cumulative league leaderboard.
    """
    permission_classes = IsLeagueParticipantOrStaff

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


class RetrieveCandidateStandingView(APIView):
    """
    Retrieves detailed performance for a specific candidate in a specific exam standing.
    """
    permission_classes = ActiveAdminPermissions

    def get(self, request, exam_id, candidate_id):
        standing = get_object_or_404(Standings, exam_id=exam_id)
        
        # Access control
        if hasattr(request.user, "candidate_profile"):
            if str(request.user.candidate_profile.id) != str(candidate_id):
                # If they are a candidate, they can only see their own detail unless they are staff
                if not request.user.is_staff:
                    return Response(
                        {"detail": "You can only view your own performance."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        entry = get_object_or_404(StandingsEntry, standings=standing, candidate_id=candidate_id)
        
        result = get_object_or_404(
            CandidateExamResult.objects.prefetch_related('answers__question'), 
            exam_id=exam_id, 
            candidate_id=candidate_id
        )
        
        # Manually attach rank/percentile from StandingsEntry to result object for serialization
        result.rank = entry.rank
        result.percentile = entry.percentile

        exam = standing.exam
        exam_details = {
            "id": exam.id,
            "title": exam.get_title(),
            "stage": standing.stage,
            "round": standing.round,
            "scheduled_date": exam.scheduled_date,
            "concluded_at": exam.concluded_at,
            "total_questions": exam.get_question_count(),
            "total_candidates": standing.entries.count(),
            "average_score": float(exam.get_average_score() or 0),
        }

        return Response({
            "exam_details": exam_details,
            "candidate_performance": CandidateResultDetailSerializer(result).data
        })


class LeagueCandidateLeaderboardView(APIView):
    """
    Retrieves cumulative performance for a specific candidate in the league leaderboard.
    """
    permission_classes = IsLeagueParticipantOrStaff

    def get(self, request, candidate_id):
        leaderboard = LeaderboardService.get_latest_league_leaderboard()
        if not leaderboard:
            return Response({"detail": "No active leaderboard found."}, status=status.HTTP_404_NOT_FOUND)

        # Access control
        if hasattr(request.user, "candidate_profile"):
            if str(request.user.candidate_profile.id) != str(candidate_id):
                if not request.user.is_staff:
                    return Response(
                        {"detail": "You can only view your own performance."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # The service already annotated rank_change on processed_entries
        entry = next((e for e in leaderboard.processed_entries if str(e.candidate_id) == str(candidate_id)), None)
        
        if not entry:
            return Response({"detail": "Candidate not found in leaderboard."}, status=status.HTTP_404_NOT_FOUND)

        return Response(AggregateLeaderboardEntrySerializer(entry).data)


class PromoteCandidatesView(APIView):
    """
    Staff-only view to promote candidates from one stage to the next.
    """
    permission_classes = ActiveManagerPermissions

    def post(self, request):
        serializer = PromoteCandidatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        try:
            promoted_count = ProgressionService.promote_candidates(
                from_stage_type=data['from_stage'],
                to_stage_type=data['to_stage'],
                cutoff_rank=data.get('cutoff_rank'),
                competition_id=data.get('competition_id')
            )
            
            return Response({
                "status": "success",
                "message": f"Successfully promoted {promoted_count} candidates to {data['to_stage']}."
            })
        except ProgressionError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
             return Response(
                {"status": "error", "message": "An unexpected error occurred during promotion."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )