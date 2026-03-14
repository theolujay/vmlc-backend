from datetime import timedelta
from django.conf import settings
from rest_framework import serializers
from vmlc.models import ExamHeartbeat, ViolationEvent

HEARTBEAT_INTERVAL_MINUTES = 1 if settings.DEBUG else 5
HEARTBEAT_INTERVAL_TOLERANCE_SECONDS = 30


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
