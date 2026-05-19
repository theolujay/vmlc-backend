from rest_framework import serializers

from identity.serializers.staff import MinimalStaffSerializer

from ..models import (
    Exam,
    Question,
)


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


class RelatedExamV2Serializer(serializers.ModelSerializer):
    competition_title = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "competition_title",
            "stage",
            "round",
            "scheduled_date",
            "status",
        ]

    def get_competition_title(self, obj):
        if obj.competition_slot:
            return str(obj.competition_slot.competition_stage.competition)
        return None


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
            "image",
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
            "image",
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


class QuestionV2Serializer(serializers.ModelSerializer):
    """
    Unified serializer for Question management in V2.
    """

    created_by = MinimalStaffSerializer(read_only=True)
    updated_by = MinimalStaffSerializer(read_only=True)
    related_exams = serializers.SerializerMethodField()
    related_exams_count = serializers.SerializerMethodField()
    exam_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

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
            "correct_answer",
            "difficulty",
            "related_exams",
            "related_exams_count",
            "exam_ids",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "created_by", "related_exams_count"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure exam_ids is populated in the response
        data["exam_ids"] = list(instance.exams.values_list("id", flat=True))
        return data

    def get_related_exams(self, obj):
        # Only show related exams if explicitly requested in context
        if self.context.get("include_related_exams", False):
            exams = obj.exams.all().select_related(
                "competition_slot__competition_stage__competition"
            )
            return RelatedExamV2Serializer(exams, many=True).data
        return None

    def get_related_exams_count(self, obj):
        return obj.exams.count()

    def validate_exam_ids(self, value):
        if not value:
            return value

        exams = Exam.objects.filter(id__in=value)
        invalid_exams = [
            exam.get_title()
            for exam in exams
            if exam.status not in [Exam.Status.DRAFT, Exam.Status.SCHEDULED]
        ]

        if invalid_exams:
            raise serializers.ValidationError(
                f"Cannot assign questions to exams that are not in Draft or Scheduled status: {', '.join(invalid_exams)}"
            )
        return value

    def create(self, validated_data):
        exam_ids = validated_data.pop("exam_ids", [])
        question = super().create(validated_data)

        if exam_ids:
            from core.utils.cache import invalidate_exam_cache, invalidate_question_pool

            exams = Exam.objects.filter(id__in=exam_ids)
            for exam in exams:
                # Skip if the question is already associated with this exam
                if not exam.questions.filter(id=question.id).exists():
                    exam.questions.add(question)

                    # Invalidate caches only for exams where the question was newly added
                    invalidate_exam_cache(exam.id)

            invalidate_question_pool()

        return question

    def update(self, instance, validated_data):
        exam_ids = validated_data.pop("exam_ids", None)
        question = super().update(instance, validated_data)

        if exam_ids is not None:
            from core.utils.cache import invalidate_exam_cache, invalidate_question_pool

            exams = Exam.objects.filter(id__in=exam_ids)

            for exam in exams:
                # Only add and invalidate cache if the question is not already in the exam
                if not exam.questions.filter(id=question.id).exists():
                    exam.questions.add(question)
                    invalidate_exam_cache(exam.id)

            invalidate_question_pool()

        return question


class QuestionBulkActionSerializer(serializers.Serializer):
    """
    Handles batch operations for questions.
    """

    question_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )
    exam_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    action = serializers.ChoiceField(
        choices=["archive", "assign", "unassign"], required=True
    )
