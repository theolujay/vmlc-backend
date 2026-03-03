from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.db import transaction

from identity.models import Staff
from identity.permissions import (
    ActiveManagerPermissions,
    ActiveAdminPermissions,
    ActiveModeratorPermissions,
    ActiveSuperadminPermissions,
    ActiveVolunteerPermissions,
    CanViewRankingSnapshot,
    CandidatePermissions,
    IsLeagueParticipantOrStaff,
    get_enrollment,
)
from competition.models import RankingSnapshot, RankingSnapshotEntry, Stage
from competition.serializers import (
    LeagueLeaderboardSerializer,
    PublishRankingSnapshotSerializer,
    RankingSnapshotListSerializer,
    RankingSnapshotSerializer,
    CandidateResultDetailSerializer,
    LeagueLeaderboardEntrySerializer,
    CompetitionDashboardSerializer,
    PromoteCandidatesSerializer,
)
from competition.tasks import (
    generate_ranking_task,
    update_leaderboard_task,
    invalidate_published_ranking_cache_task,
)
from competition.services.leaderboard import LeaderboardService
from competition.services.staff_dashboard import StaffCompetitionDashboardService
from competition.services.candidate_dashboard import CandidateDashboardService
from competition.services.progression import ProgressionService, ProgressionError

from vmlc.models import Exam, CandidateExamResult, ExamAccess
from vmlc.v2.utils import CacheKeys, get_or_set_cache


class CandidateDashboardView(APIView):
    """
    Retrieve comprehensive dashboard data for the currently authenticated candidate.
    """

    permission_classes = CandidatePermissions

    def get(self, request):
        candidate = request.user.candidate_profile
        enrollment = get_enrollment(request)
        from vmlc.v2.utils import CacheKeys

        cache_key = CacheKeys.CANDIDATE_DASHBOARD_V2.format(candidate_id=candidate.pk)

        data = get_or_set_cache(
            cache_key,
            lambda: CandidateDashboardService.get_dashboard_data(candidate, enrollment),
            ttl=3600,
        )
        return Response(data)


class StaffCompetitionDashboardView(APIView):
    """
    Provides an aggregated view of competition statistics and progress.
    """

    permission_classes = ActiveVolunteerPermissions

    def get(self, request):
        data = get_or_set_cache(
            CacheKeys.STAFF_DASHBOARD,
            lambda: StaffCompetitionDashboardService.get_dashboard_data(),
            ttl=3600,
        )
        serializer = CompetitionDashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ListRankingSnapshotsView(ListAPIView):
    """
    Lists all ranking snapshots marked as active
    """

    serializer_class = RankingSnapshotListSerializer
    permission_class = ActiveModeratorPermissions

    def get_queryset(self):
        return (
            RankingSnapshot.objects.annotate(
                question_count=Count(
                    "exam__questions", filter=Q(exam__questions__is_archived=False)
                )
            )
            .filter(is_active=True)
            .select_related("exam")
            .order_by("-created_at")
        )


