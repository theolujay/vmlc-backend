from datetime import timedelta
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models import Window
from django.db.models.functions import Rank
from django.utils import timezone

from ..models import (
    Candidate,
    CandidateScore,
    CandidateScoreSnapshot,
    Exam,
    Question,
    Staff,
)


def get_candidate_dashboard_data(candidate: Candidate) -> Dict[str, Any]:
    """
    Generate dashboard data for a specific candidate.

    Includes:
        - Candidate profile information
        - Exam statistics (taken, available, latest, average, min/max)
        - Recent scores and available exams
        - Candidate ranking (if role is 'league')

    Args:
        candidate (Candidate): The candidate for whom the dashboard is being generated.

    Returns:
        dict: A dictionary containing candidate info, exam stats, ranking, recent scores, and upcoming exams.
    """

    candidate = Candidate.objects.select_related("user").get(pk=candidate.pk)

    latest_snapshot: Optional[CandidateScoreSnapshot] = (
        CandidateScoreSnapshot.objects.filter(published_at__isnull=False)
        .order_by("-published_at")
        .first()
    )

    score_stats, recent_scores_list = _get_candidate_score_stats(
        candidate, latest_snapshot
    )
    available_exams_list = _get_candidate_available_exams(
        candidate, score_stats["taken_exam_ids"]
    )
    concluded_exams_list = _get_candidate_concluded_exams(
        candidate, score_stats["taken_exam_ids"]
    )
    candidate_rank, total_league_candidates = _get_candidate_leaderboard_ranking(
        candidate, latest_snapshot
    )

    dashboard_data = {
        "candidate_info": {
            "name": candidate.user.get_full_name(),
            "email": candidate.user.email,
            "phone": candidate.user.phone,
            "school": candidate.school,
            "role": candidate.role,
            "is_user_verified": candidate.is_user_verified,
            "is_email_verified": candidate.user.is_email_verified,
            "is_active": candidate.user.is_active,
            "date_joined": candidate.created_at,
        },
        "exam_stats": {
            "total_exams_taken": score_stats["total_exams_taken"],
            "available_exams_count": len(available_exams_list),
            "average_score": round(float(score_stats["average_score"] or 0), 2),
            "highest_score": float(score_stats["highest_score"] or 0),
            "lowest_score": float(score_stats["lowest_score"] or 0),
            "latest_score": score_stats["latest_score_data"],
        },
        "leaderboard_ranking": (
            {
                "current_rank": candidate_rank,
                "total_candidates": total_league_candidates,
            }
            if candidate.role == "league"
            else None
        ),
        "recent_scores": [
            {
                "exam_title": score["exam__title"],
                "score": float(score["score"]),
                "date": score["recorded_at"],
                "exam_stage": score["exam__stage"],
            }
            for score in recent_scores_list
        ],
        "available_exams": available_exams_list,
        "concluded_exams": concluded_exams_list,
    }

    cache_key = f"candidate_dashboard_{candidate.pk}"
    cache.set(cache_key, dashboard_data, timeout=3600)  # Cache for 1 hour
    return dashboard_data


def _get_candidate_score_stats(
    candidate: Candidate, latest_snapshot: Optional[CandidateScoreSnapshot]
) -> tuple[dict, list]:
    """Helper to get score statistics for a candidate."""
    all_scores_qs = CandidateScore.objects.filter(candidate=candidate)
    taken_exam_ids = set(all_scores_qs.values_list("exam_id", flat=True))

    scores_qs_for_snapshot_stats = all_scores_qs
    if latest_snapshot:
        scores_qs_for_snapshot_stats = all_scores_qs.filter(
            recorded_at__lte=latest_snapshot.published_at
        )

    score_stats = scores_qs_for_snapshot_stats.aggregate(
        average_score=Avg("score"),
        highest_score=Max("score"),
        lowest_score=Min("score"),
    )
    total_exams_taken = all_scores_qs.count()

    recent_scores_list = list(
        all_scores_qs.order_by("-recorded_at")
        .select_related("exam")
        .values("score", "exam__title", "recorded_at", "exam__stage")[:5]
    )

    latest_score_data = None
    if recent_scores_list:
        latest_score_data = {
            "score": float(recent_scores_list[0]["score"]),
            "exam_title": recent_scores_list[0]["exam__title"],
            "date": recent_scores_list[0]["recorded_at"],
        }
    return {
        "average_score": score_stats["average_score"],
        "highest_score": score_stats["highest_score"],
        "lowest_score": score_stats["lowest_score"],
        "total_exams_taken": total_exams_taken,
        "latest_score_data": latest_score_data,
        "taken_exam_ids": taken_exam_ids,
    }, recent_scores_list


