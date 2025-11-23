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
    AccountManagementView,
    AssignCandidateRoleView,
    AssignStaffRoleView,
    BulkAddQuestionsToExamsView,
    BulkQuestionArchiveView,
    CandidateDashboardView,
    CandidateInviteView,
    CandidateListView,
    CandidateMeView,
    CandidateRegistrationView,
    ExamDetailView,
    ExamHistoryView,
    ExamListView,
    ExamQuestionsView,
    ExamResultsView,
    LoadLeaderboardDetailView,
    LoadLeaderboardView,
    LoginView,
    LogoutView,
    PasswordChangeOTPConfirmView,
    PasswordChangeView,
    PublishLeaderboardView,
    QuestionDetailView,
    QuestionExamAssociationView,
    QuestionListView,
    RefreshTokenView,
    RequestPasswordChangeView,
    ResendPasswordChangeOTPView,
    SendEmailOTPView,
    StaffDashboardView,
    StaffInviteView,
    StaffListView,
    StaffMeView,
    StaffRegistrationView,
    SubmitAnswersView,
    SubmitScoreView,
    UserDetailView,
    UserListView,
    UserVerificationActionView,
    UserVerificationDocumentView,
    UserVerificationListView,
    UserVerificationStatusView,
    UserVerificationUploadView,
    VerifyEmailOTPView,
    candidate_take_exam,
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
    # AUTHENTICATION
    # =============================================================================
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
    path(
        "register/candidate/",
        CandidateRegistrationView.as_view(),
        name="register-candidate",
    ),
    path("register/staff/", StaffRegistrationView.as_view(), name="register-staff"),
    # Email Verification
    path("verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"),
    path("send-email-otp/", SendEmailOTPView.as_view(), name="send-email-otp"),
    # User Document Verification
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
    # =============================================================================
    # USER & ACCOUNT MANAGEMENT
    # =============================================================================
    path("user/list/", UserListView.as_view(), name="user-list"),
    path("candidates/me/", CandidateMeView.as_view(), name="candidate-me"),
    path("staff/me/", StaffMeView.as_view(), name="staff-me"),
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
    path(
        "candidates/<uuid:candidate_id>/exam-history/",
        ExamHistoryView.as_view(),
        name="candidate-exam-history",
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
    # =============================================================================
    # EXAM & QUESTION MANAGEMENT
    # =============================================================================
    # Exams
    path("exams/", ExamListView.as_view(), name="exam-list"),
    path("exams/<int:exam_id>/", ExamDetailView.as_view(), name="exam-detail"),
    path(
        "exams/<int:exam_id>/questions/",
        ExamQuestionsView.as_view(),
        name="exam-questions",
    ),
    path(
        "exams/<int:exam_id>/results/", ExamResultsView.as_view(), name="exam-results"
    ),
    # Questions
    path("questions/", QuestionListView.as_view(), name="question-list"),
    path(
        "questions/<int:question_id>/",
        QuestionDetailView.as_view(),
        name="question-detail",
    ),
    path(
        "questions/<int:question_id>/exams/",
        QuestionExamAssociationView.as_view(),
        name="question-exam-associations",
    ),
    path(
        "questions/bulk-add-to-exams/",
        BulkAddQuestionsToExamsView.as_view(),
        name="bulk-question-exam-associations",
    ),
    path(
        "questions/bulk-archive/",
        BulkQuestionArchiveView.as_view(),
        name="bulk-question-archive",
    ),
    # =============================================================================
    # SUBMISSIONS & SCORING
    # =============================================================================
    path("exams/<int:exam_id>/take-exam/", candidate_take_exam, name="take-exam"),
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
    # LEADERBOARD
    # =============================================================================
    path("leaderboard/", LoadLeaderboardView.as_view(), name="load-leaderboard"),
    path(
        "leaderboard/publish/",
        PublishLeaderboardView.as_view(),
        name="publish-leaderboard",
    ),
    path(
        "leaderboard/<str:stage>/<int:level>/candidate/<uuid:candidate_id>/",
        LoadLeaderboardDetailView.as_view(),
        name="load-leaderboard-detail",
    ),
    # =============================================================================
    # DASHBOARD & STATS
    # =============================================================================
    path(
        "dashboard/candidate/",
        CandidateDashboardView.as_view(),
        name="candidate-dashboard",
    ),
    path("dashboard/staff/", StaffDashboardView.as_view(), name="staff-dashboard"),
    path("stats/overview/", stats_overview, name="stats-overview"),
]
