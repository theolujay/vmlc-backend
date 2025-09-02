"""
URL configuration for the API endpoints of the application.

This module defines URL patterns for all API routes, including:
- Authentication and JWT token handling
- User registration (candidates and staff)
- Candidate and staff management
- Exams and questions
- Dashboard and account operations
- Leaderboard

All views are organized and grouped by functionality for clarity.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *

app_name = "api"

urlpatterns = [
    # =============================================================================
    # ROOT & AUTHENTICATION
    # =============================================================================
    path("root/", api_root, name="api-root"),
    path("auth/login/", LoginView.as_view(), name="api-login"),
    path("auth/logout/", LogoutView.as_view(), name="api-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Password Change
    path(
        "auth/password-change/request/",
        RequestPasswordChangeView.as_view(),
        name="api-request-password-change",
    ),
    path(
        "auth/password-change/confirm-otp/",
        PasswordChangeOTPConfirmView.as_view(),
        name="api-verify-password-change-otp",
    ),
    path(
        "auth/password-change/",
        PasswordChangeView.as_view(),
        name="api-password-change",
    ),
    path(
        "auth/password-change/resend-otp/",
        ResendPasswordChangeOTPView.as_view(),
        name="api-resend-password-change-otp",
    ),
    # =============================================================================
    # REGISTRATION & VERIFICATION
    # =============================================================================
    # Candidate Registration
    path(
        "register/candidate/",
        CandidateRegistrationView.as_view(),
        name="api-register-candidate",
    ),
    # path(
    #     "register/candidate/toggle/",
    #     ToggleCandidateRegistrationView.as_view(),
    #     name="api-toggle-candidate-registration",
    # ),
    # Staff Registration
    path(
        "register/staff/",
        StaffRegistrationView.as_view(),
        name="api-register-staff",
    ),
    # path(
    #     "register/staff/toggle/",
    #     ToggleStaffRegistrationView.as_view(),
    #     name="api-toggle-staff-registration",
    # ),
    # === Email Verification ===
    path(
        "verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"
    ),
    path(
        "resend-email-otp/", ResendEmailOTPView.as_view(), name="resend-email-otp"
    ),
    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path(
        "candidates/", CandidateListView.as_view(), name="api-candidate-list"
    ),
    path(
        "candidates/<uuid:candidate_id>/",
        CandidateDetailView.as_view(),
        name="api-candidate-detail",
    ),
    path(
        "candidates/<uuid:candidate_id>/roles/assign/",
        AssignCandidateRoleView.as_view(),
        name="api-candidate-role-assign",
    ),
    path(
        "candidates/<uuid:candidate_id>/scores/",
        CandidateScoreListView.as_view(),
        name="api-candidate-scores",
    ),
    path(
        "candidates/<uuid:candidate_id>/exam-history/",
        ExamHistoryView.as_view(),
        name="api-candidate-exam-history",
    ),
    # =============================================================================
    # STAFF MANAGEMENT
    # =============================================================================
    path("staff/", StaffListView.as_view(), name="api-staff-list"),
    path(
        "staff/<uuid:staff_id>/",
        StaffDetailView.as_view(),
        name="api-staff-detail",
    ),
    path(
        "staff/<uuid:staff_id>/roles/assign/",
        AssignStaffRoleView.as_view(),
        name="api-staff-role-assign",
    ),
    # =============================================================================
    # EXAM MANAGEMENT
    # =============================================================================
    # Exam CRUD Operations
    path("exams/", ExamListView.as_view(), name="api-exam-list"),
    path("exams/<int:exam_id>/", ExamDetailView.as_view(), name="api-exam-detail"),
    path(
        "exams/<int:exam_id>/questions/",
        ExamQuestionsView.as_view(),
        name="api-exam-questions",
    ),
    path(
        "exams/<int:exam_id>/results/",
        ExamResultsView.as_view(),
        name="api-exam-results",
    ),
    # Exam Taking & Submission
    path(
        "exams/<int:exam_id>/take-exam/",
        candidate_take_exam,
        name="api-take-exam",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-answers/",
        SubmitAnswersView.as_view(),
        name="api-submit-exam-answers",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-score/",
        SubmitScoreView.as_view(),
        name="api-submit-exam-score",
    ),
    # =============================================================================
    # QUESTION MANAGEMENT
    # =============================================================================
    path("questions/", QuestionListView.as_view(), name="api-question-list"),
    path(
        "questions/<int:question_id>/",
        QuestionDetailView.as_view(),
        name="api-question-detail",
    ),
    # =============================================================================
    # SCORING & RESULTS
    # =============================================================================
    path(
        "publish-scores/",
        PublishScoresView.as_view(),
        name="api-publish-scores",
    ),
    # =============================================================================
    # LEADERBOARD
    # =============================================================================
    path(
        "toggle-leaderboard/",
        ToggleLeaderboardVisibilityView.as_view(),
        name="api-toggle-leaderboard",
    ),
    path(
        "publish-leaderboard/",
        PublishLeaderboardView.as_view(),
        name="api-publish-leaderboard",
    ),
    path(
        "load-leaderboard/",
        LoadLeaderboardView.as_view(),
        name="api-load-leaderboard",
    ),
    # =============================================================================
    # DASHBOARDS & ACCOUNT MANAGEMENT
    # =============================================================================
    # User Dashboards
    path(
        "dashboard/candidate/",
        CandidateDashboardView.as_view(),
        name="api-candidate-dashboard",
    ),
    path(
        "dashboard/staff/",
        StaffDashboardView.as_view(),
        name="api-staff-dashboard",
    ),
    # Account Management
    path(
        "account-management/",
        AccountManagementView.as_view(),
        name="api-account-management",
    ),
    path(
        "account-management/<uuid:user_id>/",
        AccountManagementView.as_view(),
        name="api-account-management-detail",
    ),
    # =============================================================================
    # USER VERIFICATION
    # =============================================================================
    path(
        "user/verification/status/",
        UserVerificationStatusView.as_view(),
        name="user-verification-status",
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
    # path(
    #     "candidates/me/",
    #     CandidateMeView.as_view(),
    #     name="api-candidate-me"
    # ),
    # path(
    #     "staff/me/",
    #     StaffMeView.as_view(),
    #     name="api-staff-me"
    # ),
]
