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
from identity.views.registration import RegistrationV2View, PreRegistrationView
from vmlc.views.exam import ExamRetractV2View, ExamTimeView, ExamListV2View, ExamDetailV2View, ExamResultsV2View, ExamQuestionsV2View, ExamHistoryV2View, ExamFaceCaptureView, candidate_take_exam_V2
from vmlc.views.auth import DirectAccessLoginView
from vmlc.views.proctoring import (
    CandidateLiveStatusV2View,
    ExamHeartbeatView,
    IntegrityAuditView,
    UpdateProctoringStatusView,
)
from vmlc.views.question import (
    QuestionListCreateV2View,
    QuestionDetailV2View,
    QuestionBulkActionV2View,
)
from vmlc.views.answer import (
    SubmitAnswersV2View,
    AutoSaveAnswersV2View,
    GetSavedAnswersV2View,
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
    # =============================================================================
    # V2 ROUTES (merged from vmlc.v2.urls)
    # =============================================================================
    path("register/", RegistrationV2View.as_view(), name="register"),
    path(
        "auth/direct-access/",
        DirectAccessLoginView.as_view(),
        name="direct-access-login",
    ),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register"),
    # =============================================================================
    # EXAM & QUESTION MANAGEMENT
    # =============================================================================
    path("exams/", ExamListV2View.as_view(), name="exam-list"),
    path("exams/<uuid:exam_id>/", ExamDetailV2View.as_view(), name="exam-detail"),
    path(
        "exams/<uuid:exam_id>/retract/",
        ExamRetractV2View.as_view(),
        name="exam-retract",
    ),
    path(
        "exams/<uuid:exam_id>/questions/",
        ExamQuestionsV2View.as_view(),
        name="exam-questions",
    ),
    path(
        "exams/<uuid:exam_id>/results/",
        ExamResultsV2View.as_view(),
        name="exam-results",
    ),
    # Questions
    path("questions/", QuestionListCreateV2View.as_view(), name="question-list"),
    path(
        "questions/<int:question_id>/",
        QuestionDetailV2View.as_view(),
        name="question-detail",
    ),
    path(
        "questions/bulk-action/",
        QuestionBulkActionV2View.as_view(),
        name="question-bulk-action",
    ),
    # =============================================================================
    # SUBMISSIONS & SCORING
    # =============================================================================
    path("exams/<uuid:exam_id>/take-exam/", candidate_take_exam_V2, name="take-exam"),
    path(
        "exams/<uuid:exam_id>/face-capture/",
        ExamFaceCaptureView.as_view(),
        name="exam-face-capture",
    ),
    path(
        "exams/<uuid:exam_id>/time/",
        ExamTimeView.as_view(),
        name="exam-time",
    ),
    path(
        "exams/<uuid:exam_id>/heartbeat/",
        ExamHeartbeatView.as_view(),
        name="exam-heartbeat",
    ),
    path(
        "exams/<uuid:exam_id>/candidates/<uuid:candidate_id>/live-status/",
        CandidateLiveStatusV2View.as_view(),
        name="candidate-live-status",
    ),
    path(
        "exams/<uuid:exam_id>/candidates/<uuid:candidate_id>/integrity-audit/",
        IntegrityAuditView.as_view(),
        name="integrity-audit",
    ),
    path(
        "exams/<uuid:exam_id>/candidates/<uuid:candidate_id>/update-status/",
        UpdateProctoringStatusView.as_view(),
        name="update-proctoring-status",
    ),
    path(
        "exams/<uuid:exam_id>/submit/",
        SubmitAnswersV2View.as_view(),
        name="submit-exam",
    ),
    path(
        "exams/<uuid:exam_id>/auto-save/",
        AutoSaveAnswersV2View.as_view(),
        name="auto-save-answers",
    ),
    path(
        "exams/<uuid:exam_id>/saved-answers/",
        GetSavedAnswersV2View.as_view(),
        name="get-saved-answers",
    ),
    # =============================================================================
    # CANDIDATE MANAGEMENT
    # =============================================================================
    path(
        "candidates/<uuid:candidate_id>/exam-history/",
        ExamHistoryV2View.as_view(),
        name="candidate-exam-history",
    ),
]
