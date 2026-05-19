from datetime import timedelta
import logging

from django.db.models import Avg, Count, Q
from django.core.cache import cache

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.generics import (
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.settings import api_settings

from competition.services.eligibility import EligibilityService
from identity.models import Candidate
from identity.permissions import (
    ActiveAdminPermissions,
    ActiveModeratorPermissions,
    CandidatePermissions,
    StaffRoleHierarchy,
)

from django.utils import timezone
from vmlc.models import Exam, ExamHeartbeat, Question, CandidateExamResult, ExamAccess
from vmlc.services.candidate_records import CandidateRecordService
from vmlc.serializers.exam import (
    ExamListV2Serializer,
    ExamDetailV2Serializer,
    ExamResultV2Serializer,
    CandidateTakeExamSerializer,
    ExamFaceCaptureSerializer,
)
from vmlc.serializers.question import QuestionV2Serializer
from core.utils.cache import (
    CacheKeys,
    get_or_set_cache,
    invalidate_candidate_cache,
    invalidate_exam_cache,
    invalidate_staff_dashboard,
    question_pool_aggregate,
)
from core.utils.exceptions import PermissionDenied, NotFound
from core.utils.query_filters import ExamFilter


logger = logging.getLogger(__name__)


class ExamListV2View(ListCreateAPIView):
    """
    List all exams or create a new one.

    - GET: Returns a list of all exams.
    - POST: Creates a new exam with detailed input data.
    """

    permission_classes = ActiveModeratorPermissions
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    filterset_class = ExamFilter

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the HTTP method.
        - Uses `ExamDetailSerializer` for POST requests.
        - Uses `ExamListSerializer` for GET requests.
        """

        return (
            ExamDetailV2Serializer
            if self.request.method == "POST"
            else ExamListV2Serializer
        )

    def get_queryset(self):
        """
        Returns a queryset of all Exam objects.
        """

        return (
            Exam.objects.annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_archived=False)
                )
            )
            .select_related("created_by__user")
            .order_by("-created_at")
        )

    def list(self, request, *args, **kwargs):
        logger.info(
            f"ExamListV2View: request from user {self.request.user.id} with query params: {self.request.query_params}"
        )

        # Question Pool Data (Staff Dashboard context)
        from core.utils.cache import CacheKeys

        question_pool_data = get_or_set_cache(
            CacheKeys.QUESTION_POOL,
            lambda: question_pool_aggregate(Question.objects.filter(is_archived=False)),
            ttl=3600,
        )

        # Exam List Cache
        # Note: Listing is hard to cache per-query-params without a versioning key or complex key.
        # For now, we rely on the queryset's efficiency and cache the pool data.
        # TODO: Look into this
        response = super().list(request, *args, **kwargs)
        response.data["question_pool_data"] = question_pool_data
        return response

    def perform_create(self, serializer):
        """
        Create an exam
        Also records the staff member who created the exam
        """
        staff = self.request.user.staff_profile
        if not StaffRoleHierarchy.has_minimum_role(staff.role, "admin"):
            return Response(
                {"detail": "You do not have permission to create exams"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer.save(created_by=staff)

        invalidate_staff_dashboard()

        logger.info(
            f"Exam created by user {self.request.user.id} with data: {serializer.data}"
        )


class ExamDetailV2View(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a single exam instance.

    - GET: Retrieve exam details, including questions with their options and correct answers.
    - PUT/PATCH: Update exam information.
    - DELETE: Remove the exam.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = ExamDetailV2Serializer
    lookup_url_kwarg = "exam_id"
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        """
        Optimizes the queryset by annotating with average score and prefetching
        related data needed by the serializer.
        """
        return (
            Exam.objects.annotate(average_score=Avg("results__score"))
            .select_related("created_by__user", "updated_by__user")
            .prefetch_related("questions")
        )

    def retrieve(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        logger.info(
            f"ExamDetailView: request from user {self.request.user.id} for exam {exam_id}"
        )

        cache_key = CacheKeys.EXAM_DETAIL.format(exam_id=exam_id)
        query_params_str = str(sorted(request.query_params.items()))
        cache_key = f"{cache_key}_{query_params_str}"

        def build():
            instance = self.get_object()
            data = self.get_serializer(instance).data

            qs = instance.questions.filter(is_archived=False)
            page = self.paginate_queryset(qs)

            if page is not None:
                serialized = QuestionV2Serializer(
                    page, many=True, context={"request": request}
                ).data
                paginated_response = self.get_paginated_response(serialized)
                data["questions"] = paginated_response.data
                data["questions"]["question_pool_data"] = question_pool_aggregate(qs)
                return data

            serialized = QuestionV2Serializer(
                qs, many=True, context={"request": request}
            ).data
            data["questions"] = {
                "results": serialized,
                "question_pool_data": question_pool_aggregate(qs),
            }

            return data

        return Response(get_or_set_cache(cache_key, build))

    def perform_update(self, serializer):
        """
        Update the details of an exam instance
        """

        instance = serializer.save(updated_by=self.request.user.staff_profile)
        invalidate_exam_cache(instance.id)
        logger.info(
            f"Exam updated by user {self.request.user.id} with data: {serializer.data}"
        )

    def perform_destroy(self, instance):
        if instance.competition_slot:
            instance.competition_slot.delete()  # this cascades into instance.delete()
        else:
            instance.delete()


class ExamRetractV2View(APIView):
    """
    Retract a scheduled exam.
    Nullifies scheduled_date, open_duration_hours, and countdown_minutes, and sets status to DRAFT.
    Only allowed if the exam is currently SCHEDULED.
    """

    permission_classes = ActiveAdminPermissions

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            raise NotFound("Exam not found.")

        if exam.status != Exam.Status.SCHEDULED:
            return Response(
                {
                    "error": f"Only scheduled exams can be retracted. Current status: {exam.status}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        exam.scheduled_date = None
        exam.open_duration_hours = None
        exam.countdown_minutes = None
        # Note: Exam.status property will now return DRAFT because scheduled_date is None.
        # Exam.save() will also set competition_slot.is_active to False.
        exam.save()
        logger.info(f"Exam {exam_id} retracted by user {request.user.id}")
        invalidate_exam_cache(exam.id)
        invalidate_staff_dashboard()

        return Response({"message": "Exam retracted successfully."})


class ExamResultsV2View(ListAPIView):
    permission_classes = ActiveAdminPermissions
    serializer_class = ExamResultV2Serializer
    lookup_url_kwarg = "exam_id"

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        from core.utils.cache import CacheKeys

        cache_key = CacheKeys.EXAM_RESULTS.format(exam_id=exam_id)

        def fetch_results():
            response = super().list(request, *args, **kwargs)
            return response.data

        cached_data = get_or_set_cache(cache_key, fetch_results)
        logger.info(f"Returning results for exam {exam_id}")
        return Response(cached_data)

    def get_queryset(self):
        exam_id = self.kwargs[self.lookup_url_kwarg]
        if not Exam.objects.filter(pk=exam_id).exists():
            logger.error(f"Exam with id {exam_id} not found.")
            raise NotFound("Exam not found.")
        return (
            CandidateExamResult.objects.filter(exam_id=exam_id)
            .select_related("candidate__user")
            .order_by("-score")
        )


class ExamQuestionsV2View(ListAPIView):
    """
    API view to list all questions belonging to a specific exam.

    Requires exam_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = QuestionV2Serializer

    def list(self, request, *args, **kwargs):
        exam_id = self.kwargs["exam_id"]
        from core.utils.cache import CacheKeys

        cache_key = CacheKeys.EXAM_QUESTIONS.format(exam_id=exam_id)

        def fetch_questions():
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        cached_data = get_or_set_cache(cache_key, fetch_questions)
        return Response(cached_data)

    def get_queryset(self):
        """
        Returns the queryset of questions related to a given exam.
        """
        exam_id = self.kwargs["exam_id"]
        logger.info(
            f"ExamQuestionsView: request from user {self.request.user.id} for exam {exam_id}"
        )
        try:
            exam = Exam.objects.prefetch_related("questions__created_by__user").get(
                pk=exam_id
            )
        except Exam.DoesNotExist:
            logger.error(f"Exam with id {exam_id} not found.")
            raise NotFound("Exam not found.")
        logger.info(
            f"Questions list for exam {exam_id}. Request by user {self.request.user.id}"
        )
        return exam.questions.filter(is_archived=False)


class ExamHistoryV2View(ListAPIView):
    """
    API view to retrieve the exam history and results of a specific candidate.
    Requires candidate_id in the URL path.
    """

    permission_classes = ActiveAdminPermissions
    serializer_class = None
    lookup_url_kwarg = "candidate_id"

    def get(self, request, *args, **kwargs):
        candidate_id = self.kwargs[self.lookup_url_kwarg]

        from core.utils.cache import CacheKeys

        cache_key = CacheKeys.CANDIDATE_EXAM_HISTORY.format(candidate_id=candidate_id)

        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            raise NotFound("Candidate not found.")

        data = get_or_set_cache(
            cache_key,
            lambda: CandidateRecordService.get_exams_taken(candidate),
            ttl=3600,
        )
        logger.info(
            f"ExamHistoryV2View: request from user {self.request.user.id} for candidate {candidate_id}"
        )
        return Response(data)

    def get_queryset(self):
        """
        Returns a queryset of results for the specified candidate,
        optimized with prefetching.
        """
        candidate_id = self.kwargs[self.lookup_url_kwarg]
        try:
            Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            logger.error(f"Candidate with id {candidate_id} not found.")
            raise NotFound("Candidate not found.")
        return (
            CandidateExamResult.objects.filter(candidate_id=candidate_id)
            .select_related("exam")
            .order_by("-recorded_at")
        )


class ExamFaceCaptureView(APIView):
    """
    API view for candidates to upload their face capture before taking an exam.
    """

    permission_classes = CandidatePermissions
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, exam_id):
        candidate = request.user.candidate_profile
        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            raise NotFound("Exam not found.")

        serializer = ExamFaceCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access, created = ExamAccess.objects.get_or_create(
            candidate=candidate,
            exam=exam,
            defaults={
                "status": ExamAccess.Status.PENDING,
                "facilitator_system": ExamAccess.Facilitator.VMLC,
            },
        )

        access.face_capture = serializer.validated_data["face_capture"]
        access.status = ExamAccess.Status.PENDING
        access.save()

        logger.info(
            f"Face capture uploaded for candidate {candidate.pk}, exam {exam_id}"
        )
        return Response(
            {"message": "Face capture uploaded successfully."},
            status=status.HTTP_200_OK,
        )


