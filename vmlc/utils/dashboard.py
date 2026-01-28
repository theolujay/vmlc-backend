from datetime import timedelta
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models import Window
from django.db.models.functions import Rank
from django.utils import timezone

from identity.models import (
    Candidate,
    Staff,
)

from vmlc.models import (
    CandidateExamResult,
    CandidateExamResultSnapshot,
    Exam,
    Question,
)


def get_candidate_dashboard_data(candidate: Candidate) -> Dict[str, Any]:
    """
    Generate dashboard data for a specific candidate.

    Includes:
        - Candidate profile information
        - Exam statistics (taken, available, latest, average, min/max)
        - Recent results and available exams
        - Candidate ranking (if role is 'league')

    Args:
        candidate (Candidate): The candidate for whom the dashboard is being generated.

    Returns:
        dict: A dictionary containing candidate info, exam stats, ranking, recent results, and upcoming exams.
    """

    candidate = Candidate.objects.select_related("user").get(pk=candidate.pk)

    latest_snapshot: Optional[CandidateExamResultSnapshot] = (
        CandidateExamResultSnapshot.objects.filter(published_at__isnull=False)
        .order_by("-published_at")
        .first()
    )

    result_stats, recent_results_list = _get_candidate_performance_stats(
        candidate, latest_snapshot
    )
    available_exams_list = _get_candidate_available_exams(
        candidate, result_stats["taken_exam_ids"]
    )
    concluded_exams_list = _get_candidate_concluded_exams(
        candidate, result_stats["taken_exam_ids"]
    )
    candidate_rank, total_league_candidates = _get_candidate_leaderboard_ranking(
        candidate, latest_snapshot
    )
    screening_rank, total_screening_candidates = _get_candidate_screening_ranking(
        candidate
    )

    dashboard_data = {
        "candidate_info": {
            "first_name": candidate.user.first_name,
            "last_name": candidate.user.last_name,
        },
        "exam_stats": {
            "total_exams_taken": result_stats["total_exams_taken"],
            "available_exams_count": len(available_exams_list),
            "average_score": round(float(result_stats["average_score"] or 0), 2),
            "highest_score": float(result_stats["highest_score"] or 0),
            "lowest_score": float(result_stats["lowest_score"] or 0),
            "latest_score": (
                result_stats["latest_score_data"]["score"]
                if result_stats["latest_score_data"]
                else 0
            ),
            "latest_score_info": result_stats["latest_score_data"],
        },
        "stage_progress": {
            "current_stage": candidate.role,
            "current_round": available_exams_list[0]["round"] if available_exams_list else 1,
            "has_taken_exam": (
                available_exams_list[0]["participation"] == "done"
                if available_exams_list
                else result_stats["total_exams_taken"] > 0
            ),
            "qualification_threshold_range": None,
        },
        "league_leaderboard_ranking": (
            {
                "current_rank": candidate_rank,
                "position": candidate_rank,
                "total_candidates": total_league_candidates,
            }
            if candidate.role == "league"
            else None
        ),
        "screening_standings_ranking": (
            {
                "current_rank": screening_rank,
                "position": screening_rank,
                "total_candidates": total_screening_candidates,
            }
            if screening_rank is not None
            else None
        ),
        "recent_results": [
            {
                "exam": result["exam__title"],
                "exam_title": result["exam__title"],
                "score": float(result["score"]),
                "date": result["recorded_at"],
                "exam_stage": result["exam__stage"],
            }
            for result in recent_results_list
        ],
        "available_exams": available_exams_list,
        "concluded_exams": concluded_exams_list,
        "next_exam": available_exams_list[0] if available_exams_list else None
    }

    cache_key = f"candidate_dashboard_{candidate.pk}"
    cache.set(cache_key, dashboard_data, timeout=3600)  # Cache for 1 hour
    return dashboard_data


