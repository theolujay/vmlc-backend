from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework_api_key.permissions import HasAPIKey

from identity.models import Candidate, Staff

def _is_api_key_valid(key):
    from rest_framework_api_key.models import APIKey
    return APIKey.objects.is_valid(key)


class HasXAPIKey(HasAPIKey):
    """
    Custom API Key permission that checks 'x-api-key' or 'X-Api-Key' header.
    """
    def _get_key(self, request):
        return request.headers.get("x-api-key") or request.headers.get("X-Api-Key")

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        key = self._get_key(request)
        if not key:
            return False
        return _is_api_key_valid(key)


# Profile Helpers (Cached on request)
def get_candidate_profile(request):
    """Helper to get and cache candidate profile on the request object."""
    if not hasattr(request, "_candidate_profile"):
        try:
            request._candidate_profile = request.user.candidate_profile
        except (AttributeError, ObjectDoesNotExist):
            request._candidate_profile = None
    return request._candidate_profile


def get_staff_profile(request):
    """Helper to get and cache staff profile on the request object."""
    if not hasattr(request, "_staff_profile"):
        try:
            request._staff_profile = request.user.staff_profile
        except (AttributeError, ObjectDoesNotExist):
            request._staff_profile = None
    return request._staff_profile


# =============================================================================
# CORE PERMISSIONS
# =============================================================================

class IsCandidate(BasePermission):
    """Grants access if the user has a Candidate profile."""
    def has_permission(self, request, view):
        return get_candidate_profile(request) is not None


class IsStaff(BasePermission):
    """Grants access if the user has a Staff profile."""
    def has_permission(self, request, view):
        return get_staff_profile(request) is not None


class IsActiveStaff(BasePermission):
    """Grants access if the user is a non-deactivated Staff member."""
    message = "User is a deactivated staff member."
    def has_permission(self, request, view):
        staff = get_staff_profile(request)
        return staff is not None and (settings.DEBUG or staff.is_active)


# =============================================================================
# STAFF ROLE HIERARCHY
# =============================================================================

class StaffRoleHierarchy:
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
        user_level = cls.ROLE_LEVELS.get(user_role, 0)
        min_level = cls.ROLE_LEVELS.get(minimum_role, 999)
        return user_level >= min_level


def HasMinimumStaffRole(minimum_role):
    """Permission factory for hierarchical role checking."""
    class HasMinimumStaffRolePermission(BasePermission):
        def has_permission(self, request, view):
            staff = get_staff_profile(request)
            if not staff:
                return False
            return StaffRoleHierarchy.has_minimum_role(staff.role, minimum_role)
    return HasMinimumStaffRolePermission


# =============================================================================
# COMPETITION AWARE PERMISSIONS
# =============================================================================

class IsActiveCompetitionParticipant(BasePermission):
    """
    Grants access if the candidate is ACTIVE in the current competition edition.
    Uses context from CompetitionContextMiddleware.
    """
    def has_permission(self, request, view):
        enrollment = getattr(request, 'enrollment', None)
        if not enrollment:
            return False
        from competition.models import Enrollment
        return enrollment.status == Enrollment.Status.ACTIVE

class IsInStage(BasePermission):
    """
    Grants access if the candidate is ACTIVE and in one of the allowed stages.
    Usage: IsInStage('league') or IsInStage('league', 'final')
    """
    def __init__(self, *allowed_stages):
        self.allowed_stages = allowed_stages

    def __call__(self):
        return self

    def has_permission(self, request, view):
        enrollment = getattr(request, 'enrollment', None)
        if not enrollment:
            return False
            
        from competition.models import Enrollment
        if enrollment.status != Enrollment.Status.ACTIVE:            return False
            
        if not enrollment.current_stage:
            return False
            
        return enrollment.current_stage.type in self.allowed_stages


class CanAccessStageResource(IsInStage):
    """Alias for IsInStage for backward compatibility."""
    pass


class IsLeagueParticipantOrStaffBase(BasePermission):
    """
    Grants access if the user is an active Staff (Moderator+) OR 
    an active League candidate in the current competition.
    """
    def has_permission(self, request, view):
        # Staff check
        staff = get_staff_profile(request)
        if staff and (settings.DEBUG or staff.is_active) and StaffRoleHierarchy.has_minimum_role(staff.role, Staff.Roles.MODERATOR):
            return True
            
        # League Participant check
        enrollment = getattr(request, 'enrollment', None)
        if not enrollment:
            return False
            
        from competition.models import Enrollment, Stage
        return (
            enrollment.status == Enrollment.Status.ACTIVE and
            enrollment.current_stage and 
            enrollment.current_stage.type == Stage.Type.LEAGUE
        )


# =============================================================================
# GENERAL UTILITY PERMISSIONS
# =============================================================================

class ReadOnly(BasePermission):
    """
    Grants access only for safe methods (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

class IsManagerForStaffDetail(BasePermission):
    """
    Allows access only to managers or superadmins when the view is accessing
    a staff detail endpoint (identified by 'staff_id' in the URL).
    """

    message = "Only 'superadmin' or 'manager' has permission to manage staff members."

    def has_permission(self, request, view):
        if "staff_id" not in view.kwargs:
            return True

        staff_profile = get_staff_profile(request)
        if not staff_profile:
            return False

        return staff_profile.role in [Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]

class IsObjectOwnerOrActiveAdmin(BasePermission):
    """
    Object-level permission that grants access if the user is either:
    1. The owner of the object.
    2. A non-deactivated staff member with an 'admin' role or higher.
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

        # 2. Check if the user is a non-deactivated moderator or higher
        staff = get_staff_profile(request)
        is_admin = (
            staff is not None
            and (settings.DEBUG or staff.is_active)
            and StaffRoleHierarchy.has_minimum_role(staff.role, Staff.Roles.ADMIN)
        )

        return is_admin


class IsActiveModeratorOrCandidate(BasePermission):
    """
    Grants access to active staff (Moderator+) or any candidate.
    """
    def has_permission(self, request, view):
        staff = get_staff_profile(request)
        is_active_moderator = (
            staff is not None
            and (settings.DEBUG or staff.is_active)
            and StaffRoleHierarchy.has_minimum_role(staff.role, Staff.Roles.MODERATOR)
        )
        is_candidate = get_candidate_profile(request) is not None
        return is_active_moderator or is_candidate


# =============================================================================
# COMPOSED PERMISSION SETS
# =============================================================================

AuthenticatedUser = [
    HasXAPIKey,
    IsAuthenticated,
]


CandidatePermissions = [IsCandidate] + AuthenticatedUser
ActiveParticipantPermissions = [IsActiveCompetitionParticipant] + AuthenticatedUser
IsLeagueParticipantOrStaff = [IsLeagueParticipantOrStaffBase] + AuthenticatedUser

ActiveStaff = AuthenticatedUser + [IsActiveStaff]
ActiveVolunteerPermissions = [HasMinimumStaffRole(Staff.Roles.VOLUNTEER)] + ActiveStaff
ActiveModeratorPermissions = [HasMinimumStaffRole(Staff.Roles.MODERATOR)] + ActiveStaff
ActiveAdminPermissions = [HasMinimumStaffRole(Staff.Roles.ADMIN)] + ActiveStaff
ActiveManagerPermissions = [HasMinimumStaffRole(Staff.Roles.MANAGER)] + ActiveStaff




