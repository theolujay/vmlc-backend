import logging

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.models import (
    Candidate,
)
from ..models import (
    Exam,
    CandidateExamResult,
)
from identity.permissions import (
    ActiveAdminPermissions,
)
from ..serializers import (
    SubmitScoreSerializer,
)
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
    submit_score_request_body,
)

logger = logging.getLogger(__name__)


class SubmitScoreView(APIView):
    """
    Submit or update a candidate's score for a specific exam.
    """

    permission_classes = ActiveAdminPermissions
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
        tags=["Results"],
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
        _, created = CandidateExamResult.objects.update_or_create(
            candidate=candidate,
            exam=exam,
            defaults={
                "score": score,
                "score_submitted_by": staff,
                "auto_score": False,
                "recorded_at": timezone.now(),
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
        # Invalidate the candidate's dashboard cache
        cache.delete(f"candidate_dashboard_{candidate.pk}")
        # Invalidate the account management cache
        cache.delete(f"account_management_{candidate.user.id}")
        # Invalidate the exam history cache
        cache.delete(f"exam_history_{candidate.pk}")
        # Invalidate all staff dashboards as candidate score data changes
        from vmlc.utils.helpers import invalidate_all_staff_dashboards

        invalidate_all_staff_dashboards()

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
    Refreshes and publishes the results.
    Admin or higher.
    """

    permission_classes = ActiveAdminPermissions

    @swagger_auto_schema(
        operation_summary="Publish Scores",
        operation_description="Refreshes and publishes the results.",
        responses={
            202: openapi.Response(
                "Scores snapshot generation has been started and will be available shortly."
            ),
            401: error_response_401,
            403: error_response_403,
        },
        tags=["Results"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request):
        """
        Triggers an asynchronous task to generate and publish the results snapshot.
        """
        from ..tasks import generate_results_snapshot_task

        staff_id = request.user.staff_profile.pk
        logger.info(
            f"PublishScoresView: request from user {request.user.id} (staff_id: {staff_id})"
        )
        generate_results_snapshot_task.delay(staff_id)

        logger.info(f"Scores snapshot generation triggered by staff {staff_id}")

        return Response(
            {
                "message": "Scores snapshot generation has been started and will be available shortly."
            },
            status=status.HTTP_202_ACCEPTED,
        )
