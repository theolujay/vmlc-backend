import logging

from rest_framework.generics import (
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
    UpdateAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings
from django.db.models import QuerySet
from typing import Any, List, Type

from ..models import Staff
from ..permissions import HasStaffRole, IsVerifiedStaff
from ..serializers import (
    StaffDetailSerializer,
    StaffListSerializer,
    StaffRoleSerializer,
)
from ..utils.query_filters import filter_staffs

logger = logging.getLogger(__name__)


# class StaffMeView(RetrieveAPIView):
#     """
#     Retrieve the authenticated staff member's own profile.
#     """

#     permission_classes = [IsAuthenticated, IsStaff]
#     serializer_class = StaffDetailSerializer

#     def get_object(self):
#         """
#         Return the staff profile for the currently authenticated user.
#         """
#         # The IsStaff permission already ensures the profile exists.
#         return self.request.user.staff_profile


class StaffListView(ListAPIView):
    """
    List all staff members with pagination and optional filtering.

    Only accessible to users with roles: moderator, admin, or superadmin.
    """

    permission_classes: List[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[StaffListSerializer] = StaffListSerializer
    pagination_class: Any = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self) -> QuerySet[Staff]:
        """
        Returns a filtered queryset of staff members.
        """
        # Eagerly fetch related user data to prevent N+1 queries by the serializer.
        queryset: QuerySet[Staff] = Staff.objects.select_related("user").order_by(
            "-date_created"
        )
        return filter_staffs(queryset, self.request.query_params)


class StaffDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or deactivate a specific staff member.

    Only superadmins are allowed to access this endpoint.

    - GET: Retrieve staff details.
    - PUT/PATCH: Update staff profile.
    - DELETE: Soft delete the staff (marks as inactive).
    """

    permission_classes: List[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[StaffDetailSerializer] = StaffDetailSerializer
    queryset: QuerySet[Staff] = Staff.objects.select_related("user").all()
    lookup_url_kwarg: str = "staff_id"

    def perform_update(self, serializer: Any) -> None:
        """
        Save updates to staff member and log the action.
        """
        logger.info(
            "Updating staff %s",
            serializer.instance.pk,
            extra={"user": self.request.user.id},
        )
        serializer.save()

    def perform_destroy(self, instance: Staff) -> None:
        """
        Soft-delete staff by setting `is_active` to False.
        """
        logger.info(
            "Soft-deleting staff %s",
            instance.pk,
            extra={"user": self.request.user.id},
        )
        instance.is_active = False
        instance.save()


class AssignStaffRoleView(UpdateAPIView):
    """
    Assign a new role to a staff member.

    - Only superadmins can change roles.
    - Only accepts PUT requests.
    """

    permission_classes: List[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[StaffRoleSerializer] = StaffRoleSerializer
    queryset: QuerySet[Staff] = Staff.objects.all()
    lookup_url_kwarg: str = "staff_id"
    http_method_names: List[str] = ["put", "patch"]

    def perform_update(self, serializer: Any) -> None:
        super().perform_update(serializer)
        logger.info(
            "Assigned role '%s' to staff %s by user %s.",
            serializer.instance.role,
            serializer.instance.pk,
            self.request.user.id,
        )
