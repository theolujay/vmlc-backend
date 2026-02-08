from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework_api_key.permissions import HasAPIKey


from identity.models import Candidate, Staff


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
            request._candidate_profile = request.user.candidate_profile
        except (Candidate.DoesNotExist, AttributeError):
            request._candidate_profile = None
    return request._candidate_profile


def _get_staff_profile(request):
    """Helper to get and cache staff profile on the request object."""
    if not hasattr(request, "_staff_profile"):
        try:
            request._staff_profile = request.user.staff_profile
        except (ObjectDoesNotExist, AttributeError):
            request._staff_profile = None
    return request._staff_profile


def _get_enrollment(request):
    """Helper to get and cache enrollment on the request object."""
    enrollment = getattr(request, "enrollment", None)
    if enrollment is None:
        candidate = _get_candidate_profile(request)
        if candidate:
            from competition.models import Enrollment, Competition

            enrollment = (
                Enrollment.objects.filter(
                    candidate=candidate,
                    competition__status=Competition.Status.ACTIVE,
                    status=Enrollment.Status.ACTIVE,
                )
                .select_related("competition", "current_stage")
                .first()
            )
            request.enrollment = enrollment
    return enrollment


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
    """

    class HasStaffRolePermission(BasePermission):
        def has_permission(self, request, view):
            staff_profile = _get_staff_profile(request)
            if not staff_profile or not staff_profile.role:
                return False
            return staff_profile.role in roles

        def has_object_permission(self, request, view, obj):
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
        user_level = cls.ROLE_LEVELS.get(user_role, 0)
        min_level = cls.ROLE_LEVELS.get(minimum_role, 999)
        return user_level >= min_level


def HasMinimumStaffRole(minimum_role):
    """Permission factory for hierarchical role checking."""

    class HasMinimumStaffRolePermission(BasePermission):
        def has_permission(self, request, view):
            staff_profile = _get_staff_profile(request)
            if not staff_profile:
                return False
            return StaffRoleHierarchy.has_minimum_role(staff_profile.role, minimum_role)

    return HasMinimumStaffRolePermission


class IsInStage(BasePermission):
    """
    Grants access if the candidate is ACTIVE and in one of the allowed stages.
    Usage: IsInStage('league')
    """

    def __init__(self, *allowed_stages):
        self.allowed_stages = allowed_stages

    def __call__(self):
        return self

    def has_permission(self, request, view):
        enrollment = _get_enrollment(request)
        if not enrollment:
            return False

        from competition.models import Enrollment

        if enrollment.status != Enrollment.Status.ACTIVE:
            return False

        if not enrollment.current_stage:
            return False

        return enrollment.current_stage.type in self.allowed_stages


class IsLeagueCandidate(IsInStage):
    """
    Grants access only to candidates in the 'league' stage.
    """

    def __init__(self):
        from competition.models import Stage

        super().__init__(Stage.Type.LEAGUE)


class IsLeagueCandidateOrStaff(BasePermission):
    """
    Grants access if the user is a league candidate or a staff with an elevated role.
    """

    def has_permission(self, request, view):
        # 1. Staff check
        staff_profile = _get_staff_profile(request)
        if (
            staff_profile
            and (settings.DEBUG or staff_profile.is_active)
            and StaffRoleHierarchy.has_minimum_role(
                staff_profile.role, Staff.Roles.MODERATOR
            )
        ):
            return True

        # 2. League Candidate check
        enrollment = _get_enrollment(request)
        if not enrollment:
            return False

        from competition.models import Enrollment, Stage

        return (
            enrollment.status == Enrollment.Status.ACTIVE
            and enrollment.current_stage
            and enrollment.current_stage.type == Stage.Type.LEAGUE
        )


class ReadOnly(BasePermission):
    """
    Grants access only for safe methods (GET, HEAD, OPTIONS).
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class IsActiveStaff(BasePermission):
    """
    Grants access only to staff members whose accounts are non-deactivated.
    """

    message = "User is a deactivated staff member."

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        staff_profile = _get_staff_profile(request)
        return staff_profile is not None and staff_profile.is_active


class IsManagerForStaffDetail(BasePermission):
    """
    Allows access only to managers or superadmins when the view is accessing
    a staff detail endpoint (identified by 'staff_id' in the URL).
    """

    message = "Only 'superadmin' or 'manager' has permission to manage staff members."

    def has_permission(self, request, view):
        if "staff_id" not in view.kwargs:
            return True

        staff_profile = _get_staff_profile(request)
        if not staff_profile:
            return False

        return staff_profile.role in [Staff.Roles.MANAGER, Staff.Roles.SUPERADMIN]


class IsObjectOwnerOrActiveAdmin(BasePermission):
    """
    Object-level permission that grants access if the user is either:
    1. The owner of the object.
    2. A non-deactivated staff member with a 'admin' role or higher.
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
        staff_profile = _get_staff_profile(request)
        is_admin = (
            staff_profile is not None
            and (settings.DEBUG or staff_profile.is_active)
            and StaffRoleHierarchy.has_minimum_role(
                staff_profile.role, Staff.Roles.ADMIN
            )
        )

        return is_admin


class IsActiveModeratorOrCandidate(BasePermission):
    """
    Grants access to non-deactivated staff with at least a Moderator role, or any user with a candidate profile.
    """

    def has_permission(self, request, view):
        # Check for active moderator role
        staff_profile = _get_staff_profile(request)
        is_active_moderator = (
            staff_profile is not None
            and (settings.DEBUG or staff_profile.is_active)
            and StaffRoleHierarchy.has_minimum_role(
                staff_profile.role, Staff.Roles.MODERATOR
            )
        )

        # Check for candidate profile
        is_candidate = _get_candidate_profile(request) is not None

        return is_active_moderator or is_candidate


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

ActiveModeratorPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsActiveStaff,
    HasMinimumStaffRole(Staff.Roles.MODERATOR),
]

ActiveAdminPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsActiveStaff,
    HasMinimumStaffRole(Staff.Roles.ADMIN),
]

ActiveManagerPermissions = [
    HasXAPIKey,
    IsAuthenticated,
    IsActiveStaff,
    HasMinimumStaffRole(Staff.Roles.MANAGER),
]
