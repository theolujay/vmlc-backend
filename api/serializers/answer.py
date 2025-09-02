from rest_framework import serializers
from typing import Any, List

from ..models import CandidateAnswer


class CandidateAnswerSerializer(serializers.ModelSerializer):
    """
    Represents a candidate's answer to a question.
    - If a question is unanswered, set 'selected_option' to an empty string "".
    """

    selected_option: serializers.CharField = serializers.CharField(
        required=False, allow_blank=True
    )

    class Meta:
        model: CandidateAnswer = CandidateAnswer
        fields: List[str] = ["question", "selected_option"]


class CandidateAnswerBulkSerializer(serializers.Serializer):
    answers: CandidateAnswerSerializer = CandidateAnswerSerializer(many=True)

    def validate_answers(self, value: List[Any]) -> List[Any]:
        if not value:
            raise serializers.ValidationError("At least one answer must be provided.")
        return value
