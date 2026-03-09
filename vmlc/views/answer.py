import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CandidateAnswer, CandidateExamResult, Exam
from identity.permissions import CandidatePermissions
from ..serializers import CandidateAnswerBulkSerializer
from ..utils.swagger_schemas import (
    api_key,
    bearer_auth,
    submit_answers_request_body,
    error_response_400,
    error_response_401,
    error_response_403,
    error_response_404,
)
from ..utils.helpers import sanitize_data


logger = logging.getLogger(__name__)


class SubmitAnswersView(APIView):
    """
    Handles the submission of a candidate's answers for a specific exam.
    """

    permission_classes = CandidatePermissions
    serializer_class = CandidateAnswerBulkSerializer

    @swagger_auto_schema(
        operation_summary="Submit Exam Answers",
        operation_description="Submit answers for a specific exam.",
        request_body=submit_answers_request_body,
        responses={
            201: openapi.Response("Answers submitted successfully!"),
            400: error_response_400,
            401: error_response_401,
            403: error_response_403,
            404: error_response_404,
        },
        tags=["Exams"],
        manual_parameters=[api_key, bearer_auth],
    )
    def post(self, request, exam_id):
        return self._submit_answers(request, exam_id)

    def _submit_answers(self, request, exam_id):
        """
        Validates and saves a bulk submission of answers for an exam.

        - Ensures the exam is open and the candidate is eligible.
        - Prevents re-submission.
        - Creates all answers within a single database transaction.
        - Triggers auto-scoring upon successful submission.
        """
        from comms.tasks import notify_user_task
        from comms.models import Broadcast

        candidate = request.user.candidate_profile
        exam = get_object_or_404(Exam, pk=exam_id)
        safe_data = sanitize_data(request.data)
        logger.info(
            f"SubmitAnswersView: request from user {request.user.id} (candidate_id: {candidate.pk}) for exam {exam_id} with data: {safe_data}"
        )

        # 1. Business Logic Validation
        if not exam.is_currently_open:
            logger.warning(
                f"Candidate {candidate.pk} attempted to submit answers for closed exam {exam_id}"
            )
            return Response(
                {"detail": "This exam is not currently open for submissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if candidate.role != exam.stage:
            logger.warning(
                f"Candidate {candidate.pk} with role {candidate.role} attempted to submit answers for exam {exam_id} with stage {exam.stage}"
            )
            return Response(
                {"detail": "You are not eligible to take this exam."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Prevent Re-submission
        candidate_exam_result, created = CandidateExamResult.objects.get_or_create(
            candidate=candidate, exam=exam
        )

        if (
            not created
            and CandidateAnswer.objects.filter(
                candidate_exam_result=candidate_exam_result
            ).exists()
        ):
            logger.warning(
                f"Candidate {candidate.pk} attempted to re-submit answers for exam {exam_id}"
            )
            return Response(
                {"detail": "You have already submitted answers for this exam."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Data Validation
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers_data = serializer.validated_data["answers"]

        # Atomic Bulk Creation
        # TODO: wrap success logger and notification in the transaction and handle edge case when transaction fails and rolls back
        with transaction.atomic():
            answers_to_create = [
                CandidateAnswer(
                    candidate_exam_result=candidate_exam_result,
                    question=answer_data["question"],
                    selected_option=answer_data.get("selected_option", "")
                    .strip()
                    .upper(),
                )
                for answer_data in answers_data
            ]
            CandidateAnswer.objects.bulk_create(answers_to_create)

        logger.info(
            "Candidate %s successfully submitted answers for exam %s.",
            candidate.pk,
            exam.pk,
        )

        # Send notification
        notify_user_task.delay(
            user_id=str(request.user.id),
            subject=f"Submission Successful: {exam.title}",
            message=f"Your submission for the exam '{exam.title}' has been received successfully.",
            mediums=[
                # Broadcast.Mediums.PLATFORM,
                Broadcast.Mediums.EMAIL,
                # Broadcast.Mediums.SMS,
            ],
            notification_type="success",
        )

        return Response(
            {"message": "Answers submitted successfully!"},
            status=status.HTTP_201_CREATED,
        )
