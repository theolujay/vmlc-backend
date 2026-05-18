"""
This package contains all the views for the API.
"""

from .auth import (
    RefreshTokenView,
    VerifyEmailOTPView,
    SendEmailOTPView,
    RequestPasswordChangeView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    ResendPasswordChangeOTPView,
    CustomTokenObtainPairSerializer,
    LoginView,
    LogoutView,
)
from .candidate import (
    CandidateListView,
    AssignCandidateRoleView,
    CandidateMeView,
)
from .metrics import RegistrationMetricsView
from .staff import (
    StaffListView,
    AssignStaffRoleView,
    StaffMeView,
)
from .status import (
    health_check,
    stats_overview,
    registration_status,
)
from .user import (
    BulkNotificationView,
    BulkStaffImportView,
    BulkCandidateImportView,
    ResetUserPasswordView,
    UserActivityLogView,
    AccountManagementView,
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
    CandidateInviteView,
    StaffInviteView,
    UserExportView,
    UserListView,
    UserDetailView,
)

__all__ = [
    # auth
    "RefreshTokenView",
    "VerifyEmailOTPView",
    "SendEmailOTPView",
    "RequestPasswordChangeView",
    "PasswordChangeOTPConfirmView",
    "PasswordChangeView",
    "ResendPasswordChangeOTPView",
    "CustomTokenObtainPairSerializer",
    "LoginView",
    "LogoutView",
    # candidate
    "CandidateMeView",
    "CandidateListView",
    "AssignCandidateRoleView",
    "AccountManagementView",
    # status
    "health_check",
    "stats_overview",
    "registration_status",
    # staff
    "StaffMeView",
    "StaffListView",
    "AssignStaffRoleView",
    # user
    "BulkNotificationView",
    "BulkStaffImportView",
    "BulkCandidateImportView",
    "ResetUserPasswordView",
    "UserActivityLogView",
    "UserVerificationStatusView",
    "UserVerificationUploadView",
    "UserVerificationDocumentView",
    "UserVerificationListView",
    "UserVerificationActionView",
    "StaffInviteView",
    "CandidateInviteView",
    "UserExportView",
    "UserListView",
    "UserDetailView",
    "RegistrationMetricsView",
]
