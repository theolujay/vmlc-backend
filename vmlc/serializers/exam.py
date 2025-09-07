from django.db.models import Avg

from rest_framework import serializers

from ..models import (
    CandidateScore,
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

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "stage",
            "question_count",
            "date_created",
        ]

    def get_question_count(self, obj):
        """
        Returns the number of questions, using annotated value if available.
        """
        return getattr(obj, "question_count", obj.questions.count())


class ExamDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single exam, including:
    - question list
    - average score
    """

    questions = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), many=True
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
            "description",
            "exam_date",
            "countdown_minutes",
            "open_duration_hours",
            "is_active",
            "questions",
            "created_by",
            "updated_by",
            "average_score",
            "date_created",
        ]
        read_only_fields = ["id", "date_created", "created_by"]

    def get_average_score(self, obj):
        """
        Returns average score, using annotated value if available.
        """
        avg = getattr(
            obj, "average_score", obj.scores.aggregate(avg=Avg("score"))["avg"]
        )
        return float(avg or 0.0)


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
            "exam_date",
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
            "submitted_by",
            "date_recorded",
        ]
