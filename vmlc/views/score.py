import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView


from ..models import (
    Candidate,
    CandidateScore,
    Exam,
    Staff,
)
from ..permissions import HasStaffRole, IsVerifiedStaff
from ..serializers import (
    CandidateScoreSerializer,
    SubmitScoreSerializer,
)

logger = logging.getLogger(__name__)


class CandidateScoreListView(ListAPIView):
    """
    Retrieve all scores for a given candidate.

    Accessible by staff with 'admin' or 'superadmin' roles.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = CandidateScoreSerializer

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs.get("candidate_id")
        logger.info(
            f"CandidateScoreListView: request from user {self.request.user.id} for candidate {candidate_id}"
        )
        # Ensure the candidate exists before proceeding
        get_object_or_404(Candidate, pk=candidate_id)
        return (
            CandidateScore.objects.filter(candidate_id=candidate_id)
            .select_related("candidate__user", "exam")
            .order_by("-date_recorded")
        )


class SubmitScoreView(APIView):
    """
    Submit or update a candidate's score for a specific exam.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]
    serializer_class = SubmitScoreSerializer

    def put(self, request, exam_id):
        """
        Handles the submission of a score for a candidate in a given exam.

        Expects `candidate_id` and `score` in the request body.
        """
        logger.info(
            f"SubmitScoreView: request from user {self.request.user.id} for exam {exam_id} with data: {request.data}"
        )
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        candidate_id = validated_data["candidate_id"]
        score = validated_data["score"]

        # get_object_or_404 is fine here as the serializer already validated existence
        candidate = Candidate.objects.get(pk=candidate_id)
        exam = get_object_or_404(Exam, pk=exam_id)
        # IsVerifiedStaff permission ensures staff_profile exists
        staff = request.user.staff_profile

        # Create or update the score
        score_obj, created = CandidateScore.objects.update_or_create(
            candidate=candidate,
            exam=exam,
            defaults={
                "score": score,
                "submitted_by": staff,
                "auto_score": False,
                "date_recorded": timezone.now(),
            },
        )

        action = "submitted" if created else "updated"
        logger.info(
            "Score for candidate %s on exam %s was %s by staff %s.",
            candidate.pk,
            exam.pk,
            action,
            staff.pk,
        )

        return Response(
            {
                "message": f"Score {action}.",
                "data": {
                    "candidate": candidate.user.get_full_name(),
                    "exam": exam.title,
                    "score": float(score),
                },
            },
            status=status.HTTP_200_OK,
        )


class PublishScoresView(APIView):
    """
    Refreshes and publishes the scores.
    Admin/Superadmin only.
    """

    permission_classes = [
        IsAuthenticated,
        IsVerifiedStaff,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.SUPERADMIN),
    ]

    def post(self, request):
        """
        Triggers an asynchronous task to generate and publish the scores snapshot.
        """
        from ..tasks import generate_scores_snapshot_task

        staff_id = request.user.staff_profile.pk
        logger.info(
            f"PublishScoresView: request from user {request.user.id} (staff_id: {staff_id})"
        )
        generate_scores_snapshot_task.delay(staff_id)

        logger.info(f"Scores snapshot generation triggered by staff {staff_id}")

        return Response(
            {
                "message": "Scores snapshot generation has been started and will be available shortly."
            },
            status=status.HTTP_202_ACCEPTED,
        )
