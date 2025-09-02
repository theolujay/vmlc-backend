import logging

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from typing import Any, List

from ..models import CandidateAnswer, CandidateScore, Exam, Candidate
from ..permissions import IsCandidate
from ..serializers import CandidateAnswerBulkSerializer

logger = logging.getLogger(__name__)


class SubmitAnswersView(APIView):
    """
    Handles the submission of a candidate's answers for a specific exam.
    """

    permission_classes: List[Any] = [IsAuthenticated, IsCandidate]
    serializer_class: Any = CandidateAnswerBulkSerializer

    def post(self, request: Request, exam_id: int) -> Response:
        """
        Validates and saves a bulk submission of answers for an exam.

        - Ensures the exam is open and the candidate is eligible.
        - Prevents re-submission.
        - Creates all answers within a single database transaction.
        - Triggers auto-scoring upon successful submission.
        """
        candidate: Candidate = request.user.candidate_profile
        exam: Exam = get_object_or_404(Exam, pk=exam_id)

        # 1. Business Logic Validation
        if not exam.is_currently_open:
            return Response(
                {"detail": "This exam is not currently open for submissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if candidate.role != exam.stage:
            return Response(
                {"detail": "You are not eligible to take this exam."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Prevent Re-submission
        candidate_score: CandidateScore
        created: bool
        candidate_score, created = CandidateScore.objects.get_or_create(
            candidate=candidate, exam=exam
        )

        if (
            not created
            and CandidateAnswer.objects.filter(candidate_score=candidate_score).exists()
        ):
            return Response(
                {"detail": "You have already submitted answers for this exam."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Data Validation
        serializer: CandidateAnswerBulkSerializer = self.serializer_class(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        answers_data: List[Any] = serializer.validated_data["answers"]

        # 4. Atomic Bulk Creation and Scoring
        with transaction.atomic():
            answers_to_create: List[CandidateAnswer] = [
                CandidateAnswer(
                    candidate_score=candidate_score,
                    question=answer_data["question"],
                    selected_option=answer_data.get("selected_option", ""),
                )
                for answer_data in answers_data
            ]
            CandidateAnswer.objects.bulk_create(answers_to_create)
            candidate_score.calculate_and_save_auto_score(answers_to_create)

        logger.info(
            "Candidate %s successfully submitted answers for exam %s.",
            candidate.pk,
            exam.pk,
        )

        return Response(
            {"message": "Answers submitted successfully!"},
            status=status.HTTP_201_CREATED,
        )
