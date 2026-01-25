from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework_api_key.permissions import HasAPIKey


from .models import Candidate, Staff


def _is_api_key_valid(key):
    from rest_framework_api_key.models import APIKey

    return APIKey.objects.is_valid(key)


class HasXAPIKey(HasAPIKey):
    def _get_key(self, request):
        return request.headers.get("x-api-key") or request.headers.get("X-Api-Key")

    def has_permission(self, request, view):
        key = self._get_key(request)
        if settings.DEBUG:
            return True
        if not key:
            return False
        return _is_api_key_valid(key)


def _get_candidate_profile(request):
    """Helper to get and cache candidate profile on the request object."""
    if not hasattr(request, "_candidate_profile"):
        try:
            # Use the explicit related_name from the model for clarity.
            request._candidate_profile = request.user.candidate_profile
        except (Candidate.DoesNotExist, AttributeError):
            request._candidate_profile = None
    return request._candidate_profile


def _get_staff_profile(request):
    """Helper to get and cache staff profile on the request object."""
    if not hasattr(request, "_staff_profile"):
        try:
            # Use the explicit related_name from the model for clarity.
            request._staff_profile = request.user.staff_profile
        except (ObjectDoesNotExist, AttributeError):
            request._staff_profile = None
    return request._staff_profile


class IsCandidate(BasePermission):
    """
    Grants access if the authenticated user has a related Candidate profile.
    """

    def has_permission(self, request, view):
        return _get_candidate_profile(request) is not None


class IsStaff(BasePermission):
    """
    Grants access if the authenticated user has a related Staff profile.
    """

    def has_permission(self, request, view):
        return _get_staff_profile(request) is not None


def HasStaffRole(*roles):
    """
    Permission factory that grants access to staff users with specific roles.

    Usage:
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN)

    Args:
        *roles: Variable number of Staff.Roles enum values
    """

    class HasStaffRolePermission(BasePermission):
        """Permission class that checks if user has any of the required staff roles."""

        def has_permission(self, request, view):
            """Check if user has any of the required staff roles."""
            staff_profile = _get_staff_profile(request)

            # User must have a staff profile and role must be in allowed roles
            if not staff_profile or not staff_profile.role:
                return False

            return staff_profile.role in roles

        def has_object_permission(self, request, view, obj):
            """Object-level permission check (inherits from has_permission)."""
            return self.has_permission(request, view)

    return HasStaffRolePermission


class StaffRoleHierarchy:
    """Helper class to define role hierarchies."""

    ROLE_LEVELS = {
        Staff.Roles.VOLUNTEER: 1,
        Staff.Roles.SPONSOR: 2,
        Staff.Roles.MODERATOR: 3,
        Staff.Roles.ADMIN: 4,
        Staff.Roles.MANAGER: 5,
        Staff.Roles.SUPERADMIN: 6,
    }

    @classmethod
    def has_minimum_role(cls, user_role, minimum_role):
        """Check if user role meets minimum requirement."""
        user_level = cls.ROLE_LEVELS.get(user_role, 0)
        min_level = cls.ROLE_LEVELS.get(minimum_role, 999)
        return user_level >= min_level


def HasMinimumStaffRole(minimum_role):
    """Permission factory for hierarchical role checking.

    Usage: HasMinimumStaffRole(Staff.Roles.ADMIN)
    This grants access to ADMIN MANAGER, and SUPERADMIN automatically.
    """

    class HasMinimumStaffRolePermission(BasePermission):
        def has_permission(self, request, view):
            staff_profile = _get_staff_profile(request)

            if not staff_profile:
                return False
            return StaffRoleHierarchy.has_minimum_role(staff_profile.role, minimum_role)

    return HasMinimumStaffRolePermission


class IsLeagueCandidate(BasePermission):
    """
    Grants access only to candidates whose role is 'league'.
    Useful for league-restricted actions like viewing the leaderboard.
    """

    message = "User is not a league candidate."

    def has_permission(self, request, view):
        candidate = _get_candidate_profile(request)
        return candidate and candidate.role == Candidate.Roles.LEAGUE


