from comms.views import SupportUsView
from .registration import RegistrationV2View, PreRegistrationView
from .exam import (
    ExamListV2View,
    ExamDetailV2View,
    ExamResultsV2View,
    ExamQuestionsV2View,
    ExamHistoryV2View,
    ExamFaceCaptureView,
    candidate_take_exam_V2,
)
from .question import (
    QuestionListCreateV2View,
    QuestionDetailV2View,
    QuestionBulkActionV2View,
)
from .answer import SubmitAnswersV2View

__all__ = [
    "RegistrationV2View",
    "PreRegistrationView",
    "SupportUsView",
    "ExamListV2View",
    "ExamDetailV2View",
    "ExamResultsV2View",
    "ExamQuestionsV2View",
    "ExamHistoryV2View",
    "ExamFaceCaptureView",
    "candidate_take_exam_V2",
    "QuestionListCreateV2View",
    "QuestionDetailV2View",
    "QuestionBulkActionV2View",
    "SubmitAnswersV2View",
]
