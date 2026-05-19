from rest_framework import serializers

from ..models import CandidateAnswer, Question


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


class AutoSaveAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_option = serializers.CharField(required=False, allow_blank=True)

    def validate_question_id(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Invalid question_id.")
        return value

    def validate(self, attrs):
        question_id = attrs.get("question_id")
        try:
            question = Question.objects.get(pk=question_id)
            attrs["question"] = question
        except Question.DoesNotExist:
            raise serializers.ValidationError(
                f"Question {question_id} not found in this exam."
            )

        selected = attrs.get("selected_option", "").strip().upper()
        if selected:
            valid_options = [opt.value for opt in Question.Options]
            if selected not in valid_options:
                raise serializers.ValidationError(
                    f"'{selected}' is not a valid option for this question."
                )
        attrs["selected_option"] = selected
        return attrs


class AutoSaveAnswersBulkSerializer(serializers.Serializer):
    answers = AutoSaveAnswerSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("At least one answer must be provided.")
        return value