class PublishRankingSnapshotView(APIView):
    """
    View to trigger the generation and optional publishing of ranking snapshots.
    """

    permission_classes = ActiveAdminPermissions

    def post(self, request):
        serializer = PublishRankingSnapshotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        staff = request.user.staff_profile
        data = serializer.validated_data
        exam_id = data["exam_id"]
        publish_now = data["publish_now"]

        if publish_now and staff.role != Staff.Roles.SUPERADMIN:
            return Response(
                {
                    "detail": "You do not have permissions to publish rankings"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            exam = Exam.objects.select_related(
                "competition_slot__competition_stage__competition",
            ).get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {"detail": "Exam not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not exam.competition_slot:
            return Response(
                {"detail": "This exam is not linked to any competition stage round."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not exam.status == Exam.Status.CONCLUDED:
            return Response(
                {"detail": "This exam isn't yet concluded"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        competition_stage_round = exam.competition_slot.round
        competition_stage = exam.competition_slot.competition_stage
        stage_exam_id = exam.competition_slot.id
        competition_id = exam.competition_slot.competition_stage.competition.id

        if publish_now:
            ranking = RankingSnapshot.objects.filter(
                exam=exam, is_active=True  # only one should be active
            ).first()

            if not ranking:
                return Response(
                    {"error": "No active ranking snapshot available to publish."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Enforce the 'one_published_ranking_per_stage_round' constraint by
            # unpublishing any other ranking snapshot for the same stage/round.
            with transaction.atomic():
                RankingSnapshot.objects.filter(
                    competition=competition_id,
                    stage=competition_stage.type,
                    round=competition_stage_round,
                ).exclude(id=ranking.id).update(
                    is_published=False, published_at=None, is_active=False
                )
                ranking.is_active = True  # although this should already be True at this point, but lt's add it anyway
                ranking.is_published = True
                ranking.published_at = timezone.now()
                ranking.meta["published_by"] = str(staff.pk)
                ranking.save(
                    update_fields=[
                        "is_active",
                        "is_published",
                        "published_at",
                        "meta",
                    ]
                )
                # Trigger cache invalidation for all candidates in this snapshot
                transaction.on_commit(
                    invalidate_published_ranking_cache_task.delay(
                        ranking_snapshot_id=ranking.id
                    )
                )
                # Trigger leaderboard update if it's a league exam
                if ranking.stage == Stage.Type.LEAGUE:
                    transaction.on_commit(
                        update_leaderboard_task.delay(
                            competition_id=ranking.competition_id,
                            as_of_round=ranking.round,
                        )
                    )
                return Response(
                    {"message": "Ranking snapshot published."},
                    status=status.HTTP_202_ACCEPTED,
                )

        generate_ranking_task.delay(stage_exam_id=str(stage_exam_id), actor_id=staff.id)

        return Response(
            {"message": "Ranking snapshot generation has been started."},
            status=status.HTTP_202_ACCEPTED,
        )


class RetrieveRankingSnapshotView(RetrieveAPIView):
    """
    View to retrieve a specific ranking snapshot using Exam ID.
    """

    serializer_class = RankingSnapshotSerializer
    permission_classes = [CanViewRankingSnapshot]
    # permission_classes = ActiveModeratorPermissions
    lookup_field = "exam_id"

    def get(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_field]
        cache_key = CacheKeys.RANKING_SNAPSHOT.format(exam_id=exam_id)
        data = get_or_set_cache(
            cache_key, lambda: self._fetch_snapshot_data(exam_id=exam_id)
        )

        if data is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def _fetch_snapshot_data(self, exam_id):
        ranking = (
            RankingSnapshot.objects.prefetch_related(
                Prefetch(
                    "entries",
                    queryset=RankingSnapshotEntry.objects.select_related(
                        "candidate__user"
                    ).order_by("rank"),
                )
            )
            .filter(is_active=True, exam_id=exam_id)
            .first()
        )
        if ranking:
            return self.get_serializer(ranking).data
        return None


class LeagueLeaderboardView(APIView):
    """
    View to retrieve the cumulative league leaderboard.
    """

    permission_classes = IsLeagueParticipantOrStaff

    def get(self, request):
        # TODO: Implement stricter access control.
        # Only candidates in the 'league' stage (or staff) should view this.

        def fetch_and_serialize_leaderboard():
            leaderboard = LeaderboardService.get_latest_league_leaderboard()
            if not leaderboard:
                return None

            serializer = LeagueLeaderboardSerializer(leaderboard)
            data = serializer.data

            # Replace entries with the processed list from the service
            # (which includes rank_change annotations)
            data["entries"] = LeagueLeaderboardEntrySerializer(
                leaderboard.processed_entries, many=True
            ).data
            return data

        data = get_or_set_cache(
            CacheKeys.LEADERBOARD_LEAGUE, fetch_and_serialize_leaderboard, ttl=86400
        )

        if not data:
            return Response(
                {"detail": "No active league leaderboard found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(data)


class RetrieveCandidateRankingSnapshotEntryView(APIView):
    """
    Retrieves detailed performance for a specific candidate in a specific exam ranking snapshot.
    """

    # permission_classes = [CanViewOwnOrStaffRankingSnapshotEntry]
    permission_classes = ActiveAdminPermissions

    def get(self, request, exam_id, candidate_id):
        cache_key = CacheKeys.RANKING_SNAPSHOT_ENTRY.format(
            exam_id=exam_id, candidate_id=candidate_id
        )
        data = get_or_set_cache(
            cache_key, lambda: self._fetch_data(request, exam_id, candidate_id)
        )
        if data is None:
            return Response(
                {"detail": "Candidate not found in this ranking board."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)

    def _fetch_data(self, request, exam_id, candidate_id):
        ranking_snapshot = RankingSnapshot.objects.filter(
            exam_id=exam_id,
            is_active=True,
        ).first()

        if not ranking_snapshot:
            return None

        entry = RankingSnapshotEntry.objects.filter(
            ranking_snapshot=ranking_snapshot,
            candidate_id=candidate_id,
        ).first()

        if not entry:
            return None

        result = (
            CandidateExamResult.objects.filter(
                exam_id=exam_id,
                candidate_id=candidate_id,
            )
            .prefetch_related("answers__question")
            .first()
        )

        # if not result:
        #     return None

        # Prepare candidate info
        candidate = entry.candidate
        candidate_info = {
            "id": candidate.pk,
            "full_name": candidate.user.get_full_name(),
            "email": candidate.user.email,
            "state": candidate.user.state,
            "school_name": candidate.school_name,
            "school_type": candidate.school_type,
            "current_class": candidate.current_class,
        }

        if result:
            # Manually attach rank/percentile from RankingSnapshotEntry to result object for serialization
            result.rank = entry.rank
            result.percentile = entry.percentile
            candidate_performance = CandidateResultDetailSerializer(result).data
        else:
            # For absentees, we still want to provide basic performance info
            candidate_performance = {
                "score": "absent" if entry.exam_score is None else entry.exam_score,
                "rank": entry.rank,
                "percentile": entry.percentile,
                "recorded_at": None,
                "auto_score": False,
                "submissions": [],
            }

        exam = ranking_snapshot.exam
        exam_details = {
            "id": exam.id,
            "title": exam.get_title(),
            "stage": ranking_snapshot.stage,
            "round": ranking_snapshot.round,
            "scheduled_date": exam.scheduled_date,
            "concluded_at": exam.concluded_at,
            "total_questions": exam.get_question_count(),
            "total_candidates": ranking_snapshot.entries.count(),
            "average_score": float(exam.get_average_score() or 0),
        }

        # Add access/execution details from ExamAccess
        exam_access = ExamAccess.objects.filter(
            exam_id=exam_id, candidate_id=candidate_id
        ).first()
        if exam_access:
            candidate_performance["started_at"] = exam_access.started_at
            candidate_performance["submitted_at"] = exam_access.submitted_at
            # Serialize image URL properly
            if exam_access.face_capture:
                candidate_performance["face_capture"] = request.build_absolute_uri(
                    exam_access.face_capture.url
                )
            else:
                candidate_performance["face_capture"] = None
        else:
            candidate_performance["started_at"] = None
            candidate_performance["submitted_at"] = None
            candidate_performance["face_capture"] = None

        return {
            "exam_details": exam_details,
            "candidate_info": candidate_info,
            "candidate_performance": candidate_performance,
        }


class LeagueCandidateLeaderboardView(APIView):
    """
    Retrieves cumulative performance for a specific candidate in the league leaderboard.
    """

    permission_classes = IsLeagueParticipantOrStaff

    def get(self, request, candidate_id):
        leaderboard = LeaderboardService.get_latest_league_leaderboard()
        if not leaderboard:
            return Response(
                {"detail": "No active leaderboard found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Access control
        if hasattr(request.user, "candidate_profile"):
            if str(request.user.candidate_profile.pk) != str(candidate_id):
                if not request.user.is_staff:
                    return Response(
                        {"detail": "You can only view your own performance."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # The service already annotated rank_change on processed_entries
        entry = next(
            (
                e
                for e in leaderboard.processed_entries
                if str(e.candidate_id) == str(candidate_id)
            ),
            None,
        )

        if not entry:
            return Response(
                {"detail": "Candidate not found in leaderboard."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(LeagueLeaderboardEntrySerializer(entry).data)


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
                from_stage_type=data["from_stage"],
                to_stage_type=data["to_stage"],
                cutoff_rank=data.get("cutoff_rank", None),
                competition_id=data.get("competition_id", None),
            )

            return Response(
                {
                    "status": "success",
                    "message": f"Successfully promoted {promoted_count} candidates to {data['to_stage']}.",
                }
            )
        except ProgressionError as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": "An unexpected error occurred during promotion.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
