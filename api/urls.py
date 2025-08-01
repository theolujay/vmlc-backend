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
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


from .views import (
    answers,
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
)

app_name = "api"

urlpatterns = [
    # === ROOT & AUTH ===
    path("", root.api_root, name="api-root"),
    path("auth/login/", auth.LoginView.as_view(), name="api-login"),
    path("auth/logout/", auth.LogoutView.as_view(), name="api-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # === REGISTRATION ===
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
    # === CANDIDATES ===
    path(
        "candidates/", candidate.CandidateListView.as_view(), name="api-candidate-list"
    ),
    path("candidates/me/", candidate.CandidateMeView.as_view(), name="api-candidate-me"),
    path(
        "candidates/<int:candidate_id>/",
        candidate.CandidateDetailView.as_view(),
        name="api-candidate-detail",
    ),
    path(
        "candidates/<int:candidate_id>/roles/assign/",
        candidate.AssignCandidateRoleView.as_view(),
        name="api-candidate-role-assign",
    ),
    path(
        "candidates/<int:candidate_id>/scores/",
        score.CandidateScoreListView.as_view(),
        name="api-candidate-scores",
    ),
    path(
        "candidates/<int:candidate_id>/exam-history/",
        exam.ExamHistoryView.as_view(),
        name="api-candidate-exam-history",
    ),
    # === STAFF ===
    path("staff/", staff.StaffListView.as_view(), name="api-staff-list"),
    path("staff/me/", staff.StaffMeView.as_view(), name="api-staff-me"),
    path(
        "staff/<int:staff_id>/",
        staff.StaffDetailView.as_view(),
        name="api-staff-detail",
    ),
    path(
        "staff/<int:staff_id>/roles/assign/",
        staff.AssignStaffRoleView.as_view(),
        name="api-staff-role-assign",
    ),
    # === EXAMS ===
    path("exams/", exam.ExamListView.as_view(), name="api-exam-list"),
    path("exams/<int:exam_id>/", exam.ExamDetailView.as_view(), name="api-exam-detail"),
    path(
        "exams/<int:exam_id>/questions/",
        exam.ExamQuestionsView.as_view(),
        name="api-exam-questions",
    ),
    path(
        "exams/<int:exam_id>/take-exam/",
        exam.candidate_take_exam,
        name="api-take-exam",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-score/",
        score.SubmitScoreView.as_view(),
        name="api-submit-exam-score",
    ),
    path(
        "exams/<int:exam_id>/submit-exam-answers/",
        answers.SubmitAnswersView.as_view(),
        name="api-submit-exam-answers",
    ),
    # === QUESTIONS ===
    path("questions/", question.QuestionListView.as_view(), name="api-question-list"),
    path(
        "questions/<int:question_id>/",
        question.QuestionDetailView.as_view(),
        name="api-question-detail",
    ),
    # === DASHBOARDS ===
    path(
        "dashboard/candidate/",
        dashboard.candidate_dashboard_api,
        name="api-candidate-dashboard",
    ),
    path("dashboard/staff/", dashboard.staff_dashboard_api, name="api-staff-dashboard"),
    # === ACCOUNT MANAGEMENT ===
    path(
        "account-management/",
        dashboard.AccountManagementView.as_view(),
        name="api-account-management",
    ),
    path(
        "account-management/<int:user_id>/",
        dashboard.AccountManagementView.as_view(),
        name="api-account-management-detail",
    ),
    # === LEADERBOARD ===
    path(
        "toggle-leaderboard/",
        leaderboard.toggle_leaderboard,
        name="api-toggle-leaderboard",
    ),
    path(
        "publish-leaderboard/",
        leaderboard.publish_leaderboard,
        name="api-publish-leaderboard",
    ),
    path(
        "load-leaderboard/",
        leaderboard.load_leaderboard_api,
        name="api-load-leaderboard",
    ),
]
