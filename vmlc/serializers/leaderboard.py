from rest_framework import serializers
from vmlc.models import Exam, LeaderboardSnapshot


class LeaderboardSnapshotListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing leaderboard snapshots.
    """

    exam_title = serializers.CharField(source="exam.title", read_only=True)
    exam_stage = serializers.CharField(source="exam.stage", read_only=True)

    class Meta:
        model = LeaderboardSnapshot
        fields = ["exam_id", "exam_title", "exam_stage", "created_at", "data"]


class PublishLeaderboardSerializer(serializers.Serializer):
    exam_id = serializers.UUIDField()

    def validate_exam_id(self, value):
        try:
            exam = Exam.objects.get(pk=value)
        except Exam.DoesNotExist:
            raise serializers.ValidationError("Exam not found.")

        if exam.status != Exam.Status.CONCLUDED:
            raise serializers.ValidationError(
                "Leaderboard can only be published for concluded exams."
            )

        return value


class CandidateLeaderboardPerfSerializer(serializers.Serializer):
    """
    Serializer for candidate performance data on the leaderboard.
    """

    id = serializers.UUIDField(source="user.id")
    full_name = serializers.CharField(source="user.get_full_name")
    school = serializers.CharField()
