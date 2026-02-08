from datetime import timedelta
import re
from django.db.models import F, Count, Q, ExpressionWrapper, DateTimeField
from django.utils import timezone
from django.db.models.functions import Now
from identity.models import Candidate, Staff, User
from competition.models import Competition, Stage
from ..models import Exam
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
        "competition": _get_competition_stats(),
        "funnel": get_funnel_metrics(),
        "geographics": _get_geographic_stats(),
    }
    return data


def _get_competition_stats() -> dict:
    """Helper to get active competition statistics."""
    # Only one active competition should exist
    active_comp = Competition.objects.filter(status=Competition.Status.ACTIVE).first()

    if not active_comp:
        return None

    stages_data = []
    # Get all stages for the active competition
    stages = active_comp.stages.all().order_by("order")

    for stage in stages:
        stage_info = {
            "id": stage.id,
            "name": re.sub(r"^\d+\s-\s", "", str(stage)),
            "type": stage.type,
        }

        # If stage is LEAGUE, get available rounds
        if stage.type == Stage.Type.LEAGUE:
            # Rounds are defined in StageExam associated with this stage
            # We filter for active StageExams that have a round number
            rounds = (
                stage.stage_exams.filter(is_active=True, round__isnull=False)
                .values_list("round", flat=True)
                .distinct()
                .order_by("round")
            )
            stage_info["rounds"] = list(rounds)

        stages_data.append(stage_info)

    return {
        "active_competition": str(active_comp),
        "active_competition_id": active_comp.id,
        "stages": stages_data,
    }


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
    ongoing_count = (
        active_exams_qs.annotate(
            end_time=ExpressionWrapper(
                F("scheduled_date") + F("open_duration_hours") * timedelta(hours=1),
                output_field=DateTimeField(),
            )
        )
        .filter(scheduled_date__lte=now, end_time__gt=now)
        .count()
    )

    # Upcoming exams: is_active=True AND scheduled_date > now
    upcoming_count = active_exams_qs.filter(scheduled_date__gt=now).count()

    # Concluded exams: is_active=True AND (scheduled_date + duration) <= now
    concluded_count = (
        active_exams_qs.annotate(
            end_time=ExpressionWrapper(
                F("scheduled_date") + F("open_duration_hours") * timedelta(hours=1),
                output_field=DateTimeField(),
            )
        )
        .filter(end_time__lte=now)
        .count()
    )

    return {
        "total": Exam.objects.count(),
        "active": active_exams_qs.count(),
        "ongoing": ongoing_count,
        "upcoming": upcoming_count,
        "concluded": concluded_count,
        "drafts": Exam.objects.filter(scheduled_date__isnull=True).count(),
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

    return {"overall": overall, "candidate": candidates, "volunteer": volunteers}
