from .registration import RegistrationV2View, PreRegistrationView
from .support import SupportUsView
from .exam import (
    ExamListV2View,
    ExamDetailV2View,
    ExamResultsV2View,
    ExamQuestionsV2View,
    ExamHistoryV2View,
    candidate_take_exam_V2,
)
from .question import (
    QuestionListCreateV2View,
    QuestionDetailV2View,
    QuestionBulkActionV2View,
)

__all__ = [
    "RegistrationV2View",
    "PreRegistrationView",
    "SupportUsView",
    "ExamListV2View",
    "ExamDetailV2View",
    "ExamResultsV2View",
    "ExamQuestionsV2View",
    "ExamHistoryV2View",
    "candidate_take_exam_V2",
    "QuestionListCreateV2View",
    "QuestionDetailV2View",
    "QuestionBulkActionV2View",
]