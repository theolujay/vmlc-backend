"""
API views for retrieving and submitting candidate scores.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..models import Candidate, CandidateScore, Exam, Staff
from ..permissions import HasStaffRole, IsVerifiedStaff
from ..serializers import CandidateScoreSerializer, SubmitScoreSerializer

logger = logging.getLogger(__name__)


class CandidateScoreListView(ListAPIView):
    """
    Retrieve all scores for a given candidate.

    Accessible by staff with 'admin' or 'owner' roles.
    """

    permission_classes = [
        IsAuthenticated,
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = CandidateScoreSerializer

    def get_queryset(self):
        """
        Returns a queryset of scores for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs.get("candidate_id")
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
        HasStaffRole(Staff.Roles.ADMIN, Staff.Roles.OWNER),
    ]
    serializer_class = SubmitScoreSerializer

    def put(self, request, exam_id: int):
        """
        Handles the submission of a score for a candidate in a given exam.

        Expects `candidate_id` and `score` in the request body.
        """
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
            defaults={"score": score, "submitted_by": staff, "auto_score": False},
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
