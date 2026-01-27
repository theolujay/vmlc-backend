from django.db.models import Avg

from rest_framework import serializers

from ..models import (
    CandidateExamResult,
    Question,
    Exam,
)

from .question import CandidateQuestionSerializer
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
            "is_currently_open",
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
            obj, "average_score", obj.results.aggregate(avg=Avg("score"))["avg"]
        )
        return float(avg or 0.0)

    def get_status(self, obj):
        return obj.status

    def get_stage_display(self, obj):
        return obj.stage_display

    def get_is_currently_open(self, obj):
        return obj.is_currently_open


class CandidateExamSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()

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

    def get_questions(self, obj):
        questions = obj.questions.filter(is_archived=False)
        return CandidateQuestionSerializer(
            questions, many=True, context=self.context
        ).data


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
            "candidate_name",
            "candidate_school_name",
            "score",
            "auto_score",
            "score_submitted_by",
            "recorded_at",
        ]
