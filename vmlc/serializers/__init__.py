"""
This package contains all the serializers for the vmlc (exam-domain) API.
"""

from .answer import (
    CandidateAnswerSerializer,
    CandidateAnswerBulkSerializer,
    AutoSaveAnswerSerializer,
    AutoSaveAnswersBulkSerializer,
)
from .question import (
    QuestionListSerializer,
    QuestionDetailSerializer,
    CandidateQuestionSerializer,
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
