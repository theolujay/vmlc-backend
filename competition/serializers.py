from rest_framework import serializers
from competition.models import (
    RankingSnapshot,
    RankingSnapshotEntry,
    LeagueLeaderboard,
    LeagueLeaderboardEntry,
)
from vmlc.serializers.question import QuestionListSerializer
from vmlc.models import CandidateAnswer, CandidateExamResult, Exam


class PublishRankingSnapshotSerializer(serializers.Serializer):
    """
    Serializer for triggering the ranking snapshots generation/publish process.
    """

    exam_id = serializers.UUIDField(
        help_text="UUID of the Exam to generate ranking snapshot for."
    )
    publish_now = serializers.BooleanField(
        default=False,
        help_text="If True, immediately marks the generated ranking snapshot as published.",
    )


class RankingSnapshotEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for a single entry in the ranking snapshot.
    """

    candidate_info = serializers.SerializerMethodField()
    exam_score = serializers.SerializerMethodField()

    class Meta:
        model = RankingSnapshotEntry
        fields = [
            "candidate",
            "candidate_info",
            "exam_score",
            "rank",
            "percentile",
            "tie_break_reason",
        ]

    def get_candidate_info(self, obj):
        return {
            "id": obj.candidate.pk,
            "full_name": obj.candidate.user.get_full_name(),
            "email": obj.candidate.user.email,
            "state": obj.candidate.user.state,
            "school_name": obj.candidate.school_name,
            "school_type": obj.candidate.school_type,
            "current_class": obj.candidate.current_class
        }

    def get_exam_score(self, obj):
        if obj.exam_score is None:
            return "absent"
        return obj.exam_score


class RankingSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer for the RankingSnapshot model, including its entries.
    """

    entries = RankingSnapshotEntrySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = RankingSnapshot
        fields = [
            "id",
            "competition",
            "stage",
            "stage_display",
            "round",
            "exam",
            "facilitator_system",
            "is_published",
            "published_at",
            "meta",
            "created_at",
            "entries",
        ]


class CandidateAnswerDetailSerializer(serializers.ModelSerializer):
    question = QuestionListSerializer(read_only=True)
    selected_option = serializers.SerializerMethodField()

    class Meta:
        model = CandidateAnswer
        fields = ["question", "selected_option", "answered_at"]

    def get_selected_option(self, obj):
        if obj.selected_option:
            return obj.selected_option.strip().upper()
        return obj.selected_option


class CandidateResultDetailSerializer(serializers.ModelSerializer):
    submissions = CandidateAnswerDetailSerializer(
        source="answers", many=True, read_only=True
    )
    rank = serializers.IntegerField(read_only=True)
    percentile = serializers.FloatField(read_only=True)

    class Meta:
        model = CandidateExamResult
        fields = [
            "score",
            "rank",
            "percentile",
            "recorded_at",
            "auto_score",
            "submissions",
        ]


class LeagueLeaderboardEntrySerializer(serializers.ModelSerializer):
    candidate_info = serializers.SerializerMethodField()
    rank_change = serializers.IntegerField(default=0, read_only=True)

    class Meta:
        model = LeagueLeaderboardEntry
        fields = [
            "candidate",
            "candidate_info",
            "total_score",
            "overall_rank",
            "rank_change",
        ]

    def get_candidate_info(self, obj):
        candidate = obj.candidate
        return {
            "id": candidate.pk,
            "full_name": candidate.user.get_full_name(),
            "email": candidate.user.email,
            "state": candidate.user.state,
            "school_name": candidate.school_name,
            "school_type": candidate.school_type,
            "current_class": candidate.current_class,
        }


class LeagueLeaderboardSerializer(serializers.ModelSerializer):
    entries = LeagueLeaderboardEntrySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = LeagueLeaderboard
        fields = [
            "id",
            "competition",
            "stage",
            "stage_display",
            "as_of_round",
            "created_at",
            "updated_at",
            "entries",
        ]


class CompetitionDashboardExamSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    stage = serializers.CharField()
    status = serializers.CharField()
    ranking_status = serializers.CharField()
    stats = serializers.DictField()


class CompetitionDashboardSerializer(serializers.Serializer):
    stats = serializers.DictField()
    progress = serializers.DictField()
    exams = CompetitionDashboardExamSerializer(many=True)
    leaderboard_summary = serializers.ListField()
    latest_ranking_summary = serializers.DictField(allow_null=True)


class CandidateRankingSnapshotDetailSerializer(serializers.Serializer):
    exam_details = serializers.DictField()
    candidate_performance = serializers.DictField()


class PromoteCandidatesSerializer(serializers.Serializer):
    """
    Serializer for promoting candidates from one stage to another.
    """

    from_stage = serializers.ChoiceField(choices=["screening", "league"])
    to_stage = serializers.ChoiceField(choices=["league", "final"])
    cutoff_rank = serializers.IntegerField(required=False, min_value=1)
    competition_id = serializers.IntegerField(required=False)
