from django.db import transaction
from rest_framework import serializers

from identity.serializers.staff import MinimalStaffSerializer
from vmlc.models import (
    CandidateExamResult,
    Exam,
    ExamAccess,
)
from vmlc.serializers.question import CandidateQuestionSerializer, QuestionV2Serializer


class ExamListV2Serializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "status",
            "delivery_mode",
            "question_count",
            "scheduled_date",
            "concluded_at",
            "created_at",
        ]

    # competition_title = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    def get_stage(self, obj):
        if not obj.competition_slot:
            return None
        return obj.competition_slot.competition_stage.type

    def get_title(self, obj):
        return obj.title

    def get_question_count(self, obj):
        return getattr(obj, "question_count", obj.questions.count())

    def get_status(self, obj):
        return obj.status

    def get_competition_title(self, obj):
        if not obj.competition_slot:
            return None
        return obj.competition_slot.competition_stage.competition.get_title()

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
            "ranking",
        ]
        read_only_fields = [
            "id",
            "competition_title",
            "is_active",
            "created_at",
            "created_by",
            "updated_by",
        ]

    questions = QuestionV2Serializer(many=True, read_only=True)
    created_by = MinimalStaffSerializer(read_only=True)
    updated_by = MinimalStaffSerializer(read_only=True)
    competition_title = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    stage_id = serializers.IntegerField(required=False, allow_null=True)
    round = serializers.IntegerField(required=False, allow_null=True)
    stage = serializers.ReadOnlyField()
    ranking = serializers.SerializerMethodField()

    def get_ranking(self, obj):
        from competition.models import RankingSnapshot

        ranking = RankingSnapshot.objects.filter(exam=obj, is_active=True).first()
        return {
            "exists": ranking is not None,
            "is_published": ranking.is_published if ranking else False,
            "created_at": ranking.created_at if ranking else None,
            "published_at": ranking.published_at if ranking else None,
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

            # Handle retraction
            if attrs.get("status") == Exam.Status.DRAFT:
                if status != Exam.Status.SCHEDULED:
                    raise serializers.ValidationError(
                        f"Cannot retract an exam that is {status}. Only SCHEDULED exams can be retracted."
                    )
                return attrs

            if status != Exam.Status.DRAFT:
                raise serializers.ValidationError(
                    f"Cannot update an exam that is {status}. It must be in DRAFT status."
                )

        return attrs

    def create(self, validated_data):
        stage_id = validated_data.pop("stage_id", None)
        round = validated_data.pop("round", None)
        exam = super().create(validated_data)
        self._handle_competition_slot(exam, stage_id, round)

        # This is almost never reached, as a new exam (from the portal) leaves scheduled_date
        # and countdown_timer null.
        # if exam.status == Exam.Status.SCHEDULED:
        #     from vmlc.tasks import generate_and_send_exam_passcodes_task
        #     transaction.on_commit(
        #         lambda: generate_and_send_exam_passcodes_task.delay(exam.id)
        #     )

        return exam

    def update(self, instance, validated_data):
        # Handle retraction logic
        if validated_data.get("status") == Exam.Status.DRAFT:
            validated_data["scheduled_date"] = None
            validated_data["countdown_minutes"] = None

        stage_id = validated_data.pop("stage_id", None)
        round = validated_data.pop("round", None)

        instance = super().update(instance, validated_data)
        self._handle_competition_slot(instance, stage_id, round)

        return instance

    def _handle_competition_slot(self, exam, stage_id, round):
        from competition.models import Competition, Stage, StageExam

        stage = None
        if stage_id:
            stage = Stage.objects.filter(id=stage_id).first()

        # If no stage provided but exam is scheduled, try to find current active stage
        if not stage and exam.scheduled_date and not exam.competition_slot:
            active_comp = Competition.objects.filter(
                status=Competition.Status.ACTIVE
            ).first()
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
                    if (
                        not created
                        and hasattr(new_slot, "exam")
                        and new_slot.exam != exam
                    ):
                        raise serializers.ValidationError(
                            {
                                "round": f"Round {round} in {stage.type} is already assigned to another exam."
                            }
                        )
                else:
                    # For screening/final, reuse existing if same stage, else create/find new
                    if (
                        old_slot
                        and old_slot.competition_stage == stage
                        and old_slot.round is None
                    ):
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
            "attempt",
            "open_duration_hours",
            "scheduled_date",
            "countdown_minutes",
            "questions",
        ]

    questions = (
        serializers.SerializerMethodField()
    )  # TODO: implement question randomizer
    title = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()

    def get_title(self, obj):
        return obj.title

    def get_questions(self, obj):
        questions = obj.questions.filter(is_archived=False)
        return CandidateQuestionSerializer(
            questions, many=True, context=self.context
        ).data

    def get_attempt(self, obj):
        request = self.context.get("request")
        if not request or not hasattr(request.user, "candidate_profile"):
            return None

        exam_access = ExamAccess.objects.filter(
            exam=obj, candidate=request.user.candidate_profile
        ).first()

        if exam_access:
            return {
                "started_at": exam_access.started_at,
                "deadline": exam_access.deadline,
                "submitted_at": exam_access.submitted_at,
                "is_unlocked": exam_access.is_unlocked,
            }
        return None


class ExamResultV2Serializer(serializers.ModelSerializer):
    """
    Serializer for displaying the results of an exam.
    """

    candidate_name = serializers.CharField(
        source="candidate.user.get_full_name", read_only=True
    )
    candidate_school_name = serializers.CharField(
        source="candidate.school_name", read_only=True
    )

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


class ExamFaceCaptureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAccess
        fields = ["face_capture"]

    def validate_face_capture(self, value):
        if not value:
            raise serializers.ValidationError("Face capture image is required.")
        from identity.validators import validate_image

        validate_image(value)
        return value
