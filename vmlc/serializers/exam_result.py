from rest_framework import serializers

from ..models import (
    Candidate,
    CandidateExamResult,
)

from .candidate import CandidateListSerializer
from .exam import ExamListSerializer
class ExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school_name = serializers.CharField(source="candidate.school_name", read_only=True)

    class Meta:
        model = CandidateExamResult
        fields = [
            # "id",
            "candidate_name",
            "candidate_school_name",
            "score",
            "recorded_at",
        ]


class CandidateExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate scores, including related candidate and exam info.
    """

    candidate = CandidateListSerializer(read_only=True)
    exam = ExamListSerializer(read_only=True)

    class Meta:
        model = CandidateExamResult
        fields = ["id", "candidate", "exam", "score", "recorded_at"]
        read_only_fields = ["id", "created_at"]


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
        model = CandidateExamResult
        fields = ["exam", "score"]
