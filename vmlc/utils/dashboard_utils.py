from datetime import timedelta
from django.core.cache import cache
from django.db.models import Avg, Max, Min, Sum, Q, Count, F
from django.db.models.functions import Rank
from django.db.models import Window, QuerySet
from django.utils import timezone
from typing import Any, Dict, List, Optional

from ..models import (
    Candidate,
    CandidateScore,
    Exam,
    Question,
    CandidateScoreSnapshot,
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

    # Combine score stats and recent scores into one query if possible, or minimize separate hits
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
    )  # Converted to list to avoid re-querying

    latest_score_data = None
    if recent_scores_list:
        latest_score_data = {
            "score": float(recent_scores_list[0]["score"]),
            "exam_title": recent_scores_list[0]["exam__title"],
            "date": recent_scores_list[0]["recorded_at"],
        }

    # Optimize available_exams
    available_exams_list = []
    concluded_exams_list = []
    if candidate.is_user_verified:
        # Fetch all relevant exams in one go
        all_relevant_exams = (
            Exam.objects.filter(stage=candidate.role.lower(), is_active=True)
            .annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .order_by("scheduled_date")
        )  # Limit to 5 as per original logic

        now = timezone.now()
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

    # Optimize leaderboard ranking
    candidate_rank: Optional[int] = None
    total_league_candidates: int = 0
    if candidate.role == "league" and latest_snapshot:
        # This part is already quite optimized with Window functions
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

        total_league_candidates = (
            league_candidates_qs.count()
        )  # This is a separate query

    dashboard_data = {
        "candidate_info": {
            "name": candidate.user.get_full_name(),
            "email": candidate.user.email,
            "phone": candidate.user.phone,
            "school": candidate.school,
            "role": candidate.role.lower(),
            "is_user_verified": candidate.is_user_verified,
            "is_email_verified": candidate.user.is_email_verified,
            "is_active": candidate.user.is_active,
            "date_joined": candidate.created_at,
        },
        "exam_stats": {
            "total_exams_taken": total_exams_taken,
            "available_exams_count": len(available_exams_list),
            "average_score": round(float(score_stats["average_score"] or 0), 2),
            "highest_score": float(score_stats["highest_score"] or 0),
            "lowest_score": float(score_stats["lowest_score"] or 0),
            "latest_score": latest_score_data,
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

    now: Any = timezone.now()
    last_week: timedelta = now - timedelta(days=7)

    # Combine multiple counts into a single query
    candidate_stats = Candidate.objects.aggregate(
        total_candidates=Count("user_id"),
        active_candidates=Count("user_id", filter=Q(user__is_active=True)),
        verified_candidates=Count(
            "user_id", filter=Q(user__verification__is_approved=True)
        ),
        recent_registrations=Count("user_id", filter=Q(created_at__gte=last_week)),
    )

    total_candidates = candidate_stats["total_candidates"]
    active_candidates = candidate_stats["active_candidates"]
    verified_candidates = candidate_stats["verified_candidates"]
    recent_candidates = candidate_stats["recent_registrations"]

    # This still requires iterating through roles, but the count is per role
    candidates_by_role: Dict[str, Dict[str, Any]] = {
        key: {"display": display, "count": Candidate.candidates_by_role(key).count()}
        for key, display in Candidate.Roles.choices
    }

    exam_stats = Exam.objects.aggregate(
        total_exams=Count("id"),
        recent_exams=Count("id", filter=Q(created_at__gte=last_week)),
    )
    total_exams = exam_stats["total_exams"]
    recent_exams = exam_stats["recent_exams"]

    question_stats = Question.objects.aggregate(total_questions=Count("id"))
    total_questions = question_stats["total_questions"]

    questions_by_difficulty: Dict[str, Dict[str, Any]] = {
        key: {
            "display": display,
            "count": Question.objects.filter(difficulty=key).count(),
        }
        for key, display in Question._meta.get_field("difficulty").choices
    }

    score_stats = CandidateScore.objects.aggregate(
        total_submissions=Count("id"),
        recent_submissions=Count("id", filter=Q(recorded_at__gte=last_week)),
        average_score=Avg("score"),
        highest_score=Max("score"),
    )
    total_scores = score_stats["total_submissions"]
    recent_scores = score_stats["recent_submissions"]
    avg_score = score_stats["average_score"] or 0
    highest_score = score_stats["highest_score"] or 0

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
        .annotate(question_count=Count("questions"))[:5]  # Annotate question count here
    )

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
            "total": total_candidates,
            "active": active_candidates,
            "verified": verified_candidates,
            "recent_registrations": recent_candidates,
            "by_role": candidates_by_role,
            "verification_rate": (
                round((verified_candidates / total_candidates * 100), 1)
                if total_candidates > 0
                else 0
            ),
        },
        "exams": {
            "total": total_exams,
            "recent": recent_exams,
        },
        "questions": {
            "total": total_questions,
            "by_difficulty": questions_by_difficulty,
        },
        "scores": {
            "total_submissions": total_scores,
            "recent_submissions": recent_scores,
            "average_score": round(float(avg_score), 2),
            "highest_score": float(highest_score),
        },
        "recent_activity": [
            {
                "candidate_name": f"{activity['candidate__user__first_name']} {activity['candidate__user__last_name']}",
                "exam_title": activity["exam__title"],
                "score": float(activity["score"]),
                "date": activity["recorded_at"],
                "candidate_school": activity[
                    "candidate__school"
                ],  # Assuming school is directly accessible
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
