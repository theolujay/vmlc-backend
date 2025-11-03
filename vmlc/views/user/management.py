import logging
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone 
from django.conf import settings

from rest_framework.generics import CreateAPIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from vmlc.models import User
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    staff_registration_request_body,
    account_management_response_schema,
    account_management_request_body,
    error_response_401,
    error_response_403,
    error_response_404,
    error_response_400,
)
from vmlc.permissions import (
    AuthenticatedUser,
    IsObjectOwnerOrManagerRole,
    VerifiedManagerPermissions,
)
from vmlc.serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    StaffInviteSerializer,
    UserSerializer,
)
from vmlc.tasks import (
    send_mail_task,
    revoke_staff_invite_task,
)
from vmlc.utils.helpers import sanitize_data, invalidate_all_staff_dashboards

logger = logging.getLogger(__name__)

class AccountManagementView(APIView):
    """
    Retrieve or update user account and profile information.

    - GET: Retrieve account and profile information.
    - PUT/PATCH: Update account and profile.

    Regular users can manage their own accounts.
    Staff with 'admin' or 'superadmin' roles can manage other users' accounts.
    """

    permission_classes = AuthenticatedUser
    parser_classes = [MultiPartParser, FormParser]

    def _get_target_user(self, request, user_id=None):
        """
        Determines the target user for the action and checks permissions.
        """
        if user_id is None or user_id == str(request.user.id):
            return request.user

        # If a user_id is provided, check if the requester has permission.
        target_user = get_object_or_404(User, id=user_id)
        if not IsObjectOwnerOrManagerRole().has_object_permission(
            request, self, target_user
        ):
            logger.warning(
                f"User {request.user.id} does not have permission to manage user {user_id}."
            )
            raise PermissionDenied("You are not authorized to manage this user.")
        return target_user

    def _get_profile_and_serializer(self, user):
        """
        Gets the user's profile (Candidate or Staff) and the appropriate serializer.
        """
        if hasattr(user, "candidate_profile"):
            return user.candidate_profile, CandidateDetailSerializer
        if hasattr(user, "staff_profile"):
            return user.staff_profile, StaffDetailSerializer
        return None, None

    @swagger_auto_schema(
        operation_summary="Get User Account",
        operation_description="Retrieve the account and profile data of the target user.",
        responses={
            200: account_management_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Account Management"],
        manual_parameters=[api_key, bearer_auth],
    )
    def get(self, request, user_id=None):
        """
        Retrieve the account and profile data of the target user.
        """
        logger.info(
            f"AccountManagementView (get): request from user {request.user.id} for user {user_id}"
        )
        target_user = self._get_target_user(request, user_id)
        cache_key = f"account_management_{target_user.id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # user_data = UserSerializer(target_user).data
        profile, profile_serializer_class = self._get_profile_and_serializer(
            target_user
        )

        if profile and profile_serializer_class:
            profile_data = profile_serializer_class(profile).data
            profile_data.pop("records", None)
        else:
            logger.error(f"User {target_user.id} does not have a profile.")
            return Response(
                {"detail": "User does not have a profile."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response_data = {"profile": profile_data}
        cache.set(cache_key, response_data, 86400)  # Cache for 24 hours
        return Response(response_data)

    def _update_account(self, request, partial, user_id=None):
        """
        Handles the update logic for both user and profile data.
        """
        logger.info(
            f"AccountManagementView (_update_account): request from user {request.user.id} for user {user_id} with data: {request.data}"
        )       
        editable_fields = [
            "first_name",
            "last_name",
            "profile_picture",
            "phone_number",
            "school",
            "occupation",
        ]
        user_data = {}
        profile_data = {}
        target_user = self._get_target_user(request, user_id) 
        request_data = request.data
    
        for k, v in request_data.items():
            if k not in editable_fields:
                request_data.pop(k)
            elif k in editable_fields[:3]:
                user_data[k] = v
            elif k in editable_fields[3:]:
                profile_data[k] = v

        # If no data was extracted, it's a bad request.
        if not user_data and not profile_data:
            return Response({"detail": "No user or profile data provided."}, status=status.HTTP_400_BAD_REQUEST)

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

        # Invalidate the account management cache
        cache.delete(f"account_management_{target_user.id}")

        # Invalidate candidate dashboard cache if the user has a candidate profile
        if hasattr(target_user, "candidate_profile"):
            cache.delete(f"candidate_dashboard_{target_user.candidate_profile.pk}")
            # Invalidate all staff dashboards as candidate data changes
            from vmlc.utils.helpers import invalidate_all_staff_dashboards
            invalidate_all_staff_dashboards()
        
        # Invalidate all staff dashboards if the user has a staff profile
        if hasattr(target_user, "staff_profile"):
            from vmlc.models import Staff
            for staff in Staff.objects.all():
                cache.delete(f"staff_dashboard_data_{staff.pk}")

        logger.info(
            "Account for user %s updated by %s.",
            target_user.id,
            request.user.id,
        )
        
        # Re-serialize to get the latest data for the response
        updated_profile, updated_serializer_class = self._get_profile_and_serializer(target_user)
        if updated_profile and updated_serializer_class:
            response_profile_data = updated_serializer_class(updated_profile).data
        else:
            response_profile_data = None

        return Response(
            {
                "message": "Account updated successfully.",
                "profile": response_profile_data,
            }
        )

    @swagger_auto_schema(
        operation_summary="Update User Account",
        operation_description="Partially update user and/or profile data.",
        manual_parameters=[
            openapi.Parameter("first_name", openapi.IN_FORM, type=openapi.TYPE_STRING, description="User's first name."),
            openapi.Parameter("last_name", openapi.IN_FORM, type=openapi.TYPE_STRING, description="User's last name."),
            openapi.Parameter("profile_picture", openapi.IN_FORM, type=openapi.TYPE_FILE, description="User's profile picture."),
            openapi.Parameter("phone_number", openapi.IN_FORM, type=openapi.TYPE_STRING, description="User's phone number."),
            openapi.Parameter("school", openapi.IN_FORM, type=openapi.TYPE_STRING, description="Candidate's school."),
            openapi.Parameter("occupation", openapi.IN_FORM, type=openapi.TYPE_STRING, description="Staff's occupation."),
            api_key, 
            bearer_auth
        ],
        responses={
            200: openapi.Response("Account updated successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Account Management"],
    )
    def patch(self, request, user_id=None):
        """
        Partially update user and/or profile data.
        """
        return self._update_account(request, partial=True, user_id=user_id)

class StaffInviteView(CreateAPIView):
    """
    API view to create a new staff member.
    """
    permission_classes = VerifiedManagerPermissions
    serializer_class = StaffInviteSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.staff_profile)

    @swagger_auto_schema(
        operation_summary="Create Staff Member",
        operation_description="Creates a new staff member with the provided details.",
        request_body=staff_registration_request_body,
        responses={
            201: openapi.Response("Staff member created successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Staff Management"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request, *args, **kwargs):
        temp_password = request.data.get("password")
        login_url = f"{settings.FRONTEND_LOGIN}"
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Calculate the time delta based on environment
        revoke_delta = timedelta(days=7) if not settings.DEBUG else timedelta(minutes=5)
        time_to_revoke = timezone.now() + revoke_delta

        # Schedule the revocation task to run after 'time_to_revoke'
        revoke_staff_invite_task.apply_async(
            args=[serializer.instance.user.id],
            eta=time_to_revoke
        )

        staff_profile = serializer.instance
        user = staff_profile.user

        # Dynamically generate the human-readable time string
        if not settings.DEBUG:
            time_to_revoke_str = f"{revoke_delta.days} days"
        else:
            time_to_revoke_str = f"{revoke_delta.seconds // 60} minutes"
        send_mail_task.delay(
            subject="Staff Invite to Verboheit MLC",
            message = (
                f"Hello {user.get_full_name()},\n\n"
                f"You've been invited to join the Verboheit Mathematics League Competition "
                f"{timezone.now().year} as a staff member. To accept, log in using the link "
                f"below with this email and the temporary password provided. Remember to change "
                f"it after login. If you choose not to accept, simply ignore this message. "
                f"Note that the credentials will expire in {time_to_revoke_str} if you don't log in.\n\n"
                f"Password: {temp_password}\n"
                f"Login: {login_url}\n\n"
                f"Regards,\n"
                f"Verboheit MLC Management"
            ),
            recipient_list=[user.email],
        )
        headers = self.get_success_headers({})
        logger.info(
            f"Staff profile created successfully with email: {user.email} by {request.user.email}"
        )
        return Response(
            {"message": "Staff profile created, invite sent."},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
