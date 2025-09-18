import logging

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from channels.db import database_sync_to_async

from ..models import CandidateAnswer, CandidateScore, Exam
from ..permissions import IsCandidate
from ..serializers import CandidateAnswerBulkSerializer

logger = logging.getLogger(__name__)


class SubmitAnswersView(APIView):
    """
    Handles the submission of a candidate's answers for a specific exam.
    """

    permission_classes = [IsAuthenticated, IsCandidate]
    serializer_class = CandidateAnswerBulkSerializer

    @database_sync_to_async
    def _submit_answers(self, request, exam_id):
        """
        Validates and saves a bulk submission of answers for an exam.

        - Ensures the exam is open and the candidate is eligible.
        - Prevents re-submission.
        - Creates all answers within a single database transaction.
        - Triggers auto-scoring upon successful submission.
        """
        candidate = request.user.candidate_profile
        exam = get_object_or_404(Exam, pk=exam_id)
        logger.info(
            f"SubmitAnswersView: request from user {request.user.id} (candidate_id: {candidate.pk}) for exam {exam_id} with data: {request.data}"
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
        candidate_score, created = CandidateScore.objects.get_or_create(
            candidate=candidate, exam=exam
        )

        if (
            not created
            and CandidateAnswer.objects.filter(candidate_score=candidate_score).exists()
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

        # 4. Atomic Bulk Creation and Scoring
        with transaction.atomic():
            answers_to_create = [
                CandidateAnswer(
                    candidate_score=candidate_score,
                    question=answer_data["question"],
                    selected_option=answer_data.get("selected_option", ""),
                )
                for answer_data in answers_data
            ]
            CandidateAnswer.objects.bulk_create(answers_to_create)

            # Asynchronously calculate the score
            from ..tasks import calculate_and_save_auto_score_task

            calculate_and_save_auto_score_task.delay(candidate_score.id)

        logger.info(
            "Candidate %s successfully submitted answers for exam %s.",
            candidate.pk,
            exam.pk,
        )

        return Response(
            {"message": "Answers submitted successfully!"},
            status=status.HTTP_201_CREATED,
        )

    async def post(self, request, exam_id):
        return await self._submit_answers(request, exam_id)