class ExamTimeView(APIView):
    """
    API view for candidates to get server time and deadline for exam timer sync.
    """

    permission_classes = CandidatePermissions

    def get(self, request, exam_id):
        candidate = request.user.candidate_profile

        try:
            exam = Exam.objects.get(pk=exam_id)
        except Exam.DoesNotExist:
            raise NotFound("Exam not found.")

        try:
            access = ExamAccess.objects.get(candidate=candidate, exam=exam)
        except ExamAccess.DoesNotExist:
            raise PermissionDenied("You do not have access to this exam.")

        if access.status in [
            ExamAccess.Status.SUBMITTED,
            ExamAccess.Status.EXPIRED,
            ExamAccess.Status.FAILED,
        ]:
            raise PermissionDenied("You have already completed or attempted this exam.")

        if not access.started_at or not access.deadline:
            raise PermissionDenied("Exam has not been started yet.")

        now = timezone.now()
        return Response(
            {
                "server_time": now,
                "deadline": access.deadline,
                "remaining_seconds": max(
                    0, int((access.deadline - now).total_seconds())
                ),
            }
        )


@api_view(["GET"])
@permission_classes(CandidatePermissions)
def candidate_take_exam_V2(request, exam_id):

    candidate = request.user.candidate_profile

    # 1. Eligibility Check (Always dynamic)
    try:
        exam = Exam.objects.prefetch_related("questions").get(pk=exam_id)
    except Exam.DoesNotExist:
        raise NotFound("Exam not found.")

    is_eligible, in_eligibility_reason, access = EligibilityService.can_take_exam(candidate, exam)

    if not is_eligible:
        logger.warning(
            f"Candidate {candidate.pk} failed eligibility check for exam {exam_id}. Reason: {in_eligibility_reason}"
        )
        raise PermissionDenied(f"{in_eligibility_reason}")

    # 2. Access Management (Always dynamic)
    now = timezone.now()

    # If in PENDING or ISSUED, update to STARTED
    if access.status in [ExamAccess.Status.PENDING, ExamAccess.Status.ISSUED]:
        access.status = ExamAccess.Status.STARTED
        access.started_at = now
        access.deadline = now + timedelta(minutes=exam.countdown_minutes)
        access.save(update_fields=["status", "started_at", "deadline"])

        # purge pre-existing heartbeats if there was a previous attempt
        heartbeats = ExamHeartbeat.objects.filter(exam_access=access)
        heartbeats.delete()
        # Schedule expiration task
        from vmlc.tasks import mark_exam_access_as_expired_task
        from core.utils.cache import GRACE_PERIOD_MINUTES

        mark_exam_access_as_expired_task.apply_async(
            # Add grace period for network latency
            args=[str(access.id)],
            eta=access.deadline + timedelta(minutes=GRACE_PERIOD_MINUTES),
        )

    # 3. Global Exam Data Cache
    # We cache the serialized exam and questions (which are the same for all candidates)
    # but exclude the 'attempt' field which is candidate-specific.
    cache_key = CacheKeys.EXAM_TAKE_V2.format(exam_id=exam_id)

    def fetch_exam_data():
        serializer = CandidateTakeExamSerializer(
            exam, context={"request": None}
        )  # Context=None to avoid 'attempt' field logic during cache build if needed, though we will override it anyway
        data = serializer.data
        # Remove attempt from global cache as it's candidate-specific
        data.pop("attempt", None)
        return data

    exam_data = get_or_set_cache(cache_key, fetch_exam_data)
    invalidate_candidate_cache(candidate_id=candidate.pk)

    # 4. Candidate-Specific Data (Dynamic)
    # We manually build the 'attempt' data for the current candidate
    response_data = exam_data.copy()
    response_data["attempt"] = {
        "started_at": access.started_at,
        "deadline": access.deadline,
        "submitted_at": access.submitted_at,
    }

    return Response(response_data)
