from django.urls import path

from .views import (
    CandidateListView,
    CowrywiseKidProfileView,
    LoginView,
    LogoutView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    RefreshTokenView,
    RegistrationMetricsView,
    RequestPasswordChangeView,
    ResendPasswordChangeOTPView,
    SendEmailOTPView,
    VerifyEmailOTPView,
    registration_status,
)
from .views.auth import DirectAccessLoginView
from .views.registration import PreRegistrationView, RegistrationV2View
from .views.user import (
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

app_name = "identity"

urlpatterns = [
    path("cowrywise-kids/", CowrywiseKidProfileView.as_view(), name="cowrywise-kids"),
    # Registration
    path("register/", RegistrationV2View.as_view(), name="register"),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register"),
    path("registration/", registration_status, name="registration-status"),
    # Authentication
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path(
        "auth/direct-access/",
        DirectAccessLoginView.as_view(),
        name="direct-access-login",
    ),
    path("auth/token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path(
        "auth/password-change/request/",
        RequestPasswordChangeView.as_view(),
        name="request-password-change",
    ),
    path(
        "auth/password-change/confirm-otp/",
        PasswordChangeOTPConfirmView.as_view(),
        name="verify-password-change-otp",
    ),
    path(
        "auth/password-change/",
        PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "auth/password-change/resend-otp/",
        ResendPasswordChangeOTPView.as_view(),
        name="resend-password-change-otp",
    ),
    path("verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"),
    path("send-email-otp/", SendEmailOTPView.as_view(), name="send-email-otp"),
    # User management
    path("user/list/", UserListView.as_view(), name="user-list"),
    path("user/export/", UserExportView.as_view(), name="user-export"),
    path(
        "user/bulk-notification/",
        BulkNotificationView.as_view(),
        name="user-bulk-notification",
    ),
    path(
        "user/reset-password/",
        ResetUserPasswordView.as_view(),
        name="user-reset-password",
    ),
    path("user/activity/", UserActivityLogView.as_view(), name="user-activity"),
    path("user/import/staff/", BulkStaffImportView.as_view(), name="user-import-staff"),
    path(
        "user/import/candidate/",
        BulkCandidateImportView.as_view(),
        name="user-import-candidate",
    ),
    path("staff/invite/", StaffInviteView.as_view(), name="staff-invite"),
    # Account management
    path(
        "account-management/",
        AccountManagementView.as_view(),
        name="account-management",
    ),
    path(
        "account-management/<uuid:user_id>/",
        AccountManagementView.as_view(),
        name="account-management-detail",
    ),
    # Candidate management
    path("candidates/", CandidateListView.as_view(), name="candidate-list"),
    path(
        "candidates/<uuid:candidate_id>/",
        UserDetailView.as_view(),
        name="candidate-detail",
    ),
    # Registration metrics
    path(
        "stats/registration-trends/",
        RegistrationMetricsView.as_view(),
        name="registration-trends",
    ),
]
