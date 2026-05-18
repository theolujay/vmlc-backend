"""
URL configuration for the v1 API endpoints.
"""

from django.urls import path

from .views import (
    AccountManagementView,
    BulkCandidateImportView,
    BulkNotificationView,
    BulkStaffImportView,
    CandidateListView,
    RegistrationMetricsView,
    ResetUserPasswordView,
    StaffInviteView,
    UserActivityLogView,
    UserDetailView,
    UserExportView,
    UserListView,
    health_check,
    stats_overview,
    registration_status,
)

app_name = "vmlc"

urlpatterns = [
    # =============================================================================
    # HEALTH & ROOT
    # =============================================================================
    path("health/", health_check, name="health-check"),
    path("registration/", registration_status, name="registration-status"),
    path("user/list/", UserListView.as_view(), name="user-list"),
    path("user/export/", UserExportView.as_view(), name="user-export"),
    path("user/bulk-notification/", BulkNotificationView.as_view(), name="user-bulk-notification"),
    path("user/reset-password/", ResetUserPasswordView.as_view(), name="user-reset-password"),
    path("user/activity/", UserActivityLogView.as_view(), name="user-activity"),
    path("user/import/staff/", BulkStaffImportView.as_view(), name="user-import-staff"),
    path("user/import/candidate/", BulkCandidateImportView.as_view(), name="user-import-candidate"),
    # =============================================================================
    # USER & ACCOUNT MANAGEMENT
    # =============================================================================
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
    path("staff/invite/", StaffInviteView.as_view(), name="staff-invite"),
    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path("candidates/", CandidateListView.as_view(), name="candidate-list"),
    path(
        "candidates/<uuid:candidate_id>/",
        UserDetailView.as_view(),
        name="candidate-detail",
    ),
    path("stats/overview/", stats_overview, name="stats-overview"),
    path(
        "stats/registration-trends/",
        RegistrationMetricsView.as_view(),
        name="registration-trends",
    ),
]
