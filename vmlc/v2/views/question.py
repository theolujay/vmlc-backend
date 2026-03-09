import logging
from django.db import transaction
from rest_framework import status, parsers
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.settings import api_settings

from identity.permissions import ActiveModeratorPermissions, ActiveAdminPermissions
from vmlc.models import Question, Exam
from vmlc.v2.serializers.question import (
    QuestionV2Serializer,
    QuestionBulkActionSerializer,
)
from vmlc.utils.query_filters import filter_questions

logger = logging.getLogger(__name__)


class QuestionListCreateV2View(ListCreateAPIView):
    """
    V2 view for listing and creating questions with enhanced caching and filtering.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = QuestionV2Serializer
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_queryset(self):
        queryset = (
            Question.objects.filter(is_archived=False)
            .select_related("created_by__user", "updated_by__user")
            .order_by("-created_at")
        )
        return filter_questions(queryset, self.request.query_params)

    def list(self, request, *args, **kwargs):
        # Handle Question Pool Data Caching
        from vmlc.v2.utils import CacheKeys, get_or_set_cache, question_pool_aggregate

        pool_data = get_or_set_cache(
            CacheKeys.QUESTION_POOL,
            lambda: question_pool_aggregate(Question.objects.filter(is_archived=False)),
            ttl=3600,
        )

        response = super().list(request, *args, **kwargs)
        response.data["question_pool_data"] = pool_data
        return response

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.staff_profile)
        # Clear pool cache
        from vmlc.v2.utils import invalidate_question_pool, invalidate_staff_dashboard

        invalidate_question_pool()
        invalidate_staff_dashboard()


class QuestionDetailV2View(RetrieveUpdateDestroyAPIView):
    """
    V2 detail view for questions.
    """

    permission_classes = ActiveModeratorPermissions
    serializer_class = QuestionV2Serializer
    lookup_url_kwarg = "question_id"
    queryset = Question.objects.filter(is_archived=False).select_related(
        "created_by__user", "updated_by__user"
    )
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_related_exams"] = True
        return context

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user.staff_profile)
        # Invalidate related exam caches
        from vmlc.v2.utils import (
            invalidate_exam_cache,
            invalidate_question_pool,
            invalidate_staff_dashboard,
        )

        for exam in instance.exams.all():
            invalidate_exam_cache(exam.id)

        invalidate_question_pool()
        invalidate_staff_dashboard()

    def perform_destroy(self, instance):
        from vmlc.v2.utils import (
            invalidate_exam_cache,
            invalidate_question_pool,
            invalidate_staff_dashboard,
        )

        for exam in instance.exams.all():
            invalidate_exam_cache(exam.id)
        if instance.exams.exists():
            instance.archive()
        else:
            instance.delete()
        invalidate_question_pool()
        invalidate_staff_dashboard()


class QuestionBulkActionV2View(APIView):
    """
    Handles bulk operations: archive, assign to exams, unassign from exams.
    """

    permission_classes = ActiveAdminPermissions

    @transaction.atomic
    def post(self, request):
        serializer = QuestionBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        action = data["action"]
        question_ids = data["question_ids"]
        exam_ids = data.get("exam_ids", [])

        questions = Question.objects.filter(id__in=question_ids)

        from vmlc.v2.utils import (
            invalidate_exam_cache,
            invalidate_question_pool,
            invalidate_staff_dashboard,
        )

        if action == "archive":
            for q in questions:
                # Invalidate exams containing this question before archiving
                for exam in q.exams.all():
                    invalidate_exam_cache(exam.id)
                q.archive()
            invalidate_question_pool()
            msg = f"Archived {questions.count()} questions."

        elif action == "assign":
            exams = Exam.objects.filter(id__in=exam_ids)

            # Validation: Only allow assignment to Draft or Scheduled exams
            invalid_exams = [
                exam.get_title()
                for exam in exams
                if exam.status not in [Exam.Status.DRAFT, Exam.Status.SCHEDULED]
            ]
            if invalid_exams:
                return Response(
                    {
                        "status": "error",
                        "message": f"Cannot assign questions to exams that are not in Draft or Scheduled status: {', '.join(invalid_exams)}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for exam in exams:
                # Find questions that are NOT already in this exam
                existing_question_ids = set(exam.questions.values_list("id", flat=True))
                new_questions = [
                    q for q in questions if q.id not in existing_question_ids
                ]

                if new_questions:
                    exam.questions.add(*new_questions)
                    invalidate_exam_cache(exam.id)

            invalidate_question_pool()
            msg = f"Assigned questions to {exams.count()} exams."

        elif action == "unassign":
            exams = Exam.objects.filter(id__in=exam_ids)

            # Validation: Only allow unassignment from Draft or Scheduled exams
            invalid_exams = [
                exam.get_title()
                for exam in exams
                if exam.status not in [Exam.Status.DRAFT, Exam.Status.SCHEDULED]
            ]
            if invalid_exams:
                return Response(
                    {
                        "status": "error",
                        "message": f"Cannot unassign questions from exams that are not in Draft or Scheduled status: {', '.join(invalid_exams)}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for exam in exams:
                exam.questions.remove(*questions)
                invalidate_exam_cache(exam.id)

            invalidate_question_pool()
            msg = (
                f"Unassigned {questions.count()} questions from {exams.count()} exams."
            )

        invalidate_staff_dashboard()
        return Response({"status": "success", "message": msg})