def _get_candidate_performance_stats(
    candidate: Candidate, latest_snapshot: Optional[CandidateExamResultSnapshot]
) -> tuple[dict, list]:
    """Helper to get performance statistics for a candidate."""
    all_results_qs = CandidateExamResult.objects.filter(candidate=candidate)
    taken_exam_ids = set(all_results_qs.values_list("exam_id", flat=True))

    results_qs_for_snapshot_stats = all_results_qs
    if latest_snapshot:
        results_qs_for_snapshot_stats = all_results_qs.filter(
            recorded_at__lte=latest_snapshot.published_at
        )

    result_stats = results_qs_for_snapshot_stats.aggregate(
        average_score=Avg("score"),
        highest_score=Max("score"),
        lowest_score=Min("score"),
    )
    total_exams_taken = all_results_qs.count()

    recent_results_list = list(
        all_results_qs.order_by("-recorded_at")
        .select_related("exam")
        .values("score", "exam__title", "recorded_at", "exam__stage")[:5]
    )

    latest_score_data = None
    if recent_results_list:
        latest_score_data = {
            "score": float(recent_results_list[0]["score"]),
            "exam_title": recent_results_list[0]["exam__title"],
            "date": recent_results_list[0]["recorded_at"],
        }
    return {
        "average_score": result_stats["average_score"],
        "highest_score": result_stats["highest_score"],
        "lowest_score": result_stats["lowest_score"],
        "total_exams_taken": total_exams_taken,
        "latest_score_data": latest_score_data,
        "taken_exam_ids": taken_exam_ids,
    }, recent_results_list


def _get_candidate_available_exams(candidate: Candidate, taken_exam_ids: set) -> list:
    """Helper to get available exams for a candidate."""
    available_exams_list = []
    if candidate.is_active:
        all_relevant_exams = (
            Exam.objects.filter(stage=candidate.role.lower(), is_active=True)
            .annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .order_by("scheduled_date")
        )

        for exam in all_relevant_exams:
            if exam.status == Exam.Status.ONGOING:
                available_exams_list.append(
                    {
                        "id": exam.id,
                        "title": exam.title,
                        "stage": exam.stage,
                        "round": exam.round,
                        "stage_display": exam.stage_display,
                        "description": exam.description,
                        "open_duration_hours": exam.open_duration_hours,
                        "scheduled_date": exam.scheduled_date,
                        "countdown_minutes": exam.countdown_minutes,
                        "question_count": exam.question_count,
                        "participation": (
                            "done" if exam.id in taken_exam_ids else "not_done"
                        ),
                    }
                )
    return available_exams_list


def _get_candidate_concluded_exams(candidate: Candidate, taken_exam_ids: set) -> list:
    """Helper to get concluded exams for a candidate."""
    concluded_exams_list = []
    if candidate.is_active:
        all_relevant_exams = (
            Exam.objects.filter(stage=candidate.role, is_active=True)
            .annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .order_by("scheduled_date")
        )

        for exam in all_relevant_exams:
            if exam.status == Exam.Status.CONCLUDED:
                concluded_exams_list.append(
                    {
                        "id": exam.id,
                        "title": exam.title,
                        "stage": exam.stage,
                        "round": exam.round,
                        "stage_display": exam.stage_display,
                        "description": exam.description,
                        "concluded_at": exam.concluded_at,
                        "question_count": exam.question_count,
                        "participation": (
                            "done" if exam.id in taken_exam_ids else "missed"
                        ),
                    }
                )
    return concluded_exams_list


