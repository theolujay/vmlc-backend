import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from typing import Any, Tuple, Type, Optional

from ..models import Candidate, Staff, User
from ..permissions import (
    HasStaffRole,
    IsCandidate,
    IsObjectOwnerOrSuperAdminRole,
    IsVerifiedStaff,
)
from ..serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    UserSerializer,
)
from ..utils.dashboard_utils import (
    get_candidate_dashboard_data,
    get_staff_dashboard_data,
)

logger = logging.getLogger(__name__)


class CandidateDashboardView(APIView):
    """
    Retrieve dashboard data for the currently authenticated candidate.
    """

    permission_classes: list[Any] = [IsAuthenticated, IsCandidate]

    def get(self, request: Request) -> Response:
        """
        Returns candidate-specific dashboard stats and profile data.
        """
        # IsCandidate permission ensures candidate_profile exists
        candidate: Candidate = request.user.candidate_profile
        data: dict = get_candidate_dashboard_data(candidate)
        return Response(data)


class StaffDashboardView(APIView):
    """
    Retrieve dashboard data for the currently authenticated staff member.
    """

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]

    def get(self, request: Request) -> Response:
        """
        Returns staff-specific dashboard metrics and profile data.
        """
        # HasStaffRole permission ensures staff_profile exists
        staff: Staff = request.user.staff_profile
        data: dict = get_staff_dashboard_data(staff)
        return Response(data)


class AccountManagementView(APIView):
    """
    Retrieve or update user account and profile information.

    - GET: Retrieve account and profile information.
    - PUT/PATCH: Update account and profile.

    Regular users can manage their own accounts.
    Staff with 'admin' or 'superadmin' roles can manage other users' accounts.
    """

    permission_classes: list[Any] = [IsAuthenticated]
    # parser_classes = [MultiPartParser, FormParser]

    def _get_target_user(self, request: Request, user_id: Optional[str] = None) -> User:
        """
        Determines the target user for the action and checks permissions.
        """
        if user_id is None or user_id == str(request.user.id):
            return request.user

        # If a user_id is provided, check if the requester has permission.
        target_user: User = get_object_or_404(User, id=user_id)
        if not IsObjectOwnerOrSuperAdminRole().has_object_permission(
            request, self, target_user
        ):
            raise PermissionDenied("You are not authorized to manage this user.")
        return target_user

    def _get_profile_and_serializer(
        self, user: User
    ) -> Tuple[Optional[Any], Optional[Type[serializers.Serializer]]]:
        """
        Gets the user's profile (Candidate or Staff) and the appropriate serializer.
        """
        if hasattr(user, "candidate_profile"):
            return user.candidate_profile, CandidateDetailSerializer
        if hasattr(user, "staff_profile"):
            return user.staff_profile, StaffDetailSerializer
        return None, None

    def get(self, request: Request, user_id: Optional[str] = None) -> Response:
        """
        Retrieve the account and profile data of the target user.
        """
        target_user: User = self._get_target_user(request, user_id)
        user_data: dict = UserSerializer(target_user).data
        profile: Optional[Any]
        profile_serializer_class: Optional[Type[serializers.Serializer]]
        profile, profile_serializer_class = self._get_profile_and_serializer(
            target_user
        )

        if profile and profile_serializer_class:
            profile_data: dict = profile_serializer_class(profile).data
        else:
            return Response(
                {"detail": "User does not have a profile."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"profile": profile_data})

    def _update_account(
        self, request: Request, partial: bool, user_id: Optional[str] = None
    ) -> Response:
        """
        Handles the update logic for both user and profile data.
        """
        target_user: User = self._get_target_user(request, user_id)
        user_data: dict = request.data.get("user", {})
        profile_data: dict = request.data.get("profile", {})

        user_serializer: UserSerializer = UserSerializer(
            target_user, data=user_data, partial=partial
        )
        user_serializer.is_valid(raise_exception=True)
        profile: Optional[Any]
        profile_serializer_class: Optional[Type[serializers.Serializer]]
        profile, profile_serializer_class = self._get_profile_and_serializer(
            target_user
        )
        profile_serializer: Optional[serializers.Serializer] = None
        if profile and profile_serializer_class:
            profile_serializer = profile_serializer_class(
                profile, data=profile_data, partial=partial
            )
            profile_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user_serializer.save()
            if profile_serializer:
                profile_serializer.save()

        logger.info(
            "Account for user %s updated by %s.",
            target_user.id,
            request.user.id,
        )
        return Response(
            {
                "message": "Account updated successfully.",
                # "user": user_serializer.data,
                "profile": profile_serializer.data if profile_serializer else None,
            }
        )

    # def put(self, request, user_id=None):
    #     """
    #     Fully update both user and profile data.
    #     """
    #     return self._update_account(request, partial=False, user_id=user_id)

    def patch(self, request: Request, user_id: Optional[str] = None) -> Response:
        """
        Partially update user and/or profile data.
        """
        return self._update_account(request, partial=True, user_id=user_id)
