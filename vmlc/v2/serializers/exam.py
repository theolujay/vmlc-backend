
from django.db import transaction
from rest_framework import serializers

from vmlc.serializers.staff import MinimalStaffSerializer
from vmlc.models import (
    CandidateExamResult,
    Exam,
)
from vmlc.serializers.question import CandidateQuestionSerializer


class ExamListV2Serializer(serializers.ModelSerializer):

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "status",
            "question_count",
            "scheduled_date",
            "concluded_at",
            "created_at",
        ]

    question_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        return obj.title

    def get_question_count(self, obj):
        return getattr(obj, "question_count", obj.questions.count())

    def get_status(self, obj):
        return obj.status

    def get_competition_edition(self, obj):
        if not obj.competition_slot:
            return None
        return obj.competition_slot.competition_stage.competition.edition

class ExamDetailV2Serializer(serializers.ModelSerializer):

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "description",
            "status",
            "is_active",
            "is_currently_open",
            "competition_title",
            "stage",
            "questions",
            "open_duration_hours",
            "countdown_minutes",
            "scheduled_date",
            "concluded_at",
            "created_at",
            "created_by",
            "updated_by",
            "stage_id",
            "round",
            "standings",
        ]
        read_only_fields = [
            "id",
            "competition_title",
            "is_active",
            "created_at",
            "created_by",
            "updated_by",
            "status",
        ]

    created_by = MinimalStaffSerializer(read_only=True)
    updated_by = MinimalStaffSerializer(read_only=True)
    competition_title= serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    stage_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    round = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    stage = serializers.ReadOnlyField()
    standings = serializers.SerializerMethodField()

    def get_standings(self, obj):
        from competition.models import Standings
        standing = Standings.objects.filter(exam=obj).first()
        return {
            "exists": standing is not None,
            "is_published": standing.is_published if standing else False,
            "created_at": standing.created_at if standing else None,
            "published_at": standing.published_at if standing else None,
        }

    def get_title(self, obj):
        return obj.title

    def get_competition_title(self, obj):
        if not obj.competition_slot:
            return None
        return str(obj.competition_slot.competition_stage.competition)

    def validate(self, attrs):
        if self.instance:
            status = self.instance.status
            if status in [Exam.Status.CONCLUDED, Exam.Status.CANCELLED]:
                raise serializers.ValidationError(
                    f"Cannot update an exam that is {status}."
                )
            
            # For ONGOING exams, only allow certain fields if necessary, or block all
            if status == Exam.Status.ONGOING:
                allowed_ongoing_updates = ['is_active'] # Example: only allow cancellation
                if any(k for k in attrs if k not in allowed_ongoing_updates):
                     raise serializers.ValidationError(
                        "Cannot update core details of an ONGOING exam. You can only deactivate it."
                    )
        return attrs

    def create(self, validated_data):
        stage_id = validated_data.pop("stage_id", None)
        round = validated_data.pop("round", None)
        exam = super().create(validated_data)
        self._handle_competition_slot(exam, stage_id, round)
        return exam

    def update(self, instance, validated_data):
        stage_id = validated_data.pop("stage_id", None)
        round = validated_data.pop("round", None)
        instance = super().update(instance, validated_data)
        self._handle_competition_slot(instance, stage_id, round)
        return instance

    def _handle_competition_slot(self, exam, stage_id, round):
        from django.utils import timezone
        from competition.models import Competition, Stage, StageExam

        stage = None
        if stage_id:
            stage = Stage.objects.filter(id=stage_id).first()

        # If no stage provided but exam is scheduled, try to find current active stage
        if not stage and exam.scheduled_date and not exam.competition_slot:
            active_comp = Competition.objects.filter(status=Competition.Status.ACTIVE).first()
            if active_comp:
                # Place in Screening if no round, or current stage by order
                stage = active_comp.stages.order_by("order").first()

        if stage:
            # Ensure round is only set for League stage
            if stage.type != Stage.Type.LEAGUE:
                round = None

            with transaction.atomic():
                old_slot = exam.competition_slot
                new_slot = None

                if round is not None:
                    # Look for existing slot or create
                    new_slot, created = StageExam.objects.get_or_create(
                        competition_stage=stage, round=round
                    )
                    if not created and hasattr(new_slot, "exam") and new_slot.exam != exam:
                        raise serializers.ValidationError(
                            {"round": f"Round {round} in {stage.type} is already assigned to another exam."}
                        )
                else:
                    # For screening/final, reuse existing if same stage, else create/find new
                    if old_slot and old_slot.competition_stage == stage and old_slot.round is None:
                        new_slot = old_slot
                    else:
                        new_slot = StageExam.objects.create(
                            competition_stage=stage, round=None
                        )
                
                # Update is_active based on scheduled_date
                is_active = exam.scheduled_date is not None
                
                # If slot changed, clean up old slot
                if old_slot and old_slot != new_slot:
                    old_slot.is_active = False
                    old_slot.save(update_fields=["is_active"])

                # Update new slot
                if new_slot:
                    new_slot.is_active = is_active
                    new_slot.save(update_fields=["is_active"])
                    exam.competition_slot = new_slot

                exam.save(update_fields=["competition_slot"])



class CandidateTakeExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "description",
            "open_duration_hours",
            "scheduled_date",
            "countdown_minutes",
            "questions",
        ]

    questions = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        return obj.title

    def get_questions(self, obj):
        questions = obj.questions.filter(is_archived=False)
        return CandidateQuestionSerializer(
            questions, many=True, context=self.context
        ).data


class ExamResultV2Serializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school_name = serializers.CharField(source="candidate.school_name", read_only=True)

    class Meta:
        model = CandidateExamResult
        fields = [
            "candidate_name",
            "candidate_school_name",
            "score",
            "auto_score",
            "score_submitted_by",
            "recorded_at",
        ]
