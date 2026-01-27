import logging

from django.core.cache import cache
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.generics import (
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
    UpdateAPIView,
    RetrieveAPIView,
)
from rest_framework.settings import api_settings


from ..models import Staff
from ..permissions import (
    StaffPermissions,
    ActiveModeratorPermissions,
    ActiveManagerPermissions,
)
from ..serializers import (
    StaffDetailSerializer,
    StaffListSerializer,
    StaffRoleSerializer,
    MinimalStaffSerializer,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    staff_me_response_schema,
    staff_list_response_schema,
    staff_detail_response_schema,
    staff_role_request_body,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.query_filters import filter_staffs

logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get My Profile",
        operation_description="Retrieve the authenticated staff member's own profile.",
        responses={
            200: staff_me_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Staff"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class StaffMeView(RetrieveAPIView):
    """
    Retrieve the authenticated staff member's own profile.
    """

    permission_classes = StaffPermissions
    serializer_class = MinimalStaffSerializer

    def get_object(self):
        """
        Return the staff profile for the currently authenticated user.
        """
        user_id = self.request.user.id
        cache_key = f"staff_profile_{user_id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        data = Staff.objects.get(user=self.request.user)
        cache.set(cache_key, data, 86400)  # Cache for 24 hours
        return data


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Staff",
        operation_description="List all staff members.",
        responses={
            200: staff_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Staff"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class StaffListView(ListAPIView):
    """
    List all staff members with pagination and optional filtering.

    Only accessible to users with roles: moderator, admin, manager, or superadmin.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = StaffListSerializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Returns a filtered queryset of staff members.
        """
        logger.info(
            f"StaffListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        # Eagerly fetch related user data to prevent N+1 queries by the serializer.
        queryset = Staff.objects.select_related("user").order_by("-created_at")
        return filter_staffs(queryset, self.request.query_params)


@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        operation_summary="Assign Staff Role",
        operation_description="Assign a new role to a staff member.",
        request_body=staff_role_request_body,
        responses={
            200: StaffRoleSerializer,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Staff"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Partially Assign Staff Role",
        operation_description="Partially assign a new role to a staff member.",
        request_body=staff_role_request_body,
        responses={
            200: StaffRoleSerializer,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Staff"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class AssignStaffRoleView(UpdateAPIView):
    """
    Assign a new role to a staff member.

    - Only manager and superadmin can change roles.
    - Only accepts PUT requests.
    """

    permission_classes = ActiveManagerPermissions
    serializer_class = StaffRoleSerializer
    queryset = Staff.objects.all()
    lookup_url_kwarg = "staff_id"
    http_method_names = ["put"]

    def perform_update(self, serializer):
        old_role = serializer.instance.role
        super().perform_update(serializer)
        cache.delete(f"staff_profile_{serializer.instance.user.id}")
        cache.delete(f"staff_dashboard_data_{serializer.instance.pk}")
        logger.info(
            "Changed staff %s role from '%s' to '%s' by user %s.",
            serializer.instance.pk,
            old_role,
            serializer.instance.role,
            self.request.user.id,
        )
