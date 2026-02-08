from typing import Any, List

import django_filters
from django.db.models import Q, QuerySet

from identity.models import Candidate, PreRegUser, Staff, User
from vmlc.models import Exam, Question


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
