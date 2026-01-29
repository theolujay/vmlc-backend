from rest_framework import serializers
from competition.models import Standings, StandingsEntry, AggregateLeaderboard, AggregateLeaderboardEntry

class PublishStandingsSerializer(serializers.Serializer):
    """
    Serializer for triggering the standings generation/publish process.
    """
    stage_exam_id = serializers.UUIDField(
        help_text="UUID of the StageExam to generate standings for."
    )
    publish_now = serializers.BooleanField(
        default=False,
        help_text="If True, immediately marks the generated standings as published."
    )


class StandingsEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for a single entry in the standings.
    """
    candidate_name = serializers.SerializerMethodField()
    candidate_email = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = StandingsEntry
        fields = [
            'candidate',
            'candidate_name',
            'candidate_email',
            'school_name',
            'exam_score',
            'rank',
            'percentile',
            'tie_break_reason',
        ]

    def get_candidate_name(self, obj):
        return obj.candidate.user.get_full_name()

    def get_candidate_email(self, obj):
        return obj.candidate.user.email

    def get_school_name(self, obj):
        return obj.candidate.school_name


class StandingsSerializer(serializers.ModelSerializer):
    """
    Serializer for the Standings model, including its entries.
    """
    entries = StandingsEntrySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = Standings
        fields = [
            'id',
            'competition',
            'stage',
            'stage_display',
            'round',
            'exam',
            'facilitator_system',
            'is_published',
            'published_at',
            'meta',
            'created_at',
            'entries',
        ]


class AggregateLeaderboardEntrySerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.user.get_full_name', read_only=True)
    candidate_email = serializers.CharField(source='candidate.user.email', read_only=True)
    school_name = serializers.CharField(source='candidate.school_name', read_only=True)
    rank_change = serializers.IntegerField(default=0, read_only=True)

    class Meta:
        model = AggregateLeaderboardEntry
        fields = [
            'candidate',
            'candidate_name',
            'candidate_email',
            'school_name',
            'total_score',
            'overall_rank',
            'rank_change',
        ]


class AggregateLeaderboardSerializer(serializers.ModelSerializer):
    entries = AggregateLeaderboardEntrySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = AggregateLeaderboard
        fields = [
            'id',
            'competition',
            'stage',
            'stage_display',
            'as_of_round',
            'created_at',
            'updated_at',
            'entries',
        ]
