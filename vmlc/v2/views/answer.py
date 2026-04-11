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
from vmlc.v2.utils import GRACE_PERIOD_MINUTES

logger = logging.getLogger(__name__)


class SubmitAnswersV2View(APIView):
    """
    Handles the submission of a candidate's answers for a specific exam.
    Uses ExamAccess to track enrollment status.
    """

    permission_classes = CandidatePermissions
    serializer_class = CandidateAnswerBulkSerializer

    def post(self, request, exam_id):
        candidate = request.user.candidate_profile
        exam = get_object_or_404(Exam, pk=exam_id)

        safe_data = sanitize_data(request.data)
        logger.info(
            f"SubmitAnswersV2View: request from user {request.user.id} "
            f"(candidate_id: {candidate.pk}) for exam {exam_id} with data: {safe_data}"
        )

        # Validate submission data before acquiring any locks
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers_data = serializer.validated_data["answers"]
        is_auto_submit = serializer.validated_data["is_auto_submit"]

        with transaction.atomic():
            # Lock the ExamAccess row for this candidate+exam pair.
            # Any concurrent submission attempt will block here until this
            # transaction commits, at which point the status check below
            # will catch it.
            try:
                access = ExamAccess.objects.select_for_update().get(
                    candidate=candidate, exam=exam
                )
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
                    f"Candidate {candidate.pk} attempted to re-submit answers for exam "
                    f"{exam_id} (Access Status: {access.status})"
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
                personal_deadline = access.deadline
                # Add grace period for network latency
                if timezone.now() <= personal_deadline + timedelta(minutes=GRACE_PERIOD_MINUTES):
                    is_within_personal_time = True

            if not is_globally_open and not is_within_personal_time:
                logger.warning(
                    f"Candidate {candidate.pk} attempted to submit answers for closed exam "
                    f"{exam_id}. Global: {is_globally_open}, Personal: {is_within_personal_time}"
                )
                return Response(
                    {"detail": "This exam is no longer open for submissions."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            result = CandidateExamResult.objects.create(
                candidate=candidate,
                exam=exam,
                score=0.0,
                auto_score=False,
                is_auto_submit=is_auto_submit,
                recorded_at=timezone.now(),
            )

            CandidateAnswer.objects.bulk_create([
                CandidateAnswer(
                    candidate_exam_result=result,
                    question=answer_data["question"],
                    selected_option=answer_data.get("selected_option", "").strip().upper(),
                )
                for answer_data in answers_data
            ])

            access.status = ExamAccess.Status.SUBMITTED
            access.submitted_at = timezone.now()
            access.save(update_fields=["status", "submitted_at"])

            from vmlc.v2.utils import invalidate_candidate_cache
            invalidate_candidate_cache(candidate.pk, request.user.id)

        logger.info(
            "Candidate %s successfully submitted answers for exam %s (V2).",
            candidate.pk,
            exam.pk,
        )

        from comms.tasks import notify_user_task
        from comms.models import Broadcast

        notify_user_task.delay(
            user_id=str(request.user.id),
            subject=f"Submission Successful: {exam.title}",
            message=f"Your submission for the exam '{exam.title}' has been received successfully.",
            mediums=[Broadcast.Medium.EMAIL],
            notification_type="success",
        )

        return Response(
            {"message": "Answers submitted successfully!"},
            status=status.HTTP_201_CREATED,
        )