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

from .views import (
    root,
    RefreshTokenView,
    LoginView,
    LogoutView,
    RequestPasswordChangeView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    ResendPasswordChangeOTPView,
    CandidateRegistrationView,
    StaffRegistrationView,
    VerifyEmailOTPView,
    ResendEmailOTPView,
    CandidateListView,
    CandidateDetailView,
    AssignCandidateRoleView,
    ExamHistoryView,
    StaffListView,
    StaffDetailView,
    AssignStaffRoleView,
    ExamListView,
    ExamDetailView,
    ExamQuestionsView,
    ExamResultsView,
    candidate_take_exam,
    SubmitAnswersView,
    SubmitScoreView,
    QuestionListView,
    QuestionDetailView,
    PublishScoresView,
    ToggleLeaderboardVisibilityView,
    PublishLeaderboardView,
    LoadLeaderboardView,
    CandidateDashboardView,
    StaffDashboardView,
    AccountManagementView,
    UserVerificationStatusView,
    UserVerificationUploadView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationActionView,
    health_check,
    CandidateMeView,
    StaffMeView,
    StaffInviteView,
)

app_name = "vmlc"

urlpatterns = [
    # =============================================================================
    # ROOT & AUTHENTICATION
    # =============================================================================
    path("health/", health_check, name="health-check"),
    path("root/", root, name="root"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    # Password Change
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
    # =============================================================================
    # REGISTRATION & VERIFICATION
    # =============================================================================
    # Candidate Registration
    path(
        "register/candidate/",
        CandidateRegistrationView.as_view(),
        name="register-candidate",
    ),
    # path(
    #     "register/candidate/toggle/",
    #     ToggleCandidateRegistrationView.as_view(),
    #     name="toggle-candidate-registration",
    # ),
    # Staff Registration
    path(
        "register/staff/",
        StaffRegistrationView.as_view(),
        name="register-staff",
    ),
    # path(
    #     "register/staff/toggle/",
    #     ToggleStaffRegistrationView.as_view(),
    #     name="toggle-staff-registration",
    # ),
    # === Email Verification ===
    path("verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"),
    path("resend-email-otp/", ResendEmailOTPView.as_view(), name="resend-email-otp"),
    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path("candidates/me/", CandidateMeView.as_view(), name="candidate-me"),
    path("candidates/", CandidateListView.as_view(), name="candidate-list"),
    path(
        "candidates/<uuid:candidate_id>/",
        CandidateDetailView.as_view(),
        name="candidate-detail",
    ),
    path(
        "candidates/<uuid:candidate_id>/roles/assign/",
        AssignCandidateRoleView.as_view(),
        name="candidate-role-assign",
    ),

    path(
        "candidates/<uuid:candidate_id>/exam-history/",
        ExamHistoryView.as_view(),
        name="candidate-exam-history",
    ),
    # =============================================================================
    # STAFF MANAGEMENT
    # =============================================================================
    path("staff/me/", StaffMeView.as_view(), name="staff-me"),
    path("staff/", StaffListView.as_view(), name="staff-list"),
    path(
        "staff/<uuid:staff_id>/",
        StaffDetailView.as_view(),
        name="staff-detail",
    ),
    path(
        "staff/<uuid:staff_id>/roles/assign/",
        AssignStaffRoleView.as_view(),
        name="staff-role-assign",
    ),
    path(
        "staff/invite/",
        StaffInviteView.as_view(),
        name="staff-invite",
    ),
    # =============================================================================
    # EXAM MANAGEMENT
    # =============================================================================
    # Exam CRUD Operations
    path("exams/", ExamListView.as_view(), name="exam-list"),
    path("exams/<int:exam_id>/", ExamDetailView.as_view(), name="exam-detail"),
    path(
        "exams/<int:exam_id>/questions/",
        ExamQuestionsView.as_view(),
        name="exam-questions",
    ),
    path(
        "exams/<int:exam_id>/results/",
        ExamResultsView.as_view(),
        name="exam-results",
    ),
    # Exam Taking & Submission
    path(
        "exams/<int:exam_id>/take-exam/",
        candidate_take_exam,
        name="take-exam",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-answers/",
        SubmitAnswersView.as_view(),
        name="submit-exam-answers",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-score/",
        SubmitScoreView.as_view(),
        name="submit-exam-score",
    ),
    # =============================================================================
    # QUESTION MANAGEMENT
    # =============================================================================
    path("questions/", QuestionListView.as_view(), name="question-list"),
    path(
        "questions/<int:question_id>/",
        QuestionDetailView.as_view(),
        name="question-detail",
    ),
    # =============================================================================
    # SCORING & RESULTS
    # =============================================================================
    # path(
    #     "publish-scores/",
    #     PublishScoresView.as_view(),
    #     name="publish-scores",
    # ),
    # =============================================================================
    # LEADERBOARD
    # =============================================================================
    # path(
    #     "toggle-leaderboard/",
    #     ToggleLeaderboardVisibilityView.as_view(),
    #     name="toggle-leaderboard",
    # ),
    path(
        "publish-leaderboard/",
        PublishLeaderboardView.as_view(),
        name="publish-leaderboard",
    ),
    path(
        "load-leaderboard/",
        LoadLeaderboardView.as_view(),
        name="load-leaderboard",
    ),
    # =============================================================================
    # DASHBOARDS & ACCOUNT MANAGEMENT
    # =============================================================================
    # User Dashboards
    path(
        "dashboard/candidate/",
        CandidateDashboardView.as_view(),
        name="candidate-dashboard",
    ),
    path(
        "dashboard/staff/",
        StaffDashboardView.as_view(),
        name="staff-dashboard",
    ),
    # Account Management
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
    # =============================================================================
    # USER VERIFICATION
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
]
