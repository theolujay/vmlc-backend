import logging
import logging
from django.db.models import F, Count, Avg, Q, Max, Min, Exists, OuterRef
from competition.models import (
    Competition,
    StageExam,
    Enrollment,
    RankingSnapshot,
    RankingSnapshotEntry,
)
from vmlc.models import Exam, CandidateExamResult, CandidateAnswer, ExamAccess
from competition.services.leaderboard import LeaderboardService
from competition.serializers import (
    LeagueLeaderboardEntrySerializer,
    RankingSnapshotEntrySerializer,
)
from vmlc.v2.utils import truncate_float


logger = logging.getLogger(__name__)

_EMPTY_EXAM_STATS = {"sat": 0, "avg": 0, "highest": 0, "lowest": 0}


class RankingStatus:
    PENDING = "pending"
    READY = "ready"
    PUBLISHED = "published"


class StaffCompetitionDashboardService:
    @staticmethod
    def get_dashboard_data() -> dict:
        active_comp = Competition.objects.filter(
            status=Competition.Status.ACTIVE
        ).first()
        if not active_comp:
            return {}

        return {
            "stats": _get_enrollment_stats(active_comp),
            "progress": _get_progress(active_comp),
            "exams": _get_exams_list(active_comp),
            "leaderboard_summary": _get_leaderboard_summary(active_comp),
            "latest_ranking_summary": _get_latest_ranking_summary(active_comp),
        }


def _get_enrollment_stats(competition: Competition) -> dict:
    stats = Enrollment.objects.filter(competition=competition).aggregate(
        enrolled=Count("id"),
        active=Count("id", filter=Q(status=Enrollment.Status.ACTIVE)),
        eliminated=Count("id", filter=Q(status=Enrollment.Status.ELIMINATED)),
        disqualified=Count("id", filter=Q(status=Enrollment.Status.DISQUALIFIED)),
    )

    stage_funnel = (
        Enrollment.objects.filter(
            competition=competition,
            status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.ELIMINATED],
        )
        .values("current_stage__type")
        .annotate(count=Count("id"))
        .order_by("current_stage__order")
    )
    stats["stage_breakdown"] = {
        item["current_stage__type"]: item["count"] for item in stage_funnel
    }

    return stats


