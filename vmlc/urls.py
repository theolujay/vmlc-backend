"""
URL configuration for the v1 API endpoints.
"""

from django.urls import path

from .views import (
    ExamDetailV2View,
    ExamFaceCaptureView,
    ExamHistoryV2View,
    ExamListV2View,
    ExamQuestionsV2View,
    ExamResultsV2View,
    ExamRetractV2View,
    ExamTimeView,
    candidate_take_exam_V2,
)
from .views.answer import (
    AutoSaveAnswersV2View,
    GetSavedAnswersV2View,
    SubmitAnswersV2View,
)
from .views.proctoring import (
    CandidateLiveStatusV2View,
    ExamHeartbeatView,
    IntegrityAuditView,
    UpdateProctoringStatusView,
)
from .views.question import (
    QuestionBulkActionV2View,
    QuestionDetailV2View,
    QuestionListCreateV2View,
)

app_name = "vmlc"

urlpatterns = [
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
