from rest_framework import serializers

from ..models import (
    Question,
    Exam,
)

from .staff import MinimalStaffSerializer


class RelatedExamSerializer(serializers.ModelSerializer):
    """
    Serializer for exams related to a question.
    """

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "description",
            "stage",
            "scheduled_date",
        ]


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions
    """

    created_by = MinimalStaffSerializer(read_only=True)
    related_exams_count = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "difficulty",
            "related_exams_count",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "created_by", "related_exams_count"]

    def get_related_exams_count(self, obj):
        return obj.exams.count()


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
    """

    related_exams = serializers.SerializerMethodField()
    related_exams_count = serializers.SerializerMethodField()
    created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "difficulty",
            "related_exams",
            "related_exams_count",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "related_exams",
            "related_exams_count",
            "created_at",
            "created_by",
        ]

    def get_related_exams(self, obj):
        exams = obj.exams.all().select_related("competition_slot__competition_stage")
        return RelatedExamSerializer(exams, many=True).data

    def get_related_exams_count(self, obj):
        return obj.exams.count()


class CandidateQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "image",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
        ]
