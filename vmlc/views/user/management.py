import logging
import itertools
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.utils.decorators import method_decorator
from django.core.files.uploadedfile import UploadedFile

from rest_framework.settings import api_settings
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from vmlc.serializers import (
    StaffListSerializer,
    CandidateListSerializer,
    UserProfileListSerializer,
)
from identity.models import PreRegUser, User, UserVerification, Staff, Candidate
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
from identity.permissions import (
    AuthenticatedUser,
    IsManagerForStaffDetail,
    IsObjectOwnerOrActiveAdmin,
    ActiveAdminPermissions,
    ActiveManagerPermissions,
    ActiveModeratorPermissions,
)
from vmlc.serializers import (
    StaffInviteSerializer,
    CandidateInviteSerializer,
    UserProfileDetailSerializer,
)
from vmlc.tasks import (
    send_mail_task,
    revoke_user_invite_task,
)
from vmlc.utils.stats import generate_stats_overview_data
from vmlc.utils.query_filters import (
    filter_pre_reg_users,
    filter_staffs,
    filter_candidates,
    filter_users,
)
from vmlc.v2.serializers.registration import PreRegUserSerializer

logger = logging.getLogger(__name__)

class RequestDataExtractor:
    """Extracts and validates user and profile data from request."""
    
    USER_FIELDS = {"first_name", "last_name", "profile_picture", "phone", "state"}
    PROFILE_FIELDS = {"occupation", "current_class", "school_type"}
    FILE_FIELDS = {"profile_picture"}
    
    @classmethod
    def extract(cls, request_data):
        """
        Extract user and profile data from request, filtering out empty values.
        Returns: (user_data, profile_data)
        """
        user_data = {}
        profile_data = {}
        
        for key, value in request_data.items():
            # Skip empty values
            if not cls._is_valid_value(key, value):
                continue
            
            clean_key = cls._normalize_key(key)
            
            if clean_key in cls.USER_FIELDS:
                user_data[clean_key] = value
            elif clean_key in cls.PROFILE_FIELDS:
                profile_data[clean_key] = value
        
        return user_data, profile_data
    
    @classmethod
    def _is_valid_value(cls, key, value):
        """Check if a value is valid (not empty or placeholder)."""
        # Handle None and empty strings
        if value is None or value == '':
            return False
        
        # Handle empty lists/arrays
        if isinstance(value, (list, tuple)) and len(value) == 0:
            return False
        
        # For file fields, ensure it's an actual uploaded file
        clean_key = cls._normalize_key(key)
        if clean_key in cls.FILE_FIELDS:
            return isinstance(value, UploadedFile)
        
        return True
    
    @staticmethod
    def _normalize_key(key):
        """Remove common prefixes from field names."""
        # Handle user.field_name
        if key.startswith("user."):
            return key.replace("user.", "")
        
        # Handle user[field_name]
        if key.startswith("user[") and key.endswith("]"):
            return key[5:-1]
        
        # Handle profile.field_name
        if key.startswith("profile."):
            return key.replace("profile.", "")
        
        # Handle profile[field_name]
        if key.startswith("profile[") and key.endswith("]"):
            return key[8:-1]
        
        return key


class ProfileManager:
    """Manages profile retrieval and serialization."""
    
    PROFILE_MAPPING = {
        "candidate_profile": "CandidateDetailSerializer",
        "staff_profile": "StaffDetailSerializer",
    }
    
    @classmethod
    def get_profile_and_serializer(cls, user):
        """
        Get profile instance and serializer class for user.
        Returns: (profile_instance, serializer_class) or (None, None)
        """
        if hasattr(user, "candidate_profile"):
            from vmlc.serializers import CandidateDetailSerializer
            return user.candidate_profile, CandidateDetailSerializer
        
        if hasattr(user, "staff_profile"):
            from vmlc.serializers import StaffDetailSerializer
            return user.staff_profile, StaffDetailSerializer
        
        return None, None
    
    @classmethod
    def serialize_profile(cls, user):
        """Serialize user profile, removing unnecessary fields."""
        profile, serializer_class = cls.get_profile_and_serializer(user)
        
        if not profile or not serializer_class:
            return None
        
        profile_data = serializer_class(profile).data
        profile_data.pop("records", None)
        return profile_data


