"""
URL configuration for the API endpoints of the application.

This module defines URL patterns for all API routes, including:
- User registration (candidates and staff)
- Candidate and staff management
- Exams and questions
- Dashboard and account operations
- Leaderboard

All views are organized and grouped by functionality for clarity.
"""

from django.urls import path

from .views import (
    AccountManagementView,
    AssignCandidateRoleView,
    AssignStaffRoleView,
    BulkCandidateImportView,
    BulkNotificationView,
    BulkStaffImportView,
    CandidateInviteView,
    CandidateListView,
    RegistrationMetricsView,
    ResetUserPasswordView,
    StaffInviteView,
    StaffListView,
    UserActivityLogView,
    UserDetailView,
    UserExportView,
    UserListView,
    UserVerificationActionView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationStatusView,
    UserVerificationUploadView,
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
    # =============================================================================
    # USER DOCUMENT VERIFICATION
    # =============================================================================
    path(
        "user/verification/status/",
        UserVerificationStatusView.as_view(),
        name="user-verification-status",
    ),
    path(
        "user/verification/status/<uuid:user_id>/",
        UserVerificationStatusView.as_view(),
        name="user-verification-status-admin",
    ),
    path(
        "user/verification/upload/",
        UserVerificationUploadView.as_view(),
        name="user-verification-upload",
    ),
    path(
        "user/verification/documents/<str:file_type>/",
        UserVerificationDocumentView.as_view(),
        name="user-verification-document",
    ),
    path(
        "user/verification/documents/<str:file_type>/<uuid:user_id>/",
        UserVerificationDocumentView.as_view(),
        name="user-verification-document-admin",
    ),
    path(
        "user/verification/list/",
        UserVerificationListView.as_view(),
        name="user-verification-list",
    ),
    path(
        "user/verification/action/<uuid:user_id>/",
        UserVerificationActionView.as_view(),
        name="user-verification-action",
    ),
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
    path("candidate/invite/", CandidateInviteView.as_view(), name="candidate-invite"),
    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path("candidates/", CandidateListView.as_view(), name="candidate-list"),
    path(
        "candidates/<uuid:candidate_id>/",
        UserDetailView.as_view(),
        name="candidate-detail",
    ),
    path(
        "candidates/<uuid:candidate_id>/roles/assign/",
        AssignCandidateRoleView.as_view(),
        name="candidate-role-assign",
    ),
    # =============================================================================
    # STAFF MANAGEMENT
    # =============================================================================
    path("staff/", StaffListView.as_view(), name="staff-list"),
    path("staff/<uuid:staff_id>/", UserDetailView.as_view(), name="staff-detail"),
    path(
        "staff/<uuid:staff_id>/roles/assign/",
        AssignStaffRoleView.as_view(),
        name="staff-role-assign",
    ),
    path("stats/overview/", stats_overview, name="stats-overview"),
    path(
        "stats/registration-trends/",
        RegistrationMetricsView.as_view(),
        name="registration-trends",
    ),
]
