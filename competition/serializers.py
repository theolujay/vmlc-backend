from rest_framework import serializers
from competition.models import RankingSnapshot, RankingSnapshotEntry, LeagueLeaderboard, LeagueLeaderboardEntry
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
        help_text="If True, immediately marks the generated ranking snapshot as published."
    )


class RankingSnapshotEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for a single entry in the ranking snapshot.
    """
    candidate_name = serializers.SerializerMethodField()
    candidate_email = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = RankingSnapshotEntry
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


class RankingSnapshotSerializer(serializers.ModelSerializer):
    """
    Serializer for the RankingSnapshot model, including its entries.
    """
    entries = RankingSnapshotEntrySerializer(many=True, read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = RankingSnapshot
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


class CandidateAnswerDetailSerializer(serializers.ModelSerializer):
    question = QuestionListSerializer(read_only=True)
    selected_option = serializers.SerializerMethodField()

    class Meta:
        model = CandidateAnswer
        fields = ['question', 'selected_option', 'answered_at']

    def get_selected_option(self, obj):
        if obj.selected_option:
            return obj.selected_option.strip().upper()
        return obj.selected_option


class CandidateResultDetailSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.user.get_full_name', read_only=True)
    candidate_email = serializers.CharField(source='candidate.user.email', read_only=True)
    school_name = serializers.CharField(source='candidate.school_name', read_only=True)
    submissions = CandidateAnswerDetailSerializer(source='answers', many=True, read_only=True)
    rank = serializers.IntegerField(read_only=True)
    percentile = serializers.FloatField(read_only=True)

    class Meta:
        model = CandidateExamResult
        fields = [
            'candidate',
            'candidate_name',
            'candidate_email',
            'school_name',
            'score',
            'rank',
            'percentile',
            'recorded_at',
            'auto_score',
            'submissions'
        ]


class LeagueLeaderboardEntrySerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.user.get_full_name', read_only=True)
    candidate_email = serializers.CharField(source='candidate.user.email', read_only=True)
    school_name = serializers.CharField(source='candidate.school_name', read_only=True)
    state = serializers.CharField(source='candidate.state', read_only=True)
    rank_change = serializers.IntegerField(default=0, read_only=True)

    class Meta:
        model = LeagueLeaderboardEntry
        fields = [
            'candidate',
            'candidate_name',
            'candidate_email',
            'school_name',
            'state',
            'total_score',
            'overall_rank',
            'rank_change',
        ]


class LeagueLeaderboardSerializer(serializers.ModelSerializer):


    entries = LeagueLeaderboardEntrySerializer(many=True, read_only=True)


    stage_display = serializers.CharField(source='get_stage_display', read_only=True)





    class Meta:





        model = LeagueLeaderboard


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








class CompetitionDashboardExamSerializer(serializers.Serializer):


    id = serializers.UUIDField()


    title = serializers.CharField()


    stage = serializers.CharField()


    status = serializers.CharField()


    ranking_snapshot_status = serializers.CharField()


    stats = serializers.DictField()








class CompetitionDashboardSerializer(serializers.Serializer):


    stats = serializers.DictField()


    progress = serializers.DictField()


    exams = CompetitionDashboardExamSerializer(many=True)


    leaderboard_summary = serializers.ListField()


    latest_ranking_snapshot_summary = serializers.DictField(allow_null=True)








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










