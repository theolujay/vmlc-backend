from django.urls import path

from vmlc.v2.views.exam import ExamRetractV2View
from .views import (
    RegistrationV2View,
    PreRegistrationView,
    SupportUsView,
    ExamListV2View,
    ExamDetailV2View,
    ExamResultsV2View,
    ExamQuestionsV2View,
    ExamHistoryV2View,
    candidate_take_exam_V2,
    QuestionListCreateV2View,
    QuestionDetailV2View,
    QuestionBulkActionV2View,
    SubmitAnswersV2View,
)
from vmlc.views.status import registration_status

app_name = "vmlc-v2"

urlpatterns = [
    path("register/", RegistrationV2View.as_view(), name="register"),
    path("pre-register/", PreRegistrationView.as_view(), name="pre-register"),
    path("support-us/", SupportUsView.as_view(), name="support-us"),
    path("registration/", registration_status, name="registration-status"),
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
        "exams/<uuid:exam_id>/submit/",
        SubmitAnswersV2View.as_view(),
        name="submit-exam",
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