def _get_candidate_leaderboard_ranking(
    candidate: Candidate, latest_snapshot: Optional[CandidateExamResultSnapshot]
) -> tuple[Optional[int], int]:
    """Helper to get leaderboard ranking for a candidate."""
    candidate_rank: Optional[int] = None
    total_league_candidates: int = 0
    if candidate.role == "league" and latest_snapshot:
        league_candidates_qs = Candidate.candidates_by_role("league").annotate(
            total_score=Sum(
                "results__score",
                filter=Q(results__recorded_at__lte=latest_snapshot.published_at),
                default=0.0,
            )
        )

        ranked_candidates_qs = league_candidates_qs.annotate(
            rank=Window(
                expression=Rank(),
                order_by=F("total_score").desc(nulls_last=True),
            )
        )

        ranked_candidate = ranked_candidates_qs.filter(pk=candidate.pk).first()
        if ranked_candidate:
            candidate_rank = ranked_candidate.rank

        total_league_candidates = league_candidates_qs.count()
    return candidate_rank, total_league_candidates


def _get_candidate_screening_ranking(
    candidate: Candidate,
) -> tuple[Optional[int], int]:
    """Helper to get ranking for the Screening Round 1 exam."""
    screening_exam = Exam.objects.filter(stage="screening", round=1).first()
    if not screening_exam:
        return None, 0

    results_qs = CandidateExamResult.objects.filter(exam=screening_exam)
    total_participants = results_qs.count()

    if total_participants == 0:
        return None, 0

    ranked_qs = results_qs.annotate(
        rank=Window(
            expression=Rank(),
            order_by=F("score").desc(),
        )
    )

    target_result = ranked_qs.filter(candidate=candidate).first()
    if not target_result:
        return None, total_participants

    return target_result.rank, total_participants


def get_staff_dashboard_data(staff: Staff) -> Dict[str, Any]:
    """
    Generate dashboard data for a staff user.

    Includes:
        - Staff profile information
        - Candidate statistics (by status and role)
        - Exam and question statistics
        - Score submission stats
        - Recent candidate activity and upcoming exams
        - Registration funnel metrics

    Args:
        staff (Staff): The staff user for whom the dashboard is being generated.

    Returns:
        dict: A dictionary containing candidate stats, exams, results, recent activity, and upcoming exams.
    """
    cache_key = f"staff_dashboard_{staff.pk}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    from .metrics import get_funnel_metrics

    now = timezone.now()
    last_week = now - timedelta(days=7)

    candidate_stats_data = _get_staff_candidate_stats(last_week)
    exam_stats_data = _get_staff_exam_stats(last_week)
    question_stats_data = _get_staff_question_stats()
    result_stats_data = _get_staff_score_submission_stats(last_week)
    recent_activity_list = _get_staff_recent_activity()
    upcoming_exams_list = _get_staff_upcoming_exams(now)
    funnel_metrics = get_funnel_metrics()

    staff_info: Dict[str, Any] = {
        "name": staff.user.get_full_name(),
        "email": staff.user.email,
        "role": staff.get_role_display(),
        "occupation": staff.occupation,
        "is_email_verified": staff.user.is_email_verified,
        "is_active": staff.user.is_active,
        "date_joined": staff.created_at,
        # "face_id": staff.face_id.url if staff.face_id else None,
    }

    dashboard_data = {
        "staff_info": staff_info,
        "candidates": {
            "total": candidate_stats_data["total_candidates"],
            "active": candidate_stats_data["active_candidates"],
            "recent_registrations": candidate_stats_data["recent_registrations"],
            "by_role": candidate_stats_data["candidates_by_role"],
        },
        "registration_funnel": funnel_metrics,
        "exams": {
            "total": exam_stats_data["total_exams"],
            "recent": exam_stats_data["recent_exams"],
        },
        "questions": {
            "total": question_stats_data["total_questions"],
            "by_difficulty": question_stats_data["questions_by_difficulty"],
        },
        "results": {
            "total_submissions": result_stats_data["total_submissions"],
            "recent_submissions": result_stats_data["recent_submissions"],
            "average_score": round(float(result_stats_data["average_score"]), 2),
            "highest_score": float(result_stats_data["highest_score"]),
        },
        "recent_activity": [
            {
                "candidate_name": f"{activity['candidate__user__first_name']} {activity['candidate__user__last_name']}",
                "exam_title": activity["exam__title"],
                "score": float(activity["score"]),
                "date": activity["recorded_at"],
                "candidate_school_name": activity["candidate__school_name"],
            }
            for activity in recent_activity_list
        ],
        "upcoming_exams": [
            {
                "id": exam["id"],
                "title": exam["title"],
                "scheduled_date": exam["scheduled_date"],
                "is_active": exam["is_active"],
                "stage": f"{exam['stage']}_{exam['round']}",
                "question_count": exam["question_count"],
                "countdown_minutes": exam["countdown_minutes"],
            }
            for exam in upcoming_exams_list
        ],
    }

    cache.set(cache_key, dashboard_data, timeout=3600)  # Cache for 1 hour
    return dashboard_data


