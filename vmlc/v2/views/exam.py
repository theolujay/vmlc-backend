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
from identity.permissions import ActiveAdminPermissions, CandidatePermissions

from django.utils import timezone
from vmlc.models import Exam, Question, CandidateExamResult, ExamAccess
from vmlc.services.candidate_records import CandidateRecordService
from vmlc.utils.helpers import invalidate_all_dashboard_caches
from vmlc.v2.serializers.exam import (
    ExamListV2Serializer,
    ExamDetailV2Serializer,
    ExamResultV2Serializer,
    CandidateTakeExamSerializer,
)
from vmlc.serializers import (
    QuestionListSerializer,
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

        # Question Pool Data (Staff Dashboard context)
        from vmlc.v2.utils import CacheKeys

        question_pool_data = get_or_set_cache(
            CacheKeys.QUESTION_POOL,
            lambda: question_pool_aggregate(Question.objects.filter(is_archived=False)),
            ttl=3600,
        )

        # Exam List Cache
        # Note: Listing is hard to cache per-query-params without a versioning key or complex key.
        # For now, we rely on the queryset's efficiency and cache the pool data.
        # TODO: Look into this
        response = super().list(request, *args, **kwargs)
        response.data["question_pool_data"] = question_pool_data
        return response

    def perform_create(self, serializer):
        """
        Create an exam
        Also records the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)

        from vmlc.v2.utils import invalidate_staff_dashboard

        invalidate_staff_dashboard()

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
        from vmlc.v2.utils import CacheKeys

        cache_key = CacheKeys.EXAM_DETAIL.format(exam_id=exam_id)

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

        serializer.save(updated_by=self.request.user.staff_profile)

        logger.info(
            f"Exam updated by user {self.request.user.id} with data: {serializer.data}"
        )

    def perform_destroy(self, instance):
        instance.delete()


class ExamResultsV2View(ListAPIView):
    permission_classes = ActiveAdminPermissions
    serializer_class = ExamResultV2Serializer
    lookup_url_kwarg = "exam_id"

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        from vmlc.v2.utils import CacheKeys

        cache_key = CacheKeys.EXAM_RESULTS.format(exam_id=exam_id)

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
        from vmlc.v2.utils import CacheKeys

        cache_key = CacheKeys.EXAM_QUESTIONS.format(exam_id=exam_id)

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
    serializer_class = None
    lookup_url_kwarg = "candidate_id"

    def get(self, request, *args, **kwargs):
        candidate_id = self.kwargs[self.lookup_url_kwarg]

        from vmlc.v2.utils import CacheKeys

        cache_key = CacheKeys.CANDIDATE_EXAM_HISTORY.format(candidate_id=candidate_id)

        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            raise NotFound("Candidate not found.")

        data = get_or_set_cache(
            cache_key,
            lambda: CandidateRecordService.get_exams_taken(candidate),
            ttl=3600,
        )
        logger.info(
            f"ExamHistoryV2View: request from user {self.request.user.id} for candidate {candidate_id}"
        )
        return Response(data)

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
    from datetime import timedelta
    from competition.services.eligibility import EligibilityService

    candidate = request.user.candidate_profile

    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        raise NotFound("Exam not found.")

    if not EligibilityService.can_take_exam(candidate, exam):
        logger.warning(
            f"Candidate {candidate.pk} failed eligibility check for exam {exam_id}"
        )
        raise PermissionDenied("You are not eligible to take this exam at this time.")

    # Manage Exam Access
    now = timezone.now()
    access, created = ExamAccess.objects.get_or_create(
        candidate=candidate,
        exam=exam,
        defaults={
            "status": ExamAccess.Status.STARTED,
            "facilitator_system": ExamAccess.Facilitator.VMLC,
            "started_at": now,
            "deadline": now + timedelta(minutes=exam.countdown_minutes),
        },
    )

    if not created:
        # Check if already submitted or expired
        if access.status in [
            ExamAccess.Status.SUBMITTED,
            ExamAccess.Status.EXPIRED,
            ExamAccess.Status.FAILED,
        ]:
            raise PermissionDenied("You have already completed or attempted this exam.")

        # If in PENDING or ISSUED (unlikely for VMLC native, but possible), update to STARTED
        # TODO: revisit this when Esturdi integration is implemented, especially when fallback feature flag is implemented
        if access.status in [ExamAccess.Status.PENDING, ExamAccess.Status.ISSUED]:
            access.status = ExamAccess.Status.STARTED
            access.started_at = now
            access.deadline = now + timedelta(minutes=exam.countdown_minutes)
            access.save(update_fields=["status", "started_at", "deadline"])

    return Response(
        CandidateTakeExamSerializer(exam, context={"request": request}).data
    )
