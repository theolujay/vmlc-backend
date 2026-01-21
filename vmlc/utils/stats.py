from datetime import timedelta
from django.db.models import F, Count, Q, ExpressionWrapper, DateTimeField
from django.utils import timezone
from django.db.models.functions import Now
from ..models import Candidate, Staff, Exam, User
from .user import get_user_status_counts
from .metrics import get_funnel_metrics


def generate_stats_overview_data():
    """
    Generates and returns a dictionary containing the full stats overview.
    """

    data = {
        "candidates": _get_candidate_stats(),
        "staff": _get_staff_stats(),
        "exams": _get_exam_stats(),
        "funnel": get_funnel_metrics(),
        "geographics": _get_geographic_stats(),
    }
    return data


def _get_candidate_stats() -> dict:
    """Helper to get candidate statistics."""
    registered_candidates_qs = Candidate.objects.all()
    return get_user_status_counts(registered_candidates_qs, "candidate")


def _get_staff_stats() -> dict:
    """Helper to get staff statistics."""
    registered_staff_qs = Staff.objects.all()
    return get_user_status_counts(registered_staff_qs, "staff")


def _get_exam_stats() -> dict:
    """Helper to get exam statistics."""
    now = timezone.now()
    
    # Base queryset for active exams
    active_exams_qs = Exam.objects.filter(is_active=True)
    
    # Ongoing exams: is_active=True AND scheduled_date <= now AND (scheduled_date + duration) > now
    ongoing_count = active_exams_qs.annotate(
        end_time=ExpressionWrapper(
            F('scheduled_date') + F('open_duration_hours') * timedelta(hours=1),
            output_field=DateTimeField()
        )
    ).filter(
        scheduled_date__lte=now,
        end_time__gt=now
    ).count()
    
    # Upcoming exams: is_active=True AND scheduled_date > now
    upcoming_count = active_exams_qs.filter(scheduled_date__gt=now).count()
    
    # Concluded exams: is_active=True AND (scheduled_date + duration) <= now
    concluded_count = active_exams_qs.annotate(
        end_time=ExpressionWrapper(
            F('scheduled_date') + F('open_duration_hours') * timedelta(hours=1),
            output_field=DateTimeField()
        )
    ).filter(
        end_time__lte=now
    ).count()

    return {
        "total": Exam.objects.count(),
        "active": active_exams_qs.count(),
        "ongoing": ongoing_count,
        "upcoming": upcoming_count,
        "concluded": concluded_count,
        "drafts": Exam.objects.filter(scheduled_date__isnull=True).count()
    }


def _get_geographic_stats() -> dict:
    """
    Helper to get registration counts by state.
    Returns overall distribution and breakdown by user type.
    """
    overall = list(
        User.objects.exclude(state="")
        .values("state")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    candidates = list(
        Candidate.objects.exclude(user__state="")
        .values(state=F("user__state"))
        .annotate(count=Count("user_id"))
        .order_by("-count")
    )

    volunteers = list(
        Staff.objects.exclude(user__state="")
        .values(state=F("user__state"))
        .annotate(count=Count("user_id"))
        .order_by("-count")
    )

    return {
        "overall": overall,
        "candidate": candidates,
        "volunteer": volunteers
    }
