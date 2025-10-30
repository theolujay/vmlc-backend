from rest_framework import serializers

from ..models import (
    Question,
)

from .staff import MinimalStaffSerializer


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions
    """
    
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
            "created_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "created_by", "created_at"]

    def get_related_exams_count(self, obj):
        return obj.get_related_exams()["count"]

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
        read_only_fields = ["id", "related_exams", "related_exams_count", "created_at", "created_by"]

    def get_related_exams(self, obj):
        return obj.get_related_exams()
    def get_related_exams_count(self, obj):
        return obj.get_related_exams()["count"]


class CandidateQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
        ]