def _get_candidate_available_exams(candidate: Candidate, taken_exam_ids: set) -> list:
    """Helper to get available exams for a candidate."""
    available_exams_list = []
    if candidate.is_user_verified:
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
            if exam.status == Exam.Status.ONGOING:
                available_exams_list.append(
                    {
                        "id": exam.id,
                        "title": exam.title,
                        "stage": exam.stage,
                        "level": exam.level,
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
    if candidate.is_user_verified:
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
                        "level": exam.level,
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
    candidate: Candidate, latest_snapshot: Optional[CandidateScoreSnapshot]
) -> tuple[Optional[int], int]:
    """Helper to get leaderboard ranking for a candidate."""
    candidate_rank: Optional[int] = None
    total_league_candidates: int = 0
    if candidate.role == "league" and latest_snapshot:
        league_candidates_qs = Candidate.candidates_by_role("league").annotate(
            total_score=Sum(
                "scores__score",
                filter=Q(scores__recorded_at__lte=latest_snapshot.published_at),
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


def get_staff_dashboard_data(staff: Staff) -> Dict[str, Any]:
    """
    Generate dashboard data for a staff user.

    Includes:
        - Staff profile information
        - Candidate statistics (by status and role)
        - Exam and question statistics
        - Score submission stats
        - Recent candidate activity and upcoming exams

    Args:
        staff (Staff): The staff user for whom the dashboard is being generated.

    Returns:
        dict: A dictionary containing candidate stats, exams, scores, recent activity, and upcoming exams.
    """
    cache_key = f"staff_dashboard_{staff.pk}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    now = timezone.now()
    last_week = now - timedelta(days=7)

    candidate_stats_data = _get_staff_candidate_stats(last_week)
    exam_stats_data = _get_staff_exam_stats(last_week)
    question_stats_data = _get_staff_question_stats()
    score_stats_data = _get_staff_score_stats(last_week)
    recent_activity_list = _get_staff_recent_activity()
    upcoming_exams_list = _get_staff_upcoming_exams(now)

    staff_info: Dict[str, Any] = {
        "name": staff.user.get_full_name(),
        "email": staff.user.email,
        "role": staff.get_role_display(),
        "occupation": staff.occupation,
        "is_user_verified": staff.is_user_verified,
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
            "verified": candidate_stats_data["verified_candidates"],
            "recent_registrations": candidate_stats_data["recent_registrations"],
            "by_role": candidate_stats_data["candidates_by_role"],
            "verification_rate": (
                round(
                    (
                        candidate_stats_data["verified_candidates"]
                        / candidate_stats_data["total_candidates"]
                        * 100
                    ),
                    1,
                )
                if candidate_stats_data["total_candidates"] > 0
                else 0
            ),
        },
        "exams": {
            "total": exam_stats_data["total_exams"],
            "recent": exam_stats_data["recent_exams"],
        },
        "questions": {
            "total": question_stats_data["total_questions"],
            "by_difficulty": question_stats_data["questions_by_difficulty"],
        },
        "scores": {
            "total_submissions": score_stats_data["total_submissions"],
            "recent_submissions": score_stats_data["recent_submissions"],
            "average_score": round(float(score_stats_data["average_score"]), 2),
            "highest_score": float(score_stats_data["highest_score"]),
        },
        "recent_activity": [
            {
                "candidate_name": f"{activity['candidate__user__first_name']} {activity['candidate__user__last_name']}",
                "exam_title": activity["exam__title"],
                "score": float(activity["score"]),
                "date": activity["recorded_at"],
                "candidate_school": activity["candidate__school"],
            }
            for activity in recent_activity_list
        ],
        "upcoming_exams": [
            {
                "id": exam["id"],
                "title": exam["title"],
                "scheduled_date": exam["scheduled_date"],
                "is_active": exam["is_active"],
                "stage": f"{exam['stage']}_{exam['level']}",
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
        verified_candidates=Count(
            "user_id", filter=Q(user__verification__is_approved=True)
        ),
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


def _get_staff_score_stats(last_week: timedelta) -> Dict[str, Any]:
    """Helper to get score submission statistics for staff dashboard."""
    score_stats = CandidateScore.objects.aggregate(
        total_submissions=Count("id"),
        recent_submissions=Count("id", filter=Q(recorded_at__gte=last_week)),
        average_score=Avg("score"),
        highest_score=Max("score"),
    )
    score_stats["average_score"] = score_stats["average_score"] or 0
    score_stats["highest_score"] = score_stats["highest_score"] or 0
    return score_stats


def _get_staff_recent_activity() -> list:
    """Helper to get recent candidate activity for staff dashboard."""
    recent_activity_list = list(
        CandidateScore.objects.select_related("candidate__user", "exam")
        .order_by("-recorded_at")
        .values(
            "score",
            "recorded_at",
            "candidate__user__first_name",
            "candidate__user__last_name",
            "exam__title",
            "candidate__school",
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
            "level",
            "countdown_minutes",
        )
        .annotate(question_count=Count("questions"))[:5]
    )
    return upcoming_exams_list
