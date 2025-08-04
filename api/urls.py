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

from .views import (
    answer,
    auth,
    candidate,
    dashboard,
    exam,
    leaderboard,
    question,
    registration,
    root,
    score,
    staff,
    user,
)

app_name = "api"

urlpatterns = [
    # =============================================================================
    # ROOT & AUTHENTICATION
    # =============================================================================
    path("", root.api_root, name="api-root"),
    path("auth/login/", auth.LoginView.as_view(), name="api-login"),
    path("auth/logout/", auth.LogoutView.as_view(), name="api-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    
    # =============================================================================
    # REGISTRATION & VERIFICATION
    # =============================================================================
    # Candidate Registration
    path(
        "register/candidate/",
        registration.CandidateRegistrationView.as_view(),
        name="api-register-candidate",
    ),
    path(
        "register/candidate/toggle/",
        registration.ToggleCandidateRegistrationView.as_view(),
        name="api-toggle-candidate-registration",
    ),
    
    # Staff Registration
    path(
        "register/staff/",
        registration.StaffRegistrationView.as_view(),
        name="api-register-staff",
    ),
    path(
        "register/staff/toggle/",
        registration.ToggleStaffRegistrationView.as_view(),
        name="api-toggle-staff-registration",
    ),
    
    # Email Verification
    path(
        "verify-email-otp/",
        registration.VerifyOTPView.as_view(),
        name="verify-email-otp"
    ),
    path(
    "resend-email-otp/",
    registration.ResendOTPView.as_view(),
    name="resend-email-otp"
    ),

    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path(
        "candidates/",
        candidate.CandidateListView.as_view(),
        name="api-candidate-list"
    ),
    path(
        "candidates/<uuid:candidate_id>/",
        candidate.CandidateDetailView.as_view(),
        name="api-candidate-detail",
    ),
    path(
        "candidates/<uuid:candidate_id>/roles/assign/",
        candidate.AssignCandidateRoleView.as_view(),
        name="api-candidate-role-assign",
    ),
    path(
        "candidates/<uuid:candidate_id>/scores/",
        score.CandidateScoreListView.as_view(),
        name="api-candidate-scores",
    ),
    path(
        "candidates/<uuid:candidate_id>/exam-history/",
        exam.ExamHistoryView.as_view(),
        name="api-candidate-exam-history",
    ),
    
    # =============================================================================
    # STAFF MANAGEMENT
    # =============================================================================
    path(
        "staff/",
        staff.StaffListView.as_view(),
        name="api-staff-list"
    ),
    path(
        "staff/<uuid:staff_id>/",
        staff.StaffDetailView.as_view(),
        name="api-staff-detail",
    ),
    path(
        "staff/<uuid:staff_id>/roles/assign/",
        staff.AssignStaffRoleView.as_view(),
        name="api-staff-role-assign",
    ),
    
    # =============================================================================
    # EXAM MANAGEMENT
    # =============================================================================
    # Exam CRUD Operations
    path(
        "exams/",
        exam.ExamListView.as_view(),
        name="api-exam-list"
    ),
    path(
        "exams/<int:exam_id>/",
        exam.ExamDetailView.as_view(),
        name="api-exam-detail"
    ),
    path(
        "exams/<int:exam_id>/questions/",
        exam.ExamQuestionsView.as_view(),
        name="api-exam-questions",
    ),
    path(
        "exams/<int:exam_id>/results/",
        exam.ExamResultsView.as_view(),
        name="api-exam-results",
    ),

    # Exam Taking & Submission
    path(
        "exams/<int:exam_id>/take-exam/",
        exam.candidate_take_exam,
        name="api-take-exam",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-answers/",
        answer.SubmitAnswersView.as_view(),
        name="api-submit-exam-answers",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-score/",
        score.SubmitScoreView.as_view(),
        name="api-submit-exam-score",
    ),
    
    # =============================================================================
    # QUESTION MANAGEMENT
    # =============================================================================
    path(
        "questions/",
        question.QuestionListView.as_view(),
        name="api-question-list"
    ),
    path(
        "questions/<int:question_id>/",
        question.QuestionDetailView.as_view(),
        name="api-question-detail",
    ),
    
    # =============================================================================
    # SCORING & RESULTS
    # =============================================================================
    path(
        "publish-scores/",
        score.PublishScoresView.as_view(),
        name="api-publish-scores",
    ),
    
    # =============================================================================
    # LEADERBOARD
    # =============================================================================
    path(
        "toggle-leaderboard/",
        leaderboard.ToggleLeaderboardVisibilityView.as_view(),
        name="api-toggle-leaderboard",
    ),
    path(
        "publish-leaderboard/",
        leaderboard.PublishLeaderboardView.as_view(),
        name="api-publish-leaderboard",
    ),
    path(
        "load-leaderboard/",
        leaderboard.LoadLeaderboardView.as_view(),
        name="api-load-leaderboard",
    ),
    
    # =============================================================================
    # DASHBOARDS & ACCOUNT MANAGEMENT
    # =============================================================================
    # User Dashboards
    path(
        "dashboard/candidate/",
        dashboard.CandidateDashboardView.as_view(),
        name="api-candidate-dashboard",
    ),
    path(
        "dashboard/staff/",
        dashboard.StaffDashboardView.as_view(),
        name="api-staff-dashboard",
    ),
    
    # Account Management
    path(
        "account-management/",
        dashboard.AccountManagementView.as_view(),
        name="api-account-management",
    ),
    path(
        "account-management/<uuid:user_id>/",
        dashboard.AccountManagementView.as_view(),
        name="api-account-management-detail",
    ),
    path(
    "user-verification/",
    user.UserVerificationView.as_view(),
    name="api-verification",
    ),
    path(
        "user-verification/<uuid:user_id>/",
        user.UserVerificationView.as_view(),
        name="api-verification-detail",
    ),
    # path(
    #     "candidates/me/",
    #     candidate.CandidateMeView.as_view(),
    #     name="api-candidate-me"
    # ),
    # path(
    #     "staff/me/",
    #     staff.StaffMeView.as_view(),
    #     name="api-staff-me"
    # ),
]