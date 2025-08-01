"""
Utility functions for filtering querysets based on request parameters.

Each function applies filters to a specific model's queryset (e.g., Candidate, Staff, Exam, Question)
based on query parameters typically passed from a GET request.
"""

from django.db.models import Q

import django_filters

from ..models import Exam


def filter_candidates(queryset, params):
    """
    Filter candidate queryset based on optional query parameters.

    Supported filters:
        - role: Candidate role (e.g., 'league', 'school')
        - league: League ID or identifier
        - is_active: 'true' or 'false' (filters based on user's active status)
        - search: Partial match on email, first name, or last name

    Args:
        queryset (QuerySet): The initial Candidate queryset.
        params (QueryDict): The request query parameters.

    Returns:
        QuerySet: Filtered queryset.
    """
    role = params.get("role")
    league = params.get("league")
    is_active = params.get("is_active")
    search = params.get("search")

    if role:
        queryset = queryset.filter(role=role)

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
        )

    return queryset


def filter_staffs(queryset, params):
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
    role = params.get("role")
    is_active = params.get("is_active")
    search = params.get("search")

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


def filter_questions(queryset, params):
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
    search = params.get("search")
    difficulty = params.get("difficulty")

    if search:
        queryset = queryset.filter(Q(description__icontains=search))

    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)

    return queryset


class ExamFilter(django_filters.FilterSet):
    """
    FilterSet for filtering Exam objects.

    Supported filters:
        - search: Partial match on title or stage
        - date_created: Exact match on creation date (YYYY-MM-DD)

    Args:
        queryset (QuerySet): The initial Exam queryset.
        params (QueryDict): The request query parameters.
    """

    search = django_filters.CharFilter(method="filter_search", label="Search")
    date_created = django_filters.DateFilter(
        field_name="date_created", lookup_expr="date"
    )

    class Meta:
        model = Exam
        fields = ("search", "date_created")

    def filter_search(self, queryset, name, value):
        """Custom filter method for search functionality"""
        if value:
            return queryset.filter(
                Q(title__icontains=value) | Q(stage__icontains=value)
            )
        return queryset
