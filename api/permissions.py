"""
Custom DRF permission classes for fine-grained access control.

Includes role-based access (e.g., staff, candidate, league-specific),
object-level access, and read-only constraints.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Candidate, Staff


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
        except (Staff.DoesNotExist, AttributeError):
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


class IsOwnerOrStaff(BasePermission):
    """
    Object-level permission: grants access if the user is the object's owner (obj.user)
    or has a staff profile.
    """

    def has_object_permission(self, request, view, obj):
        # The object could be a Candidate, Staff, or User instance.
        # Check if the request.user is the owner of the object.
        is_owner = False
        if hasattr(obj, "user"):
            is_owner = request.user == obj.user
        elif isinstance(obj, request.user.__class__):
            is_owner = request.user == obj
        return is_owner or _get_staff_profile(request) is not None


def HasStaffRole(*roles):
    """
    Permission factory that grants access to staff users with specific roles.
    This is more explicit and reusable than a class with an __init__.
    """

    class HasStaffRolePermission(BasePermission):
        def has_permission(self, request, view):
            staff_profile = _get_staff_profile(request)
            return staff_profile and staff_profile.role in roles

    return HasStaffRolePermission


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
    Staff.Roles.MODERATOR, Staff.Roles.ADMIN, Staff.Roles.OWNER
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
        staff_profile = _get_staff_profile(request)
        return staff_profile is not None and staff_profile.is_verified


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: grants access if the user is the object's owner
    or a staff member with 'admin' or 'owner' role.
    """

    message = "You do not have permission to perform this action on this object."

    def has_object_permission(self, request, view, obj):
        is_owner = False
        if hasattr(obj, "user"):
            is_owner = request.user == obj.user
        elif isinstance(obj, request.user.__class__):
            is_owner = request.user == obj

        is_admin = HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER)().has_permission(
            request, view
        )

        return is_owner or is_admin
