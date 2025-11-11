from datetime import timedelta

from django.utils import timezone

from ..models import Candidate, Exam, Staff


def generate_stats_overview_data():
    """
    Generates and returns a dictionary containing the full stats overview.
    """
    # Base querysets for users with verified emails
    registered_candidates_qs = Candidate.objects.filter(user__is_email_verified=True)
    registered_staff_qs = Staff.objects.filter(user__is_email_verified=True)

    # Total counts
    total_registered_candidates = registered_candidates_qs.count()
    total_registered_staff = registered_staff_qs.count()

    # Deactivated user counts
    deactivated_candidates = registered_candidates_qs.filter(
        user__is_active=False
    ).count()
    deactivated_staff = registered_staff_qs.filter(user__is_active=False).count()

    # Pending verification counts
    pending_candidates = registered_candidates_qs.filter(
        user__verification__is_pending=True
    ).count()
    pending_staff = registered_staff_qs.filter(
        user__verification__is_pending=True
    ).count()

    seven_days_ago = timezone.now() - timedelta(days=7)

    # Active and inactive staff
    active_staff = registered_staff_qs.filter(
        user__is_active=True, user__last_login__gte=seven_days_ago
    ).count()
    inactive_staff = total_registered_staff - active_staff

    # Find the last concluded exam to determine active candidates
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

    data = {
        "candidates": {
            "registered": total_registered_candidates,
            "active": active_candidates,
            "inactive": inactive_candidates,
            "pending_verification": pending_candidates,
            "deactivated": deactivated_candidates,
        },
        "staff": {
            "registered": total_registered_staff,
            "active": active_staff,
            "inactive": inactive_staff,
            "pending_verification": pending_staff,
            "deactivated": deactivated_staff,
        },
    }
    return data
