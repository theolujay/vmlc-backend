
from rest_framework import serializers

from ..models import (
    Question,
)

from .user import MinimalStaffSerializer


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
    """

    # created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model = Question
        fields = (
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
        read_only_fields = ("id", "date_created", "created_by")


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for exam questions with created_by staff included.
    """

    created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model = Question
        fields = (
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
        read_only_fields = ("id", "date_created", "created_by")



from rest_framework import serializers

from ..models import (
    Question,
)


class CandidateQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = (
            "id",
            "text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
        )