def _get_staff_candidate_stats(last_week: timedelta) -> Dict[str, Any]:
    """Helper to get candidate statistics for staff dashboard."""
    candidate_stats = Candidate.objects.aggregate(
        total_candidates=Count("user_id"),
        active_candidates=Count("user_id", filter=Q(user__is_active=True)),
        recent_registrations=Count("user_id", filter=Q(created_at__gte=last_week)),
    )

    candidates_by_role: Dict[str, Dict[str, Any]] = {
        key: {"display": display, "count": Candidate.candidates_by_role(key).count()}
        for key, display in Candidate.Roles.choices
    }
    candidate_stats["candidates_by_role"] = candidates_by_role
    return candidate_stats


def _get_staff_exam_stats(last_week: timedelta) -> Dict[str, Any]:
    """Helper to get exam statistics for staff dashboard."""
    exam_stats = Exam.objects.aggregate(
        total_exams=Count("id"),
        recent_exams=Count("id", filter=Q(created_at__gte=last_week)),
    )
    return exam_stats


def _get_staff_question_stats() -> Dict[str, Any]:
    """Helper to get question statistics for staff dashboard."""
    question_stats = Question.objects.aggregate(total_questions=Count("id"))
    questions_by_difficulty: Dict[str, Dict[str, Any]] = {
        key: {
            "display": display,
            "count": Question.objects.filter(difficulty=key).count(),
        }
        for key, display in Question._meta.get_field("difficulty").choices
    }
    question_stats["questions_by_difficulty"] = questions_by_difficulty
    return question_stats


def _get_staff_score_submission_stats(last_week: timedelta) -> Dict[str, Any]:
    """Helper to get score submission statistics for staff dashboard."""
    result_stats = CandidateExamResult.objects.aggregate(
        total_submissions=Count("id"),
        recent_submissions=Count("id", filter=Q(recorded_at__gte=last_week)),
        average_score=Avg("score"),
        highest_score=Max("score"),
    )
    result_stats["average_score"] = result_stats["average_score"] or 0
    result_stats["highest_score"] = result_stats["highest_score"] or 0
    return result_stats


def _get_staff_recent_activity() -> list:
    """Helper to get recent candidate activity for staff dashboard."""
    recent_activity_list = list(
        CandidateExamResult.objects.select_related("candidate__user", "exam")
        .order_by("-recorded_at")
        .values(
            "score",
            "recorded_at",
            "candidate__user__first_name",
            "candidate__user__last_name",
            "exam__title",
            "candidate__school_name",
        )[:10]
    )
    return recent_activity_list


def _get_staff_upcoming_exams(now: Any) -> list:
    """Helper to get upcoming exams for staff dashboard."""
    upcoming_exams_list = list(
        Exam.objects.filter(scheduled_date__gte=now, is_active=True)
        .order_by("scheduled_date")
        .values(
            "id",
            "title",
            "scheduled_date",
            "is_active",
            "stage",
            "round",
            "countdown_minutes",
        )
        .annotate(question_count=Count("questions"))[:5]
    )
    return upcoming_exams_list
