import logging

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
# from channels.db import database_sync_to_async

from ..models import Staff, User
from ..permissions import (
    HasStaffRole,
    IsCandidate,
    IsObjectOwnerOrSuperAdminRole,
    IsVerifiedStaff,
    HasXAPIKey,
)
from ..serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    UserSerializer,
)
from ..tasks import (
    update_staff_dashboard_cache_task,
    update_candidate_dashboard_cache_task,
)

logger = logging.getLogger(__name__)


class CandidateDashboardView(APIView):
    """
    Retrieve dashboard data for the currently authenticated candidate.
    """

    permission_classes = [HasXAPIKey, IsAuthenticated, IsCandidate]

    def get(self, request):
        """
        Returns candidate-specific dashboard stats and profile data.
        """
        candidate = request.user.candidate_profile
        logger.info(
            f"CandidateDashboardView: request from user {request.user.id} (candidate_id: {candidate.pk})"
        )
        cache_key = f"candidate_dashboard_{candidate.pk}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Dashboard data for candidate {candidate.pk} found in cache.")
            return Response(cached_data)

        logger.info(
            f"Dashboard data for candidate {candidate.pk} not found in cache. Triggering background update."
        )
        # If not in cache, trigger a background update
        update_candidate_dashboard_cache_task.delay(candidate.pk)

        return Response(
            {
                "message": "Dashboard data is being generated. Please check back in a few moments."
            },
            status=status.HTTP_202_ACCEPTED,
        )


class StaffDashboardView(APIView):
    """
    Retrieve dashboard data for the currently authenticated staff member.
    """

    permission_classes = [
        HasXAPIKey,
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]

    def get(self, request):
        """
        Returns staff-specific dashboard metrics and profile data from cache if available.
        """
        staff = request.user.staff_profile
        logger.info(
            f"StaffDashboardView: request from user {request.user.id} (staff_id: {staff.pk})"
        )
        cached_data = cache.get(f"staff_dashboard_data_{staff.pk}")

        if cached_data:
            logger.info(f"Dashboard data for staff {staff.pk} found in cache.")
            return Response(cached_data)

        logger.info(
            f"Dashboard data for staff {staff.pk} not found in cache. Triggering background update."
        )
        # If not in cache, trigger a background update
        update_staff_dashboard_cache_task.delay(staff.pk)

        return Response(
            {
                "message": "Dashboard data is being generated. Please check back in a few moments."
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AccountManagementView(APIView):
    """
    Retrieve or update user account and profile information.

    - GET: Retrieve account and profile information.
    - PUT/PATCH: Update account and profile.

    Regular users can manage their own accounts.
    Staff with 'admin' or 'superadmin' roles can manage other users' accounts.
    """

    permission_classes = [HasXAPIKey, IsAuthenticated]
    # parser_classes = [MultiPartParser, FormParser]

    # @database_sync_to_async
    def _get_target_user(self, request, user_id=None):
        """
        Determines the target user for the action and checks permissions.
        """
        if user_id is None or user_id == str(request.user.id):
            return request.user

        # If a user_id is provided, check if the requester has permission.
        target_user = get_object_or_404(User, id=user_id)
        if not IsObjectOwnerOrSuperAdminRole().has_object_permission(
            request, self, target_user
        ):
            logger.warning(
                f"User {request.user.id} does not have permission to manage user {user_id}."
            )
            raise PermissionDenied("You are not authorized to manage this user.")
        return target_user

    # @database_sync_to_async
    def _get_profile_and_serializer(self, user):
        """
        Gets the user's profile (Candidate or Staff) and the appropriate serializer.
        """
        if hasattr(user, "candidate_profile"):
            return user.candidate_profile, CandidateDetailSerializer
        if hasattr(user, "staff_profile"):
            return user.staff_profile, StaffDetailSerializer
        return None, None

    def get(self, request, user_id=None):
        """
        Retrieve the account and profile data of the target user.
        """
        logger.info(
            f"AccountManagementView (get): request from user {request.user.id} for user {user_id}"
        )
        target_user = self._get_target_user(request, user_id)
        user_data = UserSerializer(target_user).data
        profile, profile_serializer_class = self._get_profile_and_serializer(
            target_user
        )

        if profile and profile_serializer_class:
            profile_data = profile_serializer_class(profile).data
        else:
            logger.error(f"User {target_user.id} does not have a profile.")
            return Response(
                {"detail": "User does not have a profile."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"profile": profile_data})

    # @database_sync_to_async
    def _update_account(self, request, partial, user_id=None):
        """
        Handles the update logic for both user and profile data.
        """
        logger.info(
            f"AccountManagementView (_update_account): request from user {request.user.id} for user {user_id} with data: {request.data}"
        )
        target_user = self._get_target_user(request, user_id)
        user_data = request.data.get("user", {})
        profile_data = request.data.get("profile", {})

        user_serializer = UserSerializer(target_user, data=user_data, partial=partial)
        user_serializer.is_valid(raise_exception=True)
        profile, profile_serializer_class = self._get_profile_and_serializer(
            target_user
        )
        profile_serializer = None
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

    def patch(self, request, user_id=None):
        """
        Partially update user and/or profile data.
        """
        return self._update_account(request, partial=True, user_id=user_id)