class AccountCacheManager:
    """Handles caching logic for account data."""
    
    CACHE_TTL = 86400  # 24 hours
    
    @staticmethod
    def get_cache_key(user_id):
        return f"account_management_{user_id}"
    
    @classmethod
    def get_cached_data(cls, user_id):
        """Retrieve cached account data."""
        return cache.get(cls.get_cache_key(user_id))
    
    @classmethod
    def cache_data(cls, user_id, data):
        """Cache account data."""
        cache.set(cls.get_cache_key(user_id), data, cls.CACHE_TTL)
    
    @classmethod
    def invalidate_user_cache(cls, user):
        """Invalidate all caches related to a user."""
        from identity.models import Staff
        
        cache.delete(cls.get_cache_key(user.id))
        
        if hasattr(user, "candidate_profile"):
            cache.delete(f"candidate_dashboard_{user.candidate_profile.pk}")
            from vmlc.utils.helpers import invalidate_all_staff_dashboards
            invalidate_all_staff_dashboards()
        
        if hasattr(user, "staff_profile"):
            for staff in Staff.objects.all():
                cache.delete(f"staff_dashboard_data_{staff.pk}")


class AccountManagementView(APIView):
    """
    Retrieve or update user account and profile information.
    
    - GET: Retrieve account and profile information.
    - PATCH: Update account and profile.
    
    Regular users can manage their own accounts.
    Staff with 'admin' or 'superadmin' roles can manage other users' accounts.
    """
    
    permission_classes = AuthenticatedUser
    parser_classes = [MultiPartParser, FormParser]
    
    def _get_target_user(self, request, user_id=None):
        """Determine target user and verify permissions."""
        if user_id is None or user_id == str(request.user.id):
            return request.user
        
        target_user = get_object_or_404(User, id=user_id)
        
        if not IsObjectOwnerOrActiveAdmin().has_object_permission(request, self, target_user):
            logger.warning(
                f"User {request.user.id} lacks permission to manage user {user_id}"
            )
            raise PermissionDenied("You are not authorized to manage this user.")
        
        return target_user
    
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
        """Retrieve account and profile data."""
        logger.info(
            f"GET account_management: user {request.user.id} requesting user {user_id}"
        )
        
        target_user = self._get_target_user(request, user_id)
        
        # Check cache first
        cached_data = AccountCacheManager.get_cached_data(target_user.id)
        if cached_data:
            return Response(cached_data)
        
        # Serialize profile
        profile_data = ProfileManager.serialize_profile(target_user)
        if not profile_data:
            logger.error(f"User {target_user.id} has no profile")
            return Response(
                {"detail": "User does not have a profile."},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        response_data = {"profile": profile_data}
        AccountCacheManager.cache_data(target_user.id, response_data)
        
        return Response(response_data)
    
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
                "phone",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="User's phone number.",
            ),
            openapi.Parameter(
                "state",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="User's state of origin.",
            ),
            openapi.Parameter(
                "school_name",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Candidate's school.",
            ),
            openapi.Parameter(
                "school_type",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                enum=["public", "private"],
                description="Candidate's school type.",
            ),
            openapi.Parameter(
                "current_class",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                enum=["SS1", "SS2", "SS3"],
                description="Candidate's current class.",
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
        """Partially update user and/or profile data."""
        logger.info(
            f"PATCH account_management: user {request.user.id} updating user {user_id}"
        )
        
        target_user = self._get_target_user(request, user_id)
        
        # Extract and validate data
        user_data, profile_data = RequestDataExtractor.extract(request.data)
        
        if not user_data and not profile_data:
            logger.warning(
                f"No valid data provided for user {user_id} update. "
                f"Request data keys: {list(request.data.keys())}"
            )
            return Response(
                {"detail": "No user or profile data provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Prepare serializers for validation
        serializers_to_save = []
        
        # Validate user data if provided
        if user_data:
            from vmlc.serializers import UserSerializer
            user_serializer = UserSerializer(
                target_user, 
                data=user_data, 
                partial=True
            )
            user_serializer.is_valid(raise_exception=True)
            serializers_to_save.append(user_serializer)
        
        # Validate profile data if provided
        if profile_data:
            profile, profile_serializer_class = ProfileManager.get_profile_and_serializer(
                target_user
            )
            if profile and profile_serializer_class:
                profile_serializer = profile_serializer_class(
                    profile, 
                    data=profile_data, 
                    partial=True
                )
                profile_serializer.is_valid(raise_exception=True)
                serializers_to_save.append(profile_serializer)
        
        # Save all validated data atomically
        with transaction.atomic():
            for serializer in serializers_to_save:
                serializer.save()
        
        # Invalidate caches
        AccountCacheManager.invalidate_user_cache(target_user)
        
        logger.info(f"Account {target_user.id} updated by {request.user.id}")
        
        # Return updated profile data
        updated_profile_data = ProfileManager.serialize_profile(target_user)
        
        return Response({
            "message": "Account updated successfully.",
            "profile": updated_profile_data,
        })


class BaseInviteView(CreateAPIView):
    """
    Base API view to create a new user invite.
    """

    permission_classes = ActiveManagerPermissions
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
                "You've been invited to join the Verboheit Mathematics League Competition "
                f"{timezone.now().year} as a staff member. "
            )
        elif self.profile_type == "candidate":
            profile_msg = (
                "Your profile has been created to participate in the "
                "Verboheit Mathematics League Competition. "
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


# @method_decorator(
#     name="post",
#     decorator=swagger_auto_schema(
#         operation_summary="Staff Invite",
#         operation_description="Create a staff profile and send the user an invite.",
#         responses={
#             200: staff_invite_response_schema,
#             401: error_response_401,
#             403: error_response_403,
#         },
#         tags=["Staff"],
#         manual_parameters=[api_key, bearer_auth],
#     ),
# )
class StaffInviteView(BaseInviteView):
    """
    API view to create a new staff member.
    """

    permission_classes = ActiveManagerPermissions
    serializer_class = StaffInviteSerializer
    profile_type = "staff"


# @method_decorator(
#     name="post",
#     decorator=swagger_auto_schema(
#         operation_summary="Candidate Invite",
#         operation_description="Create a candidate profile and send the user an invite.",
#         responses={
#             200: candidate_invite_response_schema,
#             401: error_response_401,
#             403: error_response_403,
#         },
#         tags=["Candidate"],
#         manual_parameters=[api_key, bearer_auth],
#     ),
# )
class CandidateInviteView(BaseInviteView):
    """
    API view to create a new candidate.
    """

    permission_classes = ActiveManagerPermissions
    serializer_class = CandidateInviteSerializer
    profile_type = "candidate"


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
    Can be filtered by `profile` query parameter to 'staff', 'candidate', or 'pre_reg_candidate'.
    Level of detail depends on role.
    """

    permission_classes = ActiveModeratorPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def list(self, request, *args, **kwargs):
        user = request.user
        staff = Staff.objects.get(user=user)

        # Get cache version
        version = cache.get("user_list_version", 1)
        # Create a stable cache key based on role, query parameters and version
        query_params_str = str(sorted(request.query_params.items()))
        cache_key = f"user_list_view_{version}_{staff.role}_{query_params_str}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        stats_overview = self._get_stats_overview(staff.role)

        queryset_or_list = self.get_queryset()
        
        # Only call filter_queryset if it's a real QuerySet
        if isinstance(queryset_or_list, QuerySet):
            queryset_or_list = self.filter_queryset(queryset_or_list)

        page = self.paginate_queryset(queryset_or_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["stats_overview"] = stats_overview
            response.data["results"] = response.data.pop("results")
            cache.set(cache_key, response.data, 43200)  # Cache for 12 hours
            return response

        serializer = self.get_serializer(queryset_or_list, many=True)
        response_data = {"stats_overview": stats_overview, "results": serializer.data}
        cache.set(cache_key, response_data, 43200)  # Cache for 12 hour
        return Response(response_data)

    def _get_stats_overview(self, staff_role):
        """Helper to get the stats overview from cache, regenerating if necessary."""
        stats_overview = cache.get("stats_overview")

        if stats_overview is None:
            stats_overview = generate_stats_overview_data()
            cache.set("stats_overview", stats_overview, timeout=3600)

        # Make a copy to avoid modifying the cached object.
        stats_overview = stats_overview.copy()
        if staff_role not in [Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]:
            stats_overview.pop("staff", None)

        return stats_overview

    def get_serializer_class(self):
        requested_profile = self.request.query_params.get("profile")
        if requested_profile == "candidate":
            return CandidateListSerializer
        if requested_profile == "staff":
            return StaffListSerializer
        if requested_profile in ["pre_reg_candidate", "pre_reg_staff"]:
            return PreRegUserSerializer
        return UserProfileListSerializer

    def get_serializer_kwargs(self):
        kwargs = super().get_serializer_kwargs()
        requested_profile = self.request.query_params.get("profile")
        if requested_profile == "pre_reg_candidate":
            kwargs["interest_type"] = "candidate"
        if requested_profile == "pre_reg_staff":
            kwargs["interest_type"] = "volunteer"
        return kwargs

    def get_queryset(self):
        """Returns a filtered queryset or combined list of users"""

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
        if requested_profile in ["pre_reg_candidate", "pre_reg_staff"]:
            queryset = PreRegUser.objects.order_by("-created_at")
            return filter_pre_reg_users(queryset, self.request.query_params)

        # Combined view: fully registered and pre-registered users
        users_qs = User.objects.prefetch_related(
            "staff_profile", "candidate_profile", "verification"
        ).order_by("-date_joined")
        users_qs = filter_users(users_qs, self.request.query_params)

        # Pre-registered users should also be filtered by common params like search
        pre_reg_qs = PreRegUser.objects.order_by("-created_at")
        search = self.request.query_params.get("search")
        if search:
            pre_reg_qs = pre_reg_qs.filter(
                Q(full_name__icontains=search) | Q(email__icontains=search)
            )
        
        # Don't show pre-registered users if filtering by role/school since they don't have them
        role = self.request.query_params.get("role")
        school = self.request.query_params.get("school_name")
        if role or school:
            return users_qs

        # Merge and sort by join/creation date
        combined = sorted(
            itertools.chain(users_qs, pre_reg_qs),
            key=lambda x: x.date_joined if isinstance(x, User) else x.created_at,
            reverse=True,
        )
        return combined


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get User Profile",
        operation_description="Retrieve details for a specific staff or candidate profile.",
        responses={
            200: openapi.Response(
                "Profile details for a staff or candidate member. The schema depends on the user profile.",
                schema=UserProfileDetailSerializer,
            ),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Management"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Update User Profile",
        operation_description="Partially update a staff or candidate profile. The available fields depend on the profile type.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "school_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Candidate's school. (Candidate only)",
                ),
                "occupation": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Staff's occupation. (Staff only)",
                ),
                "role": openapi.Schema(
                    type=openapi.TYPE_STRING, description="User role within the system."
                ),
                "is_active": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN, description="Set profile active status."
                ),
            },
        ),
        responses={
            200: openapi.Response(
                "Profile updated successfully.", schema=UserProfileDetailSerializer
            ),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Management"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        operation_summary="Deactivate User Profile",
        operation_description="Deactivates a staff or candidate profile by setting `is_active` to false (soft delete).",
        responses={
            204: openapi.Response("Profile deactivated successfully."),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["User Management"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class UserDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or deactivate a specific staff or candidate member.

    - GET: Retrieve profile details.
    - PATCH: Update profile.
    - DELETE: Soft delete the profile (marks as inactive).

    Access to staff profiles is restricted to Managers and Superadmins.
    """

    serializer_class = UserProfileDetailSerializer
    permission_classes = ActiveAdminPermissions + [IsManagerForStaffDetail]
    http_method_names = ["get", "patch", "delete"]
    profile = ""

    def initial(self, request, *args, **kwargs):
        """
        Dynamically set lookup_url_kwarg and profile based on URL.
        """
        super().initial(request, *args, **kwargs)
        if "staff_id" in self.kwargs:
            self.lookup_url_kwarg = "staff_id"
            self.profile = "staff"
        elif "candidate_id" in self.kwargs:
            self.lookup_url_kwarg = "candidate_id"
            self.profile = "candidate"

    def retrieve(self, request, *args, **kwargs):
        """Get candidate/staff profile detail"""
        profile_id = self.kwargs.get(self.lookup_url_kwarg)
        cache_key = f"{self.profile}_profile_{profile_id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        cache.set(cache_key, data, 3600)  # Cache for 1 hour
        return Response(data)

    def perform_update(self, serializer):
        """Save updates to candidate/staff"""
        target_profile = serializer.instance
        request_user = self.request.user
        logger.info(
            "%s profile %s update request by user %s",
            self.profile.title(),
            target_profile.pk,
            request_user.id,
        )
        serializer.save()
        cache.delete(f"{self.profile}_profile_{target_profile.pk}")
        cache.delete(f"{self.profile}_dashboard_data_{target_profile.pk}")

    def perform_destroy(self, instance):
        """Deactivates a candidate/staff profile (soft delete)"""
        target_profile = instance
        request_user = self.request.user
        logger.info(
            "%s profile %s soft-delete request by user %s",
            self.profile.title(),
            target_profile.pk,
            request_user.id,
        )
        instance.is_active = False
        instance.save()
        cache.delete(f"{self.profile}_profile_{target_profile.pk}")
        cache.delete(f"{self.profile}_dashboard_data_{target_profile.pk}")

    def get_queryset(self):
        if self.profile == "candidate":
            return (
                Candidate.objects.select_related("user", "user__verification")
                .prefetch_related("results__exam", "results__score_submitted_by__user")
                .all()
            )
        if self.profile == "staff":
            return Staff.objects.select_related("user", "user__verification").all()
        return User.objects.none()
