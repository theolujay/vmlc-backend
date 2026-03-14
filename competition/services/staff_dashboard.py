import logging
from django.db.models import Count, Avg, Q, Max, Min
from competition.models import (
    Competition,
    StageExam,
    Enrollment,
    RankingSnapshot,
    Stage,
)
from vmlc.models import Exam, CandidateExamResult
from competition.services.leaderboard import LeaderboardService
from competition.serializers import (
    LeagueLeaderboardEntrySerializer,
    RankingSnapshotEntrySerializer,
)
from vmlc.v2.utils import truncate_float

logger = logging.getLogger(__name__)


class StaffCompetitionDashboardService:
    @staticmethod
    def get_dashboard_data():
        active_comp = Competition.objects.filter(
            status=Competition.Status.ACTIVE
        ).first()
        if not active_comp:
            return {}

        # 1. Global Enrollment Stats
        stats = Enrollment.objects.filter(competition=active_comp).aggregate(
            enrolled=Count("id"),
            active=Count("id", filter=Q(status=Enrollment.Status.ACTIVE)),
            eliminated=Count("id", filter=Q(status=Enrollment.Status.ELIMINATED)),
            disqualified=Count("id", filter=Q(status=Enrollment.Status.DISQUALIFIED)),
        )

        # 2. Stage-wise Funnel (How many candidates are in each stage right now)
        stage_funnel = (
            Enrollment.objects.filter(
                competition=active_comp,
                status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.ELIMINATED],
            )
            .values("current_stage__type")
            .annotate(count=Count("id"))
            .order_by("current_stage__order")
        )
        stats["stage_breakdown"] = {
            item["current_stage__type"]: item["count"] for item in stage_funnel
        }

        # 3. Compute Progress
        latest_active_slot = (
            StageExam.objects.filter(
                competition_stage__competition=active_comp, is_active=True
            )
            .select_related("competition_stage")
            .order_by("-competition_stage__order", "-round")
            .first()
        )

        current_stage_type = (
            latest_active_slot.competition_stage.type if latest_active_slot else None
        )
        current_round = latest_active_slot.round if latest_active_slot else None

        total_rounds = 0
        published_rounds = 0
        if current_stage_type is not None:
            total_rounds = StageExam.objects.filter(
                competition_stage__competition=active_comp,
                competition_stage__type=current_stage_type,
            ).count()

            published_rounds = RankingSnapshot.objects.filter(
                competition=active_comp, stage=current_stage_type, is_published=True
            ).count()

        progress = {
            "current_stage": current_stage_type,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "published_rounds": published_rounds,
        }

        # 4. Gather Exams data (Optimized with batch aggregation)
        slots = (
            StageExam.objects.filter(competition_stage__competition=active_comp)
            .select_related("competition_stage", "exam")
            .order_by("competition_stage__order", "round")
        )

        # Batch fetch all exam results for this competition to avoid N+1
        exam_results_aggregate = (
            CandidateExamResult.objects.filter(
                exam__competition_slot__competition_stage__competition=active_comp,
                candidate__user__is_active=True,
            )
            .values("exam_id")
            .annotate(
                sat=Count("id"),
                avg=Avg("score"),
                highest=Max("score"),
                lowest=Min("score"),
            )
        )
        exam_stats_map = {res["exam_id"]: res for res in exam_results_aggregate}

        # Batch fetch ranking status
        rankings_map = {
            r.exam_id: r
            for r in RankingSnapshot.objects.filter(
                competition=active_comp, is_active=True
            )
        }

        # Count candidates per stage for participation rates
        # Each stage shows candidates currently in that stage (ACTIVE + ELIMINATED)
        stage_eligibility_map = {
            s["current_stage__type"]: s["count"] for s in stage_funnel
        }

        exams_list = []
        for slot in slots:
            try:
                exam = slot.exam
            except Exam.DoesNotExist:
                continue

            curr_status = exam.status
            if curr_status in [Exam.Status.DRAFT, Exam.Status.CANCELLED]:
                continue

            res_stats = exam_stats_map.get(
                exam.id, {"sat": 0, "avg": 0, "highest": 0, "lowest": 0}
            )
            ranking = rankings_map.get(exam.id)
            ranking_status = "pending"
            if ranking:
                ranking_status = "published" if ranking.is_published else "ready"

            eligible_count = ranking.entries.count()
            participation_rate = (
                (res_stats["sat"] / eligible_count * 100) if eligible_count > 0 else 0
            )

            exams_list.append(
                {
                    "id": exam.id,
                    "title": str(exam),
                    "stage": slot.competition_stage.type,
                    "round": slot.round,
                    "status": curr_status,
                    "ranking_status": ranking_status,
                    "stats": {
                        "candidates_sat": res_stats["sat"],
                        "eligible_candidates": eligible_count,
                        "participation_rate": truncate_float(participation_rate),
                        "avg_score": truncate_float(float(res_stats["avg"] or 0)),
                        "highest_score": truncate_float(
                            float(res_stats["highest"] or 0)
                        ),
                        "lowest_score": truncate_float(float(res_stats["lowest"] or 0)),
                    },
                }
            )

        # 5. Summaries (Top Performers)
        leaderboard_summary_data = []
        latest_leaderboard = LeaderboardService.get_latest_league_leaderboard(
            active_comp
        )
        if latest_leaderboard:
            leaderboard_summary_data = LeagueLeaderboardEntrySerializer(
                latest_leaderboard.processed_entries[:3], many=True
            ).data

        latest_ranking_summary = None
        latest_published_ranking = (
            RankingSnapshot.objects.filter(competition=active_comp, is_published=True)
            .select_related("exam")
            .order_by("-published_at", "-created_at")
            .first()
        )

        if latest_published_ranking:
            entries = latest_published_ranking.entries.select_related(
                "candidate__user"
            ).order_by("rank")[:3]
            latest_ranking_summary = {
                "exam_id": latest_published_ranking.exam_id,
                "exam_title": str(latest_published_ranking.exam),
                "stage": latest_published_ranking.stage,
                "round": latest_published_ranking.round,
                "entries": RankingSnapshotEntrySerializer(entries, many=True).data,
            }

        return {
            "stats": stats,
            "progress": progress,
            "exams": exams_list,
            "leaderboard_summary": leaderboard_summary_data,
            "latest_ranking_summary": latest_ranking_summary,
        }
