import logging

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.utils.decorators import method_decorator

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.settings import api_settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)

from vmlc.utils.helpers import invalidate_all_dashboard_caches
from identity.models import Candidate
from ..models import Exam, Question, CandidateExamResult
from ..serializers import (
    ExamListSerializer,
    ExamDetailSerializer,
    ExamResultSerializer,
    QuestionListSerializer,
    CandidateExamSerializer,
)
from identity.permissions import (
    ActiveAdminPermissions,
    CandidatePermissions,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    exam_list_response_schema,
    exam_detail_request_body,
    exam_detail_response_schema,
    exam_result_response_schema,
    question_detail_list_response_schema,
    candidate_exam_result_list_response_schema,
    candidate_exam_response_schema,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.query_filters import ExamFilter
from ..utils.exceptions import PermissionDenied, NotFound
from ..services.candidate_records import CandidateRecordService
from ..v2.utils import get_or_set_cache


logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Exams",
        operation_description="List all exams.",
        responses={
            200: exam_list_response_schema,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="post",
    decorator=swagger_auto_schema(
        operation_summary="Create Exam",
        operation_description="Create a new exam.",
        request_body=exam_detail_request_body,
        responses={
            201: exam_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ExamListView(ListCreateAPIView):
    """
    API view to list all exams or create a new exam.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    permission_classes = ActiveAdminPermissions
    serializer_class = ExamListSerializer
    filterset_class = ExamFilter

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Try to get question_pool_data from cache
        question_pool_data = cache.get("question_pool_data")
        if not question_pool_data:
            question_pool_data = Question.objects.aggregate(
                total_questions=Count("id", filter=Q(is_archived=False)),
                hard_questions_count=Count(
                    "id",
                    filter=Q(difficulty=Question.Difficulty.HARD)
                    & Q(is_archived=False),
                ),
                moderate_questions_count=Count(
                    "id",
                    filter=Q(difficulty=Question.Difficulty.MODERATE)
                    & Q(is_archived=False),
                ),
                easy_questions_count=Count(
                    "id",
                    filter=Q(difficulty=Question.Difficulty.EASY)
                    & Q(is_archived=False),
                ),
            )
            # Cache the data for 1 hour
            cache.set("question_pool_data", question_pool_data, 3600)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["question_pool_data"] = question_pool_data
            response.data["results"] = response.data.pop("results")
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {"question_pool_data": question_pool_data, "results": serializer.data}
        )

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the HTTP method.
        - Uses `ExamDetailSerializer` for POST requests.
        - Uses `ExamListSerializer` for GET requests.
        """
        return (
            ExamDetailSerializer
            if self.request.method == "POST"
            else ExamListSerializer
        )

    def get_queryset(self):
        """
        Returns a queryset of all Exam objects.
        """
        logger.info(
            f"ExamListView: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )
        return (
            Exam.objects.annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .select_related("created_by__user")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        """
        Saves the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)
        # Invalidate all staff dashboards as exam data changes
        invalidate_all_dashboard_caches()
        logger.info(
            f"Exam created by user {self.request.user.id} with data: {serializer.data}"
        )


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Exam Details",
        operation_description="Retrieve an exam.",
        responses={
            200: exam_detail_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="put",
    decorator=swagger_auto_schema(
        operation_summary="Update Exam",
        operation_description="Update an exam.",
        request_body=exam_detail_request_body,
        responses={
            200: exam_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="patch",
    decorator=swagger_auto_schema(
        operation_summary="Partially Update Exam",
        operation_description="Partially update an exam.",
        request_body=exam_detail_request_body,
        responses={
            200: exam_detail_response_schema,
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
@method_decorator(
    name="delete",
    decorator=swagger_auto_schema(
        operation_summary="Delete Exam",
        operation_description="Delete an exam.",
        responses={
            204: openapi.Response("Exam deleted successfully."),
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ExamDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details, including questions with their options and correct answers.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = ExamDetailSerializer
    lookup_url_kwarg = "exam_id"
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        logger.info(
            f"ExamDetailView: request from user {self.request.user.id} for exam {self.kwargs.get(self.lookup_url_kwarg)}"
        )
        return (
            Exam.objects.annotate(average_score=Avg("results__score"))
            .select_related("created_by__user", "updated_by__user")
            .prefetch_related("questions")
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        cache_key = f"exam_detail_{instance.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        serializer = self.get_serializer(instance)
        data = serializer.data
        data["questions"] = self._get_questions_data(instance, request)

        cache.set(cache_key, data, 86400)  # Cache for 24 hours
        return Response(data)

    def _get_questions_data(self, exam_instance, request):
        """Helper to get paginated and aggregated question data for an exam."""
        questions_qs = exam_instance.questions.filter(is_archived=False)

        question_pool_data = questions_qs.aggregate(
            total_questions=Count("id", filter=Q(is_archived=False)),
            hard_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.HARD) & Q(is_archived=False),
            ),
            moderate_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.MODERATE)
                & Q(is_archived=False),
            ),
            easy_questions_count=Count(
                "id",
                filter=Q(difficulty=Question.Difficulty.EASY) & Q(is_archived=False),
            ),
        )

        page = self.paginate_queryset(questions_qs)
        question_serializer = QuestionListSerializer(
            page if page is not None else questions_qs,
            many=True,
            context={"request": request},
        )

        if page is not None:
            paginated_response = self.get_paginated_response(question_serializer.data)
            paginated_response.data["question_pool_data"] = question_pool_data
            return paginated_response.data

        return {
            "question_pool_data": question_pool_data,
            "results": question_serializer.data,
            "count": len(question_serializer.data),
            "next": None,
            "previous": None,
        }

    def perform_update(self, serializer):
        """
        Saves the staff member who updated the exam and invalidates the cache.
        """
        instance = serializer.instance
        serializer.save(updated_by=self.request.user.staff_profile)

        # Invalidate the cache
        cache.delete(f"exam_detail_{instance.id}")
        # Invalidate all staff dashboards as exam data changes
        invalidate_all_dashboard_caches()

        # Invalidate account management cache for all candidates who have taken this exam
        for result in instance.results.all():
            cache.delete(f"account_management_{result.candidate.user.id}")

        logger.info(
            f"Exam updated by user {self.request.user.id} with data: {serializer.data}"
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        exam_id = instance.id
        response = super().destroy(request, *args, **kwargs)
        cache.delete(f"exam_detail_{exam_id}")
        # Invalidate all staff dashboards as exam data changes
        invalidate_all_dashboard_caches()
        return response


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Exam Results",
        operation_description="Get results for an exam.",
        responses={
            200: exam_result_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ExamResultsView(ListAPIView):
    """
    API view to retrieve the results of a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = ExamResultSerializer
    lookup_url_kwarg = "exam_id"

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        cache_key = f"exam_results_{exam_id}"

        cached_response = cache.get(cache_key)
        if cached_response:
            logger.info(f"Returning cached results for exam {exam_id}")
            # We need to manually construct a Response object from cached data
            return Response(cached_response)

        response = super().list(request, *args, **kwargs)

        # Only cache if the response was successful
        if response.status_code == 200:
            cache.set(cache_key, response.data, timeout=86400)  # Cache for 24 hours
        return response

    def get_queryset(self):
        """
        Returns a queryset of results for the specified exam,
        optimized with prefetching.
        """
        exam_id = self.kwargs[self.lookup_url_kwarg]
        logger.info(
            f"ExamResultsView: request from user {self.request.user.id} for exam {exam_id}"
        )
        try:
            Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            logger.error(f"Exam with id {exam_id} not found.")
            raise NotFound("Exam not found.")
        return (
            CandidateExamResult.objects.filter(exam_id=exam_id)
            .select_related("candidate__user")
            .order_by("-score")
        )


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Exam Questions",
        operation_description="Get questions for an exam.",
        responses={
            200: question_detail_list_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ExamQuestionsView(ListAPIView):
    """
    API view to list all questions belonging to a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = QuestionListSerializer

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs["exam_id"]
        cache_key = f"exam_questions_{exam_id}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        cache.set(cache_key, data, 86400)
        return Response(data)

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
        return exam.questions.filter(is_archived=False)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="Get Exam History",
        operation_description="Get exam history for a candidate.",
        responses={
            200: candidate_exam_result_list_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class ExamHistoryView(ListAPIView):
    """
    API view to retrieve the exam history and results of a specific candidate.

    Requires candidate_id in the URL path.
    """

    permission_classes = (
        ActiveAdminPermissions  # This was originally ActiveAdminPermissions
    )
    serializer_class = None
    lookup_url_kwarg = "candidate_id"

    def get(self, request, *args, **kwargs):
        candidate_id = self.kwargs[self.lookup_url_kwarg]

        # Access Control: Allow if staff OR if it's the candidate themselves
        is_staff = hasattr(request.user, "staff_profile")
        is_self = hasattr(request.user, "candidate_profile") and str(
            request.user.candidate_profile.pk
        ) == str(candidate_id)

        if not (is_staff or is_self):
            print(f"DEBUG: Permission Denied. is_staff: {is_staff}, is_self: {is_self}")
            if hasattr(request.user, "candidate_profile"):
                print(
                    f"DEBUG: request.user.candidate_profile.pk: {request.user.candidate_profile.pk}"
                )
            print(f"DEBUG: candidate_id from kwargs: {candidate_id}")
            raise PermissionDenied(
                "You do not have permission to view this candidate's history."
            )

        cache_key = f"candidate_exam_history_v2_{candidate_id}"

        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            raise NotFound("Candidate not found.")

        data = get_or_set_cache(
            cache_key,
            lambda: CandidateRecordService.get_exams_taken(candidate),
            ttl=3600,
        )
        return Response(data)


@swagger_auto_schema(
    method="get",
    operation_summary="Take Exam",
    operation_description="Allows a candidate to retrieve the questions for a specific exam if they are eligible.",
    responses={
        200: candidate_exam_response_schema,
        401: error_response_401,
        403: error_response_403,
        404: error_response_404,
    },
    tags=["Exams"],
    manual_parameters=[api_key, bearer_auth],
)
@api_view(["GET"])
@permission_classes(CandidatePermissions)
def candidate_take_exam(request, exam_id):
    """
    Allows a candidate to retrieve the questions for a specific exam if they are eligible.
    """
    from competition.services.eligibility import EligibilityService

    logger.info(
        f"candidate_take_exam: request from user {request.user.id} for exam {exam_id}"
    )
    candidate = request.user.candidate_profile
    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        logger.error(f"Exam with id {exam_id} not found.")
        raise NotFound("Exam not found.")

    if not EligibilityService.can_take_exam(candidate, exam):
        logger.warning(
            f"Candidate {candidate.pk} failed eligibility check for exam {exam_id}"
        )
        raise PermissionDenied("You are not eligible to take this exam at this time.")

    serializer = CandidateExamSerializer(exam)
    return Response(serializer.data)
