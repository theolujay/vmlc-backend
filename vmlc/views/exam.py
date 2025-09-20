import logging

from django.db.models import Avg, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)

from ..models import Exam, CandidateScore, Candidate
from ..serializers import (
    ExamListSerializer,
    ExamDetailSerializer,
    ExamResultSerializer,
    QuestionDetailSerializer,
    CandidateExamSerializer,
    CandidateExamScoreSerializer,
)
from ..permissions import (
    VerifiedAdminPermissions,
    CandidatePermissions,
)
from ..utils.query_filters import ExamFilter
from ..utils.exceptions import PermissionDenied, NotFound


logger = logging.getLogger(__name__)


class ExamListView(ListCreateAPIView):
    """
    API view to list all exams or create a new exam.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes = VerifiedAdminPermissions
    serializer_class = ExamListSerializer
    filterset_class = ExamFilter

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
            .order_by("-date_created")
        )

    def perform_create(self, serializer):
        """
        Saves the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)
        logger.info(
            f"Exam created by user {self.request.user.id} with data: {serializer.data}"
        )


class ExamDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details.
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
        return Exam.objects.annotate(average_score=Avg("scores__score")).select_related(
            "created_by__user", "updated_by__user"
        )

    # `perform_destroy` is handled by the parent class, no need to override.


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


class ExamQuestionsView(ListAPIView):
    """
    API view to list all questions belonging to a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = VerifiedAdminPermissions
    serializer_class = QuestionDetailSerializer

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
        return exam.questions.filter(is_active=True)


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
            .order_by("-date_recorded")
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
