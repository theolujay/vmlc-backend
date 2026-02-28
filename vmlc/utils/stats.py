from datetime import timedelta
import re
from django.db.models import F, Q, Count, ExpressionWrapper, DateTimeField, OuterRef, Subquery
from django.utils import timezone
from identity.models import Candidate, Staff, User
from competition.models import Competition, Stage
from ..models import Exam
from comms.models import HelpdeskThread, PublicSupportRequest, ThreadMessage
from vmlc.utils.query_filters import annotate_thread_with_staff_unread_count
from ..v2.utils import CacheKeys, get_or_set_cache
from .user import get_user_status_counts
from .metrics import get_funnel_metrics


def generate_stats_overview_data():
    """
    Generates and returns a dictionary containing the full stats overview.
    Uses decentralized caching for each section.
    """

    data = {
        "candidates": get_candidate_stats_cached(),
        "staff": get_staff_stats_cached(),
        "exams": get_exam_stats_cached(),
        "competition": get_competition_stats_cached(),
        "helpdesk": get_helpdesk_stats_cached(),
        "funnel": get_funnel_metrics_cached(),
        "geographics": get_geographic_stats_cached(),
    }
    return data


def get_candidate_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_CANDIDATES, _get_candidate_stats)


def get_staff_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_STAFF, _get_staff_stats)


def get_exam_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_EXAMS, _get_exam_stats)


def get_competition_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_COMPETITION, _get_competition_stats)


def get_helpdesk_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_HELPDESK, _get_helpdesk_stats)


def get_funnel_metrics_cached():
    return get_or_set_cache(CacheKeys.STATS_FUNNEL, get_funnel_metrics)


def get_geographic_stats_cached():
    return get_or_set_cache(CacheKeys.STATS_GEOGRAPHICS, _get_geographic_stats)


def _get_helpdesk_stats() -> dict:
    """Helper to get helpdesk statistics."""
    # Only include threads that have at least one message from a candidate
    threads_qs = HelpdeskThread.objects.filter(
        messages__sender_type=ThreadMessage.SenderType.CANDIDATE
    ).distinct()

    unread_messages_count = (
        ThreadMessage.objects.filter(sender_type=ThreadMessage.SenderType.CANDIDATE)
        .exclude(reads__user__staff_profile__isnull=False)
        .count()
    )

    # 'unattended_candidates' here means threads that have at least one candidate message
    # unread by any staff member.
    unattended_count = (
        annotate_thread_with_staff_unread_count(threads_qs)
        .filter(unread_cnt__gt=0)
        .count()
    )

    from comms.services.ws_helpdesk_thread import WSHelpdeskThreadService
    online_counts = WSHelpdeskThreadService.get_online_counts()

    return {
        "total_threads": threads_qs.count(),
        "open_threads": threads_qs.filter(status=HelpdeskThread.Status.OPEN).count(),
        "in_progress_threads": threads_qs.filter(
            status=HelpdeskThread.Status.IN_PROGRESS
        ).count(),
        "resolved_threads": threads_qs.filter(
            status=HelpdeskThread.Status.RESOLVED
        ).count(),
        "unassigned_threads": threads_qs.filter(assigned_staff__isnull=True).count(),
        "unattended_candidates": unattended_count,
        "unread_messages": unread_messages_count,
        "online_candidates": online_counts["online_candidates"],
        "online_staff": online_counts["online_staff"],
        "public_requests": PublicSupportRequest.objects.count(),
    }


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
