from rest_framework import serializers
from typing import List

from ..models import (
    Question,
)

from .staff import MinimalStaffSerializer


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
    """

    # created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model: Question = Question
        fields: List[str] = (
            "id",
            "text",
            # "option_a",
            # "option_b",
            # "option_c",
            # "option_d",
            # "correct_answer",
            "difficulty",
            "date_created",
            # "created_by",
        )
        read_only_fields: List[str] = ("id", "date_created", "created_by")


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
    """

    created_by: MinimalStaffSerializer = MinimalStaffSerializer(read_only=True)

    class Meta:
        model: Question = Question
        fields: List[str] = (
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
        )
        read_only_fields: List[str] = ("id", "date_created", "created_by")


class CandidateQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model: Question = Question
        fields: List[str] = (
            "id",
            "text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
        )
