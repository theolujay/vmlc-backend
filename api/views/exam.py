"""
API views to set, list, and retrieve exam details.
"""
from django.db.models import Avg, Count

from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)

from ..models import Exam, CandidateScore, Candidate, Question, Staff
from ..serializers import (
    ExamListSerializer,
    ExamDetailSerializer,
    QuestionDetailSerializer,
    CandidateExamSerializer,
)
from ..permissions import HasStaffRole, IsCandidate, IsLeagueCandidate, IsVerifiedStaff
from ..utils.query_filters import ExamFilter


class ExamListView(ListCreateAPIView):
    """
    API view to list all exams or create a new exam.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
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
        """Returns a queryset of all Exam objects."""
        

    def perform_create(self, serializer):
        """
        Saves the staff member who created the exam
        """
        serializer.save(created_by=self.request.user.staff)


class ExamDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = ExamDetailSerializer
    lookup_url_kwarg = "exam_id"

    def get_queryset(self):
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        return Exam.objects.annotate(average_score=Avg("scores__score")).select_related(
            "created_by__user", "updated_by__user"
        )
    # `perform_destroy` is handled by the parent class, no need to override.


class ExamQuestionsView(ListAPIView):
    """
    API view to list all questions belonging to a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = QuestionDetailSerializer

    def get_queryset(self):
        """
        Returns the queryset of questions related to a given exam.
        """
        # Use prefetch_related to optimize fetching the question creator's user data.
        exam = get_object_or_404(Exam.objects.prefetch_related('questions__created_by__user'), pk=self.kwargs["exam_id"])
        return exam.questions.all()


class ExamHistoryView(ListAPIView):
    """
    API view to retrieve the exam history and scores of a specific candidate.

    Requires candidate_id in the URL path.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]

    def get(self, request, *args, **kwargs):
        """
        Returns a list of exams taken by the candidate and their respective scores.
        """
        candidate = get_object_or_404(Candidate, pk=self.kwargs["candidate_id"])
        scores = CandidateScore.objects.filter(candidate=candidate).select_related(
            "exam"
        )

        data = [
            {
                "exam": s.exam.title,
                "score": float(s.score),
            }
            for s in scores
        ]

        return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCandidate])
def candidate_take_exam(request, exam_id: int):
    """
    Allows a candidate to retrieve the questions for a specific exam if they are eligible.
    """
    candidate = request.user.candidate
    exam = get_object_or_404(Exam, pk=exam_id)

    if candidate.role != exam.stage:
        return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

    serializer = CandidateExamSerializer(exam)
    return Response(serializer.data)
