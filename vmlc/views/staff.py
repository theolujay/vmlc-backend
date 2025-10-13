import logging

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
    VerifiedModeratorPermissions,
    VerifiedManagerPermissions,
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
        data = Staff.objects.get(user=self.request.user)
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

    permission_classes = VerifiedModeratorPermissions
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
        queryset = Staff.objects.select_related("user").order_by("-date_created")
        return filter_staffs(queryset, self.request.query_params)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Staff Details",
        operation_description="Retrieve a staff member.",
        responses={
            200: staff_detail_response_schema,
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
        operation_summary="Partially Update Staff",
        operation_description="Partially update a staff member.",
        request_body=StaffDetailSerializer,
        responses={
            200: staff_detail_response_schema,
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
    name="delete",
    decorator=swagger_auto_schema(
        operation_summary="Delete Staff",
        operation_description="Delete a staff member.",
        responses={
            204: openapi.Response("Staff member deleted successfully."),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Staff"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class StaffDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or deactivate a specific staff member.

    Only manager and superadmins are allowed to access this endpoint.

    - GET: Retrieve staff details.
    - PUT/PATCH: Update staff profile.
    - DELETE: Soft delete the staff (marks as inactive).
    """

    permission_classes = VerifiedManagerPermissions
    serializer_class = StaffDetailSerializer
    queryset = Staff.objects.select_related("user", "user__verification").all()
    lookup_url_kwarg = "staff_id"
    http_method_names = ["get", "patch", "delete"]

    def perform_update(self, serializer):
        """
        Save updates to staff member and log the action.
        """
        logger.info(
            "Updating staff %s by user %s",
            serializer.instance.pk,
            self.request.user.id,
        )
        serializer.save()

    def perform_destroy(self, instance):
        """
        Soft-delete staff by setting `is_active` to False.
        """
        logger.info(
            "Soft-deleting staff %s by user %s",
            instance.pk,
            self.request.user.id,
        )
        instance.is_active = False
        instance.save()


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

    permission_classes = VerifiedManagerPermissions
    serializer_class = StaffRoleSerializer
    queryset = Staff.objects.all()
    lookup_url_kwarg = "staff_id"
    http_method_names = ["put"]

    def perform_update(self, serializer):
        old_role = serializer.instance.role
        super().perform_update(serializer)
        logger.info(
            "Changed staff %s role from '%s' to '%s' by user %s.",
            serializer.instance.pk,
            old_role,
            serializer.instance.role,
            self.request.user.id,
        )
