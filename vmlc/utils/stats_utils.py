from datetime import timedelta
from typing import Any

from django.utils import timezone

from ..models import Candidate, Exam, Staff


def generate_stats_overview_data():
    """
    Generates and returns a dictionary containing the full stats overview.
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    candidate_stats = _get_candidate_stats(seven_days_ago)
    staff_stats = _get_staff_stats(seven_days_ago)

    data = {
        "candidates": candidate_stats,
        "staff": staff_stats,
    }
    return data


def _get_candidate_stats(seven_days_ago: Any) -> dict:
    """Helper to get candidate statistics."""
    registered_candidates_qs = Candidate.objects.filter(user__is_email_verified=True)

    total_registered_candidates = registered_candidates_qs.count()
    deactivated_candidates = registered_candidates_qs.filter(
        user__is_active=False
    ).count()
    pending_candidates = registered_candidates_qs.filter(
        user__verification__is_pending=True
    ).count()

    all_exams = Exam.objects.filter(is_active=True, scheduled_date__isnull=False)
    concluded_exams = [
        exam for exam in all_exams if exam.status == Exam.Status.CONCLUDED
    ]

    last_concluded_exam = None
    if concluded_exams:
        last_concluded_exam = max(
            concluded_exams,
            key=lambda e: e.scheduled_date + timedelta(hours=e.open_duration_hours),
        )

    active_candidates = 0
    if last_concluded_exam:
        active_candidates = (
            registered_candidates_qs.filter(
                user__is_active=True,
                user__verification__is_approved=True,
                user__last_login__gte=seven_days_ago,
                scores__exam=last_concluded_exam,
            )
            .distinct()
            .count()
        )

    inactive_candidates = total_registered_candidates - active_candidates

    return {
        "registered": total_registered_candidates,
        "active": active_candidates,
        "inactive": inactive_candidates,
        "pending_verification": pending_candidates,
        "deactivated": deactivated_candidates,
    }


def _get_staff_stats(seven_days_ago: Any) -> dict:
    """Helper to get staff statistics."""
    registered_staff_qs = Staff.objects.filter(user__is_email_verified=True)

    total_registered_staff = registered_staff_qs.count()
    deactivated_staff = registered_staff_qs.filter(user__is_active=False).count()
    pending_staff = registered_staff_qs.filter(
        user__verification__is_pending=True
    ).count()

    active_staff = registered_staff_qs.filter(
        user__is_active=True, user__last_login__gte=seven_days_ago
    ).count()
    inactive_staff = total_registered_staff - active_staff

    return {
        "registered": total_registered_staff,
        "active": active_staff,
        "inactive": inactive_staff,
        "pending_verification": pending_staff,
        "deactivated": deactivated_staff,
    }
