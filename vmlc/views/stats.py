import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from vmlc.models import Candidate, Exam, Staff
from vmlc.permissions import (
    VerifiedManagerPermissions,
    VerifiedModeratorPermissions,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([VerifiedModeratorPermissions | VerifiedManagerPermissions])
def stats_overview(request):
    """
    Retrieve overall statistics for candidates and staff.

    This view provides a cached overview of user statistics, including counts for
    registered, active, inactive, pending, and deactivated users (both candidates
    and staff).
    """
    cache_key = "stats_overview"
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data)

    logger.info(
        f"Generating stats overview for user {request.user.id} from {request.META.get('REMOTE_ADDR')}"
    )

    registered_candidates_qs = Candidate.objects.filter(user__is_email_verified=True)
    registered_staff_qs = Staff.objects.filter(user__is_email_verified=True)

    total_registered_candidates = registered_candidates_qs.count()
    total_registered_staff = registered_staff_qs.count()

    deactivated_candidates = registered_candidates_qs.filter(user__is_active=False).count()
    deactivated_staff = registered_staff_qs.filter(user__is_active=False).count()

    pending_candidates = registered_candidates_qs.filter(
        user__verification__is_pending=True
    ).count()
    pending_staff = registered_staff_qs.filter(
        user__verification__is_pending=True
    ).count()

    seven_days_ago = timezone.now() - timedelta(days=7)

    active_staff = registered_staff_qs.filter(
        user__is_active=True, user__last_login__gte=seven_days_ago
    ).count()
    inactive_staff = total_registered_staff - active_staff

    # Find the last concluded exam to determine active candidates
    all_exams = Exam.objects.filter(is_active=True, scheduled_date__isnull=False)
    concluded_exams = [exam for exam in all_exams if exam.status == Exam.Status.CONCLUDED]

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

    cache.set(cache_key, data, timeout=3600)  # Cache for 1 hour

    return Response(data)
