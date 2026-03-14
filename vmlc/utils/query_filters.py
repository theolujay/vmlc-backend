from typing import Any, List

import django_filters
from django.utils import timezone
from django.db.models import (
    Q,
    OuterRef,
    QuerySet,
    Count,
    Max,
    Subquery,
    Case,
    When,
    Value,
    IntegerField,
)

from identity.models import Candidate, PreRegUser, Staff, User
from vmlc.models import Exam, Question
from comms.models import Broadcast, HelpdeskThread, ThreadMessage


def annotate_thread_with_staff_unread_count(
    queryset: QuerySet[HelpdeskThread],
) -> QuerySet[HelpdeskThread]:
    """
    Annotates a HelpdeskThread queryset with 'unread_cnt',
    representing messages from candidates unread by any staff member.
    """
    return queryset.annotate(
        unread_cnt=Count(
            "messages",
            filter=Q(messages__sender_type=ThreadMessage.SenderType.CANDIDATE)
            & ~Q(messages__reads__user__staff_profile__isnull=False),
            distinct=True,
        )
    )


def annotate_thread_with_last_candidate_message_at(
    queryset: QuerySet[HelpdeskThread],
) -> QuerySet[HelpdeskThread]:
    """
    Annotates a HelpdeskThread queryset with 'last_candidate_message_at',
    representing the timestamp of the latest message sent by the candidate.
    """
    return queryset.annotate(
        last_candidate_message_at=Max(
            "messages__created_at",
            filter=Q(messages__sender_type=ThreadMessage.SenderType.CANDIDATE),
        )
    )


def annotate_thread_with_last_message_sender_type(
    queryset: QuerySet[HelpdeskThread],
) -> QuerySet[HelpdeskThread]:
    """
    Annotates a HelpdeskThread queryset with 'last_msg_sender_type',
    representing the sender_type of the most recent message in the thread.
    """
    latest_message_sender_type = Subquery(
        ThreadMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at")
        .values("sender_type")[:1]
    )
    return queryset.annotate(last_msg_sender_type=latest_message_sender_type)


