from datetime import timedelta
from django.db.models import Q, QuerySet, F, ExpressionWrapper, DateTimeField
from django.utils import timezone
from ..models import Exam, PreRegUser

def normalize_title(name):
    return name.lower().title()

def get_user_status_counts(base_queryset: QuerySet, user_type: str) -> dict:
    """
    Calculates the counts of users by status (active, inactive, pre-registered, deactivated).

    Status priority (mutually exclusive):
    1. Deactivated: user.is_active = False
    2. Active: logged in within 7 days + additional criteria (excluding verification)
    3. Inactive: everyone else
    4. Pre-registered: PreRegUser entries (excluding those fully registered)
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Total count (fully registered users)
    total_registered = base_queryset.count()

    # 1. Deactivated (highest priority)
    deactivated = base_queryset.filter(user__is_active=False).count()

    # 2. Active users
    # Base requirement: is_active=True, logged in recently
    # Removed verification checks as requested
    active_filter = Q(user__is_active=True) & Q(user__last_login__gte=seven_days_ago)

    if user_type == "candidate":
        # Candidates must also:
        # - Have participated in the last concluded exam
        last_concluded_exam = get_last_concluded_exam()
        if last_concluded_exam:
            active_filter &= Q(scores__exam=last_concluded_exam)
            active = base_queryset.filter(active_filter).distinct().count()
        else:
            # No concluded exam = no candidates can be "active" based on this rule
            active = 0
    else:  # staff
        # Staff just need to have logged in recently
        active = base_queryset.filter(active_filter).count()

    # 3. Inactive: everyone who isn't deactivated or active
    inactive = total_registered - (active + deactivated)

    # Safety check
    if inactive < 0:
        inactive = 0

    # 4. Pre-registered (from PreRegUser model)
    # Determine interest type based on user_type
    interest_type = (
        PreRegUser.InterestType.CANDIDATE
        if user_type == "candidate"
        else PreRegUser.InterestType.VOLUNTEER
    )

    # Filter for pre-registered users of the correct type
    # And exclude those who are already fully registered (exist in base_queryset)
    # We use email to check for existence
    registered_emails = base_queryset.values_list("user__email", flat=True)
    
    pre_registered = PreRegUser.objects.filter(
        interest_type=interest_type
    ).exclude(email__in=registered_emails).count()

    # Filter for cases when a user has both entities (fully registered AND in PreRegUser)
    both_entities = PreRegUser.objects.filter(
        interest_type=interest_type,
        email__in=registered_emails
    ).count()

    return {
        "registered": total_registered,
        "active": active,
        "inactive": inactive,
        "pre_registered": pre_registered,
        "deactivated": deactivated,
        "both_entities": both_entities,
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
