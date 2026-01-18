from rest_framework import serializers

from ..models import CandidateScore


class ExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school_name = serializers.CharField(source="candidate.school_name", read_only=True)

    class Meta:
        model = CandidateScore
        fields = [
            # "id",
            "candidate_name",
            "candidate_school_name",
            "score",
            "recorded_at",
        ]
