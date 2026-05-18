"""
This package contains all the views for the API.
"""

from identity.views.auth import (
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
from identity.views.user import (
    AccountManagementView,
    BulkCandidateImportView,
    BulkNotificationView,
    BulkStaffImportView,
    ResetUserPasswordView,
    StaffInviteView,
    UserActivityLogView,
    UserDetailView,
    UserExportView,
    UserListView,
)
from .candidate import CandidateListView
from .metrics import RegistrationMetricsView
from .status import (
    health_check,
    stats_overview,
    registration_status,
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
    "CandidateListView",
    # status
    "health_check",
    "stats_overview",
    "registration_status",
    # user
    "AccountManagementView",
    "BulkCandidateImportView",
    "BulkNotificationView",
    "BulkStaffImportView",
    "ResetUserPasswordView",
    "StaffInviteView",
    "UserActivityLogView",
    "UserDetailView",
    "UserExportView",
    "UserListView",
    "RegistrationMetricsView",
]
