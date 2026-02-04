import logging
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.permissions import CandidatePermissions
from vmlc.models import Exam, ExamAccess, CandidateExamResult, CandidateAnswer
from vmlc.serializers.answer import CandidateAnswerBulkSerializer
from vmlc.utils.helpers import sanitize_data

logger = logging.getLogger(__name__)


class SubmitAnswersV2View(APIView):
    """
    Handles the submission of a candidate's answers for a specific exam.
    Uses ExamAccess to track participation status.
    """

    permission_classes = CandidatePermissions
    serializer_class = CandidateAnswerBulkSerializer

    def post(self, request, exam_id):
        candidate = request.user.candidate_profile
        exam = get_object_or_404(Exam, pk=exam_id)

        safe_data = sanitize_data(request.data)
        logger.info(
            f"SubmitAnswersV2View: request from user {request.user.id} (candidate_id: {candidate.pk}) for exam {exam_id} with data: {safe_data}"
        )

        # Check ExamAccess
        try:
            access = ExamAccess.objects.get(candidate=candidate, exam=exam)
        except ExamAccess.DoesNotExist:
            return Response(
                {"detail": "You have not started this exam or do not have access."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if access.status in [
            ExamAccess.Status.SUBMITTED,
            ExamAccess.Status.EXPIRED,
            ExamAccess.Status.FAILED,
        ]:
            logger.warning(
                f"Candidate {candidate.pk} attempted to re-submit answers for exam {exam_id} (Access Status: {access.status})"
            )
            return Response(
                {
                    "detail": "You have already submitted answers for this exam or your access has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check Exam Status (Is it still open?)
        # We allow submission if:
        # 1. The exam is globally open (is_currently_open)
        # 2. OR the candidate started the exam and is still within their allotted countdown time (plus grace period)

        is_globally_open = exam.is_currently_open
        is_within_personal_time = False

        if access.started_at:
            personal_deadline = access.started_at + timedelta(
                minutes=exam.countdown_minutes
            )
            # Add 5 minutes grace period for network latency
            if timezone.now() <= personal_deadline + timedelta(minutes=5):
                is_within_personal_time = True

        if not is_globally_open and not is_within_personal_time:
            logger.warning(
                f"Candidate {candidate.pk} attempted to submit answers for closed exam {exam_id}. Global: {is_globally_open}, Personal: {is_within_personal_time}"
            )
            return Response(
                {"detail": "This exam is no longer open for submissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate Data
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers_data = serializer.validated_data["answers"]

        # 4. Process Submission
        with transaction.atomic():
            # Create CandidateExamResult (placeholder for answers, unscored)
            # We create this to link answers to the candidate and exam.
            result, created = CandidateExamResult.objects.get_or_create(
                candidate=candidate,
                exam=exam,
                defaults={
                    "score": 0.0,
                    "auto_score": False,
                    "recorded_at": timezone.now(),
                },
            )

            # Save Answers
            answers_to_create = [
                CandidateAnswer(
                    candidate_exam_result=result,
                    question=answer_data["question"],
                    selected_option=answer_data.get("selected_option", "").strip().upper(),
                )
                for answer_data in answers_data
            ]
            CandidateAnswer.objects.bulk_create(answers_to_create)

            # Update ExamAccess
            access.status = ExamAccess.Status.SUBMITTED
            access.submitted_at = timezone.now()
            # Store metadata? access.facilitator_payload = ...
            # TODO: revisit access.facilitator_payload when Esturdi is integrated
            access.save(update_fields=["status", "submitted_at"])

            # Invalidate cache
            from vmlc.v2.utils import invalidate_candidate_cache

            invalidate_candidate_cache(candidate.pk, request.user.id)

        logger.info(
            "Candidate %s successfully submitted answers for exam %s (V2).",
            candidate.pk,
            exam.pk,
        )

        return Response(
            {"message": "Answers submitted successfully!"},
            status=status.HTTP_201_CREATED,
        )
