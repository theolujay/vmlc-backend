from rest_framework import serializers

from ..models import (
    Question,
)

from .staff import MinimalStaffSerializer


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions
    """

    class Meta:
        model = Question
        fields = ["id", "text", "difficulty", "date_created"]
        read_only_fields = ["id", "date_created"]


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
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
            "date_created",
            "created_by",
        ]
        read_only_fields = ["id", "date_created", "created_by"]


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
