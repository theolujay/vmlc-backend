from datetime import timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from ..models import Exam


def get_user_status_counts(
    base_queryset: QuerySet, user_type: str
) -> dict:
    """
    Calculates the counts of users by status (active, inactive, pending, deactivated).

    Args:
        base_queryset: The initial queryset of users (Staff or Candidate).
        user_type: A string, either 'candidate' or 'staff'.

    Returns:
        A dictionary with the counts for each status.
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    total_registered = base_queryset.count()
    deactivated = base_queryset.filter(user__is_active=False).count()
    pending = base_queryset.filter(user__verification__is_pending=True).count()

    active_filter = Q(user__is_active=True) & Q(
        user__last_login__gte=seven_days_ago
    )

    if user_type == "candidate":
        # Candidates are active if they participated in the last concluded exam
        last_concluded_exam = get_last_concluded_exam()
        if last_concluded_exam:
            active_filter &= Q(
                user__verification__is_approved=True,
                scores__exam=last_concluded_exam,
            )
            active = base_queryset.filter(active_filter).distinct().count()
        else:
            active = 0
    else:  # staff
        active = base_queryset.filter(active_filter).count()

    inactive = total_registered - (active + deactivated + pending)
    if inactive < 0:
        inactive = 0

    return {
        "registered": total_registered,
        "active": active,
        "inactive": inactive,
        "pending_verification": pending,
        "deactivated": deactivated,
    }


def get_last_concluded_exam() -> Exam | None:
    """
    Finds and returns the most recently concluded exam.
    """
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
    return last_concluded_exam