def filter_broadcasts(
    queryset: QuerySet[Broadcast], params: Any
) -> QuerySet[Broadcast]:
    """
    Filter broadcast queryset based on optional query parameters.

    Supported filters:
        - status: Exact match on broadcast status
        - medium: Match if the specified medium is in the mediums array
        - search: Partial match on subject or message
        - created_at: Exact match on creation date (YYYY-MM-DD)

    Args:
        queryset (QuerySet): The initial Broadcast queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    status: Any = params.get("status")
    medium: Any = params.get("medium")
    search: Any = params.get("search")
    created_at: Any = params.get("created_at")

    if status:
        queryset = queryset.filter(status=status)

    if medium:
        queryset = queryset.filter(mediums__contains=[medium])

    if search:
        queryset = queryset.filter(
            Q(subject__icontains=search) | Q(message__icontains=search)
        )

    if created_at:
        queryset = queryset.filter(created_at__date=created_at)

    return queryset


def filter_candidates(
    queryset: QuerySet[Candidate], params: Any
) -> QuerySet[Candidate]:
    """
    Filter candidate queryset based on optional query parameters.

    Supported filters:
        - role: Candidate role (e.g., 'league', 'final')
        - school_name: Filter by school name
        - is_active: 'true' or 'false' (filters based on user's active status)
        - search: Partial match on email, first name, last name, or school name
        - ordering: Sort by 'first_name', 'last_name', or 'date_joined' (prefix with '-' for descending)

    Args:
        queryset (QuerySet): The initial Candidate queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    role: Any = params.get("role")
    school_name: Any = params.get("school_name")
    is_active: Any = params.get("is_active")
    search: Any = params.get("search")
    ordering: Any = params.get("ordering")

    if role:
        queryset = queryset.filter(role=role)

    if school_name:
        queryset = queryset.filter(school_name__icontains=school_name)

    if is_active is not None:
        if is_active.lower() == "true":
            queryset = queryset.filter(user__is_active=True)
        elif is_active.lower() == "false":
            queryset = queryset.filter(user__is_active=False)

    if search:
        queryset = queryset.filter(
            Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(school_name__icontains=search)
        )

    if ordering:
        ordering_map = {
            "first_name": "user__first_name",
            "last_name": "user__last_name",
            "date_joined": "user__date_joined",
        }
        prefix = "-" if ordering.startswith("-") else ""
        base_field = ordering.lstrip("-")
        if base_field in ordering_map:
            queryset = queryset.order_by(f"{prefix}{ordering_map[base_field]}")

    return queryset


def filter_staffs(queryset: QuerySet[Staff], params: Any) -> QuerySet[Staff]:
    """
    Filter staff queryset based on optional query parameters.

    Supported filters:
        - role: Staff role (e.g., 'moderator', 'admin', 'owner')
        - is_active: 'true' or 'false' (based on user's active status)
        - search: Partial match on first name, last name, or email
        - ordering: Sort by 'first_name', 'last_name', or 'date_joined' (prefix with '-' for descending)

    Args:
        queryset (QuerySet): The initial Staff queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    role: Any = params.get("role")
    is_active: Any = params.get("is_active")
    search: Any = params.get("search")
    ordering: Any = params.get("ordering")

    if role:
        queryset = queryset.filter(role=role)

    if is_active is not None:
        if is_active.lower() == "true":
            queryset = queryset.filter(user__is_active=True)
        elif is_active.lower() == "false":
            queryset = queryset.filter(user__is_active=False)

    if search:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
        )

    if ordering:
        ordering_map = {
            "first_name": "user__first_name",
            "last_name": "user__last_name",
            "date_joined": "user__date_joined",
        }
        prefix = "-" if ordering.startswith("-") else ""
        base_field = ordering.lstrip("-")
        if base_field in ordering_map:
            queryset = queryset.order_by(f"{prefix}{ordering_map[base_field]}")

    return queryset


def filter_pre_reg_users(
    queryset: QuerySet[PreRegUser], params: Any
) -> QuerySet[PreRegUser]:
    """
    Filter pre-registration users based on interest profile.

    Supported filters:
        - profile: 'pre_reg_candidate' or 'pre_reg_staff'
        - ordering: Sort by 'full_name' or 'created_at' (prefix with '-' for descending)

    Args:
        queryset (QuerySet): The initial PreRegUser queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    profile = params.get("profile")
    ordering = params.get("ordering")

    if profile is not None:
        if profile.lower() == "pre_reg_candidate":
            queryset = queryset.filter(interest_type="candidate")
        elif profile.lower() == "pre_reg_staff":
            queryset = queryset.filter(interest_type="volunteer")

    if ordering:
        allowed_ordering = ["full_name", "created_at"]
        base_field = ordering.lstrip("-")
        if base_field in allowed_ordering:
            queryset = queryset.order_by(ordering)

    return queryset


def filter_users(queryset: QuerySet[User], params: Any) -> QuerySet[User]:
    """
    Filter user queryset based on optional query parameters.

    Supported filters:
        - is_active: 'true' or 'false'
        - role: Filter by staff or candidate role
        - school_name: Partial match on candidate's school name
        - school_type: Exact match on candidate's school type
        - current_class: Exact match on candidate's current class
        - search: Partial match on names, email, school, or occupation
        - ordering: Sort by 'first_name', 'last_name', or 'date_joined' (prefix with '-' for descending)

    Args:
        queryset (QuerySet): The initial User queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    is_active = params.get("is_active")
    search = params.get("search")
    role = params.get("role")
    school_name = params.get("school_name")
    school_type = params.get("school_type")
    current_class = params.get("current_class")
    ordering = params.get("ordering")

    if is_active is not None:
        if is_active.lower() == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == "false":
            queryset = queryset.filter(is_active=False)

    if role:
        queryset = queryset.filter(
            Q(staff_profile__role=role) | Q(candidate_profile__role=role)
        )

    if school_name:
        queryset = queryset.filter(
            candidate_profile__school_name__icontains=school_name
        )

    if school_type:
        queryset = queryset.filter(candidate_profile__school_type=school_type)

    if current_class:
        queryset = queryset.filter(candidate_profile__current_class=current_class)

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(candidate_profile__school_name__icontains=search)
            | Q(staff_profile__occupation__icontains=search)
        ).distinct()

    if ordering:
        allowed_ordering = ["first_name", "last_name", "date_joined"]
        base_field = ordering.lstrip("-")
        if base_field in allowed_ordering:
            queryset = queryset.order_by(ordering)

    return queryset


def filter_questions(queryset: QuerySet[Question], params: Any) -> QuerySet[Question]:
    """
    Filter question queryset based on optional query parameters.

    Supported filters:
        - search: Partial match on question description
        - difficulty: Exact match on difficulty level

    Args:
        queryset (QuerySet): The initial Question queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    search: Any = params.get("search")
    difficulty: Any = params.get("difficulty")

    if search:
        queryset = queryset.filter(Q(text__icontains=search))

    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)

    return queryset


