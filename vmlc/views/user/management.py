import logging
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.utils.decorators import method_decorator

from rest_framework.settings import api_settings
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from vmlc.serializers import (
    StaffListSerializer,
    CandidateListSerializer,
)
from vmlc.models import User, UserVerification, Staff, Candidate
from vmlc.utils.auth import generate_password
from vmlc.utils.swagger_schemas import (
    api_key,
    bearer_auth,
    staff_registration_request_body,
    candidate_registration_request_body,
    account_management_response_schema,
    error_response_401,
    error_response_403,
    error_response_404,
    error_response_400,
)
from vmlc.permissions import (
    AuthenticatedUser,
    IsObjectOwnerOrManagerRole,
    VerifiedManagerPermissions,
    VerifiedModeratorPermissions,
)
from vmlc.serializers import (
    CandidateDetailSerializer,
    StaffDetailSerializer,
    StaffInviteSerializer,
    CandidateInviteSerializer,
    UserSerializer,
)
from vmlc.tasks import (
    generate_stats_overview_task,
    send_mail_task,
    revoke_user_invite_task,
)
from vmlc.utils.query_filters import (
    filter_staffs,
    filter_candidates,
    filter_users,
)

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
            f"AccountManagementView (get): "
            f"request from user {request.user.id} for user {user_id}"
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
            f"AccountManagementView (_update_account): request from user {request.user.id} "
            f"for user {user_id} with data: {request.data}"
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
            return Response(
                {"detail": "No user or profile data provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        updated_profile, updated_serializer_class = self._get_profile_and_serializer(
            target_user
        )
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
            openapi.Parameter(
                "first_name",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="User's first name.",
            ),
            openapi.Parameter(
                "last_name",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="User's last name.",
            ),
            openapi.Parameter(
                "profile_picture",
                openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="User's profile picture.",
            ),
            openapi.Parameter(
                "phone_number",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="User's phone number.",
            ),
            openapi.Parameter(
                "school",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Candidate's school.",
            ),
            openapi.Parameter(
                "occupation",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Staff's occupation.",
            ),
            api_key,
            bearer_auth,
        ],
        responses={
            200: openapi.Response("Account updated successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Management"],
    )
    def patch(self, request, user_id=None):
        """
        Partially update user and/or profile data.
        """
        return self._update_account(request, partial=True, user_id=user_id)


