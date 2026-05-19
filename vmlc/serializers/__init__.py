"""
This package contains all the serializers for the vmlc (exam-domain) API.
"""

from .answer import (
    AutoSaveAnswersBulkSerializer,
    AutoSaveAnswerSerializer,
    CandidateAnswerBulkSerializer,
    CandidateAnswerSerializer,
)
from .question import (
    CandidateQuestionSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
)

__all__ = [
    "CandidateAnswerSerializer",
    "CandidateAnswerBulkSerializer",
    "AutoSaveAnswerSerializer",
    "AutoSaveAnswersBulkSerializer",
    "QuestionListSerializer",
    "QuestionDetailSerializer",
    "CandidateQuestionSerializer",
]
