import logging

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

from ..models import Exam, CandidateScore, Candidate, Question
from ..serializers import (
    ExamListSerializer,
    ExamDetailSerializer,
    ExamResultSerializer,
    QuestionListSerializer,
    CandidateExamSerializer,
    CandidateExamScoreSerializer,
)
from ..permissions import (
    VerifiedAdminPermissions,
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
    candidate_exam_score_list_response_schema,
    candidate_exam_response_schema,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.query_filters import ExamFilter
from ..utils.exceptions import PermissionDenied, NotFound


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
    permission_classes = VerifiedAdminPermissions
    serializer_class = ExamListSerializer
    filterset_class = ExamFilter
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        meta = queryset.aggregate(
            total_questions=Count("questions"),
            hard_questions_count=Count(
                "questions", filter=Q(questions__difficulty=Question.Difficulty.HARD)
            ),
            medium_questions_count=Count(
                "questions", filter=Q(questions__difficulty=Question.Difficulty.MEDIUM)
            ),
            easy_questions_count=Count(
                "questions", filter=Q(questions__difficulty=Question.Difficulty.EASY)
            ),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["meta"] = meta
            response.data["list"] = response.data.pop("results")
            del response.data["count"]
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({"meta": meta, "list": serializer.data})
    
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
            Exam.objects.annotate(question_count=Count("questions"))
            .select_related("created_by__user")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        """
        Saves the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)
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

    permission_classes = VerifiedAdminPermissions
    serializer_class = ExamDetailSerializer
    lookup_url_kwarg = "exam_id"

    def get_queryset(self):
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        logger.info(
            f"ExamDetailView: request from user {self.request.user.id} for exam {self.kwargs.get(self.lookup_url_kwarg)}"
        )
        return (
            Exam.objects.annotate(average_score=Avg("scores__score"))
            .select_related("created_by__user", "updated_by__user")
            .prefetch_related("questions")
        )

    def perform_update(self, serializer):
        """
        Saves the staff member who updated the exam
        """
        serializer.save(updated_by=self.request.user.staff_profile)
        logger.info(
            f"Exam updated by user {self.request.user.id} with data: {serializer.data}"
        )

    # `perform_destroy` is handled by the parent class, no need to override.


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

    permission_classes = VerifiedAdminPermissions
    serializer_class = ExamResultSerializer
    lookup_url_kwarg = "exam_id"

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified exam,
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
            CandidateScore.objects.filter(exam_id=exam_id)
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

    permission_classes = VerifiedAdminPermissions
    serializer_class = QuestionListSerializer

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
            200: candidate_exam_score_list_response_schema,
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
    API view to retrieve the exam history and scores of a specific candidate.

    Requires candidate_id in the URL path.
    """

    permission_classes = VerifiedAdminPermissions
    serializer_class = CandidateExamScoreSerializer
    lookup_url_kwarg = "candidate_id"

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs[self.lookup_url_kwarg]
        logger.info(
            f"ExamHistoryView: request from user {self.request.user.id} for candidate {candidate_id}"
        )
        try:
            Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            logger.error(f"Candidate with id {candidate_id} not found.")
            raise NotFound("Candidate not found.")
        return (
            CandidateScore.objects.filter(candidate_id=candidate_id)
            .select_related("exam")
            .order_by("-recorded_at")
        )


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
    logger.info(
        f"candidate_take_exam: request from user {request.user.id} for exam {exam_id}"
    )
    candidate = request.user.candidate_profile
    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        logger.error(f"Exam with id {exam_id} not found.")
        raise NotFound("Exam not found.")

    if not candidate.is_verified:
        logger.warning(
            f"Unverified candidate {candidate.id} attempted to take exam {exam_id}"
        )
        raise PermissionDenied("Candidate must be verified to take this exam.")

    if candidate.role != exam.stage:
        logger.warning(
            f"Candidate {candidate.id} with role {candidate.role} attempted to take exam {exam_id} with stage {exam.stage}"
        )
        raise PermissionDenied("Not allowed.")

    if not exam.is_currently_open:
        logger.warning(
            f"Candidate {candidate.id} attempted to take exam {exam_id} which is not open."
        )
        raise PermissionDenied("Exam is not currently open.")

    serializer = CandidateExamSerializer(exam)
    return Response(serializer.data)