# Pre-instantiate permission classes for efficiency in composed permissions.
_is_league_candidate_perm = IsLeagueCandidate()
_is_elevated_staff_perm = HasStaffRole(
    Staff.Roles.MODERATOR,
    Staff.Roles.ADMIN,
    Staff.Roles.MANAGER,
    Staff.Roles.SUPERADMIN,
)()


class IsLeagueCandidateOrStaff(BasePermission):
    """
    Grants access if the user is a league candidate or a staff with an elevated role.
    """

    def has_permission(self, request, view):
        return _is_league_candidate_perm.has_permission(
            request, view
        ) or _is_elevated_staff_perm.has_permission(request, view)


class ReadOnly(BasePermission):
    """
    Grants access only for safe methods (GET, HEAD, OPTIONS).
    Blocks POST, PUT, PATCH, DELETE.
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class IsVerifiedStaff(BasePermission):
    """
    Grants access only to staff members whose accounts are verified.
    """

    message = "User is not a verified staff member."

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        staff_profile = _get_staff_profile(request)
        return staff_profile is not None and staff_profile.is_user_verified


class IsManagerForStaffDetail(BasePermission):
    """
    Allows access only to managers or superadmins when the view is accessing
    a staff detail endpoint (identified by 'staff_id' in the URL).
    """

    message = "Only 'superadmin' or 'manager' has permission to manage staff members."

    def has_permission(self, request, view):
        # If we are not accessing a staff detail page, this permission does not apply.
        if "staff_id" not in view.kwargs:
            return True

        # If we are on a staff detail page, check the user's role.
        staff_profile = _get_staff_profile(request)
        if not staff_profile:
            return False

        return staff_profile.role in [Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]


class IsObjectOwnerOrVerifiedAdmin(BasePermission):
    """
    Object-level permission that grants access if the user is either:
    1. The owner of the object (e.g., `request.user == obj.user`).
    2. A verified staff member with a 'admin' role or higher.
    """

    message = "You do not have permission to perform this action on this object."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # 1. Check if the user is the owner
        is_owner = False
        if hasattr(obj, "user"):
            is_owner = request.user == obj.user
        elif isinstance(obj, request.user.__class__):
            is_owner = request.user == obj

        if is_owner:
            return True

        # 2. Check if the user is a verified moderator or higher
        staff_profile = _get_staff_profile(request)
        is_admin = (
            staff_profile is not None
            and (settings.DEBUG or staff_profile.is_user_verified)
            and StaffRoleHierarchy.has_minimum_role(
                staff_profile.role, Staff.Roles.ADMIN
            )
        )

        return is_admin


class IsVerifiedModeratorOrCandidate(BasePermission):
    """
    Grants access to verified staff with at least a Moderator role, or any user with a candidate profile.
    """

    def has_permission(self, request, view):
        # Check for verified moderator role
        staff_profile = _get_staff_profile(request)
        is_verified_moderator = (
            staff_profile is not None
            and staff_profile.is_user_verified
            and StaffRoleHierarchy.has_minimum_role(
                staff_profile.role, Staff.Roles.MODERATOR
            )
        )

        # Check for candidate profile
        is_candidate = _get_candidate_profile(request) is not None

        return is_verified_moderator or is_candidate


AuthenticatedUser = [
    HasXAPIKey,
    IsAuthenticated,
]

CandidatePermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsCandidate,
]

StaffPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsStaff,
]

VerifiedModeratorPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsVerifiedStaff,
    HasMinimumStaffRole(Staff.Roles.MODERATOR),
]

VerifiedAdminPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsVerifiedStaff,
    HasMinimumStaffRole(Staff.Roles.ADMIN),
]

VerifiedManagerPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsVerifiedStaff,
    HasMinimumStaffRole(Staff.Roles.MANAGER),
]
