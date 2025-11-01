from django.db.models import Avg, Count, Q

from rest_framework import serializers

from ..models import (
    CandidateScore,
    Question,
    Exam,
)

from .question import CandidateQuestionSerializer, QuestionDetailSerializer
from .staff import MinimalStaffSerializer


class ExamListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing exams with question count and creator.
    """

    question_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    stage_display = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "stage",
            "level",
            "stage_display",
            "created_at",
            "question_count",
            "scheduled_date",
            "status",
            "concluded_at",
        ]

    def get_question_count(self, obj):
        """
        Returns the number of questions, using annotated value if available.
        """
        return getattr(obj, "question_count", obj.questions.count())

    def get_status(self, obj):
        return obj.status
    
    def get_stage_display(self, obj):
        return obj.stage_display

class ExamDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single exam, including:
    - question list
    - average score
    """

    questions = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), many=True, required=False
    )
    created_by = MinimalStaffSerializer(read_only=True)
    average_score = serializers.SerializerMethodField(
        help_text="Average score of all submissions for this exam."
    )

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "stage",
            "level",
            "stage_display",
            "description",
            "created_at",
            "created_by",
            "updated_by",
            "open_duration_hours",
            "countdown_minutes",
            "scheduled_date",
            "is_active",
            "status",
            "concluded_at",
            "questions",
            "average_score",
            
        ]
        read_only_fields = ["id", "created_at", "created_by", "status"]

    def get_average_score(self, obj):
        """
        Returns average score, using annotated value if available.
        """
        avg = getattr(
            obj, "average_score", obj.scores.aggregate(avg=Avg("score"))["avg"]
        )
        return float(avg or 0.0)

    def get_status(self, obj):
        return obj.status

    def get_stage_display(self, obj):
        return obj.stage_display

    def to_representation(self, instance):
        """
        Customize the exam representation to include a nested structure
        for questions with metadata.
        """
        representation = super().to_representation(instance)
        questions_queryset = instance.questions.all()

        pool = questions_queryset.aggregate(
            total_count=Count(
                "id",
                filter=Q(is_archived=False),
            ),
            hard_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.HARD) & Q(is_archived=False)
            ),
            medium_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.MODERATE) & Q(is_archived=False)
            ),
            easy_questions_count=Count(
                "id", filter=Q(difficulty=Question.Difficulty.EASY) & Q(is_archived=False)
            ),
        )

        representation["questions"] = {
            "pool": pool,
            "list": QuestionDetailSerializer(
                questions_queryset, many=True, context=self.context
            ).data,
        }
        return representation


class CandidateExamSerializer(serializers.ModelSerializer):
    questions = CandidateQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "stage",
            "description",
            "open_duration_hours",
            "scheduled_date",
            "countdown_minutes",
            "questions",
        ]


class ExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school = serializers.CharField(source="candidate.school", read_only=True)

    class Meta:
        model = CandidateScore
        fields = [
            "candidate_name",
            "candidate_school",
            "score",
            "auto_score",
            "score_submitted_by",
            "recorded_at",
        ]
