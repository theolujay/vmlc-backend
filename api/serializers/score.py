from rest_framework import serializers
from typing import Any, List

from ..models import (
    Candidate,
    CandidateScore,
)

from .candidate import CandidateListSerializer
from .exam import ExamListSerializer


class CandidateScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate scores, including related candidate and exam info.
    """

    candidate: CandidateListSerializer = CandidateListSerializer(read_only=True)
    exam: ExamListSerializer = ExamListSerializer(read_only=True)

    class Meta:
        model: CandidateScore = CandidateScore
        fields: List[str] = ("id", "candidate", "exam", "score", "date_recorded")
        read_only_fields: List[str] = ("id", "date_created")


class SubmitScoreSerializer(serializers.Serializer):
    """
    Serializer for validating the submission of a candidate's score for an exam.
    """

    candidate_id: serializers.UUIDField = serializers.UUIDField(required=True)
    score: serializers.DecimalField = serializers.DecimalField(
        required=True, max_digits=5, decimal_places=2
    )

    def validate_candidate_id(self, value: Any) -> Any:
        if not Candidate.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                "A candidate with this ID does not exist."
            )
        return value

    class Meta:
        fields: List[str] = ["candidate_id", "score"]


class CandidateExamScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying an exam title and the score a candidate achieved.
    """

    exam: serializers.CharField = serializers.CharField(
        source="exam.title", read_only=True
    )

    class Meta:
        model: CandidateScore = CandidateScore
        fields: List[str] = ["exam", "score"]
