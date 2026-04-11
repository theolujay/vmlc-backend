from rest_framework import serializers


from ..models import CandidateAnswer


class CandidateAnswerSerializer(serializers.ModelSerializer):
    """
    Represents a candidate's answer to a question.
    - If a question is unanswered, set 'selected_option' to an empty string "".
    """

    selected_option = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = CandidateAnswer
        fields = ["question", "selected_option"]


class CandidateAnswerBulkSerializer(serializers.Serializer):
    is_auto_submit = serializers.BooleanField(required=False)
    answers = CandidateAnswerSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("At least one answer must be provided.")
        return value
