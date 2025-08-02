"""
Dashboard utility functions for candidates and staff.

These functions prepare and return summarized dashboard data, statistics,
and relevant activity for frontend display.
"""

from datetime import timedelta
from django.db.models import Avg, Max, Min, Sum
from django.utils import timezone

from ..models import Candidate, CandidateScore, Exam, Question, CandidateScoreSnapshot


def get_candidate_dashboard_data(candidate):
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
    latest_snapshot = (
        CandidateScoreSnapshot.objects.filter(published_at__isnull=False)
        .order_by("-published_at")
        .first()
    )

    if latest_snapshot:
        scores = CandidateScore.objects.filter(
            candidate=candidate, date_recorded__lte=latest_snapshot.published_at
        )
    else:
        scores = CandidateScore.objects.none()

    total_exams_taken = scores.count()
    latest_score = scores.latest("date_recorded") if total_exams_taken > 0 else None
    average_score = scores.aggregate(avg=Avg("score"))["avg"] or 0
    highest_score = scores.aggregate(max=Max("score"))["max"] or 0
    lowest_score = scores.aggregate(min=Min("score"))["min"] or 0

    available_exams = [
        exam
        for exam in Exam.objects.filter(stage=candidate.role, is_active=True)
        if exam.is_currently_open
    ]
    recent_scores = scores.order_by("-date_recorded")[:5]

    # Ranking logic for league candidates
    candidate_rank = None
    total_league_candidates = 0
    if candidate.role == "league":
        league_candidates = (
            Candidate.candidates_by_role("league")
            .annotate(total_score=Sum("scores__score"))
            .order_by("-total_score")
        )

        for index, c in enumerate(league_candidates, 1):
            if c.pk == candidate.pk:
                candidate_rank = index
                break
        total_league_candidates = league_candidates.count()

    return {
        "candidate_info": {
            "id": candidate.user.id,
            "name": candidate.user.get_full_name(),
            "email": candidate.user.email,
            "school": candidate.school,
            "role": candidate.get_role_display(),
            "is_verified": candidate.is_verified,
            "date_joined": candidate.date_created,
            "profile_photo": (
                candidate.profile_photo.url if candidate.profile_photo else None
            ),
        },
        "exam_stats": {
            "total_exams_taken": total_exams_taken,
            "available_exams_count": len(available_exams),
            "average_score": round(float(average_score), 2),
            "highest_score": float(highest_score),
            "lowest_score": float(lowest_score),
            "latest_score": (
                {
                    "score": float(latest_score.score),
                    "exam_title": latest_score.exam.title,
                    "date": latest_score.date_recorded,
                }
                if latest_score
                else None
            ),
        },
        "leaderboard_ranking": (
            {
                "current_rank": candidate_rank,
                "total_candidates": total_league_candidates,
                "role": candidate.role,
            }
            if candidate.role == "league"
            else None
        ),
        "recent_scores": [
            {
                "exam_title": score.exam.title,
                "score": float(score.score),
                "date": score.date_recorded,
                "exam_stage": score.exam.stage,
            }
            for score in recent_scores
        ],
        "available_exams": [
            {
                "id": exam.id,
                "title": exam.title,
                "description": exam.description,
                "open_duration_hours": exam.open_duration_hours,
                "exam_date": exam.exam_date,
                "countdown_minutes": exam.countdown_minutes,
                "question_count": exam.get_question_count(),
                "stage": exam.stage,
            }
            for exam in available_exams[:5]
        ],
    }


def get_staff_dashboard_data(staff):
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
    now = timezone.now()
    last_week = now - timedelta(days=7)

    total_candidates = Candidate.objects.count()
    active_candidates = Candidate.active_candidates().count()
    verified_candidates = Candidate.objects.filter(is_verified=True).count()

    candidates_by_role = {
        key: {"display": display, "count": Candidate.candidates_by_role(key).count()}
        for key, display in Candidate.ROLE_CHOICES
    }

    recent_candidates = Candidate.objects.filter(date_created__gte=last_week).count()

    total_exams = Exam.objects.count()
    recent_exams = Exam.objects.filter(date_created__gte=last_week).count()

    total_questions = Question.objects.count()
    questions_by_difficulty = {
        key: {
            "display": display,
            "count": Question.objects.filter(difficulty=key).count(),
        }
        for key, display in Question._meta.get_field("difficulty").choices
    }

    total_scores = CandidateScore.objects.count()
    recent_scores = CandidateScore.objects.filter(date_recorded__gte=last_week).count()

    avg_score = CandidateScore.objects.aggregate(avg=Avg("score"))["avg"] or 0
    highest_score = CandidateScore.objects.aggregate(max=Max("score"))["max"] or 0

    recent_activity = CandidateScore.objects.select_related(
        "candidate__user", "exam"
    ).order_by("-date_recorded")[:10]

    upcoming_exams = Exam.objects.filter(exam_date__gte=now, is_active=True).order_by(
        "exam_date"
    )[:5]

    staff_info = {
        "id": staff.user.id,
        "name": staff.user.get_full_name(),
        "email": staff.user.email,
        "role": staff.get_role_display(),
        "occupation": staff.occupation,
        "is_verified": staff.is_verified,
        "date_joined": staff.date_created,
        "profile_photo": staff.profile_photo.url if staff.profile_photo else None,
    }

    return {
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
                "candidate_name": activity.candidate.user.get_full_name(),
                "exam_title": activity.exam.title,
                "score": float(activity.score),
                "date": activity.date_recorded,
                "candidate_school": activity.candidate.school,
            }
            for activity in recent_activity
        ],
        "upcoming_exams": [
            {
                "id": exam.id,
                "title": exam.title,
                "exam_date": exam.exam_date,
                "stage": exam.get_stage_display(),
                "question_count": exam.get_question_count(),
                "countdown_minutes": exam.countdown_minutes,
            }
            for exam in upcoming_exams
        ],
    }