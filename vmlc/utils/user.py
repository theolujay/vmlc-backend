from datetime import timedelta
from django.db.models import Q, QuerySet, F, ExpressionWrapper, DateTimeField
from django.utils import timezone
from ..models import Exam


def get_user_status_counts(base_queryset: QuerySet, user_type: str) -> dict:
    """
    Calculates the counts of users by status (active, inactive, pending, deactivated).

    Status priority (mutually exclusive):
    1. Deactivated: user.is_active = False
    2. Pending: has verification record with is_pending = True
    3. Active: logged in within 7 days + additional criteria
    4. Inactive: everyone else
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Total count
    total_registered = base_queryset.count()

    # 1. Deactivated (highest priority)
    deactivated = base_queryset.filter(user__is_active=False).count()

    # 2. Pending verification (second priority)
    # Only count users who ARE active but have pending verification
    pending = base_queryset.filter(
        user__is_active=True, user__verification__is_pending=True  # Not deactivated
    ).count()

    # 3. Active users (third priority)
    # Base requirement: is_active=True, logged in recently, NOT pending
    active_filter = (
        Q(user__is_active=True)
        & Q(user__last_login__gte=seven_days_ago)
        & ~Q(user__verification__is_pending=True)  # Exclude pending users
    )

    if user_type == "candidate":
        # Candidates must also:
        # - Be verified (is_approved=True)
        # - Have participated in the last concluded exam
        last_concluded_exam = get_last_concluded_exam()
        if last_concluded_exam:
            active_filter &= Q(
                user__verification__is_approved=True,
                scores__exam=last_concluded_exam,
            )
            active = base_queryset.filter(active_filter).distinct().count()
        else:
            # No concluded exam = no candidates can be "active"
            active = 0
    else:  # staff
        # Staff just need to have logged in recently
        # But they should NOT be pending, and NOT 'not_started' verification
        staff_active_filter = active_filter & (
            Q(user__verification__is_approved=True)
            | Q(user__verification__is_rejected=True)
        )
        active = base_queryset.filter(staff_active_filter).count()

    # 4. Inactive: everyone who isn't deactivated, pending, or active
    inactive = total_registered - (active + deactivated + pending)

    # Safety check (shouldn't happen with correct logic)
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
    Finds and returns the most recently concluded exam based on its end time.
    """
    from django.db.models.functions import Now

    return (
        Exam.objects.annotate(
            conclusion_time=ExpressionWrapper(
                F("scheduled_date") + F("open_duration_hours") * timedelta(hours=1),
                output_field=DateTimeField(),
            )
        )
        .filter(
            is_active=True, scheduled_date__isnull=False, conclusion_time__lte=Now()
        )
        .order_by("-conclusion_time")
        .first()
    )
