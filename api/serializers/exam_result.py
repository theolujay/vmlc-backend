from rest_framework import serializers
from typing import List

from ..models import CandidateScore


class ExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name: serializers.CharField = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school: serializers.CharField = serializers.CharField(
        source="candidate.school", read_only=True
    )

    class Meta:
        model: CandidateScore = CandidateScore
        fields: List[str] = (
            "candidate_name",
            "candidate_school",
            "score",
            "date_recorded",
        )
