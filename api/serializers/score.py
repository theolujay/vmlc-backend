from rest_framework import serializers

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

    candidate = CandidateListSerializer(read_only=True)
    exam = ExamListSerializer(read_only=True)

    class Meta:
        model = CandidateScore
        fields = ("id", "candidate", "exam", "score", "date_recorded")
        read_only_fields = ("id", "date_created")


class SubmitScoreSerializer(serializers.Serializer):
    """
    Serializer for validating the submission of a candidate's score for an exam.
    """

    candidate_id = serializers.UUIDField(required=True)
    score = serializers.DecimalField(required=True, max_digits=5, decimal_places=2)

    def validate_candidate_id(self, value):
        if not Candidate.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                "A candidate with this ID does not exist."
            )
        return value

    class Meta:
        fields = ["candidate_id", "score"]


class CandidateExamScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying an exam title and the score a candidate achieved.
    """

    exam = serializers.CharField(source="exam.title", read_only=True)

    class Meta:
        model = CandidateScore
        fields = ["exam", "score"]
