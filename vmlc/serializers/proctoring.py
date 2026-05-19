from datetime import timedelta

from django.conf import settings
from rest_framework import serializers

from vmlc.models import ExamHeartbeat, ViolationEvent

HEARTBEAT_INTERVAL_MINUTES = (
    1 if settings.APP_ENVIRONMENT in ["development", "staging"] else 5
)
HEARTBEAT_INTERVAL_TOLERANCE_SECONDS = (
    30 if settings.APP_ENVIRONMENT in ["development", "staging"] else 6
)


class ViolationEventSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="event_type")

    class Meta:
        model = ViolationEvent
        fields = ["type", "timestamp", "metadata", "is_critical"]


class ExamHeartbeatSerializer(serializers.ModelSerializer):
    events = ViolationEventSerializer(many=True, read_only=True)
    face_capture_url = serializers.SerializerMethodField()

    class Meta:
        model = ExamHeartbeat
        fields = [
            "sequence_number",
            "client_uuid",
            "timestamp",
            "period_start",
            "period_end",
            "summary",
            "face_capture_url",
            "suspicion_score",
            "meta",
            "events",
        ]

    def get_face_capture_url(self, obj):
        request = self.context.get("request")
        if obj.face_capture and request:
            return request.build_absolute_uri(obj.face_capture.url)
        return None


class HeartbeatPayloadSerializer(serializers.Serializer):
    sequence_number = serializers.IntegerField(min_value=1)
    client_uuid = serializers.UUIDField()
    timestamp = serializers.DateTimeField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    summary = serializers.JSONField(required=False, default=dict)
    meta = serializers.JSONField(required=False, default=dict)
    events = serializers.ListField(
        child=serializers.JSONField(), required=False, default=list
    )

    def validate(self, attrs):
        period_start = attrs.get("period_start")
        period_end = attrs.get("period_end")

        if period_start and period_end:
            interval = period_end - period_start
            if interval.total_seconds() < 0:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Heartbeat period_end cannot be before period_start."
                        ]
                    }
                )
            # Allow any positive interval - gaps will be detected in integrity audit
            if interval > timedelta(minutes=15):
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Heartbeat interval cannot exceed 15 minutes"
                        ]
                    }
                )
        return attrs


class CandidateLiveStatusV2Serializer(serializers.Serializer):
    exam = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    proctoring = serializers.SerializerMethodField()

    @staticmethod
    def _iso(dt):
        return dt.isoformat() if dt else None

    def get_exam(self, obj):
        exam = obj.exam
        return {
            "id": str(exam.id),
            "title": exam.title,
            "status": exam.status,
            "duration_minutes": exam.countdown_minutes,
            "starts_at": self._iso(exam.scheduled_date),
            "ends_at": self._iso(exam.concluded_at),
        }

    def get_attempt(self, obj):
        from django.utils import timezone

        now = timezone.now()
        time_remaining = 0
        if obj.status == "started" and obj.deadline:
            time_remaining = max(0, int((obj.deadline - now).total_seconds()))

        time_used = 0
        if obj.started_at:
            end_time = obj.submitted_at or now
            time_used = int((end_time - obj.started_at).total_seconds())

        return {
            "status": obj.status,
            "started_at": self._iso(obj.started_at),
            "deadline": self._iso(obj.deadline),
            "submitted_at": self._iso(obj.submitted_at),
            "time_remaining_seconds": time_remaining,
            "time_used_seconds": time_used,
        }

    def get_progress(self, obj):
        from vmlc.models import CandidateAnswer

        # Current data model only saves answers on submission,
        # so this will be 0 until submission.
        attempted = CandidateAnswer.objects.filter(
            candidate_exam_result__candidate=obj.candidate,
            candidate_exam_result__exam=obj.exam,
        ).count()
        total = obj.exam.get_question_count()

        return {
            "questions_attempted": attempted,
            "questions_total": total,
            "percent_complete": round((attempted / total * 100), 2) if total > 0 else 0,
        }

    def get_proctoring(self, obj):
        from vmlc.models import ViolationEvent
        from vmlc.services.proctoring import ProctoringService

        summary = ProctoringService.get_proctoring_summary(obj)
        last_hb = obj.heartbeats.order_by("-sequence_number").first()
        recent_events = ViolationEvent.objects.filter(
            heartbeat__exam_access=obj
        ).order_by("-timestamp")[:10]

        # Aggregate violations by type for the summary
        violations_by_type = {}
        all_violations = ViolationEvent.objects.filter(heartbeat__exam_access=obj)
        for v in all_violations:
            violations_by_type[v.event_type] = (
                violations_by_type.get(v.event_type, 0) + 1
            )

        return {
            "status": summary.get("status"),
            "suspicion_score": summary.get("average_suspicion"),
            "last_heartbeat_at": self._iso(last_hb.timestamp) if last_hb else None,
            "heartbeat_sequence": last_hb.sequence_number if last_hb else 0,
            "violations": {
                "total": summary.get("total_violations"),
                "critical": summary.get("critical_violations"),
                "by_type": violations_by_type,
            },
            "recent_events": ViolationEventSerializer(
                recent_events, many=True, context=self.context
            ).data,
        }