def _get_progress(competition: Competition) -> dict:
    latest_active_slot = (
        StageExam.objects.filter(
            competition_stage__competition=competition, is_active=True
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
            competition_stage__competition=competition,
            competition_stage__type=current_stage_type,
        ).count()

        published_rounds = RankingSnapshot.objects.filter(
            competition=competition,
            stage=current_stage_type,
            is_published=True,
        ).count()

    return {
        "current_stage": current_stage_type,
        "current_round": current_round,
        "total_rounds": total_rounds,
        "published_rounds": published_rounds,
    }


def _get_exams_list(competition: Competition) -> list:
    slots = (
        StageExam.objects.filter(competition_stage__competition=competition)
        .select_related("competition_stage", "exam")
        .order_by(
            "competition_stage__order",
            "round",
            F("exam__scheduled_date").desc(nulls_last=True),
        )
    )

    exam_stats_map = _build_exam_stats_map(competition)
    rankings_map = _build_rankings_map(competition)
    eligible_counts_map = _build_eligible_counts_map(competition)

    exams_list = []
    for slot in slots:
        try:
            exam = slot.exam
        except Exam.DoesNotExist:
            continue

        if exam.status in [Exam.Status.DRAFT, Exam.Status.CANCELLED]:
            continue

        exams_list.append(
            _build_exam_entry(
                slot, exam, exam_stats_map, rankings_map, eligible_counts_map
            )
        )

    return exams_list


def _build_exam_stats_map(competition: Competition) -> dict:
    """
    Builds a map of exam_id -> aggregate stats.
    Uses RankingSnapshot data if available and active,
    otherwise falls back to CandidateExamResult with strict participation checks.
    """
    # Identify exams with active rankings in this competition.
    active_rankings = RankingSnapshot.objects.filter(
        competition=competition, is_active=True
    ).values_list("exam_id", flat=True)

    # 2. Query stats from RankingSnapshotEntry for those exams
    ranking_aggregates = (
        RankingSnapshotEntry.objects.filter(
            ranking_snapshot__exam_id__in=active_rankings,
            ranking_snapshot__is_active=True,
            attempt_status="present",
        )
        .values("ranking_snapshot__exam_id")
        .annotate(
            sat=Count("id"),
            avg=Avg("exam_score"),
            highest=Max("exam_score"),
            lowest=Min("exam_score"),
        )
    )

    stats_map = {
        res["ranking_snapshot__exam_id"]: {
            "sat": res["sat"],
            "avg": res["avg"],
            "highest": res["highest"],
            "lowest": res["lowest"],
        }
        for res in ranking_aggregates
    }

    # 3. Query "live" stats for remaining exams
    remaining_exams_ids = (
        StageExam.objects.filter(competition_stage__competition=competition)
        .exclude(exam__id__in=active_rankings)
        .values_list("exam__id", flat=True)
    )

    if remaining_exams_ids:
        has_answers_subquery = CandidateAnswer.objects.filter(
            candidate_exam_result=OuterRef("id")
        )

        live_aggregates = (
            CandidateExamResult.objects.filter(
                exam_id__in=remaining_exams_ids,
                candidate__user__is_active=True,
            )
            .annotate(
                has_answers=Exists(has_answers_subquery),
            )
            .filter(
                # A candidate is considered to have "sat" if they have answers
                # or if a staff member manually submitted a score for them.
                Q(has_answers=True)
                | Q(score_submitted_by__isnull=False)
            )
            .values("exam_id")
            .annotate(
                sat=Count("id"),
                avg=Avg("score"),
                highest=Max("score"),
                lowest=Min("score"),
            )
        )

        for res in live_aggregates:
            stats_map[res["exam_id"]] = {
                "sat": res["sat"],
                "avg": res["avg"],
                "highest": res["highest"],
                "lowest": res["lowest"],
            }

    return stats_map


def _build_rankings_map(competition: Competition) -> dict:
    return {
        r.exam_id: r
        for r in RankingSnapshot.objects.filter(competition=competition, is_active=True)
    }


def _build_eligible_counts_map(competition: Competition) -> dict:
    """
    Builds a map of exam_id -> eligible candidate count in a single query,
    avoiding the N+1 that results from calling exam.access_records.count()
    per exam inside a loop.
    """
    counts = (
        ExamAccess.objects.filter(
            exam__competition_slot__competition_stage__competition=competition
        )
        .values("exam_id")
        .annotate(count=Count("id"))
    )
    return {row["exam_id"]: row["count"] for row in counts}


def _build_exam_entry(
    slot, exam, exam_stats_map, rankings_map, eligible_counts_map
) -> dict:
    res_stats = exam_stats_map.get(exam.id, _EMPTY_EXAM_STATS)
    ranking = rankings_map.get(exam.id)

    if ranking is None:
        ranking_status = RankingStatus.PENDING
    elif ranking.is_published:
        ranking_status = RankingStatus.PUBLISHED
    else:
        ranking_status = RankingStatus.READY

    eligible_count = eligible_counts_map.get(exam.id, 0)
    participation_rate = (
        (res_stats["sat"] / eligible_count * 100) if eligible_count > 0 else 0
    )

    return {
        "id": exam.id,
        "title": str(exam),
        "stage": slot.competition_stage.type,
        "round": slot.round,
        "status": exam.status,
        "ranking_status": ranking_status,
        "stats": {
            "candidates_sat": res_stats["sat"],
            "eligible_candidates": eligible_count,
            "participation_rate": truncate_float(participation_rate),
            "avg_score": truncate_float(float(res_stats["avg"] or 0)),
            "highest_score": truncate_float(float(res_stats["highest"] or 0)),
            "lowest_score": truncate_float(float(res_stats["lowest"] or 0)),
        },
    }


def _get_leaderboard_summary(competition: Competition) -> list:
    latest_leaderboard = LeaderboardService.get_latest_league_leaderboard(competition, is_public=True)
    if not latest_leaderboard:
        return []

    return LeagueLeaderboardEntrySerializer(
        latest_leaderboard.processed_entries[:3], many=True
    ).data


def _get_latest_ranking_summary(competition: Competition) -> dict | None:
    latest_published_ranking = (
        RankingSnapshot.objects.filter(competition=competition, is_published=True)
        .select_related("exam")
        .order_by("-published_at", "-created_at")
        .first()
    )
    if not latest_published_ranking:
        return None

    entries = latest_published_ranking.entries.select_related(
        "candidate__user"
    ).order_by("rank")[:3]

    return {
        "exam_id": latest_published_ranking.exam_id,
        "exam_title": str(latest_published_ranking.exam),
        "stage": latest_published_ranking.stage,
        "round": latest_published_ranking.round,
        "entries": RankingSnapshotEntrySerializer(entries, many=True).data,
    }
