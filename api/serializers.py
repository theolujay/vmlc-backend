"""
Serializers for converting model instances to and from JSON representations.

Includes:
- User, Candidate, and Staff serializers
- Exam and Question serializers
- CandidateScore and registration serializers
"""

from django.db.models import Avg, Count, Sum
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import (
    Candidate,
    Staff,
    Question,
    Exam,
    CandidateScore,
    CandidateAnswer,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for the Django User model.
    """

    username = serializers.CharField(
        max_length=14, validators=[UniqueValidator(queryset=User.objects.all())]
    )
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")


class MinimalCandidateSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = ["user", "school"]


class CandidateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing candidate info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "user",
            "phone",
            "school",
            "role",
            # "profile_photo",
            # "is_verified",
            # "date_created",
        )


class CandidateDetailSerializer(serializers.ModelSerializer):
    """
    Detailed candidate serializer including:
    - latest score
    - all scores
    - total and average score
    """
    user = UserSerializer(read_only=True)
    scores = serializers.SerializerMethodField(help_text="Detailed score breakdown for the candidate.")

    class Meta:
        model = Candidate
        fields = (
            "user",
            "phone",
            "school",
            "profile_photo",
            "role",
            "is_verified",
            "is_active",
            "date_created",
            "date_updated",
            "scores",
        )
        read_only_fields = ("date_created", "date_updated", "user")

    def get_scores(self, obj: Candidate) -> dict:
        """
        Efficiently returns a dictionary of scores by leveraging the
        annotated and prefetched data from the model's `get_score_dict` method.
        """
        return obj.get_score_dict()


class MinimalStaffSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for listing staff info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = ["user"]


class StaffListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing staff info.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = (
            "user",
            "role",
            # "profile_photo",
            "occupation",
            # "is_verified",
            # "date_created"
        )


class StaffDetailSerializer(serializers.ModelSerializer):
    """
    Detailed staff serializer.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = (
            "user",
            "phone",
            "occupation",
            "profile_photo",
            "role",
            "is_verified",
            "is_active",
            "date_created",
            "date_updated",
        )
        read_only_fields = ("date_created", "date_updated", "user")

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


class ExamListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing exams with question count and creator.
    """

    question_count = serializers.SerializerMethodField()
    # created_by = MinimalStaffSerializer(read_only=True)

    class Meta:
        model = Exam
        fields = (
            "id",
            "title",
            "stage",
            # "description",
            "exam_date",
            # "countdown_minutes",
            # "open_duration_hours",
            # "is_active",
            # "is_currently_open",
            "question_count",
            # "created_by",
            "date_created",
        )

    def get_question_count(self, obj: Exam) -> int:
        """
        Returns the number of questions, using annotated value if available.
        """
        return getattr(obj, "question_count", obj.questions.count())


class ExamDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single exam, including:
    - question list
    - average score
    """

    questions = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), many=True
    )
    created_by = MinimalStaffSerializer(read_only=True)
    average_score = serializers.SerializerMethodField(
        help_text="Average score of all submissions for this exam."
    )

    class Meta:
        model = Exam
        fields = (
            "id",
            "title",
            "stage",
            "description",
            "exam_date",
            "countdown_minutes",
            "open_duration_hours",
            "is_active",
            "questions",
            "created_by",
            "updated_by",
            "average_score",
            "date_created",
        )
        read_only_fields = ("id", "date_created", "created_by")

    def get_average_score(self, obj: Exam) -> float:
        """
        Returns average score, using annotated value if available.
        """
        avg = getattr(obj, "average_score", obj.scores.aggregate(avg=Avg("score"))["avg"])
        return float(avg or 0.0)


class CandidateScoreSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate scores, including related candidate and exam info.
    """

    candidate = CandidateListSerializer(read_only=True)
    exam = ExamListSerializer(read_only=True)

    class Meta:
        model = CandidateScore
        fields = ("id", "candidate", "exam", "score", "date_recorded")
        read_only_fields = ("id", "date_created")


class SubmitScoreSerializer(serializers.Serializer):
    """
    Serializer for validating the submission of a candidate's score for an exam.
    """

    candidate_id = serializers.IntegerField(required=True)
    score = serializers.DecimalField(required=True, max_digits=5, decimal_places=2)

    def validate_candidate_id(self, value):
        if not Candidate.objects.filter(pk=value).exists():
            raise serializers.ValidationError("A candidate with this ID does not exist.")
        return value

    class Meta:
        fields = ["candidate_id", "score"]


class BaseRegistrationSerializer(serializers.ModelSerializer):
    """
    Abstract base serializer for user registration.
    Handles common user creation and password validation logic.
    """
    user = UserSerializer()
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[password_validation.validate_password],
        style={"input_type": "password"},
        help_text="Required. 8 characters minimum.",
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Confirm password",
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create_user(self, user_data, password):
        return User.objects.create_user(
            username=user_data["username"],
            email=user_data["email"],
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            password=password,
        )


class CandidateRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new candidates (creates User and Candidate).
    """

    class Meta:
        model = Candidate
        fields = ("user", "password", "password2", "phone", "school", "profile_photo")

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password")
        validated_data.pop("password2")

        with transaction.atomic():
            user = self.create_user(user_data, password)
            candidate = Candidate.objects.create(user=user, **validated_data)
            return candidate


class StaffRegistrationSerializer(BaseRegistrationSerializer):
    """
    Serializer for registering new staff (creates User and Staff).
    """

    class Meta:
        model = Staff
        fields = (
            "user",
            "password",
            "password2",
            "phone",
            "occupation",
            "profile_photo",
        )

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password")
        validated_data.pop("password2")

        with transaction.atomic():
            user = self.create_user(user_data, password)
            staff = Staff.objects.create(user=user, **validated_data)
            return staff


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
    answers = CandidateAnswerSerializer(many=True)

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("At least one answer must be provided.")
        return value


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


class CandidateExamSerializer(serializers.ModelSerializer):
    questions = CandidateQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = (
            "id",
            "title",
            "stage",
            "description",
            "open_duration_hours",
            "exam_date",
            "countdown_minutes",
            "questions",
        )
