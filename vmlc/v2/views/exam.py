import logging

from django.db.models import Avg, Count, Q

from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.settings import api_settings

from identity.models import Candidate
from vmlc.utils.helpers import invalidate_all_dashboard_caches

from vmlc.models import Exam, Question, CandidateExamResult
from vmlc.permissions import ActiveAdminPermissions, CandidatePermissions
from vmlc.v2.serializers.exam import (
    ExamListV2Serializer,
    ExamDetailV2Serializer,
    ExamResultV2Serializer,
    CandidateTakeExamSerializer,
)
from vmlc.serializers import (
    QuestionListSerializer,
    CandidateExamScoreSerializer,
)
from vmlc.v2.utils import get_or_set_cache, delete_many_cache, question_pool_aggregate
from vmlc.utils.exceptions import PermissionDenied, NotFound
from vmlc.utils.query_filters import ExamFilter
from vmlc.utils.swagger_schemas import *

logger = logging.getLogger(__name__)


class ExamListV2View(ListCreateAPIView):
    """
    List all exams or create a new one.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes = ActiveAdminPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    filterset_class = ExamFilter

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the HTTP method.
        - Uses `ExamDetailSerializer` for POST requests.
        - Uses `ExamListSerializer` for GET requests.
        """

        return (
            ExamDetailV2Serializer
            if self.request.method == "POST"
            else ExamListV2Serializer
        )

    def get_queryset(self):
        """
        Returns a queryset of all Exam objects.
        """

        return (
            Exam.objects.annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .select_related("created_by__user")
            .order_by("-created_at")
        )

    def list(self, request, *args, **kwargs):
        logger.info(
            f"ExamListV2View: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        response = super().list(request, *args, **kwargs)

        question_pool_data = get_or_set_cache(
            "question_pool_data",
            lambda: question_pool_aggregate(Question.objects.filter(is_archived=False)),
            ttl=3600,
        )

        response.data["question_pool_data"] = question_pool_data
        return response

    def perform_create(self, serializer):
        """
        Create an exam
        Also records the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)
        invalidate_all_dashboard_caches()
        logger.info(
            f"Exam created by user {self.request.user.id} with data: {serializer.data}"
        )


class ExamDetailV2View(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details, including questions with their options and correct answers.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = ExamDetailV2Serializer
    lookup_url_kwarg = "exam_id"
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        return (
            Exam.objects.annotate(average_score=Avg("results__score"))
            .select_related("created_by__user", "updated_by__user")
            .prefetch_related("questions")
        )

    def retrieve(self, request, *args, **kwargs):

        exam_id = self.kwargs[self.lookup_url_kwarg]
        logger.info(
            f"ExamDetailView: request from user {self.request.user.id} for exam {exam_id}"
        )
        cache_key = f"exam_detail:{exam_id}"

        def build():
            instance = self.get_object()
            data = self.get_serializer(instance).data

            qs = instance.questions.filter(is_archived=False)
            page = self.paginate_queryset(qs)

            serialized = QuestionListSerializer(
                page or qs, many=True, context={"request": request}
            ).data

            data["questions"] = {
                "question_pool_data": question_pool_aggregate(qs),
                "results": serialized,
                "count": qs.count(),
                "next": None,
                "previous": None,
            }

            return data

        return Response(get_or_set_cache(cache_key, build))

    def perform_update(self, serializer):
        """
        Update the details of an exam instance
        """

        instance = serializer.save(updated_by=self.request.user.staff_profile)

        logger.info(
            f"Exam updated by user {self.request.user.id} with data: {serializer.data}"
        )

        delete_many_cache(
            [
                f"exam_detail:{instance.id}",
                *[
                    f"account_management_{r.candidate.user.id}"
                    for r in instance.results.all()
                ],
            ]
        )

        invalidate_all_dashboard_caches()

    def perform_destroy(self, instance):
        delete_many_cache([f"exam_detail:{instance.id}"])
        invalidate_all_dashboard_caches()
        instance.delete()


class ExamResultsV2View(ListAPIView):
    permission_classes = ActiveAdminPermissions
    serializer_class = ExamResultV2Serializer
    lookup_url_kwarg = "exam_id"

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        cache_key = f"exam_results:{exam_id}"

        def fetch_results():
            response = super().list(request, *args, **kwargs)
            return response.data

        cached_data = get_or_set_cache(cache_key, fetch_results)
        logger.info(f"Returning results for exam {exam_id}")
        return Response(cached_data)

    def get_queryset(self):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        if not Exam.objects.filter(pk=exam_id).exists():
            logger.error(f"Exam with id {exam_id} not found.")
            raise NotFound("Exam not found.")
        return (
            CandidateExamResult.objects.filter(exam_id=exam_id)
            .select_related("candidate__user")
            .order_by("-score")
        )


class ExamQuestionsV2View(ListAPIView):
    """
    API view to list all questions belonging to a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = QuestionListSerializer

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs["exam_id"]
        cache_key = f"exam_questions_{exam_id}"

        def fetch_questions():
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        cached_data = get_or_set_cache(cache_key, fetch_questions)
        return Response(cached_data)

    def get_queryset(self):
        """
        Returns the queryset of questions related to a given exam.
        """
        exam_id = self.kwargs["exam_id"]
        logger.info(
            f"ExamQuestionsView: request from user {self.request.user.id} for exam {exam_id}"
        )
        try:
            exam = Exam.objects.prefetch_related("questions__created_by__user").get(
                pk=exam_id
            )
        except Exam.DoesNotExist:
            logger.error(f"Exam with id {exam_id} not found.")
            raise NotFound("Exam not found.")
        logger.info(
            f"Questions list for exam {exam_id}. Request by user {self.request.user.id}"
        )
        return exam.questions.filter(is_archived=False)


class ExamHistoryV2View(ListAPIView):
    """
    API view to retrieve the exam history and results of a specific candidate.
    Requires candidate_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = CandidateExamScoreSerializer
    lookup_url_kwarg = "candidate_id"

    def list(self, request, *args, **kwargs):
        candidate_id = self.kwargs[self.lookup_url_kwarg]
        cache_key = f"exam_history_{candidate_id}"

        def fetch_history():
            response = super().list(request, *args, **kwargs)
            return response.data

        cached_data = get_or_set_cache(cache_key, fetch_history, ttl=86400)
        logger.info(
            f"ExamHistoryView: request from user {self.request.user.id} for candidate {candidate_id}"
        )
        return Response(cached_data)

    def get_queryset(self):
        """
        Returns a queryset of results for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs[self.lookup_url_kwarg]
        try:
            Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            logger.error(f"Candidate with id {candidate_id} not found.")
            raise NotFound("Candidate not found.")
        return (
            CandidateExamResult.objects.filter(candidate_id=candidate_id)
            .select_related("exam")
            .order_by("-recorded_at")
        )


@api_view(["GET"])
@permission_classes(CandidatePermissions)
def candidate_take_exam_V2(request, exam_id):
    candidate = request.user.candidate_profile

    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        raise NotFound("Exam not found.")

    if not candidate.is_active:
        logger.warning(
            f"Deactivated candidate {candidate.id} attempted to take exam {exam_id}"
        )
        raise PermissionDenied("Candidate is deactivated.")

    if candidate.role != exam.stage:
        raise PermissionDenied("Not allowed.")

    if not exam.is_currently_open:
        logger.warning(
            f"Candidate {candidate.id} attempted to take exam {exam_id} which is not open."
        )
        raise PermissionDenied("Exam is not currently open.")

    return Response(CandidateTakeExamSerializer(exam).data)
