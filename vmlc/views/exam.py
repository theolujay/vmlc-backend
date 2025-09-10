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
from ..utils.exceptions import PermissionDenied, NotFound


class ExamListView(ListCreateAPIView):
    """
    API view to list all exams or create a new exam.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
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
        """
        Returns a queryset of all Exam objects.
        """
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


class ExamDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
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


class ExamResultsView(ListAPIView):
    """
    API view to retrieve the results of a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = ExamResultSerializer
    lookup_url_kwarg = "exam_id"

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified exam,
        optimized with prefetching.
        """
        exam_id = self.kwargs[self.lookup_url_kwarg]
        try:
            Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
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

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = QuestionDetailSerializer

    def get_queryset(self):
        """
        Returns the queryset of questions related to a given exam.
        """
        try:
            exam = Exam.objects.prefetch_related("questions__created_by__user").get(
                pk=self.kwargs["exam_id"]
            )
        except Exam.DoesNotExist:
            raise NotFound("Exam not found.")
        return exam.questions.filter(is_active=True)


class ExamHistoryView(ListAPIView):
    """
    API view to retrieve the exam history and scores of a specific candidate.

    Requires candidate_id in the URL path.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = CandidateExamScoreSerializer
    lookup_url_kwarg = "candidate_id"

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs[self.lookup_url_kwarg]
        try:
            Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            raise NotFound("Candidate not found.")
        return (
            CandidateScore.objects.filter(candidate_id=candidate_id)
            .select_related("exam")
            .order_by("-date_recorded")
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCandidate])
def candidate_take_exam(request, exam_id):
    """
    Allows a candidate to retrieve the questions for a specific exam if they are eligible.
    """
    candidate = request.user.candidate_profile
    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        raise NotFound("Exam not found.")

    if not candidate.is_verified:
        raise PermissionDenied("Candidate must be verified to take this exam.")

    if candidate.role != exam.stage:
        raise PermissionDenied("Not allowed.")

    if not exam.is_currently_open:
        raise PermissionDenied("Exam is not currently open.")

    serializer = CandidateExamSerializer(exam)
    return Response(serializer.data)
