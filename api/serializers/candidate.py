
from rest_framework import serializers

from ..models import (
    Candidate,
)

from .user import UserSerializer

class MinimalCandidateSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = ["user", "school"]


class CandidateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "user",
            "phone",
            "school",
            "role",
            # "profile_photo",
            # "is_verified",
            # "date_created",
        )


class CandidateDetailSerializer(serializers.ModelSerializer):
    """
    Detailed candidate serializer including:
    - latest score
    - all scores
    - total and average score
    """

    user = UserSerializer(read_only=True)
    scores = serializers.SerializerMethodField(
        help_text="Detailed score breakdown for the candidate."
    )

    class Meta:
        model = Candidate
        fields = (
            "user",
            "phone",
            "school",
            "profile_photo",
            "role",
            "is_verified",
            "is_active",
            "date_created",
            "date_updated",
            "scores",
        )
        read_only_fields = ("date_created", "date_updated", "user")

    def get_scores(self, obj: Candidate) -> dict:
        """
        Efficiently returns a dictionary of scores by leveraging the
        annotated and prefetched data from the model's `get_score_dict` method.
        """
        return obj.get_score_dict()