class BaseInviteView(CreateAPIView):
    """
    Base API view to create a new user invite.
    """

    permission_classes = VerifiedManagerPermissions
    serializer_class = None
    profile_type = ""

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.staff_profile)

    @swagger_auto_schema(
        operation_summary=f"Create {profile_type.title()} User",
        operation_description=(
            f"Creates a new {profile_type.title()} user with the provided details."
            " An invitation email with login credentials will be sent to the user."
        ),
        request_body=(
            staff_registration_request_body
            if profile_type == "staff"
            else candidate_registration_request_body
        ),
        responses={
            201: openapi.Response(f"{profile_type.title()} user created successfully."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["User Management"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request, *args, **kwargs):
        request_data = request.data.copy()
        temp_password = generate_password()
        request_data["password"] = temp_password
        request_data["password2"] = temp_password
        login_url = f"{settings.FRONTEND_LOGIN}"
        serializer = self.get_serializer(data=request_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        UserVerification.objects.get_or_create(user=serializer.instance.user)
        # Calculate the time delta based on environment
        revoke_delta = timedelta(days=7) if not settings.DEBUG else timedelta(minutes=5)
        time_to_revoke = timezone.now() + revoke_delta

        # Schedule the revocation task to run after 'time_to_revoke'
        revoke_user_invite_task.apply_async(
            args=[serializer.instance.user.id], eta=time_to_revoke
        )

        profile = serializer.instance
        user = profile.user
        profile_msg = ""
        # Dynamically generate the human-readable time string
        if not settings.DEBUG:
            time_to_revoke_str = f"{revoke_delta.days} days"
        else:
            time_to_revoke_str = f"{revoke_delta.seconds // 60} minutes"

        if self.profile_type == "staff":
            profile_msg = (
                f"You've been invited to join the Verboheit Mathematics League Competition "
                f"{timezone.now().year} as a staff member. "
            )
        elif self.profile_type == "candidate":
            profile_msg = (
                f"Your profile has been created to participate in the "
                f"Verboheit Mathematics League Competition. "
            )
        message = (
            f"Hello, {user.first_name}.\n\n"
            f"{profile_msg}"
            f"To accept, log in using the link "
            f"below with this email address and the generated password provided. Please use "
            f"'Forgot Password' to set your own password. If you choose not to accept, simply ignore this message. "
            f"Note that the credentials will expire in {time_to_revoke_str} if you do not log in.\n\n"
            f"Email: {user.email}\n"
            f"Password: {temp_password}\n"
            f"Login: {login_url}\n\n"
            f"Regards,\n"
            f"Management, Verboheit MLC."
        )
        send_mail_task.delay(
            subject="Welcome to Verboheit MLC - Your Account Details",
            message=message,
            recipient_list=[user.email],
        )
        headers = self.get_success_headers({})
        logger.info(
            f"{self.profile_type.title()} profile created successfully with user: {user.id} by user {request.user.id}"
        )
        return Response(
            {"message": f"{self.profile_type.title()} profile created, invite sent."},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class StaffInviteView(BaseInviteView):
    """
    API view to create a new staff member.
    """

    permission_classes = VerifiedManagerPermissions
    serializer_class = StaffInviteSerializer
    profile_type = "staff"

    def post(self, request, *args, **kwargs):
        """
        Creates a new staff user and sends an invitation email.
        """
        return super().post(request, *args, **kwargs)


class CandidateInviteView(BaseInviteView):
    """
    API view to create a new candidate.
    """

    permission_classes = VerifiedManagerPermissions
    serializer_class = CandidateInviteSerializer
    profile_type = "candidate"

    def post(self, request, *args, **kwargs):
        """
        Creates a new candidate user and sends an invitation email.
        """
        return super().post(request, *args, **kwargs)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Users",
        operation_description="List all users. Can be filtered by profile type ('staff' or 'candidate').",
        manual_parameters=[
            openapi.Parameter(
                "profile",
                openapi.IN_QUERY,
                description="Filter by user profile type ('staff' or 'candidate').",
                type=openapi.TYPE_STRING,
            ),
            api_key,
            bearer_auth,
        ],
        responses={
            200: openapi.Response("Paginated list of users."),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["User Management"],
    ),
)
class UserListView(ListAPIView):
    """
    List all users with pagination and optional filtering.
    Can be filtered by `profile` query parameter to 'staff' or 'candidate'.
    Level of detail depends on role.
    """

    permission_classes = VerifiedModeratorPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def list(self, request, *args, **kwargs):
        user = request.user
        staff = Staff.objects.get(user=user)
        queryset = self.filter_queryset(self.get_queryset())
        stats_overview = cache.get("stats_overview")

        if staff.role in [Staff.Roles.MODERATOR, Staff.Roles.ADMIN]:
            if stats_overview is not None:
                _ = stats_overview.pop("staff")
            if stats_overview is None:
                generate_stats_overview_task.delay()
                stats_overview = "Statistics overview is being generated. Please check back in a few moments."
            if (
                request.query_params.get("profile") is None
                or request.query_params.get("profile") == "staff"
            ):
                return Response(
                    {"detail": "manager or superadmin role required"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if staff.role in [Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]:
            if stats_overview is None:
                generate_stats_overview_task.delay()
                stats_overview = "Statistics overview is being generated. Please check back in a few moments."

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["stats_overview"] = stats_overview
            response.data["results"] = response.data.pop("results")
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({"stats_overview": stats_overview, "results": serializer.data})

    def get_serializer_class(self):
        requested_profile = self.request.query_params.get("profile")
        if requested_profile == "candidate":
            return CandidateListSerializer
        if requested_profile == "staff":
            return StaffListSerializer
        return UserSerializer

    def get_queryset(self):
        """Returns a filtered queryset of users"""

        requested_profile = self.request.query_params.get("profile")
        logger.info(
            f"UserListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        if requested_profile == "candidate":
            queryset = Candidate.objects.select_related("user").order_by("-created_at")
            return filter_candidates(queryset, self.request.query_params)
        if requested_profile == "staff":
            queryset = Staff.objects.select_related("user").order_by("-created_at")
            return filter_staffs(queryset, self.request.query_params)

        queryset = User.objects.prefetch_related(
            "staff_profile", "candidate_profile"
        ).order_by("-date_joined")
        return filter_users(queryset, self.request.query_params)
