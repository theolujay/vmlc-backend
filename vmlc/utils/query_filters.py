from typing import Any, List

import django_filters
from django.db.models import Q, QuerySet

from vmlc.models import Candidate, Exam, Question, Staff, User


def filter_candidates(
    queryset: QuerySet[Candidate], params: Any
) -> QuerySet[Candidate]:
    """
    Filter candidate queryset based on optional query parameters.

    Supported filters:
        - role: Candidate role (e.g., 'league', 'final')
        - school_name: Filter by school name
        - league: League ID or identifier
        - is_active: 'true' or 'false' (filters based on user's active status)
        - search: Partial match on email, first name, last name, or school name

    Args:
        queryset (QuerySet): The initial Candidate queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    role: Any = params.get("role")
    school_name: Any = params.get("school_name")
    league: Any = params.get("league")
    is_active: Any = params.get("is_active")
    search: Any = params.get("search")

    if role:
        queryset = queryset.filter(role=role)

    if school_name:
        queryset = queryset.filter(school_name__icontains=school_name)

    if league:
        queryset = queryset.filter(league=league)

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

    return queryset


def filter_staffs(queryset: QuerySet[Staff], params: Any) -> QuerySet[Staff]:
    """
    Filter staff queryset based on optional query parameters.

    Supported filters:
        - role: Staff role (e.g., 'moderator', 'admin', 'owner')
        - is_active: 'true' or 'false' (based on user's active status)
        - search: Partial match on first name, last name, or email

    Args:
        queryset (QuerySet): The initial Staff queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    role: Any = params.get("role")
    is_active: Any = params.get("is_active")
    search: Any = params.get("search")

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

    return queryset


def filter_users(queryset: QuerySet[User], params: Any) -> QuerySet[User]:
    is_active = params.get("is_active")
    search = params.get("search")

    if is_active is not None:
        if is_active.lower() == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == "false":
            queryset = queryset.filter(is_active=False)

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(candidate_profile__school_name__icontains=search)
            | Q(staff_profile__occupation__icontains=search)
        ).distinct()

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
                Q(title__icontains=value) | Q(stage__icontains=value)
            )
        return queryset
