from rest_framework import serializers
from vmlc.models import Question, Exam
from vmlc.serializers.staff import MinimalStaffSerializer

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

class QuestionV2Serializer(serializers.ModelSerializer):
    """
    Unified serializer for Question management in V2.
    """
    created_by = MinimalStaffSerializer(read_only=True)
    updated_by = MinimalStaffSerializer(read_only=True)
    related_exams = serializers.SerializerMethodField()
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
            "related_exams",
            "related_exams_count",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "created_by", "related_exams_count"]

    def get_related_exams(self, obj):
        # Only show related exams if explicitly requested in context
        if self.context.get('include_related_exams', False):
            exams = obj.exams.all().select_related("competition_slot__competition_stage__competition")
            return RelatedExamV2Serializer(exams, many=True).data
        return None

    def get_related_exams_count(self, obj):
        return obj.exams.count()

class QuestionBulkActionSerializer(serializers.Serializer):
    """
    Handles batch operations for questions.
    """
    question_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        allow_empty=False
    )
    exam_ids = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False
    )
    action = serializers.ChoiceField(
        choices=["archive", "assign", "unassign"], 
        required=True
    )
