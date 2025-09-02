from django.db.models import Avg, Count

from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, serializers
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)
from rest_framework.request import Request
from django.db.models import QuerySet
from typing import Any, Type

from ..models import Exam, CandidateScore, Candidate, Question, Staff
from ..serializers import (
    ExamListSerializer,
    ExamDetailSerializer,
    ExamResultSerializer,
    QuestionDetailSerializer,
    CandidateExamSerializer,
    CandidateExamScoreSerializer,
)
from ..permissions import HasStaffRole, IsCandidate, IsVerifiedStaff
from ..utils.query_filters import ExamFilter


class ExamListView(ListCreateAPIView):
    """
    API view to list all exams or create a new exam.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[ExamListSerializer] = ExamListSerializer
    filterset_class: Type[ExamFilter] = ExamFilter

    def get_serializer_class(self) -> Type[serializers.Serializer]:
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

    def get_queryset(self) -> QuerySet[Exam]:
        """
        Returns a queryset of all Exam objects.
        """
        return (
            Exam.objects.annotate(question_count=Count("questions"))
            .select_related("created_by__user")
            .order_by("-date_created")
        )

    def perform_create(self, serializer: serializers.Serializer) -> None:
        """
        Saves the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff_profile)


class ExamDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[ExamDetailSerializer] = ExamDetailSerializer
    lookup_url_kwarg: str = "exam_id"

    def get_queryset(self) -> QuerySet[Exam]:
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        return Exam.objects.annotate(average_score=Avg("scores__score")).select_related(
            "created_by__user", "updated_by__user"
        )

    # `perform_destroy` is handled by the parent class, no need to override.


class ExamResultsView(ListAPIView):
    """
    API view to retrieve the results of a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[ExamResultSerializer] = ExamResultSerializer
    lookup_url_kwarg: str = "exam_id"

    def get_queryset(self) -> QuerySet[CandidateScore]:
        """
        Returns a queryset of scores for the specified exam,
        optimized with prefetching.
        """
        exam_id: int = self.kwargs[self.lookup_url_kwarg]
        # Ensure the exam exists before proceeding.
        get_object_or_404(Exam, pk=exam_id)
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

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[QuestionDetailSerializer] = QuestionDetailSerializer

    def get_queryset(self) -> QuerySet[Question]:
        """
        Returns the queryset of questions related to a given exam.
        """
        # Use prefetch_related to optimize fetching the question creator's user data.
        exam: Exam = get_object_or_404(
            Exam.objects.prefetch_related("questions__created_by__user"),
            pk=self.kwargs["exam_id"],
        )
        return exam.questions.filter(is_active=True)


class ExamHistoryView(ListAPIView):
    """
    API view to retrieve the exam history and scores of a specific candidate.

    Requires candidate_id in the URL path.
    """

    permission_classes: list[Any] = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class: Type[CandidateExamScoreSerializer] = CandidateExamScoreSerializer
    lookup_url_kwarg: str = "candidate_id"

    def get_queryset(self) -> QuerySet[CandidateScore]:
        """
        Returns a queryset of scores for the specified candidate,
        optimized with prefetching.
        """
        candidate_id: str = self.kwargs[self.lookup_url_kwarg]
        # Ensure the candidate exists before proceeding.
        get_object_or_404(Candidate, pk=candidate_id)
        return (
            CandidateScore.objects.filter(candidate_id=candidate_id)
            .select_related("exam")
            .order_by("-date_recorded")
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCandidate])
def candidate_take_exam(request: Request, exam_id: int) -> Response:
    """
    Allows a candidate to retrieve the questions for a specific exam if they are eligible.
    """
    candidate: Candidate = request.user.candidate_profile
    exam: Exam = get_object_or_404(Exam, pk=exam_id)

    if not candidate.is_verified:
        return Response(
            {"detail": "Candidate must be verified to take this exam."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if candidate.role != exam.stage:
        return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

    if not exam.is_currently_open:
        return Response(
            {"detail": "Exam is not currently open."}, status=status.HTTP_403_FORBIDDEN
        )

    serializer: CandidateExamSerializer = CandidateExamSerializer(exam)
    return Response(serializer.data)
