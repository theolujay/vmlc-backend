import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Candidate,
    CandidateScore,
    Exam,
)
from ..permissions import (
    VerifiedAdminPermissions,
)
from ..serializers import (
    CandidateScoreSerializer,
    SubmitScoreSerializer,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    candidate_score_list_response_schema,
    submit_score_request_body,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)

logger = logging.getLogger(__name__)


@method_decorator(
    name="get",
    decorator=swagger_auto_schema(
        operation_summary="List Candidate Scores",
        operation_description="Retrieve all scores for a given candidate.",
        responses={
            200: candidate_score_list_response_schema,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Scores"],
        manual_parameters=[api_key, bearer_auth],
    ),
)
class CandidateScoreListView(ListAPIView):
    """
    Retrieve all scores for a given candidate.

    Accessible by staff with 'admin', 'manager', or 'superadmin' roles.
    """

    permission_classes = VerifiedAdminPermissions
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

    permission_classes = VerifiedAdminPermissions
    serializer_class = SubmitScoreSerializer

    @swagger_auto_schema(
        operation_summary="Submit Score",
        operation_description="Submit or update a candidate's score for a specific exam.",
        request_body=submit_score_request_body,
        responses={
            200: openapi.Response("Score submitted/updated."),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Scores"],
        manual_parameters=[api_key, bearer_auth],
    )
    def put(self, request, exam_id):
        return self._submit_score(request, exam_id)

    # @database_sync_to_async
    def _submit_score(self, request, exam_id):
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
        _, created = CandidateScore.objects.update_or_create(
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

    permission_classes = VerifiedAdminPermissions

    @swagger_auto_schema(
        operation_summary="Publish Scores",
        operation_description="Refreshes and publishes the scores.",
        responses={
            202: openapi.Response(
                "Scores snapshot generation has been started and will be available shortly."
            ),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Scores"],
        manual_parameters=[api_key, bearer_auth],
    )
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
