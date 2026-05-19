"""
This package contains all the views for the vmlc (exam-domain) API.
"""

from .answer import (
    AutoSaveAnswersV2View,
    GetSavedAnswersV2View,
    SubmitAnswersV2View,
)
from .exam import (
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
from .proctoring import (
    CandidateLiveStatusV2View,
    ExamHeartbeatView,
    IntegrityAuditView,
    UpdateProctoringStatusView,
)
from .question import (
    QuestionBulkActionV2View,
    QuestionDetailV2View,
    QuestionListCreateV2View,
)

__all__ = [
    "SubmitAnswersV2View",
    "AutoSaveAnswersV2View",
    "GetSavedAnswersV2View",
    "ExamRetractV2View",
    "ExamTimeView",
    "ExamListV2View",
    "ExamDetailV2View",
    "ExamResultsV2View",
    "ExamQuestionsV2View",
    "ExamHistoryV2View",
    "ExamFaceCaptureView",
    "candidate_take_exam_V2",
    "CandidateLiveStatusV2View",
    "ExamHeartbeatView",
    "IntegrityAuditView",
    "UpdateProctoringStatusView",
    "QuestionListCreateV2View",
    "QuestionDetailV2View",
    "QuestionBulkActionV2View",
]