def filter_helpdesk_threads(
    queryset: QuerySet[HelpdeskThread], params: Any
) -> QuerySet[HelpdeskThread]:
    """
    Filter and sort HelpdeskThread queryset based on optional query parameters.

    Supported filters:
        - search: Partial match on candidate's name or email.
        - status: Exact match on thread status.
        - priority: Exact match on thread priority.
        - unread: Filters for threads with unread messages.

    Supported sorting:
        - sort: Field to sort by (e.g., 'last_message_at', '-priority').
                Defaults to '-unread_cnt, -last_message_at'.

    Args:
        queryset (QuerySet): The initial HelpdeskThread queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered and sorted queryset.
    """
    search = params.get("search")
    status = params.get("status")
    priority = params.get("priority")
    unread = params.get("unread")
    sort = params.get("sort")

    if search:
        queryset = queryset.filter(
            Q(candidate__user__first_name__icontains=search)
            | Q(candidate__user__last_name__icontains=search)
            | Q(candidate__user__email__icontains=search)
        )

    if status:
        if status == "all":
            # Show all threads (no filtering by status)
            pass
        elif status == "default":
            # Default: Exclude CLOSED and SNOOZED threads
            queryset = queryset.exclude(
                status__in=[HelpdeskThread.Status.CLOSED, HelpdeskThread.Status.SNOOZED]
            )
        else:
            queryset = queryset.filter(status=status)
    else:
        # Default: Exclude CLOSED and SNOOZED threads if no status is specified
        queryset = queryset.exclude(
            status__in=[HelpdeskThread.Status.CLOSED, HelpdeskThread.Status.SNOOZED]
        )

    if priority:
        queryset = queryset.filter(priority=priority)

    if unread and unread.lower() == "true":
        queryset = queryset.filter(unread_cnt__gt=0)

    # Sorting
    if sort:
        queryset = queryset.order_by(sort)
    else:
        # Default sorting: OPEN first, then IN_PROGRESS, then others
        # Within each status, sort by candidate's latest message date and time
        queryset = queryset.annotate(
            status_order=Case(
                When(status=HelpdeskThread.Status.OPEN, then=Value(1)),
                When(status=HelpdeskThread.Status.IN_PROGRESS, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        ).order_by("status_order", "-last_candidate_message_at", "-unread_cnt")

    return queryset


class ExamFilter(django_filters.FilterSet):
    """
    FilterSet for filtering Exam objects.

    Supported filters:
        - search: Partial match on title or stage
        - created_at: Exact match on creation date (YYYY-MM-DD)

    Args:
        queryset (QuerySet): The initial Exam queryset.
        params (QueryDict): The request query parameters.
    """

    search: django_filters.CharFilter = django_filters.CharFilter(
        method="filter_search", label="Search"
    )
    created_at: django_filters.DateFilter = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date"
    )

    class Meta:
        model: Exam = Exam
        fields: List[str] = ("search", "created_at")

    def filter_search(
        self, queryset: QuerySet[Exam], _name: str, value: str
    ) -> QuerySet[Exam]:
        """Custom filter method for search functionality"""
        if value:
            return queryset.filter(
                Q(title__icontains=value)
                | Q(competition_contexts__competition_stage__type__icontains=value)
            ).distinct()
        return queryset


def ongoing_exam_exists() -> bool:
    """Check if any exam is currently active (candidates actively taking it)."""
    from django.core.cache import cache

    cache_key = "ongoing_exam_exists"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from vmlc.models import ExamAccess

    exam_access = (
        ExamAccess.objects.select_related("exam")
        .filter(status=ExamAccess.Status.STARTED)
        .first()
    )
    if not exam_access:
        cache.set(cache_key, False, timeout=30)
        return False

    is_exam_ongoing = exam_access.exam.status == Exam.Status.ONGOING

    cache.set(cache_key, is_exam_ongoing, timeout=30)
    return is_exam_ongoing
