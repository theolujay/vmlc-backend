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
]