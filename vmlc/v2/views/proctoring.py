import logging
import json
from datetime import datetime, timedelta
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from vmlc.models import Exam, ExamAccess
from identity.permissions import CandidatePermissions, ActiveAdminPermissions
from vmlc.services.proctoring import ProctoringService
from vmlc.v2.serializers.proctoring import (
    HeartbeatPayloadSerializer,
    ExamHeartbeatSerializer,
    CandidateLiveStatusV2Serializer,
)
from vmlc.v2.utils import CacheKeys, get_or_set_cache, invalidate_integrity_audit_cache
from core.utils.exceptions import NotFound, PermissionDenied

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_MINUTES = 5
HEARTBEAT_INTERVAL_TOLERANCE_SECONDS = 30


class CandidateLiveStatusV2View(APIView):
    """
    Staff-facing endpoint to get the real-time status of a candidate's exam attempt.
    """

    permission_classes = ActiveAdminPermissions

    def get(self, request, exam_id, candidate_id):
        try:
            access = ExamAccess.objects.select_related(
                "exam", "candidate__user"
            ).get(exam_id=exam_id, candidate_id=candidate_id)
        except ExamAccess.DoesNotExist:
            raise NotFound("Exam access record not found for this candidate.")

        serializer = CandidateLiveStatusV2Serializer(
            access, context={"request": request}
        )
        return Response(serializer.data)


class ExamHeartbeatView(APIView):
    """
    Candidate-facing endpoint to receive periodic proctoring telemetry.
    """

    permission_classes = CandidatePermissions
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, exam_id):
        candidate = request.user.candidate_profile
        try:
            exam = Exam.objects.get(pk=exam_id)
            access = ExamAccess.objects.get(candidate=candidate, exam=exam)
        except (Exam.DoesNotExist, ExamAccess.DoesNotExist):
            raise NotFound("Exam or Access record not found.")

        if access.status != ExamAccess.Status.STARTED:
            raise PermissionDenied("Heartbeat is only accepted for ongoing attempts.")

        # The 'payload' field is expected as a JSON string in multipart form
        payload_str = request.data.get("payload")
        if not payload_str:
            return Response(
                {"error": "Missing payload."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payload_data = json.loads(payload_str)
        except ValueError:
            return Response(
                {"error": "Invalid JSON in payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = HeartbeatPayloadSerializer(data=payload_data)
        serializer.is_valid(raise_exception=True)

        face_capture = request.FILES.get("face_capture")

        heartbeat = ProctoringService.process_heartbeat(
            access, serializer.validated_data, face_capture
        )

        logger.info(
            f"Heartbeat {heartbeat.sequence_number} received for candidate {candidate.pk}"
        )
        return Response({"status": "ok", "sequence": heartbeat.sequence_number})


class IntegrityAuditView(APIView):
    """
    Admin-facing endpoint to drill down into a candidate's attempt integrity.
    """

    permission_classes = ActiveAdminPermissions

    def get(self, request, exam_id, candidate_id):
        cache_key = CacheKeys.INTEGRITY_AUDIT.format(
            exam_id=exam_id, candidate_id=candidate_id
        )

        def build_response():
            try:
                access = ExamAccess.objects.get(
                    exam_id=exam_id, candidate_id=candidate_id
                )
            except ExamAccess.DoesNotExist:
                raise NotFound("Exam access record not found.")

            heartbeats = access.heartbeats.all().order_by("sequence_number")
            serializer = ExamHeartbeatSerializer(
                heartbeats, many=True, context={"request": request}
            )

            summary = ProctoringService.get_proctoring_summary(access)

            # Detect gaps (sequence and time-based)
            timeline = []
            last_seq = 0
            last_period_end = None
            expected_interval = timedelta(minutes=HEARTBEAT_INTERVAL_MINUTES)
            time_tolerance = timedelta(seconds=HEARTBEAT_INTERVAL_TOLERANCE_SECONDS)

            for hb in serializer.data:
                curr_seq = hb["sequence_number"]

                # Sequence gap detection
                if curr_seq > last_seq + 1:
                    timeline.append(
                        {
                            "type": "sequence_gap",
                            "expected_sequence": last_seq + 1,
                            "message": f"Missing heartbeat(s) between Seq {last_seq} and Seq {curr_seq}",
                        }
                    )

                # Time gap detection
                if last_period_end is not None:
                    period_start = hb.get("period_start")
                    if period_start:
                        if isinstance(period_start, str):
                            period_start = datetime.fromisoformat(
                                period_start.replace("Z", "+00:00")
                            )
                        if isinstance(last_period_end, str):
                            last_period_end = datetime.fromisoformat(
                                last_period_end.replace("Z", "+00:00")
                            )
                        actual_gap = period_start - last_period_end
                        expected_gap = expected_interval
                        if actual_gap > expected_gap + time_tolerance:
                            timeline.append(
                                {
                                    "type": "time_gap",
                                    "expected_duration_seconds": expected_gap.total_seconds(),
                                    "actual_duration_seconds": actual_gap.total_seconds(),
                                    "message": f"Time gap of {actual_gap.total_seconds() / 60:.1f} min (expected ~{expected_gap.total_seconds() / 60:.0f} min)",
                                }
                            )

                hb_entry = hb.copy()
                hb_entry["type"] = "heartbeat"
                timeline.append(hb_entry)
                last_seq = curr_seq
                last_period_end = hb.get("period_end")

            return {
                "candidate": {
                    "id": access.candidate_id,
                    "name": access.candidate.user.get_full_name(),
                },
                "attempt_summary": {
                    "started_at": access.started_at,
                    "submitted_at": access.submitted_at,
                    "total_duration": (
                        str(access.submitted_at - access.started_at)
                        if access.submitted_at and access.started_at
                        else None
                    ),
                },
                "proctoring_summary": summary,
                "timeline": timeline,
            }

        data = get_or_set_cache(cache_key, build_response, ttl=300)
        return Response(data)


class UpdateProctoringStatusView(APIView):
    """
    Staff-only view to manually override the proctoring status of an attempt.
    """

    permission_classes = ActiveAdminPermissions

    def post(self, request, exam_id, candidate_id):
        new_status = request.data.get("status")
        if new_status not in ["clear", "suspicious", "flagged"]:
            return Response(
                {
                    "error": "Invalid status. Must be 'clear', 'suspicious', or 'flagged'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            access = ProctoringService.update_proctoring_status(
                exam_id, candidate_id, new_status
            )
            cache.delete(CacheKeys.RANKING_SNAPSHOT.format(exam_id=exam_id))
            return Response(
                {
                    "message": f"Proctoring status updated to {new_status}.",
                    "status": access.proctoring_status,
                }
            )
        except ExamAccess.DoesNotExist:
            raise NotFound("Exam access record not found.")
        except Exception as e:
            logger.error(f"Error updating proctoring status: {str(e)}")
            return Response(
                {"error": "An error occurred while updating the status."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
